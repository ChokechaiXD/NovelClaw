#!/usr/bin/env python3
"""
novelctl.py — NovelClaw Job Orchestrator

Single command layer between Telegram/Hermes and translation tools.
Never call translate.py directly from Telegram — always use this.

Usage:
    python tools/novelctl.py translate 139 --slug global-descent
    python tools/novelctl.py translate 140-150 --mode autopilot
    python tools/novelctl.py repair 139
    python tools/novelctl.py validate 139
    python tools/novelctl.py preflight 140-150
    python tools/novelctl.py rebuild
    python tools/novelctl.py status
    python tools/novelctl.py resume
    python tools/novelctl.py stop
    python tools/novelctl.py report
"""

import sys
import time
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))

from orchestrator import commands, jobs, locks, preflight, repair, report, runner, quality


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

    # Run per chapter
    for num in nums:
        # Check lock
        if not locks.acquire(slug, num, job.id):
            existing = locks.who_holds(slug, num)
            yield f"⚠️ ตอน {num} กำลังทำงานโดย job: {existing} — ข้าม"
            job = job.copy(failed=job.failed + [{"chapter": num, "reason": "locked", "retryCount": 0}])
            job.save()
            continue

        # Check if already translated (safe mode)
        th_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"
        if th_path.exists() and not force and mode != "draft":
            yield f"⏭️ ตอน {num} มี th.json แล้ว — ข้าม (ใช้ --force เพื่อแปลใหม่)"
            job = job.copy(done=job.done + [num], current=num)
            job.save()
            locks.release(slug, num)
            continue

        # Update job state
        job = job.copy(state="running", current=num)
        job.save()

        # Translate
        yield f"🔄 กำลังแปลตอน {num}..."
        tr = runner.translate_single(slug, num, mode=mode, force=force, score=(mode != "draft"))

        if not tr["ok"]:
            err = tr.get("error", "unknown error")
            yield f"❌ ตอน {num} ล้มเหลว: {err}"
            quality.write_needs_review(slug, num, err, mode=mode,
                                       fix_command=f"/แปลใหม่ {num}" if mode == "draft" else f"/แปลใหม่ {num}")
            job = job.copy(state="failed",
                           failed=job.failed + [{"chapter": num, "reason": err, "retryCount": 0}])
            job.save()
            locks.release(slug, num)

            if mode == "safe" or mode == "strict":
                break  # stop on fail
            else:
                continue  # autopilot: skip to next

        if mode == "draft":
            # Draft mode: save preview to staging/drafts/ and report
            yield f"📝 ร่างตอน {num} (draft mode) — preview ที่ staging/drafts/{slug}/{num:04d}.th.json"
            score = tr.get("score")
            if score:
                yield f"   Score: {score}/100"
            yield "   ✅ ไม่มีการแก้ไข canonical file (chapters/*.th.json)"
            job = job.copy(done=job.done + [num])
            job.save()
            locks.release(slug, num)
            continue

        # Validate
        job = job.copy(state="validating")
        job.save()
        yield f"🔍 ตรวจสอบตอน {num}..."
        vr = runner.validate_single(slug, num)
        score = vr.get("score") or tr.get("score")

        # Validate result enforcement
        val_ok = vr.get("ok", False)
        val_error = vr.get("error")
        score_ok = score is not None and score >= 70  # minimum pass

        # Determine if validation failed enough to block
        val_failed = not val_ok or (val_error is not None) or not score_ok

        if val_failed:
            reason_parts = []
            if not val_ok:
                reason_parts.append(f"scorer exit fail")
            if val_error:
                reason_parts.append(val_error[:100])
            if score is not None and not score_ok:
                reason_parts.append(f"score {score}/100 < 70")
            reason = "; ".join(reason_parts)

            if mode == "safe":
                yield f"❌ ตอน {num} validation ล้มเหลว: {reason} — หยุด"
                quality.write_needs_review(slug, num, reason, score=score, mode=mode)
                job = job.copy(state="failed",
                              failed=job.failed + [{"chapter": num, "reason": reason, "retryCount": 0}])
                job.save()
                locks.release(slug, num)
                break  # safe mode: stop on any failure

            elif mode == "strict":
                yield f"⚠️ ตอน {num} validation ล้มเหลว: {reason} — needs_review"
                job = job.copy(state="needs_review",
                              failed=job.failed + [{"chapter": num, "reason": f"strict:{reason}", "retryCount": 0}])
                job.save()
                locks.release(slug, num)
                break  # strict: stop and flag needs_review

            else:  # autopilot
                yield f"⚠️ ตอน {num} validation ล้มเหลว: {reason} — จะ repair แล้ว continue"
                # Attempt repair
                rr = repair.repair_chapter(slug, num)
                if rr.fixes:
                    for fix in rr.fixes:
                        yield f"  🔧 {fix}"
                    # Re-validate after repair
                    vr2 = runner.validate_single(slug, num)
                    score = vr2.get("score") or score
                    if vr2.get("ok") and (score is not None and score >= 60):
                        yield f"  ✅ repair ช่วยให้ผ่าน validation แล้ว"
                    else:
                        yield f"  ⚠️ repair ไม่พอ — เก็บเป็น needs_review"
                        job = job.copy(failed=job.failed + [{"chapter": num, "reason": f"autopilot:{reason}", "retryCount": 1}])
                        job.save()
                        locks.release(slug, num)
                        continue
                else:
                    yield f"  ⚠️ ไม่มี repair ที่ทำได้ — เก็บเป็น needs_review"
                    job = job.copy(failed=job.failed + [{"chapter": num, "reason": f"autopilot:{reason}", "retryCount": 1}])
                    job.save()
                    locks.release(slug, num)
                    continue

        # translate.py already wrote .th.json — verify exists
        yield f"💾 ตรวจสอบตอน {num}..."
        th_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"
        if not th_path.exists():
            yield f"❌ ตอน {num} ไม่พบ .th.json หลังแปล"
            job = job.copy(failed=job.failed + [{"chapter": num, "reason": "th.json_not_found_after_translate", "retryCount": 0}])
            job.save()
            locks.release(slug, num)
            if mode == "safe" or mode == "strict":
                break
            continue

        # Success
        job = job.copy(state="done", done=job.done + [num])
        job.save()
        locks.release(slug, num)

        yield report.success_translate(slug, num, tr["chapter_data"], score, tr.get("warnings"))

    # After all chapters done: rebuild
    yield "🔄 Rebuilding index..."
    ri = runner.rebuild_index(slug)
    if ri["ok"]:
        yield "✅ Index rebuilt"
    else:
        yield f"⚠️ Index rebuild failed: {ri.get('error', 'unknown')}"

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
        if latest.state != "failed" and latest.state != "needs_review":
            return [f"Job {latest.id} ยังไม่ fail (status: {latest.state})"]

        nums = latest.pending + [f.get("chapter") for f in latest.failed if f.get("retryCount", 0) < 3]
        nums = sorted(set(nums))
        if not nums:
            return ["ไม่มีตอนที่ต้องทำต่อ"]

        mode = latest.mode
        force = latest.data.get("force", False)
        out = handle_translate(slug, nums, mode, force)
        return out

    elif command == "stop":
        active = jobs.load_active()
        if not active:
            return ["ไม่มี job ที่กำลังรัน"]
        for j in active:
            j.archive("failed")
            locks.release_all(j.slug)
        return ["🛑 หยุด job ทั้งหมดแล้ว"]

    elif command == "report":
        from schema import CHAPTERS_DIR
        from pathlib import Path
        try:
            cj = Path(CHAPTERS_DIR).parent / "chapters.json"
            if cj.exists():
                import json
                data = json.loads(cj.read_text(encoding="utf-8"))
                chs = data.get("chapters", [])
            else:
                chs = []
        except Exception:
            chs = []
        return [report.novel_report(slug, chs)]

    elif command == "check":
        """Show needs_review queue."""
        from orchestrator.quality import list_needs_review
        entries = list_needs_review(slug)
        if not entries:
            return ["✅ ไม่มีตอนที่รอตรวจสอบ"]
        lines = [f"📋 รอตรวจสอบ {len(entries)} ตอน:"]
        for e in entries[:20]:
            lines.append(f"  ❌ ตอน {e.get('chapter')}: {e.get('reason', '?')[:80]}")
            lines.append(f"     แก้: {e.get('suggestedCommand', 'N/A')}")
        if len(entries) > 20:
            lines.append(f"  ...และอีก {len(entries) - 20} ตอน")
        return lines

    return [f"Unknown command: {command}"]


def main():
    """CLI entry point."""
    result = commands.run(sys.argv[1:] if len(sys.argv) > 1 else ["--help"])

    if not result.get("ok"):
        print(result.get("message", "Error"), file=sys.stderr)
        sys.exit(1)

    cmd = result.pop("command", None)
    if not cmd:
        print("No command specified", file=sys.stderr)
        sys.exit(1)
    slug = result.pop("slug", "global-descent")

    output = handle(slug, cmd, **result)
    for line in output:
        print(line)


if __name__ == "__main__":
    main()
