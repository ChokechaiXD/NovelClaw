"""
Telegram-friendly report formatting.
Includes needs_review queue counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Import needs_review counter
_NEEDS_DIR = _PROJECT_ROOT / "jobs" / "needs_review"


def _count_needs_review(slug: str | None = None) -> int:
    """Count needs_review entries."""
    if not _NEEDS_DIR.exists():
        return 0
    count = 0
    for p in _NEEDS_DIR.glob("*.json"):
        if slug and not p.name.startswith(slug):
            continue
        count += 1
    return count


def _reader_url(slug: str, num: int) -> str:
    return f"http://localhost:4173/#novel/{slug}/{num}"


def success_translate(slug: str, num: int, chapter_data: dict | None, score: int | None,
                      warnings: list[str] | None = None) -> str:
    """Format a successful translation report."""
    paras = len(chapter_data.get("paragraphs", [])) if chapter_data else 0
    output = f"chapters/{num:04d}.th.json"

    lines = [
        f"✅ แปลตอน {num} สำเร็จ",
        "",
        f"Novel: {slug}",
        f"Output: {output}",
        f"Paragraphs: {paras}",
    ]
    if score is not None:
        lines.append(f"Quality: {score}/100")

    if warnings:
        lines.append(f"Warnings: {len(warnings)}")
        for w in warnings[:5]:
            lines.append(f"  ⚠️ {w}")

    lines += [
        "Index: rebuilt ✓",
        "Search: updated ✓",
        "",
        f"อ่านเลย: {_reader_url(slug, num)}",
    ]
    return "\n".join(lines)


def failure_translate(slug: str, num: int, reason: str, details: list[str] | None = None,
                      fix_command: str | None = None) -> str:
    """Format a failed translation report."""
    lines = [
        f"❌ ตอน {num} ไม่ผ่าน",
        "",
        f"Novel: {slug}",
        f"เหตุผล: {reason}",
    ]
    if details:
        lines.append("")
        for d in details:
            lines.append(f"- {d}")

    lines.append("")
    lines.append("ระบบทำแล้ว:")
    lines.append("✅ เก็บ source ไว้")
    lines.append("✅ เก็บ raw LLM output")
    lines.append("✅ ไม่ save ทับไฟล์เดิม")
    lines.append("⏸️ job paused")

    if fix_command:
        lines.append("")
        lines.append(f"คำสั่งต่อ: {fix_command}")

    return "\n".join(lines)


def preflight_summary(result: Any) -> str:
    """Format preflight check result."""
    total = len(result.checks)
    passed = sum(1 for c in result.checks if c["ok"])
    lines = [f"Preflight: {passed}/{total} checks {'✅' if passed == total else '⚠️'}"]
    for c in result.checks:
        icon = "✅" if c["ok"] else "⚠️"
        lines.append(f"  {icon} {c['name']} {c['detail']}")
    if passed != total:
        lines.append("")
        lines.append("แก้ไขข้อ⚠️ ก่อนเริ่มแปล หรือพิมพ์ /แปลต่อ เพื่อข้าม")
    return "\n".join(lines)


def job_status(jobs_list: list) -> str:
    """Format active jobs summary."""
    if not jobs_list:
        return "ไม่มี job ที่กำลังรันอยู่"

    lines = [f"Jobs ที่กำลังทำงาน: {len(jobs_list)}"]
    for j in jobs_list:
        total = len(j.chapters)
        done_n = len(j.done)
        failed_n = len(j.failed)
        pct = int((done_n / total) * 100) if total else 0
        lines.append(f"")
        lines.append(f"📋 {j.id}")
        lines.append(f"  สถานะ: {j.state}")
        lines.append(f"  โหมด: {j.mode}")
        lines.append(f"  ความคืบ: {done_n}/{total} ({pct}%)")
        if j.current:
            lines.append(f"  กำลังทำ: ตอน {j.current}")
        if failed_n:
            lines.append(f"  ล้มเหลว: {failed_n} ตอน")
            for f in j.failed:
                lines.append(f"    ❌ ตอน {f.get('chapter')}: {f.get('reason', 'unknown')}")
        if j.pending:
            lines.append(f"  รอทำ: {','.join(str(n) for n in j.pending[:10])}")
            if len(j.pending) > 10:
                lines.append(f"    ...และอีก {len(j.pending) - 10} ตอน")

    # Add needs_review count
    nr = _count_needs_review()
    if nr:
        lines.append("")
        lines.append(f"📋 รอตรวจสอบ (needs_review): {nr} ตอน")
        lines.append("  พิมพ์ /check เพื่อดูรายละเอียด")

    return "\n".join(lines)


def novel_report(slug: str, chapters_list: list[dict]) -> str:
    """Format novel translation status report."""
    total = len(chapters_list)
    translated = sum(1 for c in chapters_list if c.get("status") == "translated")
    source_only = sum(1 for c in chapters_list if c.get("status") == "source_only")
    pct = int((translated / total) * 100) if total else 0
    nr = _count_needs_review(slug)
    lines = [
        f"📊 {slug}",
        f"  ทั้งหมด: {total} ตอน",
        f"  แปลแล้ว: {translated} ({pct}%)",
        f"  ยังไม่แปล: {source_only}",
    ]
    if nr:
        lines.append(f"  รอตรวจสอบ: {nr} ตอน")
        lines.append(f"  พิมพ์ /check {slug} เพื่อดูรายละเอียด")
    lines += [
        "",
        f"อ่านเลย: http://localhost:4173/#novel/{slug}",
    ]
    return "\n".join(lines)
