#!/usr/bin/env python3
"""
glossary_discovery.py — Auto term discovery for NovelClaw.

หลังแปลเสร็จ → scan source → เจอคำที่ไม่อยู่ใน glossary
→ ใช้ LLM เสนอคำแปล → เพิ่มเข้า glossary.json อัตโนมัติ

Architecture:
  - Uses a SEPARATE model (judge/discovery model) from translate model
  - Runs after Station 6.75 (Judge), before final save
  - Only processes terms that appear 2+ times in source (confidence filter)
  - Saves to glossary.json with priority=3 (auto) + notes="auto_discovered"
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json
from novel_paths import glossary_json_path
from source_cleaner import KOREAN_MARKERS, UI_NOISE

# ── CJK term extraction ───────────────────────────────────────────────

_CN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")  # 2-8 CJK chars
_HANGUL_RE = re.compile(r"[\uac00-\ud7af]{2,8}")
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]{2,8}")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]{2,8}")
_SAVE_CONFIDENCE = {"high", "medium"}


def _get_glossary_path(slug: str = "global-descent") -> Path:
    """Get path to glossary.json."""
    return glossary_json_path(slug)


@lru_cache(maxsize=8)
def _load_existing_terms(slug: str = "global-descent") -> set[str]:
    """Load ALL existing source terms from glossary.json (cached)."""
    path = _get_glossary_path(slug)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {t["source"] for t in data.get("terms", []) if t.get("source")}
    except Exception:
        return set()


def extract_unknown_terms(
    source_text: str,
    slug: str = "global-descent",
    source_lang: str = "cn",
    min_freq: int = 2,
) -> list[dict[str, Any]]:
    """Extract terms from source that aren't in glossary yet.

    Args:
        source_text: Cleaned source text.
        slug: Novel slug.
        source_lang: 'cn', 'jp', 'kr', 'en'
        min_freq: Minimum occurrences to consider (filter noise).

    Returns:
        [{"term": "黑龍", "freq": 3, "context": "..."}, ...]
    """
    existing = _load_existing_terms(slug)
    noise = UI_NOISE.copy()

    # Pick regex based on language
    if source_lang == "kr":
        re_term = _HANGUL_RE
        noise |= KOREAN_MARKERS
    elif source_lang == "jp":
        re_term = re.compile(
            r"[\u3040-\u309f]{3,8}|[\u30a0-\u30ff]{2,8}|[\u4e00-\u9fff]{2,8}"
        )
    else:
        re_term = _CN_RE

    # Extract ALL terms
    all_terms = re_term.findall(source_text)

    # Count frequency
    freq: dict[str, int] = {}
    for term in all_terms:
        if term in existing or term in noise:
            continue
        freq[term] = freq.get(term, 0) + 1

    # Filter by frequency
    candidates = {t for t, c in freq.items() if c >= min_freq}

    # Attach context snippet (first occurrence ±20 chars)
    result = []
    for term in sorted(candidates, key=lambda t: -freq[t]):
        idx = source_text.find(term)
        start = max(0, idx - 15)
        end = min(len(source_text), idx + len(term) + 15)
        context = source_text[start:end].replace("\n", " ")
        result.append({
            "term": term,
            "freq": freq[term],
            "context": context,
        })

    return result


# ── LLM-based translation proposal ────────────────────────────────────

_DISCOVERY_PROMPT = """You are a Chinese→Thai glossary term translator.

For each Chinese term below, propose a Thai translation.
Rules:
- Keep it concise (1-3 Thai words)
- Use natural Thai, not transliteration by default
- If it's a proper name (person/place), use phonetic transliteration
- If it's a game skill/item, translate meaning
- If unsure, provide your best guess with a "?" prefix

Output format:
term | proposed_thai | confidence(high/medium/low) | note

Terms:
{terms}"""


_KR_DISCOVERY_PROMPT = """You are a Korean→Thai glossary term translator.

For each Korean term below, propose a Thai translation.
Rules:
- Keep it concise (1-3 Thai words)
- Proper names → phonetic transliteration
- Items/skills → translate meaning

Output format:
term | proposed_thai | confidence(high/medium/low) | note

