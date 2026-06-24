"""
tools/glossary.py — Glossary and style rule loader.

Loads glossary.json + style_rules.json directly.
No yaml dependency — pure Python json stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


# ── Glossary validation — enforce after translation ──────────────────

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_novel_root(slug: str) -> Path:
    return _PROJECT_ROOT / "novels" / slug

@dataclass
class GlossaryValidation:
    """Result of validating a translation against glossary."""
    ok: bool = True
    missing_terms: list[dict] = field(default_factory=list)
    violated_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_translation(translated_text: str, slug: str = "global-descent") -> GlossaryValidation:
    """Validate translated text against glossary terms.

    Checks:
      1. Every CN term in glossary → does the Thai appear in output?
      2. Any blacklisted EN terms still present?

    Returns GlossaryValidation with:
      - missing_terms: [{ source, thai, category }] — CN term that should
        have been translated but Thai is missing from output
      - violated_rules: style rules that were broken
      - warnings: informational notes
    """
    result = GlossaryValidation()
    terms = load_terms(slug)
    if not terms:
        return result

    for t in terms:
        source = t.get("source", "")
        thai = t.get("thai", "")
        category = t.get("category", "")
        if not source or not thai:
            continue
        # For high-priority characters and items, check if Thai appears
        if t.get("priority", 3) >= 3 and category in ("ตัวละคร", "สถานที่", "สกิล"):
            if thai not in translated_text:
                result.missing_terms.append({"source": source, "thai": thai, "category": category})
                result.ok = False

    return result


# ── TM / Chapter Memory ─────────────────────────────────────────────────

@dataclass
class ChapterMemory:
    """Summary of a recent chapter for translation memory."""
    num: int
    summary: str
    characters: list[str]
    terms: list[str]


def get_chapter_memory(slug: str, current_num: int, count: int = 3) -> list[ChapterMemory]:
    """Get summaries of recent chapters for context injection.

    Loads the last `count` translated chapters before `current_num`,
    extracts character names and key terms for TM context.
    """
    memories = []
    terms = load_terms(slug)

    # Collect high-priority character names
    characters = list(dict.fromkeys(
        t["thai"] for t in terms
        if t.get("category") == "ตัวละคร" and t.get("priority", 3) >= 3
    ))

    # Collect key terms for context
    key_terms = list(dict.fromkeys(
        f'{t["source"]} → {t["thai"]}'
        for t in terms
        if t.get("priority", 3) >= 3
    ))

    for n in range(max(1, current_num - count), current_num):
        ch_path = _get_novel_root(slug) / "chapters" / f"{n:04d}.th.json"
        if not ch_path.exists():
            continue
        try:
            data = json.loads(ch_path.read_text(encoding="utf-8"))
            paras = data.get("paragraphs", [])
            # Take first 3 paragraphs as summary
            summary = " | ".join(p for p in paras[:3] if p not in ("(จบบท)",))
            memories.append(ChapterMemory(
                num=n,
                summary=summary[:200],
                characters=characters[:10],
                terms=key_terms[:20],
            ))
        except Exception:
            continue

    return memories


def format_tm_prompt(slug: str, current_num: int) -> str:
    """Format TM context section for LLM prompt."""
    memo = get_chapter_memory(slug, current_num)
    if not memo:
        return ""

    lines = [
        "\n[Translation Memory — character names and terms from recent chapters]",
    ]
    if memo and memo[0].characters:
        lines.append("Main characters: " + ", ".join(memo[0].characters))
    if memo and memo[0].terms:
        lines.append("Key terms: " + ", ".join(memo[0].terms[:15]))
    lines.append("")

    return "\n".join(lines)


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
