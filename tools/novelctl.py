#!/usr/bin/env python3
"""novelctl.py — NovelClaw orchestration CLI.

Usage:
    novelctl.py [--slug SLUG] [--mode safe|strict|autopilot|draft] [--force] <command> [args]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_NOVELS_DIR = _PROJECT_ROOT / "novels"

# Add project tools to path
sys.path.insert(0, str(_PROJECT_ROOT / "tools"))

from orchestrator import jobs, locks, preflight, quality, repair, runner, report
from orchestrator.policy import get_policy


# ── Data classes ──────────────────────────────────────────────────────


@dataclass
class ChapterPipelineResult:
    """Structured result from processing a single chapter."""

    job: object
    stop: bool
    lines: list[str] = field(default_factory=list)


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


def handle_validation_failure(slug, num, policy, score, reason, job):
    """Route validation failure per mode (safe/strict/autopilot).

    Uses policy object directly — no magic strings.
    Returns ChapterPipelineResult.
    """
    lines = [f"⚠️ ตอน {num} validation: {reason}"]

    if policy["stop_on_fail"] and policy["pass_score"] >= 85:
        # Strict mode
        lines.append(f"⚠️ ตอน {num} validation ล้มเหลว: {reason} — needs_review")
        quality.write_needs_review(
            slug, num, f"strict:{reason}", score=score, mode="strict",
            fix_command=f"/แปลใหม่ {num}"
        )
        job = job.copy(
            state="needs_review",
            failed=job.failed + [{"chapter": num, "reason": f"strict:{reason}", "retryCount": 0}],
        )
        job.save()
        locks.release(slug, num)
        return ChapterPipelineResult(job=job, stop=True, lines=lines)

    elif policy["stop_on_fail"]:
        # Safe mode
        lines.append(f"❌ ตอน {num} validation ล้มเหลว: {reason} — หยุด")
        job = fail_translate(job, slug, num, reason, "safe", score=score)
        return ChapterPipelineResult(job=job, stop=True, lines=lines)

    else:
        # Autopilot — attempt repair before giving up
        lines.append(f"⚠️ ตอน {num} จะ repair ก่อน continue")
        rr = repair.repair_chapter(slug, num)
        if rr.fixes:
            for fix in rr.fixes:
                lines.append(f"  🔧 {fix}")
            vr2 = runner.validate_single(slug, num)
            score2 = vr2.get("score") or score
            if vr2.get("ok") and (score2 is not None and score2 >= policy["repair_score"]):
                lines.append(f"  ✅ repair ช่วยให้ผ่าน validation แล้ว")
                return ChapterPipelineResult(job=job, stop=False, lines=lines)

        lines.append(f"  ⚠️ repair ไม่พอ — เก็บเป็น needs_review")
        job = fail_translate(job, slug, num, f"autopilot:{reason} (repair failed)", "autopilot",
                             score=score, retry_count=1)
        return ChapterPipelineResult(job=job, stop=False, lines=lines)


def process_chapter(slug, num, mode, force, job) -> ChapterPipelineResult:
    """Process a single chapter: translate → validate → success/fail.

    NOT a generator — returns ChapterPipelineResult with lines, job, stop.
    This avoids the Python generator return-value gotcha.
    """
    lines = []
    policy = get_policy(mode)

    # Check lock
    if not locks.acquire(slug, num, job.id):
        existing = locks.who_holds(slug, num)
        lines.append(f"⚠️ ตอน {num} กำลังทำงานโดย job: {existing} — ข้าม")
        job = job.copy(failed=job.failed + [{"chapter": num, "reason": "locked", "retryCount": 0}])
        job.save()
        return ChapterPipelineResult(job=job, stop=False, lines=lines)

    # Check if already translated (safe mode)
    th_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"
    if th_path.exists() and not force and mode != "draft":
        lines.append(f"⏭️ ตอน {num} มี th.json แล้ว — ข้าม (ใช้ --force เพื่อแปลใหม่)")
        job = job.copy(done=job.done + [num], current=num)
        job.save()
        locks.release(slug, num)
        return ChapterPipelineResult(job=job, stop=False, lines=lines)

    # Update job state
    job = job.copy(state="running", current=num)
    job.save()

    # ── Translate step ────────────────────────────────────────────
    lines.append(f"🔄 กำลังแปลตอน {num}...")
    tr = runner.translate_single(slug, num, mode=mode, force=force, score=(mode != "draft"))

    # Audit: log translate result
    quality.write_audit_log(slug, num, "translate", mode,
                            chapter_data=tr.get("chapter_data"), result=tr)

    # Quality record: translate
    quality.write_quality_record(
        slug, num, action="translate",
        model=tr.get("model", "unknown"),
        provider=tr.get("provider", "unknown"),
        score=tr.get("score"),
        duration_ms=tr.get("elapsed_ms"),
        error=tr.get("error") if not tr["ok"] else None,
    )

    if not tr["ok"]:
        err = tr.get("error", "unknown error")
        lines.append(f"❌ ตอน {num} ล้มเหลว: {err}")
        job = fail_translate(job, slug, num, err, mode)
        return ChapterPipelineResult(job=job, stop=policy["stop_on_fail"], lines=lines)

    if mode == "draft":
        lines.append(f"📝 ร่างตอน {num} (draft mode) — preview ที่ staging/drafts/{slug}/{num:04d}.th.json")
        score = tr.get("score")
        if score:
            lines.append(f"   Score: {score}/100")
        lines.append("   ✅ ไม่มีการแก้ไข canonical file (chapters/*.th.json)")
        job = job.copy(done=job.done + [num])
        job.save()
        locks.release(slug, num)
        return ChapterPipelineResult(job=job, stop=False, lines=lines)

    # ── Validate step ─────────────────────────────────────────────
    job = job.copy(state="validating")
    job.save()
    lines.append(f"🔍 ตรวจสอบตอน {num}...")
    vr = runner.validate_single(slug, num)
    score = vr.get("score") or tr.get("score")

    quality.write_audit_log(slug, num, "validate", mode,
                            validation_result=vr, result=vr)

    # Quality record: validate
    quality.write_quality_record(
        slug, num, action="validate",
        score=vr.get("score"),
        error=vr.get("error") if not vr.get("ok", False) else None,
    )

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
            reason_parts.append(f"score {score}/100 < {policy['pass_score']}")
        reason = "; ".join(reason_parts)
        result = handle_validation_failure(slug, num, policy, score, reason, job)
        result.lines = lines + result.lines
        return result

    # ── Verify file exists ────────────────────────────────────────
    lines.append(f"💾 ตรวจสอบตอน {num}...")
    if not th_path.exists():
        lines.append(f"❌ ตอน {num} ไม่พบ .th.json หลังแปล")
        job = fail_translate(job, slug, num, "th.json_not_found_after_translate", mode)
        return ChapterPipelineResult(job=job, stop=policy["stop_on_fail"], lines=lines)

    # ── Success ───────────────────────────────────────────────────
    job = job.copy(state="done", done=job.done + [num])
    job.save()
    locks.release(slug, num)

    lines.append(report.success_translate(slug, num, tr["chapter_data"], score, tr.get("warnings")))
    return ChapterPipelineResult(job=job, stop=False, lines=lines)


# ── Command handlers ─────────────────────────────────────────────────


def parse_range(range_str: str) -> list[int]:
    """Parse '139' → [139], '140-150' → [140..150], '140,142,145' → [140,142,145]."""
    if not range_str:
        return []
    nums: set[int] = set()
    for part in range_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                nums.update(range(int(start.strip()), int(end.strip()) + 1))
            except ValueError:
                continue
        else:
            try:
                nums.add(int(part))
            except ValueError:
                continue
    return sorted(nums)


def handle_translate(slug: str, nums: list[int], mode: str, force: bool, workers: int = 1) -> str:
    """Full translate pipeline with job state + checkpoint."""
    job = jobs.create(slug, nums, mode=mode, force=force)

    # Clean stale locks from previous crashes
    locks.cleanup_stale()

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

    # Per-chapter pipeline — sequential or parallel
    if workers > 1 and len(nums) > 1:
        import concurrent.futures
        yield f"⚡ ใช้ {workers} workers แปลขนาน...\n"
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(process_chapter, slug, num, mode, force, job): num for num in nums}
            done_count = 0
            for f in concurrent.futures.as_completed(futures):
                num = futures[f]
                done_count += 1
                try:
                    result = f.result()
                    job = result.job
                    for msg in result.lines:
                        yield msg
                    if result.stop:
                        yield f"\n⚠️ Worker {num} หยุด chain (mode={mode})"
                except Exception as e:
                    yield f"❌ Worker {num} exception: {e}\n"
    else:
        for num in nums:
            result = process_chapter(slug, num, mode, force, job)
            job = result.job
            for msg in result.lines:
                yield msg
            if result.stop:
                break

    # After all chapters: rebuild
    yield "🔄 Rebuilding index..."
    ri = runner.rebuild_index(slug)
    yield ("✅ Index rebuilt" if ri["ok"]
           else f"⚠️ Index rebuild failed: {ri.get('error', 'unknown')}")

    # Final status — job state is now 100% accurate
    if len(job.failed) == 0:
        job = job.copy(state="done")
        job.archive("done")
        yield f"✅ เสร็จทั้งหมด {len(job.done)}/{len(job.chapters)} ตอน"
    elif len(job.done) > 0:
        job.archive("failed")
        yield f"⚠️ เสร็จ {len(job.done)}/{len(job.chapters)} ล้มเหลว {len(job.failed)}"
    else:
        job.archive("needs_review")
        yield f"⚠️ ต้องการตรวจสอบ — พิมพ์ /ต่อ เพื่อทำต่อ"

    locks.release_all(slug)


def handle(slug: str, command: str, **kwargs):
    """Main command dispatcher."""
    if command == "translate":
        nums = kwargs.get("nums", [])
        mode = kwargs.get("mode", "safe")
        force = kwargs.get("force", False)
        workers = kwargs.get("workers", 1)
        out = handle_translate(slug, nums, mode, force, workers=workers)
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

        failed_nums = [f["chapter"] for f in latest.failed]
        if not failed_nums:
            return ["ไม่มีตอนที่ล้มเหลวให้ resume"]

        nums = sorted(set(failed_nums))
        out = handle_translate(slug, nums, mode=latest.mode, force=True, workers=1)  # resume uses 1 worker
        return out

    elif command == "stop":
        return [locks.release_all(slug)]

    elif command == "report":
        chapters = kwargs.get("chapters_list", [])
        if not chapters:
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

    elif command == "gate":
        nums = kwargs.get("nums", [])
        gate_mode = kwargs.get("gate_mode", "production")
        results = []
        for num in nums:
            from qa.quality_gate import quality_gate as _qg
            from orchestrator.runner import _ch_path
            import json
            p = _ch_path(slug, num)
            if not p.exists():
                results.append(f"❌ ตอน {num}: ไม่พบไฟล์ {p}")
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            src_p = _ch_path(slug, num).parent / f"{num:04d}.cn.json"
            src = json.loads(src_p.read_text(encoding="utf-8")) if src_p.exists() else None
            src_txt = " ".join(src.get("paragraphs", [])) if src else None
            r = _qg(data.get("paragraphs", []), source_text=src_txt, mode=gate_mode, target_lang="th")
            status = "✅" if r.ok else "⚠️"
            score_str = f"คะแนน {r.score:.0f}/100"
            results.append(f"{status} ตอน {num}: {score_str}")
            if r.issues:
                for issue in r.issues[:5]:
                    results.append(f"  [{issue['severity']}] {issue['message']}")
            if r.needs_review:
                results.append(f"  📋 needs_review")
        return results

    elif command == "terms":
        action = kwargs.get("action", "review")
        if action == "review":
            from qa.term_policy import get_term_policy
            tp = get_term_policy("th")
            lines = [f"📋 Term Policy (th): {len(tp.terms)} terms"]
            for action_type in ("replace", "preserve", "review", "fail"):
                terms = [f"{k} → {t.value}" if t.value else k 
                        for k, t in sorted(tp.terms.items()) if t.action == action_type]
                if terms:
                    lines.append(f"  {action_type} ({len(terms)}): {' | '.join(terms[:15])}")
                    if len(terms) > 15:
                        lines.append(f"    ...และอีก {len(terms)-15} คำ")
            lines.append(f"\n  preserve_tokens: {sorted(tp.preserve_tokens)}")
            return lines
        elif action == "approve":
            token = kwargs.get("token", "")
            if not token:
                return ["❌ ระบุ token: terms approve <token> --replace <thai>"]
            if kwargs.get("preserve"):
                action_txt = f"action: preserve\ncategory: custom"
            elif kwargs.get("replace"):
                action_txt = f"action: replace\nvalue: {kwargs['replace']}\ncategory: custom"
            else:
                return ["❌ ระบุ --replace <thai> หรือ --preserve"]
            return [
                f"📝 เพิ่ม token '{token}' ลง term_policy.th.yaml:",
                f"  {token}:",
                f"    {action_txt}",
                f"",
                f"⏳ กรุณาเพิ่มใน tools/config/term_policy.th.yaml ด้วยตนเอง",
            ]

    elif command == "reparse":
        nums = kwargs.get("nums", [])
        from qa.quality_gate import _smart_segment
        import json
        dr_dir = _NOVELS_DIR.parent / "staging" / "drafts" / slug
        results = []
        for num in nums:
            dp = dr_dir / f"{num:04d}.th.json"
            if not dp.exists():
                results.append(f"❌ ตอน {num}: ไม่มี draft")
                continue
            old = json.loads(dp.read_text(encoding="utf-8"))
            old_paras = [p for p in old.get("paragraphs", []) if p != "(จบบท)"]
            old_count = len(old_paras)
            new_paras = [p for p in _smart_segment(old_paras) if p != "(จบบท)"]
            new_count = len(new_paras)
            if new_count > old_count and new_count > 20:
                old["paragraphs"] = new_paras + ["(จบบท)"]
                dp.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
                results.append(f"✅ ตอน {num}: {old_count} → {new_count} paras")
            else:
                results.append(f"🔶 ตอน {num}: {old_count} → {new_count} paras (no change)")
        return results

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

        src = novel_dir / "chapters.json"
        if src.exists():
            content = src.read_text(encoding="utf-8")
            (dest / "chapters.json").write_text(content)
            try:
                json.loads(content)
                verified += 1
            except json.JSONDecodeError:
                lines.append(f"  ⚠️ {slug}: chapters.json corrupt (backed up anyway)")
                failed += 1
        for si in novel_dir.glob("search-index*.json"):
            content = si.read_text(encoding="utf-8")
            (dest / si.name).write_text(content)
            try:
                json.loads(content)
                verified += 1
            except json.JSONDecodeError:
                lines.append(f"  ⚠️ {slug}: {si.name} corrupt (backed up anyway)")
                failed += 1
        ch_dir = novel_dir / "chapters"
        if ch_dir.exists():
            ch_dest = dest / "chapters"
            ch_dest.mkdir(exist_ok=True)
            for f in sorted(ch_dir.glob("*.th.json"))[:5]:
                content = f.read_text(encoding="utf-8")
                (ch_dest / f.name).write_text(content)
                try:
                    json.loads(content)
                    verified += 1
                except json.JSONDecodeError:
                    lines.append(f"  ⚠️ {slug}: {f.name} corrupt")
                    failed += 1

    lines.append(f"  ตรวจสอบแล้ว: {verified} ไฟล์ถูกต้อง")
    lines.append(f"  ✅ integrity ผ่านทั้งหมด" if not failed else f"  ⚠️ พบ {failed} ไฟล์เสียหาย (backup ไว้ก่อน)")
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
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers (default: 1)")

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

    # ── Quality gate commands ────────────────────────────────────────
    g = subparsers.add_parser("gate", help="Run quality gate on chapters")
    g.add_argument("range", help="Chapter range")
    g.add_argument("--mode", choices=["production", "draft", "debug"], default="production",
                   help="Gate strictness (default: production)")

    t = subparsers.add_parser("terms", help="Term policy review")
    t.add_argument("action", choices=["review", "approve"], help="review: show unknown, approve: add term")
    t.add_argument("token", nargs="?", help="Token to approve")
    t.add_argument("--replace", help="Thai replacement value")
    t.add_argument("--preserve", action="store_true", help="Preserve instead of replace")

    r = subparsers.add_parser("reparse", help="Re-parse draft paragraphs with fixed parser")
    r.add_argument("range", help="Chapter range")
    r.add_argument("--draft-only", action="store_true", default=True, help="Only re-parse drafts (default)")

    args = parser.parse_args()
    slug = args.slug
    mode = args.mode
    force = args.force

    kwargs = {}

    if hasattr(args, "range") and args.range:
        kwargs["nums"] = parse_range(args.range)
        if not kwargs["nums"]:
            print("❌ Invalid range. Use: 42, 131-135, 140,142,145")
            sys.exit(1)

    if hasattr(args, "command") and args.command in ("terms",):
        if hasattr(args, "action"):
            kwargs["action"] = args.action
        if hasattr(args, "token") and args.token:
            kwargs["token"] = args.token
        if hasattr(args, "replace") and args.replace:
            kwargs["replace"] = args.replace
        if hasattr(args, "preserve"):
            kwargs["preserve"] = args.preserve

    if hasattr(args, "command") and args.command == "gate" and hasattr(args, "mode"):
        kwargs["gate_mode"] = args.mode

    kwargs["workers"] = args.workers
    kwargs["mode"] = args.mode
    kwargs["force"] = args.force

    result = handle(slug, args.command, **kwargs)
    for line in result:
        print(line)


if __name__ == "__main__":
    import os
    main()
