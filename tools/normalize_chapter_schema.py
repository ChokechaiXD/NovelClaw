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
    - missing `output_lang`
    - missing end marker
    - end marker not last
    - end marker not matching output language

What it does NOT fix:
    - translation quality
    - glossary drift
    - quote style conversion
    - source completeness
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOVELS_DIR = PROJECT_ROOT / "novels"

# Single source of truth for bracket/end-marker config
BRACKETS_PATH = PROJECT_ROOT / "reader" / "config" / "brackets.json"

if BRACKETS_PATH.exists():
    _brackets_data: dict[str, dict[str, str]] = json.loads(
        BRACKETS_PATH.read_text(encoding="utf-8")
    )
else:
    _brackets_data = {}


def expected_end_marker(output_lang: str) -> str:
    """Read end marker from brackets.json (single source of truth)."""
    profile = _brackets_data.get(output_lang, {})
    return profile.get("end_marker", "(จบบท)")


def normalize_chapter(
    data: dict[str, Any], num: int, lang: str, output_lang: str
) -> tuple[dict[str, Any], list[str]]:
    changes: list[str] = []
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
        out["title"] = f"ตอนที่ {num}: {title}"
        changes.append("prefix title with chapter number")

    if out.get("source") != f"ch {num}":
        out["source"] = f"ch {num}"
        changes.append("set source")

    if out.get("lang") != lang:
        out["lang"] = lang
        changes.append(f"set lang={lang}")

    if out.get("output_lang") != output_lang:
        out["output_lang"] = output_lang
        changes.append(f"set output_lang={output_lang}")

    if not isinstance(out.get("notes"), list):
        out["notes"] = []
        changes.append("set notes=[]")

    blocks = out.get("blocks")
    if not isinstance(blocks, list):
        out["blocks"] = []
        blocks = out["blocks"]
        changes.append("set blocks=[]")

    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "dialogue" and "speaker" not in block:
            block["speaker"] = None
            changes.append("add missing dialogue speaker=null")

    end_marker_text = expected_end_marker(output_lang)
    end_blocks = [b for b in blocks if isinstance(b, dict) and b.get("type") == "end"]
    if not end_blocks:
        blocks.append({"type": "end", "text": end_marker_text})
        changes.append(f"append end marker {end_marker_text}")
    else:
        first_end = end_blocks[0]
        if first_end.get("text") != end_marker_text:
            first_end["text"] = end_marker_text
            changes.append(f"set end marker {end_marker_text}")
        if len(end_blocks) > 1:
            blocks[:] = [b for b in blocks if not (isinstance(b, dict) and b.get("type") == "end")]
            blocks.append(first_end)
            changes.append("dedupe end markers")
        elif blocks and blocks[-1] is not end_blocks[0]:
            blocks.remove(end_blocks[0])
            blocks.append(end_blocks[0])
            changes.append("move end marker to last")

    return out, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize chapter JSON metadata to NovelClaw v2.")
    parser.add_argument(
        "--novel",
        default=os.environ.get("NOVEL_SLUG", "global-descent"),
        help="Novel slug under novels/. Uses $NOVEL_SLUG env var or default 'global-descent'.",
    )
    parser.add_argument("--start", type=int, required=True, help="First chapter number.")
    parser.add_argument("--end", type=int, required=True, help="Last chapter number.")
    parser.add_argument("--lang", default="cn", help="Current v2 source language field value.")
    parser.add_argument(
        "--output-lang", default="th", help="Output language/profile to set on translated chapters."
    )
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

        original = json.loads(path.read_text(encoding="utf-8"))
        normalized, changes = normalize_chapter(original, num, args.lang, args.output_lang)
        if changes:
            changed += 1
            print(f"CHANGE ch{num:04d}: " + "; ".join(changes))
            if args.write:
                path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            print(f"OK ch{num:04d}")

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"{mode}: {changed} changed, {missing} missing, range={args.start}-{args.end}")


if __name__ == "__main__":
    main()
