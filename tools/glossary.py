"""glossary.py — Single source of truth glossary and style rule loader.

Loads glossary.yml + style_rules.yml directly from the filesystem,
completely replacing the legacy SQLite glossary.db database.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
import json

PROJECT_ROOT = Path(__file__).parent.parent
NOVELS_DIR = PROJECT_ROOT / "novels"


def get_novel_root(slug: str = "global-descent") -> Path:
    import os
    s = os.environ.get('NOVEL_SLUG', slug) if slug == "global-descent" else slug
    return NOVELS_DIR / s


def get_glossary_yml_path(slug: str = "global-descent") -> Path:
    return get_novel_root(slug) / "glossary" / "glossary.yml"


def get_style_yml_path(slug: str = "global-descent") -> Path:
    return get_novel_root(slug) / "style_rules.yml"


def get_format_spec_path(slug: str = "global-descent") -> Path:
    """Return the path to format_spec.json."""
    return get_novel_root(slug) / "format_spec.json"


def load_format_spec(slug: str = "global-descent") -> dict:
    """Load format_spec.json as dict. Returns empty dict if missing."""
    path = get_format_spec_path(slug)
    if not path.exists():
        print(f"Warning: format_spec.json not found for '{slug}'")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_style_rules_from_spec(slug: str = "global-descent") -> dict:
    """Generate style_rules.yml content from format_spec.json."""
    spec = load_format_spec(slug)
    rules = {}

    punct = spec.get("punctuation", {})
    punc_rules = []
    if "em_dash" in punct:
        punc_rules.append({"text": f'Use em-dash ({punct["em_dash"]}) for missing numbers in stat blocks.'})
    if "end_marker" in punct:
        punc_rules.append({"text": f'End marker: use {punct["end_marker"]} in the last block of every chapter.'})
    if "source_footer" in punct:
        punc_rules.append({"text": f'Source footer: {punct["source_footer"]} (no novel title or author).'})
    punc_rules.append({"text": "Paragraph spacing: single blank line between paragraphs."})
    punc_rules.append({"text": "Cleaning: no trailing whitespace, no tabs, final newline at end of files."})
    if punc_rules:
        rules["punctuation"] = punc_rules

    nat = spec.get("naturalness", {})
    nat_rules = []
    fw = nat.get("filter_words", [])
    if fw:
        nat_rules.append({"text": "Filter words: remove " + ", ".join(fw) + "."})
    if "adverb_doubling" in nat:
        nat_rules.append({"text": nat["adverb_doubling"]})
    el = nat.get("eliminate", [])
    if el:
        nat_rules.append({"text": "Elimination: drop unnecessary " + ", ".join(el) + "."})
    if "dialogue_anchoring" in nat:
        nat_rules.append({"text": nat["dialogue_anchoring"]})
    if nat_rules:
        rules["naturalness"] = nat_rules

    pol = spec.get("policies", {})
    pol_rules = []
    labels = {"scene_integrity": "Scene Integrity", "intimacy": "Intimacy", "doubt": "When in Doubt"}
    for k, v in pol.items():
        lbl = labels.get(k, k.replace("_", " ").title())
        pol_rules.append({"text": lbl + ": " + v})
    if pol_rules:
        rules["policies"] = pol_rules

    return rules


@lru_cache(maxsize=16)
def load_terms(slug: str = "global-descent") -> list[dict]:
    """Load all terms from glossary.yml."""
    yml_path = get_glossary_yml_path(slug)
    if not yml_path.exists():
        return []
    try:
        data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
        terms = data.get("terms", [])
        # Coerce priority to int (YAML may parse it as int or str)
        for t in terms:
            try:
                t["priority"] = int(t.get("priority", 3))
            except (ValueError, TypeError):
                t["priority"] = 3
        return terms
    except Exception as e:
        print(f"⚠️  Failed to load glossary YAML for {slug}: {e}")
        return []


@lru_cache(maxsize=16)
def load_style_rules(slug: str = "global-descent") -> dict[str, list[dict]]:
    """Load style rules grouped by section."""
    yml_path = get_style_yml_path(slug)
    if not yml_path.exists():
        return {}
    try:
        return yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"⚠️  Failed to load style rules YAML for {slug}: {e}")
        return {}


def find_term(source: str, terms: list[dict] = None, slug: str = "global-descent") -> Optional[dict]:
    """Find term by CN source (case-sensitive)."""
    terms = terms or load_terms(slug)
    for t in terms:
        if t["source"] == source:
            return t
    return None


def search_terms(query: str, terms: list[dict] = None, slug: str = "global-descent") -> list[dict]:
    """Search by CN source or Thai translation (case-insensitive)."""
    terms = terms or load_terms(slug)
    q = query.lower()
    return [t for t in terms if q in t["source"].lower() or q in t["thai"].lower()]


def locked_terms(terms: list[dict] = None, slug: str = "global-descent") -> list[dict]:
    """Return only locked (lock == 'locked') terms."""
    terms = terms or load_terms(slug)
    return [t for t in terms if t.get("lock") == "locked"]
def save_terms(terms: list[dict], slug: str = "global-descent") -> None:
    """Save terms list back to glossary.yml."""
    yml_path = get_glossary_yml_path(slug)
    yml_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_terms = []
    for t in terms:
        cleaned_term = {
            "source": t.get("source", "").strip(),
            "thai": t.get("thai", "").strip(),
            "category": t.get("category", "").strip(),
            "priority": int(t.get("priority", 3)),
            "lock": t.get("lock", "auto").strip(),
            "explanation": t.get("explanation", "").strip(),
            "notes": t.get("notes", "").strip(),
        }
        if cleaned_term["source"] and cleaned_term["thai"]:
            cleaned_terms.append(cleaned_term)

    data = {"terms": cleaned_terms}
    with open(yml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    # Clear the LRU cache
    load_terms.cache_clear()


def save_style_rules(rules: dict[str, list[dict]], slug: str = "global-descent") -> None:
    """Save style rules back to style_rules.yml."""
    yml_path = get_style_yml_path(slug)
    cleaned_rules = {}
    for key, items in rules.items():
        if isinstance(items, list):
            cleaned_items = []
            for item in items:
                if isinstance(item, dict) and "text" in item:
                    cleaned_items.append({"text": item["text"].strip()})
                elif isinstance(item, str):
                    cleaned_items.append({"text": item.strip()})
            cleaned_rules[key] = cleaned_items

    with open(yml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cleaned_rules, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    # Clear the LRU cache
    load_style_rules.cache_clear()


def main():
    import argparse
    import json
    import sys

    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Glossary YAML read/write CLI")
    ap.add_argument("--novel", type=str, default="global-descent", help="Novel slug")
    ap.add_argument("--sync", action="store_true", help="Regenerate style_rules.yml from format_spec.json")
    ap.add_argument("--load", action="store_true", help="Load glossary and style rules as JSON")
    ap.add_argument("--save", action="store_true", help="Save glossary and style rules from JSON stdin")
    args = ap.parse_args()

    if args.sync:
        rules = generate_style_rules_from_spec(args.novel)
        save_style_rules(rules, args.novel)
        print(f"Synced style_rules.yml from format_spec.json ({len(rules)} sections)")
        return

    if args.load:
        terms = load_terms(args.novel)
        rules = load_style_rules(args.novel)
        print(json.dumps({"terms": terms, "rules": rules}, ensure_ascii=False))
        sys.exit(0)

    elif args.save:
        try:
            payload = json.load(sys.stdin)
            if "terms" in payload:
                save_terms(payload["terms"], args.novel)
            if "rules" in payload:
                save_style_rules(payload["rules"], args.novel)
            print(json.dumps({"success": True}))
            sys.exit(0)
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}), file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
