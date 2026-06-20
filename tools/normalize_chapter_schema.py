"""Normalize translated chapter JSON files to the current NovelClaw v2 shape.

This tool is intentionally mechanical. It does not rewrite prose.

Examples:
    python tools/normalize_chapter_schema.py --novel global-descent --start 1 --end 138
    python tools/normalize_chapter_schema.py --novel global-descent --start 1 --end 138 --write

What it fixes:
    - `format: v2` -> `schema_version: 2`
    - missing `num`
    - missing `source`
    - missing `notes`
    - missing `lang`
    - missing end marker block
    - end marker not last

What it does NOT fix:
    - translation quality
    - glossary drift
    - quote style conversion
    - source completeness
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOVELS_DIR = PROJECT_ROOT / "novels"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_chapter(data: Dict[str, Any], num: int, lang: str) -> tuple[Dict[str, Any], List[str]]:
    changes: List[str] = []
    out = dict(data)

    if out.get("schema_version") != 2:
        if out.get("format") == "v2":
            out.pop("format", None)
        out["schema_version"] = 2
        changes.append("set schema_version=2")

    if out.get("num") != num:
        out["num"] = num
        changes.append(f"set num={num}")

    title = str(out.get("title", "")).strip()
    if not title:
        out["title"] = f"ตอนที่ {num} (ไม่มีชื่อตอน)"
        changes.append("set fallback title")
    elif not title.startswith(f"ตอนที่ {num}"):
        # Keep existing title text, but make the chapter number explicit.
        out["title"] = f"ตอนที่ {num}: {title}"
        changes.append("prefix title with chapter number")

    if out.get("source") != f"ch {num}":
        out["source"] = f"ch {num}"
        changes.append("set source")

    if out.get("lang") != lang:
        out["lang"] = lang
        changes.append(f"set lang={lang}")

    if not isinstance(out.get("notes"), list):
        out["notes"] = []
        changes.append("set notes=[]")

    blocks = out.get("blocks")
    if not isinstance(blocks, list):
        out["blocks"] = []
        blocks = out["blocks"]
        changes.append("set blocks=[]")

    # Normalize empty speaker fields on dialogue blocks only enough to keep JSON stable.
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "dialogue" and "speaker" not in block:
            block["speaker"] = None
            changes.append("add missing dialogue speaker=null")

    end_blocks = [b for b in blocks if isinstance(b, dict) and b.get("type") == "end"]
    if not end_blocks:
        blocks.append({"type": "end", "text": "(จบบท)"})
        changes.append("append end marker")
    elif len(end_blocks) > 1:
        first_end = end_blocks[0]
        blocks[:] = [b for b in blocks if not (isinstance(b, dict) and b.get("type") == "end")]
        blocks.append(first_end)
        changes.append("dedupe end markers")
    elif blocks and blocks[-1] is not end_blocks[0]:
        blocks.remove(end_blocks[0])
        blocks.append(end_blocks[0])
        changes.append("move end marker to last")

    return out, changes


def iter_chapter_paths(novel: str, start: int, end: int):
    chapters_dir = NOVELS_DIR / novel / "chapters"
    for num in range(start, end + 1):
        path = chapters_dir / f"{num:04d}.json"
        if path.exists():
            yield num, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize chapter JSON metadata to NovelClaw v2.")
    parser.add_argument("--novel", default="global-descent", help="Novel slug under novels/.")
    parser.add_argument("--start", type=int, required=True, help="First chapter number.")
    parser.add_argument("--end", type=int, required=True, help="Last chapter number.")
    parser.add_argument("--lang", default="cn", help="Current v2 source language field value.")
    parser.add_argument("--write", action="store_true", help="Write changes. Omit for dry-run.")
    args = parser.parse_args()

    changed = 0
    missing = 0

    for num in range(args.start, args.end + 1):
        path = NOVELS_DIR / args.novel / "chapters" / f"{num:04d}.json"
        if not path.exists():
            missing += 1
            print(f"MISSING ch{num:04d}: {path}")
            continue

        original = load_json(path)
        normalized, changes = normalize_chapter(original, num, args.lang)
        if changes:
            changed += 1
            print(f"CHANGE ch{num:04d}: " + "; ".join(changes))
            if args.write:
                dump_json(path, normalized)
        else:
            print(f"OK ch{num:04d}")

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"{mode}: {changed} changed, {missing} missing, range={args.start}-{args.end}")


if __name__ == "__main__":
    main()
