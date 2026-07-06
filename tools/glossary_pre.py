#!/usr/bin/env python3
"""glossary_pre.py — Character + term injection for prompt (Station 3 Pre).

โหลด glossary.json → inject ทั้ง character voice maps AND known terms
เพื่อให้ LLM แปลถูกตั้งแต่รอบแรก (proactive, not post-hoc)

Two sections injected:
  1. <character_voice> — character name maps + pronoun guidance
  2. <glossary_map> — known CN→TH term pairs (priority 1 + top auto)

Used by pipeline.py Station 3 — inject เข้า prompt ก่อนส่ง LLM
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from novel_paths import glossary_json_path


_MAX_GLOSSARY_TERMS = 40  # ponytail: cap total injected terms to keep prompt lean


def _get_glossary_path(slug: str = "global-descent") -> Path:
    """Get path to glossary.json for a novel."""
    return glossary_json_path(slug)


# ── Character loading ──────────────────────────────────────────────────


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
        characters = [
            t for t in terms
            if t.get("category") == "ตัวละคร" and t.get("source") and t.get("thai")
        ]
        # Sort: locked/priority 1 first, then alphabetical by source
        characters.sort(key=lambda t: (t.get("priority", 3), t.get("source", "")))
        return characters
    except Exception:
        return []


# ── Term loading (non-character known terms) ────────────────────────────


@lru_cache(maxsize=8)
def load_known_terms(slug: str = "global-descent") -> list[dict]:
    """Load non-character terms that LLM should translate correctly.

    Returns priority-descending list:
      - Locked terms (priority=1) — always included
      - auto_discovered terms with highest frequency — up to _MAX_GLOSSARY_TERMS total
    """
    path = _get_glossary_path(slug)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])

        # Separate characters out (handled by build_character_prompt)
        # Collect replace-action terms with valid source→thai mapping
        known: list[dict] = []
        auto: list[dict] = []

        for t in terms:
            if not t.get("source") or not t.get("thai"):
                continue
            if t.get("category") == "ตัวละคร":
                continue
            if t.get("priority") == 1:
                known.append(t)
            else:
                auto.append(t)

        # Sort auto-discovered by frequency descending (from notes field)
        def _extract_freq(t: dict) -> int:
            notes = str(t.get("notes", "") or t.get("explanation", ""))
            # Extract freq=N from "auto_discovered (freq=3, ...)"
            idx = notes.find("freq=")
            if idx >= 0:
                try:
                    return int(notes[idx + 5 :].split(",")[0].split(")")[0])
                except (ValueError, IndexError):
                    pass
            return 0

        auto.sort(key=_extract_freq, reverse=True)

        # Combine: known (priority) + top auto up to cap
        cap = _MAX_GLOSSARY_TERMS
        result = known[:cap]
        if len(result) < cap:
            result.extend(auto[: cap - len(result)])

        return result
    except Exception:
        return []


# ── Prompt builders ────────────────────────────────────────────────────


def build_character_prompt(slug: str = "global-descent", max_chars: int = 20) -> str:
    """Build character voice map for prompt injection.

    Returns compressed string like:
      <character_voice>
      CN→Thai name map (main characters):
        | เฉาซิง (MC) | ...
      Pronoun guidance:
        ...
      </character_voice>
    """
    chars = load_characters(slug)
    if not chars:
        return ""

    main_chars = chars[:max_chars]

    lines = [
        "<character_voice>",
        "CN→Thai name map (HARD CONSTRAINTS):",
        "  - If a source name appears, use exactly its mapped Thai name.",
        "  - Never substitute one character's Thai name for another.",
    ]
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


def build_term_map(slug: str = "global-descent") -> str:
    """Build known-term map for prompt injection.

    Returns string like:
      <glossary_map>
      黑龍 → มังกรดำ  [ไอเทม]
      VIP → VIP  [ทั่วไป]
      ...
      </glossary_map>
    """
    terms = load_known_terms(slug)
    if not terms:
        return ""

    lines = ["<glossary_map>"]
    for t in terms:
        lines.append(f"  {t['source']} → {t['thai']}  [{t.get('category', '?')}]")
    lines.append("</glossary_map>")
    return "\n".join(lines)


def build_glossary_pre_chunk(slug: str = "global-descent") -> str:
    """One-shot: full character + term context for prompt injection.

    Returns combined string of character voice map + term map,
    or empty string if glossary.json doesn't exist.
    """
    path = _get_glossary_path(slug)
    if not path.exists():
        return ""

    parts = [build_character_prompt(slug), build_term_map(slug)]
    combined = "\n\n".join(p for p in parts if p)
    return combined


if __name__ == "__main__":
    print(build_glossary_pre_chunk())
