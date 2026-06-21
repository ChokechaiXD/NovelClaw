"""cumulative_glossary.py — Auto-discover and suggest new glossary entries.

After each chapter translation, entities detected by the entity pipeline
that are NOT in the glossary are extracted and appended to auto.md.
This builds up the glossary cumulatively across chapters.

Flow:
  1. After successful translate_one(), extract entities from source
  2. Filter: only non-glossary, non-generic, bracket-derived entities
  3. Append new rows to auto.md
  4. Rebuild glossary.yml via build_yaml.py

auto.md format: | Source | Thai | Category | Priority | Notes |
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from constants import NOVELS_DIR
from extract_entities import extract_from_brackets, extract_dialogue_speakers

# ── Bracket type → glossary category mapping ────────────────────────
BRACKET_TO_CATEGORY = {
    "game_title": "ไอเทม",
    "system": "สกิล",
    "jp_bracket": "ทั่วไป",
    "dialogue": "ตัวละคร",
    "frequent": "ทั่วไป",
}


# ── Helpers ─────────────────────────────────────────────────────────


def _get_auto_md_path(slug: str = "global-descent") -> Path:
    """Get path to auto.md for a novel."""
    return NOVELS_DIR / slug / "glossary" / "auto.md"


def _parse_auto_md_existing(slug: str = "global-descent") -> set[str]:
    """Return set of all CN source terms already in auto.md."""
    path = _get_auto_md_path(slug)
    if not path.exists():
        return set()
    from build_yaml import parse_markdown_terms
    terms = parse_markdown_terms(path, "auto", 3)
    return {str(t["source"]) for t in terms}


def _build_auto_md_row(source: str, category: str, ch_num: int, thai: str = "") -> str:
    """Build a markdown table row for auto.md.

    Format: | Source | Thai | Category | Priority | Notes |
    """
    thai_text = thai if thai else source
    notes = f"auto-detect from ch{ch_num} — รอคำแปล"
    return f"| {source} | {thai_text} | {category} | 3 | {notes} |\n"


# ── Public API ──────────────────────────────────────────────────────


def get_candidate_entities(
    ch_num: int,
    source_text: str,
    glossary_terms: list[dict[str, Any]],
    slug: str = "global-descent",
) -> list[dict[str, Any]]:
    """Extract entities from source that should become auto-glossary entries."""

    known_sources: set[str] = {str(t["source"]) for t in glossary_terms}
    auto_sources = _parse_auto_md_existing(slug)

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 1. Extract from brackets (highest certainty)
    for ent in extract_from_brackets(source_text):
        src = ent["source"]
        if src not in known_sources and src not in auto_sources and src not in seen:
            seen.add(src)
            ent["ch_num"] = ch_num
            ent["category"] = BRACKET_TO_CATEGORY.get(ent["bracket_type"], "ทั่วไป")
            candidates.append(ent)

    # 2. Extract dialogue speakers (medium certainty)
    for ent in extract_dialogue_speakers(source_text):
        src = ent["source"]
        if src not in known_sources and src not in auto_sources and src not in seen:
            seen.add(src)
            ent["ch_num"] = ch_num
            ent["category"] = "ตัวละคร"
            candidates.append(ent)

    return candidates


def append_candidates_to_auto_md(
    candidates: list[dict[str, Any]],
    slug: str = "global-descent",
) -> int:
    """Append candidate entities as new rows in auto.md. Returns added count."""
    if not candidates:
        return 0

    path = _get_auto_md_path(slug)

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            f"# Auto Glossary — auto-detected",
            "",
            "> Terms auto-discovered during translation. Review and fill Thai.",
            "> Terms with Thai already filled are ready for locked/reference promotion.",
            "",
            "| Source | Thai | Category | Priority | Notes |",
            "|--------|------|----------|----------|-------|",
        ]

    existing_sources = _parse_auto_md_existing(slug)
    added = 0
    new_rows = []

    for ent in candidates:
        src = ent["source"]
        if src in existing_sources:
            continue
        row = _build_auto_md_row(
            source=src,
            category=ent.get("category", "ทั่วไป"),
            ch_num=ent.get("ch_num", 0),
        )
        new_rows.append(row)
        added += 1
        existing_sources.add(src)

    if not new_rows:
        return 0

    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    content += "".join(new_rows)
    path.write_text(content, encoding="utf-8")
    return added


def rebuild_glossary_yml(slug: str = "global-descent") -> int:
    """Rebuild glossary.yml from all .md source files. Returns term count."""
    try:
        from build_yaml import build_terms, write_yaml
        terms = build_terms(slug)
        write_yaml(slug, terms)
        return len(terms)
    except Exception as e:
        print(f"⚠ Failed to rebuild glossary YAML: {e}")
        return 0


def process_translation_candidates(
    ch_num: int,
    source_text: str,
    glossary_terms: list[dict[str, Any]],
    slug: str = "global-descent",
    auto_rebuild: bool = True,
) -> dict:
    """Main entry point: after a translation, extract and save new candidates."""
    candidates = get_candidate_entities(ch_num, source_text, glossary_terms, slug)

    if not candidates:
        return {"added": 0, "total": len(glossary_terms)}

    added = append_candidates_to_auto_md(candidates, slug)

    total_terms = len(glossary_terms)
    if auto_rebuild and added > 0:
        total_terms = rebuild_glossary_yml(slug)
        from glossary import load_terms
        load_terms.cache_clear()

    return {
        "added": added,
        "total": total_terms,
        "candidates": [c["source"] for c in candidates[:10]],
    }
