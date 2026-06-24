#!/usr/bin/env python3
"""novelctl.py — NovelClaw orchestration CLI.

Usage:
    novelctl.py [--slug SLUG] [--mode safe|strict|autopilot|draft] [--force] <command> [args]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_NOVELS_DIR = _PROJECT_ROOT / "novels"

# Add project tools to path
sys.path.insert(0, str(_PROJECT_ROOT / "tools"))

from orchestrator import jobs, locks, preflight, quality, repair, runner, report
from orchestrator.policy import get_policy


# ── Pipeline helpers ──────────────────────────────────────────────────


def fail_translate(job, slug, num, reason, mode, score=None, retry_count=0):
    """Centralized failure handler — writes needs_review, updates job, releases lock."""
    quality.write_needs_review(
        slug, num, reason, score=score, mode=mode,
        fix_command=f"/แปลใหม่ {num}"
    )
    job = job.copy(
        state="failed",
        failed=job.failed + [{"chapter": num, "reason": reason, "retryCount": retry_count}],
    )
    job.save()
    locks.release(slug, num)
    return job


def handle_validation_failure(slug, num, mode, score, reason, job):
    """Route validation failure per mode (safe/strict/autopilot)."""
    yield f"⚠️ ตอน {num} validation: {reason}"
    if mode == "safe":
        yield f"❌ ตอน {num} validation ล้มเหลว: {reason} — หยุด"
        job = fail_translate(job, slug, num, reason, mode, score=score)
        yield from []
        return job, True  # True = stop

    elif mode == "strict":
        yield f"⚠️ ตอน {num} validation ล้มเหลว: {reason} — needs_review"
        quality.write_needs_review(
            slug, num, f"strict:{reason}", score=score, mode=mode,
            fix_command=f"/แปลใหม่ {num}"
        )
        job = job.copy(
            state="needs_review",
            failed=job.failed + [{"chapter": num, "reason": f"strict:{reason}", "retryCount": 0}],
        )
        job.save()
        locks.release(slug, num)
        yield from []
        return job, True  # strict also stops

    else:  # autopilot
        yield f"⚠️ ตอน {num} จะ repair ก่อน continue"
        rr = repair.repair_chapter(slug, num)
        if rr.fixes:
            for fix in rr.fixes:
                yield f"  🔧 {fix}"
            vr2 = runner.validate_single(slug, num)
            score2 = vr2.get("score") or score
            if vr2.get("ok") and (score2 is not None and score2 >= policy["repair_score"]):
                yield f"  ✅ repair ช่วยให้ผ่าน validation แล้ว"
                return job, False  # continue
        yield f"  ⚠️ repair ไม่พอ — เก็บเป็น needs_review"
        job = fail_translate(job, slug, num, f"autopilot:{reason} (repair failed)", mode,
                             score=score, retry_count=1)
        yield from []
        return job, False  # still continue (autopilot)


def process_chapter(slug, num, mode, force, job):
    """Process a single chapter: translate → validate → success/fail.

    Yields status lines. Returns (updated_job, should_stop).
    """
    policy = get_policy(mode)
    # Check lock
    if not locks.acquire(slug, num, job.id):
        existing = locks.who_holds(slug, num)
        yield f"⚠️ ตอน {num} กำลังทำงานโดย job: {existing} — ข้าม"
        job = job.copy(failed=job.failed + [{"chapter": num, "reason": "locked", "retryCount": 0}])
        job.save()
        yield from []
        return job, False

    # Check if already translated (safe mode)
    th_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"
    if th_path.exists() and not force and mode != "draft":
        yield f"⏭️ ตอน {num} มี th.json แล้ว — ข้าม (ใช้ --force เพื่อแปลใหม่)"
        job = job.copy(done=job.done + [num], current=num)
        job.save()
        locks.release(slug, num)
        yield from []
        return job, False

    # Update job state
    job = job.copy(state="running", current=num)
    job.save()

    # ── Translate step ────────────────────────────────────────────
    yield f"🔄 กำลังแปลตอน {num}..."
    tr = runner.translate_single(slug, num, mode=mode, force=force, score=(mode != "draft"))

    # Audit: log translate result
    quality.write_audit_log(slug, num, "translate", mode,
                            chapter_data=tr.get("chapter_data"), result=tr)

    if not tr["ok"]:
        err = tr.get("error", "unknown error")
        yield f"❌ ตอน {num} ล้มเหลว: {err}"
        job = fail_translate(job, slug, num, err, mode)
        yield from []
        return job, mode in ("safe", "strict")  # stop on safe/strict

    if mode == "draft":
        yield f"📝 ร่างตอน {num} (draft mode) — preview ที่ staging/drafts/{slug}/{num:04d}.th.json"
        score = tr.get("score")
        if score:
            yield f"   Score: {score}/100"
        yield "   ✅ ไม่มีการแก้ไข canonical file (chapters/*.th.json)"
        job = job.copy(done=job.done + [num])
        job.save()
        locks.release(slug, num)
        yield from []
        return job, False

    # ── Validate step ─────────────────────────────────────────────
    job = job.copy(state="validating")
    job.save()
    yield f"🔍 ตรวจสอบตอน {num}..."
    vr = runner.validate_single(slug, num)
    score = vr.get("score") or tr.get("score")

    quality.write_audit_log(slug, num, "validate", mode,
                            validation_result=vr, result=vr)

    val_ok = vr.get("ok", False)
    val_error = vr.get("error")
    score_ok = score is not None and score >= policy["pass_score"]
    val_failed = not val_ok or (val_error is not None) or not score_ok

    if val_failed:
        reason_parts = []
        if not val_ok:
            reason_parts.append("scorer exit fail")
        if val_error:
            reason_parts.append(val_error[:100])
        if score is not None and not score_ok:
            reason_parts.append(f"score {score}/100 < 70")
        reason = "; ".join(reason_parts)
        job = handle_validation_failure(slug, num, mode, score, reason, job)
        yield from []
        return job, mode in ("safe", "strict")

    # ── Verify file exists ────────────────────────────────────────
    yield f"💾 ตรวจสอบตอน {num}..."
    if not th_path.exists():
        yield f"❌ ตอน {num} ไม่พบ .th.json หลังแปล"
        job = fail_translate(job, slug, num, "th.json_not_found_after_translate", mode)
        yield from []
        return job, mode in ("safe", "strict")

    # ── Success ───────────────────────────────────────────────────
    job = job.copy(state="done", done=job.done + [num])
    job.save()
    locks.release(slug, num)

    yield report.success_translate(slug, num, tr["chapter_data"], score, tr.get("warnings"))
    yield from []
    return job, False


# ── Command handlers ─────────────────────────────────────────────────


def handle_translate(slug: str, nums: list[int], mode: str, force: bool) -> str:
    """Full translate pipeline with job state + checkpoint."""
    job = jobs.create(slug, nums, mode=mode, force=force)

    lines = [f"🚀 เริ่มแปล {slug} {nums[0]}-{nums[-1]} ({len(nums)} ตอน)"]
    lines.append(f"   Mode: {mode}")
    yield "\n".join(lines)

    # Preflight
    job = job.copy(state="preflight")
    job.save()
    pf = preflight.run(slug, nums)
    if not pf.ok and mode != "autopilot":
        job = job.copy(state="failed")
        job.archive("failed")
        locks.release_all(slug)
        yield pf.summary()
        return

    # Per-chapter pipeline
    for num in nums:
        stop = False
        pipeline_gen = process_chapter(slug, num, mode, force, job)
        for msg in pipeline_gen:
            yield msg
            if isinstance(msg, tuple):
                job, stop = msg
        if stop:
            break

    # After all chapters: rebuild
    yield "🔄 Rebuilding index..."
    ri = runner.rebuild_index(slug)
    yield ("✅ Index rebuilt" if ri["ok"]
           else f"⚠️ Index rebuild failed: {ri.get('error', 'unknown')}")

    # Final status
    if len(job.pending) == 0 and len(job.failed) == 0:
        job = job.copy(state="done")
        job.archive("done")
        yield f"✅ เสร็จทั้งหมด {len(job.done)}/{len(job.chapters)} ตอน"
    elif len(job.failed) > 0:
        job.archive("failed")
        yield f"⚠️ เสร็จ {len(job.done)}/{len(job.chapters)} ล้มเหลว {len(job.failed)}"
    else:
        job.archive("needs_review")
        yield f"⚠️ ต้องการตรวจสอบ — พิมพ์ /ต่อ เพื่อทำต่อ"

    locks.release_all(slug)


def handle(slug: str, command: str, *args, **kwargs):
    """Main command dispatcher."""
    if command == "translate":
        nums = kwargs.get("nums", [])
        mode = kwargs.get("mode", "safe")
        force = kwargs.get("force", False)
        out = handle_translate(slug, nums, mode, force)
        return out

    elif command == "validate":
        nums = kwargs.get("nums", [])
        results = []
        for num in nums:
            vr = runner.validate_single(slug, num)
            if vr["ok"]:
                results.append(f"✅ ตอน {num}: score {vr.get('score', 'N/A')}/100")
            else:
                results.append(f"❌ ตอน {num}: {vr.get('error', 'unknown')}")
            for d in (vr.get("details") or []):
                results.append(f"  {d}")
        return results

    elif command == "repair":
        nums = kwargs.get("nums", [])
        results = []
        for num in nums:
            rr = repair.repair_chapter(slug, num)
            results.append(rr.summary())
        return results

    elif command == "preflight":
        nums = kwargs.get("nums", [])
        pf = preflight.run(slug, nums)
        return [pf.summary()]

    elif command == "rebuild":
        ri = runner.rebuild_index(slug)
        if ri["ok"]:
            return ["✅ Rebuild index สำเร็จ"]
        return [f"❌ Rebuild ล้มเหลว: {ri.get('error', 'unknown')}"]

    elif command == "status":
        active = jobs.load_active()
        return [report.job_status(active)]

    elif command == "resume":
        latest = jobs.load_latest(slug)
        if not latest:
            return ["ไม่มี job ที่ resume ได้"]
        if latest.state not in ("failed", "needs_review"):
            return [f"Job {latest.id} ยังไม่ fail (status: {latest.state})"]

        # Get pending chapters from failed
        failed_nums = [f["chapter"] for f in latest.failed]
        if not failed_nums:
            return ["ไม่มีตอนที่ล้มเหลวให้ resume"]

        nums = sorted(set(failed_nums))
        # Respect job's original mode
        out = handle_translate(slug, nums, mode=latest.mode, force=True)
        return out

    elif command == "stop":
        return [locks.release_all(slug)]

    elif command == "report":
        chapters = kwargs.get("chapters_list", [])
        if not chapters:
            # Read from disk
            ch_path = _NOVELS_DIR / slug / "chapters.json"
            if ch_path.exists():
                import json
                raw = json.loads(ch_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    chapters = raw.get("chapters", [])
                elif isinstance(raw, list):
                    chapters = raw
        return [report.novel_report(slug, chapters)]

    elif command == "check":
        return report.check_needs_review(slug)

    elif command == "bench":
        count = kwargs.get("count", 5)
        return [benchmark.run(slug, count)]

    elif command == "backup":
        return run_backup()

    return [f"❌ Unknown command: {command}"]


def run_backup():
    """Backup all novel data with integrity check."""
    import json
    from datetime import datetime

    backup_dir = _PROJECT_ROOT / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"📦 Backup saved to {backup_dir.name}"]

    verified = 0
    failed = 0

    for novel_dir in sorted(_NOVELS_DIR.iterdir()):
        if not novel_dir.is_dir() or novel_dir.name.startswith("."):
            continue
        slug = novel_dir.name
        dest = backup_dir / slug
        dest.mkdir(parents=True, exist_ok=True)

        # chapters.json
        src = novel_dir / "chapters.json"
        if src.exists():
            content = src.read_text(encoding="utf-8")
            (dest / "chapters.json").write_text(content)
            # Integrity: verify it parses
            try:
                json.loads(content)
                verified += 1
            except json.JSONDecodeError:
                lines.append(f"  ⚠️ {slug}: chapters.json corrupt (backed up anyway)")
                failed += 1
        # search-index
        for si in novel_dir.glob("search-index*.json"):
            content = si.read_text(encoding="utf-8")
            (dest / si.name).write_text(content)
            try:
                json.loads(content)
                verified += 1
            except json.JSONDecodeError:
                lines.append(f"  ⚠️ {slug}: {si.name} corrupt (backed up anyway)")
                failed += 1
        # chapter list
        ch_dir = novel_dir / "chapters"
        if ch_dir.exists():
            ch_dest = dest / "chapters"
            ch_dest.mkdir(exist_ok=True)
            for f in sorted(ch_dir.glob("*.th.json"))[:5]:  # first 5 only
                content = f.read_text(encoding="utf-8")
                (ch_dest / f.name).write_text(content)
                try:
                    json.loads(content)
                    verified += 1
                except json.JSONDecodeError:
                    lines.append(f"  ⚠️ {slug}: {f.name} corrupt")
                    failed += 1

    lines.append(f"  ตรวจสอบแล้ว: {verified} ไฟล์ถูกต้อง")
    if failed:
        lines.append(f"  ⚠️ พบ {failed} ไฟล์เสียหาย (backup ไว้ก่อน)")
    else:
        lines.append("  ✅ integrity ผ่านทั้งหมด")
    return lines


# ── CLI entry point ──────────────────────────────────────────────────


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="NovelClaw Orchestrator")
    parser.add_argument("--slug", default=os.environ.get("NOVEL_SLUG", "global-descent"),
                        help="Novel slug (default: global-descent or $NOVEL_SLUG)")
    parser.add_argument("--mode", choices=["safe", "strict", "autopilot", "draft"],
                        default="safe", help="Operation mode")
    parser.add_argument("--force", action="store_true", help="Force re-translate")
    parser.add_argument("--no-score", action="store_true", help="Skip quality scoring")

    subparsers = parser.add_subparsers(dest="command", required=True)

    t_parser = subparsers.add_parser("translate", help="Translate chapters")
    t_parser.add_argument("range", help="Chapter range, e.g. 42 or 131-135")

    for cmd in ("validate", "repair", "preflight"):
        p = subparsers.add_parser(cmd, help=f"{cmd} chapters")
        p.add_argument("range", help="Chapter range, e.g. 42 or 131-135")

    subparsers.add_parser("status", help="Show job status")
    subparsers.add_parser("stop", help="Release all locks")
    subparsers.add_parser("report", help="Novel report")
    subparsers.add_parser("check", help="Check needs_review queue")
    subparsers.add_parser("rebuild", help="Rebuild index")
    subparsers.add_parser("resume", help="Resume failed job")
    subparsers.add_parser("backup", help="Backup novel data")

    args = parser.parse_args()
    slug = args.slug
    mode = args.mode
    force = args.force

    kwargs = {}

    if hasattr(args, "range") and args.range:
        # Parse chapter range
        m = re.match(r"^(\d+)(?:-(\d+))?$", args.range)
        if not m:
            print("❌ Invalid range. Use: 42 or 131-135")
            sys.exit(1)
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        kwargs["nums"] = list(range(start, end + 1))

    result = handle(slug, args.command, mode=mode, force=force, **kwargs)
    for line in result:
        print(line)


if __name__ == "__main__":
    import os
    main()
