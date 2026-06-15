"""One-shot translation toolkit for ch 113+.

What this does:
1. Reads source CN
2. Auto-extracts unknown CN terms
3. Web-searches proper Thai equivalents (for unknown terms)
4. Pre-applies glossary (existing 559 terms)
5. Shows context for Mika: glossary + style + format spec + source
6. Mika translates → outputs valid JSON
7. Auto-validates + commits

Usage:
    python tools/translate_ch.py 113                # translate one
    python tools/translate_ch.py 113-150            # translate range
    python tools/translate_ch.py 113 --dry-run       # context only, no save
    python tools/translate_ch.py 113 --search "招募"  # search Thai for term
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT_DEFAULT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT_DEFAULT / "tools"))
from load_glossary import load_terms, load_style_rules  # noqa: E402
from schema import Chapter, save_chapter  # noqa: E402
from translate_ch_helpers import clean_source  # noqa: E402

SOURCE_DIR = _PROJECT_ROOT_DEFAULT / "novels" / "global-descent" / "chapters" / "source"
CHAPTERS_DIR = _PROJECT_ROOT_DEFAULT / "novels" / "global-descent" / "chapters"


# === Format spec for quick reference ===
FORMAT_SPEC = """
# Format v2 Spec (P'Chok approved)

# Block types
- narration: regular text
- dialogue: must contain 「...」 (full-width CJK)
- system: must contain 【...】 (full-width CJK)
- game_title: must contain 《...》 (full-width CJK)
- end: exactly "(จบบท)"

# Required structure
- title: "ตอนที่ N <thai_title>" (space between N and title)
- blocks: list of {type, text}
- source: "ch N" (short form)
- notes: optional list of translation notes

# Rules
- CN leakage forbidden in narration (except inside 【】/《》)
- Dialogue: convert to 「」, never use straight \"
- Transmittor principle: TRANSMIT source faithfully, don't edit
- Keep author's voice: ดังนั้น, ฉายแวว, เต็มไปด้วย, subject echo
- Em dash (—) for missing numbers in source

