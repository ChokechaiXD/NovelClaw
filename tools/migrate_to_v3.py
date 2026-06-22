#!/usr/bin/env python3
"""
migrate_to_v3.py — Convert chapter JSON from blocks format → paragraphs format.

Adds `paragraphs` field while preserving `blocks` for backward compatibility.
Idempotent: skips chapters already migrated.

Usage:
    python tools/migrate_to_v3.py novels/global-descent
"""

import json
import sys
from pathlib import Path


def migrate_chapter(json_path: Path) -> bool:
    """Migrate one chapter. Returns True if changed."""
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # Already migrated or paragraphs format
    if data.get("paragraphs"):
        return False

    blocks = data.get("blocks", [])
    if not blocks:
        return False

    paragraphs = []
    for block in blocks:
        text = block.get("text", "").strip()
        if not text:
            continue
        # Skip standalone end marker (will be auto-appended by schema)
        if block.get("type") == "end":
            continue
        paragraphs.append(text)

    # Ensure end marker
    end = blocks[-1].get("text", "(จบบท)") if blocks else "(จบบท)"
    paragraphs.append(end)

    data["paragraphs"] = paragraphs
    data["schema_version"] = 3
    # Keep blocks for backward compat (reader.js still checks data.blocks)

    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("novels/global-descent")
    chapters_dir = root / "chapters"
    if not chapters_dir.exists():
        print(f"❌ Chapters dir not found: {chapters_dir}")
        sys.exit(1)

    json_files = sorted(chapters_dir.glob("*.json"))
    migrated = 0
    skipped = 0

    for jf in json_files:
        try:
            if migrate_chapter(jf):
                migrated += 1
                print(f"  ✅ {jf.name}")
            else:
                skipped += 1
        except Exception as e:
            print(f"  ❌ {jf.name}: {e}")

    print(f"\nDone: {migrated} migrated, {skipped} skipped ({len(json_files)} total)")


if __name__ == "__main__":
    main()
