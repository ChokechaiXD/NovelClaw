#!/usr/bin/env python3
"""
glossary_pre.py — Character name injection for prompt (Station 3 Pre).

โหลดชื่อตัวละคร (ตัวละคร category) จาก glossary.json
และสร้าง character voice map ให้ LLM ใช้ pronoun ได้ถูกต้อง

ใช้ใน pipeline.py Station 3 — inject เข้า prompt ก่อนส่ง LLM
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def _get_glossary_path(slug: str = "global-descent") -> Path:
    """Get path to glossary.json for a novel."""
    from schema import get_novel_root
    return get_novel_root(slug, check_exists=False) / "glossary" / "glossary.json"


@lru_cache(maxsize=8)
def load_characters(slug: str = "global-descent") -> list[dict]:
    """Load character terms (ตัวละคร) from glossary.json.

    Returns sorted list: main characters first (priority 1), then others.
    """
    path = _get_glossary_path(slug)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])
        characters = [t for t in terms if t.get("category") == "ตัวละคร" and t.get("source") and t.get("thai")]

        # Sort: locked/priority 1 first, then alphabetical by source
        characters.sort(key=lambda t: (t.get("priority", 3), t.get("source", "")))
        return characters
    except Exception:
        return []


def build_character_prompt(slug: str = "global-descent", max_chars: int = 20) -> str:
    """Build character voice map for prompt injection.

    Returns compressed string like:
      <character_voice>
      CN→Thai name map (main characters):
        | เฉาซิง (MC) | เรียกตัวเอง: ข้า | เรียกผู้อื่น: เจ้า/นาย |
        | หลิวมู่เสวี่ย | เรียกตัวเอง: ข้า | เรียกเฉาซิง: อาซิง |
        | อาซัม | เรียกตัวเอง: ข้า | เรียกเฉาซิง: ท่านลอร์ด |
        ...
      Pronoun guidance:
        他 → เขา/มัน/ตัวนั้น
        她 → เธอ/นาง
        你 → เจ้า/นาย/ท่าน
        我 → ข้า/ฉัน/กระผม
      </character_voice>
    """
    chars = load_characters(slug)
    if not chars:
        return ""

    # Limit to main characters for prompt brevity
    main_chars = chars[:max_chars]

    lines = ["<character_voice>", "CN→Thai name map (main characters):"]
    for c in main_chars:
        src = c["source"]
        thai = c["thai"]
        notes = c.get("notes", "")
        note_str = f" — {notes[:40]}" if notes else ""
        lines.append(f"  {src} → {thai}{note_str}")

    lines.append("")
    lines.append("Pronoun guidance:")
    lines.append("  他 → เขา / มัน / ตัวนั้น (by context)")
    lines.append("  她 → เธอ / นาง (by character voice and register)")
    lines.append("  你 → เจ้า / นาย / ท่าน (by relationship)")
    lines.append("  我 → ข้า / ฉัน / กระผม (by speaker voice)")
    lines.append("</character_voice>")

    return "\n".join(lines)


def build_glossary_pre_chunk(slug: str = "global-descent") -> str:
    """One-shot: full character context for prompt injection.

    Used by pipeline.py Station 3.
    """
    return build_character_prompt(slug)


if __name__ == "__main__":
    print(build_glossary_pre_chunk())
