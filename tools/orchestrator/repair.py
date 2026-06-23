"""Mechanical repair — fix known issues without calling LLM."""

import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CHAPTERS_DIR = _PROJECT_ROOT / "novels"


def _th_path(slug: str, num: int) -> Path:
    return _CHAPTERS_DIR / slug / "chapters" / f"{num:04d}.th.json"


def _cn_path(slug: str, num: int) -> Path:
    return _CHAPTERS_DIR / slug / "chapters" / f"{num:04d}.cn.json"


def _source_path(slug: str, num: int) -> Path:
    return _CHAPTERS_DIR / slug / "chapters" / "source" / f"{num:04d}.md"


class RepairResult:
    def __init__(self, slug: str, num: int):
        self.slug = slug
        self.num = num
        self.fixes: list[str] = []
        self.warnings: list[str] = []
        self.ok = True

    def add_fix(self, msg: str):
        self.fixes.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def summary(self) -> str:
        lines = [f"ซ่อมตอน {self.num} {'✅' if self.ok else '⚠️'}"]
        for f in self.fixes:
            lines.append(f"  🔧 {f}")
        for w in self.warnings:
            lines.append(f"  ⚠️ {w}")
        if not self.fixes and not self.warnings:
            lines.append("  ไม่มีอะไรต้องซ่อม")
        return "\n".join(lines)


def repair_chapter(slug: str, num: int) -> RepairResult:
    """Run mechanical repairs on a single chapter."""
    result = RepairResult(slug, num)
    tp = _th_path(slug, num)

    if not tp.exists():
        result.add_warning("ไม่พบ th.json — ข้ามการซ่อม")
        result.ok = False
        return result

    try:
        data = json.loads(tp.read_text(encoding="utf-8"))
    except Exception as e:
        result.add_warning(f"ไฟล์ JSON เสีย: {e}")
        result.ok = False
        return result

    paragraphs = data.get("paragraphs", [])
    if not paragraphs:
        result.add_warning("ไม่มี paragraphs ในไฟล์")
        result.ok = False

    # 1. End marker check
    has_end = any(
        p.strip() in ("(จบบท)", "(End)", "（終）", "(끝)")
        for p in paragraphs
    )
    if not has_end and paragraphs:
        paragraphs.append("(จบบท)")
        data["paragraphs"] = paragraphs
        result.add_fix("เติม (จบบท) ที่ท้าย")

    # 2. Title normalization
    title = data.get("title", {})
    if isinstance(title, str) and title:
        data["title"] = {"translated": title, "source": ""}
        result.add_fix(f"ย้าย title จาก string → object: {title[:30]}")

    # 3. CN leak mechanical clean (remove stray CN chars in known artifacts)
    cn_clean = re.compile(r"[一-龥]{1,3}(?=[\s\n【「])")
    changed = 0
    new_paras = []
    for p in paragraphs:
        cleaned = cn_clean.sub("", p)
        if cleaned != p:
            changed += 1
        new_paras.append(cleaned)
    if changed:
        data["paragraphs"] = new_paras
        result.add_fix(f"ลบ CN leak {changed} ย่อหน้า (mechanical clean)")

    # 4. Schema: ensure required fields
    if "novelId" not in data:
        data["novelId"] = slug
        result.add_fix("เพิ่ม novelId")
    if "chapterNo" not in data:
        data["chapterNo"] = num
        result.add_fix("เพิ่ม chapterNo")
    if "updatedAt" not in data:
        from datetime import datetime, timezone
        data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        result.add_fix("เพิ่ม updatedAt")
    if "status" not in data:
        data["status"] = "translated"
        result.add_fix("เพิ่ม status=translated")

    # Write back
    tp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