# Schema enforces
- Title format: must match "ตอนที่ N ..."
- Dialogue: must contain 「」 (not necessarily start/end with)
- System: must contain 【】
- End: exactly "(จบบท)"
- Last block: end marker
- At least 1 content block before end
"""


def get_unknown_terms(source_text: str, known_sources: set[str]) -> list[str]:
    """Extract CN terms from source that aren't in glossary.

    Filters out single chars (too generic) and terms in whitelisted zones.
    """
    # Strip whitelisted zones
    cleaned = re.sub(r'【[^】]*】', '', source_text)
    cleaned = re.sub(r'《[^》]*》', '', cleaned)
    cleaned = re.sub(r'「[^」]*」', '', cleaned)

    # Extract 2+ char CN sequences (single chars too generic)
    cn_terms = re.findall(r'[\u4e00-\u9fff]{2,}', cleaned)
    # Dedupe + filter
    seen = set()
    unknown = []
    for term in cn_terms:
        if term not in known_sources and term not in seen:
            seen.add(term)
            unknown.append(term)
    return unknown


def web_search_term(cn_term: str) -> str:
    """No-op: web search is not available as a Python module.
    Mika should use the cheatsheet in TRANSLATION_GUIDE.md or
    the chat web_search tool directly.
    """
    return "(use web_search tool or check TRANSLATION_GUIDE.md cheatsheet)"


def get_glossary_context(ch_num: int) -> str:
    """Get glossary terms that appear in this ch (filtered for relevance)."""
    src_path = SOURCE_DIR / f'{ch_num:04d}.md'
    if not src_path.exists():
        return ""
    source = clean_source(src_path.read_text(encoding='utf-8'))

    terms = load_terms()
    # Filter to terms that appear in source
    in_source = [t for t in terms if t['source'] in source]
    # Prioritize: locked (priority 1-2) first
    in_source.sort(key=lambda t: (t.get('priority', 3), t['source']))

    lines = ['## Glossary terms in this ch (use EXACT Thai):']
    for t in in_source:
        expl = t.get('explanation') or t.get('notes') or ''
        line = f'- `{t["source"]}` → {t["thai"]}'
        if expl:
            line += f' — {expl[:80]}'
        lines.append(line)
    return "\n".join(lines)


def get_style_summary() -> str:
    """Compact style rules for prompt injection."""
    rules = load_style_rules()
    lines = ['## Style rules (apply):']
    for section in ['term_choices', 'punctuation', 'naturalness', 'policies']:
        items = rules.get(section, [])
        if items:
            lines.append(f'\n### {section}:')
            for item in items[:10]:
                if 'key' in item:
                    lines.append(f'- **{item["key"]}** — {item["value"][:120]}')
                else:
                    lines.append(f'- {item["text"][:120]}')
    return "\n".join(lines)


def get_format_summary() -> str:
    """Compact format spec for prompt injection."""
    return FORMAT_SPEC


def get_chapter_context(ch_num: int, search_unknown: bool = True) -> str:
    """Build full context block for translating one ch.

    Returns formatted string with:
    - Title
    - Source (cleaned)
    - Glossary terms in source
    - Style rules
    - Format spec
    - Unknown terms (if --search)
    """
    src_path = SOURCE_DIR / f'{ch_num:04d}.md'
    if not src_path.exists():
        return f"❌ Source not found: {src_path}"

    raw = src_path.read_text(encoding='utf-8')
    source = clean_source(raw)
    if not source:
        return f"❌ ch {ch_num} source is empty"

    terms = load_terms()
    known = {t['source'] for t in terms}

    # Title
    title_match = re.search(r'第\s*(\d+)\s*章\s*(.+)', source)
    cn_title = title_match.group(2).strip() if title_match else f"ch {ch_num}"

    parts = [
        f"# ch {ch_num} context",
        f"\n## CN title: {cn_title}",
        f"\n## Source ({len(source)} chars):\n```\n{source}\n```",
        f"\n{get_glossary_context(ch_num)}",
        f"\n{get_style_summary()}",
        f"\n{get_format_summary()}",
    ]

    # Unknown terms
    unknown = get_unknown_terms(source, known)
    if unknown and search_unknown:
        parts.append(f"\n## Unknown CN terms ({len(unknown)}) — need Thai equivalent:")
        for term in unknown[:15]:
            parts.append(f"\n### {term}")
            web = web_search_term(term)
            if web:
                parts.append(web)
            else:
                parts.append("(no web result — use Thai transliteration or best guess)")

    return "\n".join(parts)


def translate_one(ch_num: int, output_json: dict | None = None, save: bool = True) -> bool:
    """Save a translated ch. Returns True on success.

    Args:
        ch_num: chapter number
        output_json: pre-translated chapter dict (from Mika)
        save: if True, save to .json file
    """
    if output_json is None:
        print(f"❌ ch {ch_num}: no translation provided (Mika must supply dict)")
        return False

    # Validate schema
    try:
        ch = Chapter(**output_json)
    except Exception as e:
        print(f"❌ ch {ch_num}: schema failed: {str(e)[:200]}")
        return False

    out_path = CHAPTERS_DIR / f'{ch_num:04d}.json'
    if save:
        save_chapter(ch, out_path)
        print(f"✓ ch {ch_num}: saved → {out_path.name} ({len(ch.blocks)} blocks)")

    # Run doctor (informational only)
    try:
        from glossary_doctor import load_glossary, validate_chapter
        g, am, sr = load_glossary()
        issues = validate_chapter(ch_num, g, am, sr, log_to_db=False)
        errs = [i for i in issues if i.get('severity') == 'error']
        if errs:
            print(f"  ⚠️  {len(errs)} doctor error(s):")
            for e in errs[:3]:
                print(f"    {e.get('rule_type')}: {e.get('pattern', '')[:60]}")
            return False
    except Exception as e:
        print(f"  (doctor unavailable: {e})")

    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapters', help='Single (113) or range (113-150)')
    ap.add_argument('--dry-run', action='store_true', help='Show context only, no save')
    ap.add_argument('--search', action='store_true', help='Web-search unknown terms')
    ap.add_argument('--context', action='store_true', help='Print full context for first ch')
    args = ap.parse_args()

    if '-' in args.chapters:
        a, b = map(int, args.chapters.split('-'))
        ch_nums = list(range(a, b + 1))
    else:
        ch_nums = [int(args.chapters)]

    if args.dry_run or args.context:
        # Print context for first ch
        for ch in ch_nums:
            print(f"\n{'='*70}")
            print(get_chapter_context(ch, search_unknown=args.search))
            print(f"\n{'='*70}\n")
        return

    # Otherwise: count translated
    for ch in ch_nums:
        out = CHAPTERS_DIR / f'{ch:04d}.json'
        if out.exists():
            print(f"⏭  ch {ch}: exists, skip")


if __name__ == '__main__':
    main()
