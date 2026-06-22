"""glossary.py — Single source of truth glossary and style rule loader.

Loads glossary.yml + style_rules.yml directly from the filesystem,
completely replacing the legacy SQLite glossary.db database.
"""
from functools import lru_cache
from pathlib import Path

import yaml
import json

from schema import PROJECT_ROOT, NOVELS_DIR, get_novel_root


def get_glossary_yml_path(slug: str = "global-descent") -> Path:
    return get_novel_root(slug, check_exists=False) / "glossary" / "glossary.yml"


def get_style_yml_path(slug: str = "global-descent") -> Path:
    return get_novel_root(slug, check_exists=False) / "style_rules.yml"


@lru_cache(maxsize=16)
def load_terms(slug: str = "global-descent") -> list[dict]:
    """Load all terms from glossary.yml."""
    yml_path = get_glossary_yml_path(slug)
    if not yml_path.exists():
        return []
    try:
        data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
        terms = data.get("terms", [])
        for t in terms:
            try:
                t["priority"] = int(t.get("priority", 3))
            except (ValueError, TypeError):
                t["priority"] = 3
        return terms
    except Exception as e:
        print(f"  Failed to load glossary YAML for {slug}: {e}")
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
        print(f"  Failed to load style rules YAML for {slug}: {e}")
        return {}


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
    yml_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    load_terms.cache_clear()


def save_style_rules(rules: dict[str, list[dict]], slug: str = "global-descent") -> None:
    """Save style rules back to style_rules.yml."""
    yml_path = get_style_yml_path(slug)
    yml_path.parent.mkdir(parents=True, exist_ok=True)
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
    yml_path.write_text(
        yaml.safe_dump(cleaned_rules, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    load_style_rules.cache_clear()


def main():
    import argparse
    import sys

    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Glossary YAML read/write CLI")
    ap.add_argument("--novel", type=str, default="global-descent", help="Novel slug")
    ap.add_argument("--load", action="store_true", help="Load glossary and style rules as JSON")
    ap.add_argument("--save", action="store_true", help="Save glossary and style rules from JSON stdin")
    args = ap.parse_args()

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