Terms:
{terms}"""


def propose_translations(
    candidates: list[dict[str, Any]],
    source_lang: str = "cn",
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Use LLM to propose Thai translations for unknown terms.

    Args:
        candidates: From extract_unknown_terms()
        source_lang: Source language.
        model: Model name for discovery (default: from pipeline config).

    Returns:
        Updated candidates with "proposed_thai" and "confidence" fields.
    """
    if not candidates:
        return candidates

    from pipeline_llm import call_llm

    # Build term list for prompt (max 30 per call to keep prompt short)
    batch_size = 30
    results = []

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        term_lines = []
        for c in batch:
            term_lines.append(f"{c['term']} | context: {c['context']}")

        prompt_text = "\n".join(term_lines)
        prompt = (
            (_KR_DISCOVERY_PROMPT if source_lang == "kr" else _DISCOVERY_PROMPT)
            .format(terms=prompt_text)
        )

        try:
            response, provider, model_name = call_llm(
                prompt=prompt,
                system=None,
                model=model,
                temperature=0.1,
                max_tokens=2000,
            )
        except Exception as e:
            # Fallback: mark all as unknown
            for c in batch:
                c["proposed_thai"] = f"?[error: {str(e)[:40]}]"
                c["confidence"] = "low"
            results.extend(batch)
            continue

        # Parse response. Accept both plain pipe rows and Markdown table rows.
        for line in response.strip().split("\n"):
            line = line.strip()
            if "|" not in line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if not parts:
                continue
            first = parts[0].lower()
            if first == "term" or set(first) <= {"-", " "}:
                continue
            if len(parts) < 2:
                continue
            term = parts[0]
            proposed = parts[1]
            confidence = parts[2] if len(parts) > 2 else "medium"
            note = parts[3] if len(parts) > 3 else ""

            # Find matching candidate and update
            for c in batch:
                if c["term"] == term:
                    c["proposed_thai"] = proposed
                    c["confidence"] = confidence
                    c["note"] = note
                    break

        results.extend(batch)

    return results


# ── Save discovered terms to glossary ─────────────────────────────────

def _normalize_confidence(value: Any) -> str:
    return str(value or "").strip().lower().split()[0]


def _should_save_discovered_term(candidate: dict[str, Any]) -> bool:
    term = str(candidate.get("term", "")).strip()
    proposed = str(candidate.get("proposed_thai", "")).strip()
    confidence = _normalize_confidence(candidate.get("confidence", "medium"))

    if not term or term in UI_NOISE or term in KOREAN_MARKERS:
        return False
    if not proposed or proposed.startswith("?"):
        return False
    return confidence in _SAVE_CONFIDENCE


def _clear_glossary_caches() -> None:
    """Clear glossary readers that may be stale after saving new terms."""
    _load_existing_terms.cache_clear()
    try:
        from glossary_pre import load_characters

        load_characters.cache_clear()
    except Exception:
        pass

def save_discovered_terms(
    discovered: list[dict[str, Any]],
    slug: str = "global-descent",
) -> int:
    """Save auto-discovered terms to glossary.json.

    Only saves medium/high-confidence terms with safe proposed_thai values.

    Returns:
        Number of terms saved.
    """
    path = _get_glossary_path(slug)
    if not path.exists():
        return 0

    # Load existing
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])
    except Exception:
        terms = []

    existing_sources = {t["source"] for t in terms if t.get("source")}
    saved = 0

    for c in discovered:
        if not _should_save_discovered_term(c):
            continue

        proposed = str(c.get("proposed_thai", "")).strip()
        term = str(c["term"]).strip()
        if term in existing_sources:
            continue  # Already in glossary, skip

        new_entry = {
            "source": term,
            "thai": proposed,
            "category": "auto_discovered",
            "priority": 3,
            "lock": "auto",
            "verified": False,
            "explanation": c.get("note", ""),
            "notes": f"auto_discovered (freq={c['freq']}, confidence={c.get('confidence', 'medium')})",
        }
        terms.append(new_entry)
        existing_sources.add(term)
        saved += 1

    if saved > 0:
        data = {"terms": terms}
        atomic_write_json(path, data, ensure_ascii=False, indent=2)
        _clear_glossary_caches()

    return saved


# ── One-shot pipeline hook ────────────────────────────────────────────

def discover_and_save(
    source_text: str,
    slug: str = "global-descent",
    source_lang: str = "cn",
    discovery_model: str | None = None,
    max_terms: int = 30,  # ponytail: cap to prevent LLM call explosion
) -> dict[str, Any]:
    """Full discovery pipeline: extract → propose → save.

    Called from pipeline.py after Station 6.75.

    Args:
        max_terms: Maximum candidate terms to propose per call.
                   Hard cap prevents explosion when source has 200+ unique terms.
    Returns:
        {"discovered": N, "saved": N, "terms": [...]}
    """
    candidates = extract_unknown_terms(source_text, slug, source_lang, min_freq=2)
    if not candidates:
        return {"discovered": 0, "saved": 0, "terms": []}

    # Cap candidates to prevent LLM call explosion
    if len(candidates) > max_terms:
        candidates = candidates[:max_terms]

    proposed = propose_translations(candidates, source_lang, discovery_model)
    saved = save_discovered_terms(proposed, slug)

    return {
        "discovered": len(candidates),
        "saved": saved,
        "terms": [{"term": c["term"], "thai": c.get("proposed_thai", "?"), "confidence": c.get("confidence", "low")}
                  for c in proposed[:10]],  # Top 10 for display
    }
