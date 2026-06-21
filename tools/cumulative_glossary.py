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

# ── Thai placeholder for unknown terms ──────────────────────────────
# When no Thai translation exists, use the CN source as placeholder.
# The "auto" lock + priority 3 + notes "(รอคำแปล)" tells the human
# this needs a real Thai entry.
THAI_PLACEHOLDER = ""
# (Using empty string — the Markdown cell will be blank.
#  build_yaml.py requires thai to be non-empty, so we use CN source
#  as temporary Thai. The notes field says "(รอคำแปล)" to flag it.)


def get_auto_md_path(slug: str = "global-descent") -> Path:
    """Get path to auto.md for a novel."""
    return NOVELS_DIR / slug / "glossary" / "auto.md"


def _already_in_auto_md(source: str, slug: str = "global-descent") -> bool:
    """Check if source term already exists in auto.md."""
    path = get_auto_md_path(slug)
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    # Match exact source term in markdown row
    for line in content.splitlines():
        if line.strip().startswith(f"| {source} |"):
            return True
    return False


def _parse_auto_md_existing(slug: str = "global-descent") -> set[str]:
    """Return set of all CN source terms already in auto.md."""
    path = get_auto_md_path(slug)
    if not path.exists():
        return set()
    existing = set()
    from build_yaml import parse_markdown_terms
    terms = parse_markdown_terms(path, "auto", 3)
    for t in terms:
        existing.add(str(t["source"]))
    return existing


def _build_auto_md_row(source: str, category: str, ch_num: int, thai: str = "") -> str:
    """Build a markdown table row for auto.md.
    
    Format: | Source | Thai | Category | Priority | Notes |
    """
    thai_text = thai if thai else source  # Use CN source as placeholder if no Thai
    notes = f"auto-detect from ch{ch_num} — รอคำแปล"
    return f"| {source} | {thai_text} | {category} | 3 | {notes} |\n"


def get_candidate_entities(
    ch_num: int,
    source_text: str,
    glossary_terms: list[dict[str, Any]],
    slug: str = "global-descent",
) -> list[dict[str, Any]]:
    """Extract entities from source that should become auto-glossary entries.
    
    Criteria:
      1. Must be a bracket-derived entity (game_title, system, dialogue)
         - These have high certainty of being proper nouns
      2. Must NOT already be in glossary (any tier)
      3. Must NOT be generic/common vocabulary
      4. Must NOT already be in auto.md
    """
    # All known glossary sources
    known_sources: set[str] = set()
    for t in glossary_terms:
        known_sources.add(str(t["source"]))
    
    # Already in auto.md
    auto_sources = _parse_auto_md_existing(slug)
    
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    
    # 1. Extract from brackets (highest certainty)
    for ent in extract_from_brackets(source_text):
        src = ent["source"]
        if (src not in known_sources 
            and src not in auto_sources 
            and src not in seen):
            seen.add(src)
            ent["ch_num"] = ch_num
            candidate_category = BRACKET_TO_CATEGORY.get(ent["bracket_type"], "ทั่วไป")
            ent["category"] = candidate_category
            candidates.append(ent)
    
    # 2. Extract dialogue speakers (medium certainty)
    for ent in extract_dialogue_speakers(source_text):
        src = ent["source"]
        if (src not in known_sources 
            and src not in auto_sources 
            and src not in seen):
            seen.add(src)
            ent["ch_num"] = ch_num
            ent["category"] = "ตัวละคร"
            candidates.append(ent)
    
    return candidates


def append_candidates_to_auto_md(
    candidates: list[dict[str, Any]],
    slug: str = "global-descent",
) -> int:
    """Append candidate entities as new rows in auto.md.
    
    Returns number of rows added.
    """
    if not candidates:
        return 0
    
    path = get_auto_md_path(slug)
    
    # Read existing content
    if path.exists():
        existing_content = path.read_text(encoding="utf-8")
        lines = existing_content.splitlines()
    else:
        # Create new auto.md with header
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
    
    # Append before the last blank line or at the end
    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    content += "".join(new_rows)
    
    path.write_text(content, encoding="utf-8")
    return added


def rebuild_glossary_yml(slug: str = "global-descent") -> int:
    """Rebuild glossary.yml from all .md source files.
    
    Returns number of terms in built glossary.
    """
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
    """Main entry point: after a translation, extract and save new candidates.
    
    Args:
        ch_num: chapter number
        source_text: cleaned source text
        glossary_terms: current glossary terms list
        slug: novel slug
        auto_rebuild: whether to rebuild glossary.yml after adding
        
    Returns:
        dict with count of new candidates and total glossary size
    """
    candidates = get_candidate_entities(ch_num, source_text, glossary_terms, slug)
    
    if not candidates:
        return {"added": 0, "total": len(glossary_terms)}
    
    added = append_candidates_to_auto_md(candidates, slug)
    
    total_terms = len(glossary_terms)
    if auto_rebuild and added > 0:
        total_terms = rebuild_glossary_yml(slug)
        # Clear LRU cache on glossary module so future loads see new data
        from glossary import load_terms
        load_terms.cache_clear()
    
    return {
        "added": added,
        "total": total_terms,
        "candidates": [c["source"] for c in candidates[:10]],  # first 10
    }
