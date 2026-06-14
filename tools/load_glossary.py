"""Load glossary.yml + style_rules.yml — single source of truth.

Replaces glossary.db at runtime. The .db is now optional (only for FTS).

Usage:
    from tools.load_glossary import load_terms, load_style_rules, find_term
    terms = load_terms()                    # list[dict]
    rules = load_style_rules()              # dict[section] -> list
    t = find_term("曹星", terms)            # dict or None
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).parent.parent
GLOSSARY_YML = ROOT / "novels" / "global-descent" / "glossary" / "glossary.yml"
STYLE_YML = ROOT / "novels" / "global-descent" / "style_rules.yml"


@lru_cache(maxsize=1)
def load_terms() -> list[dict]:
    """Load all terms from glossary.yml."""
    if not GLOSSARY_YML.exists():
        return []
    data = yaml.safe_load(GLOSSARY_YML.read_text(encoding="utf-8")) or {}
    terms = data.get("terms", [])
    # Coerce priority to int (YAML may parse it as int or str)
    for t in terms:
        try:
            t["priority"] = int(t.get("priority", 3))
        except (ValueError, TypeError):
            t["priority"] = 3
    return terms


@lru_cache(maxsize=1)
def load_style_rules() -> dict[str, list[dict]]:
    """Load style rules grouped by section."""
    if not STYLE_YML.exists():
        return {}
    return yaml.safe_load(STYLE_YML.read_text(encoding="utf-8")) or {}


def find_term(source: str, terms: list[dict] | None = None) -> Optional[dict]:
    """Find term by CN source (case-sensitive)."""
    terms = terms or load_terms()
    for t in terms:
        if t["source"] == source:
            return t
    return None


def search_terms(query: str, terms: list[dict] | None = None) -> list[dict]:
    """Search by CN source or Thai translation (case-insensitive)."""
    terms = terms or load_terms()
    q = query.lower()
    return [t for t in terms if q in t["source"].lower() or q in t["thai"].lower()]


def locked_terms(terms: list[dict] | None = None) -> list[dict]:
    """Return only locked (priority 1 + 2) terms."""
    terms = terms or load_terms()
    return [t for t in terms if t.get("lock") == "locked" and t.get("priority", 3) <= 2]


def get_drift_check(terms: list[dict] | None = None) -> dict:
    """Stats for monitoring glossary health."""
    terms = terms or load_terms()
    return {
        "total": len(terms),
        "locked": sum(1 for t in terms if t.get("lock") == "locked"),
        "reference": sum(1 for t in terms if t.get("lock") == "reference"),
        "auto": sum(1 for t in terms if t.get("lock") == "auto"),
    }


if __name__ == "__main__":
    terms = load_terms()
    rules = load_style_rules()
    stats = get_drift_check(terms)
    print(f"Glossary: {stats['total']} terms")
    print(f"  Locked: {stats['locked']}, Reference: {stats['reference']}, Auto: {stats['auto']}")
    print(f"\nStyle rules: {len(rules)} sections")
    for k, v in rules.items():
        print(f"  {k}: {len(v)}")
    # Verify
    t = find_term("曹星")
    print(f"\n曹星 → {t['thai'] if t else 'NOT FOUND'}")
    t = find_term("เฉาซิง")
    # Note: search by Thai requires search_terms
    results = search_terms("เฉาซิง")
    print(f"Search เฉาซิง: {len(results)} hits")
    if results:
        print(f"  First: {results[0]['source']} → {results[0]['thai']}")
