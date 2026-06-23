"""glossary.py — Glossary and style rule loader.

Loads glossary.json + style_rules.json directly.
No yaml dependency — pure Python json stdlib.
"""

from functools import lru_cache
from pathlib import Path

import json

from schema import PROJECT_ROOT, NOVELS_DIR, get_novel_root


def get_glossary_json_path(slug: str = "global-descent") -> Path:
    return get_novel_root(slug, check_exists=False) / "glossary" / "glossary.json"


def get_style_json_path(slug: str = "global-descent") -> Path:
    return get_novel_root(slug, check_exists=False) / "style_rules.json"


@lru_cache(maxsize=16)
def load_terms(slug: str = "global-descent") -> list[dict]:
    """Load all terms from glossary.json."""
    json_path = get_glossary_json_path(slug)
    if not json_path.exists():
        return []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8")) or {}
        terms = data.get("terms", [])
        for t in terms:
            try:
                t["priority"] = int(t.get("priority", 3))
            except (ValueError, TypeError):
                t["priority"] = 3
        return terms
    except Exception as e:
        print(f"  Failed to load glossary JSON for {slug}: {e}")
        return []


@lru_cache(maxsize=16)
def load_style_rules(slug: str = "global-descent") -> dict[str, list[dict]]:
    """Load style rules grouped by section."""
    json_path = get_style_json_path(slug)
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"  Failed to load style rules JSON for {slug}: {e}")
        return {}


def save_terms(terms: list[dict], slug: str = "global-descent") -> None:
    """Save terms list back to glossary.json."""
    json_path = get_glossary_json_path(slug)
    json_path.parent.mkdir(parents=True, exist_ok=True)

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
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    load_terms.cache_clear()


def save_style_rules(rules: dict[str, list[dict]], slug: str = "global-descent") -> None:
    """Save style rules back to style_rules.json."""
    json_path = get_style_json_path(slug)
    json_path.parent.mkdir(parents=True, exist_ok=True)
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
    json_path.write_text(
        json.dumps(cleaned_rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── CLI Entry Point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovelClaw Glossary Tool")
    parser.add_argument("--novel", default="global-descent", help="Novel slug")
    parser.add_argument("--load", action="store_true", help="Load and print glossary JSON")
    parser.add_argument("--save", nargs="?", const="-", help="Save glossary from stdin JSON")
    args = parser.parse_args()

    if args.load:
        terms = load_terms(args.novel)
        print(json.dumps({"terms": terms}, ensure_ascii=False))
    elif args.save:
        import sys
        raw = sys.stdin.read() if args.save == "-" else open(args.save, encoding="utf-8").read()
        data = json.loads(raw)
        save_terms(data if isinstance(data, list) else data.get("terms", []), args.novel)
        print(json.dumps({"ok": True, "count": len(data if isinstance(data, list) else data.get("terms", []))}))
    else:
        parser.print_help()
