"""translate.py — Translate CN source chapters to TH JSON (end-to-end pipeline).

This is the unified translation tool combining the best of translate.py and translate_ch.py.

Pipeline:
  1. Read source/XXXX.md (cleaned CN)
  2. Auto-extract unknown CN terms (not in glossary)
  3. Build context: format spec + style + locked glossary + unknown terms
  4. Call LLM (or use mock translation)
  5. Parse LLM output → JSON blocks
  6. Validate via Pydantic schema
  7. Save chapters/NNNN.json

Usage:
  python tools/translate.py 113                    # translate ch 113
  python tools/translate.py 113-150                # batch translate range
  python tools/translate.py 113 --mock             # don't call LLM, use placeholder
  python tools/translate.py 113 --no-validate      # skip schema validation
  python tools/translate.py 113 --dry-run          # show context only, no save
  python tools/translate.py 113 --search "招募"     # search Thai for a term
  python tools/translate.py 113 --context          # print full context for ch

The LLM integration point is `_call_llm()`. The mock returns a placeholder;
the real integration uses hermes CLI or direct API.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))
from constants import NOVEL_ROOT, CHAPTERS_DIR, GLOSSARY_DIR, get_novel_root  # noqa: E402
from schema import Chapter, Narration, Dialogue, SystemMessage, GameTitle, EndMarker  # noqa: E402
from chapter_io import save_chapter
from providers import get_provider  # noqa: E402
from load_glossary import load_terms, load_style_rules  # noqa: E402

# ── Inline helpers (from translate_ch_helpers.py, deleted in ponytail merge) ──
import re as _re
from typing import Iterable as _Iterable

def clean_source(raw: str) -> str:
    """Strip line numbers, reader comments, duplicate title."""
    parts = raw.split('\n---\n')
    body = parts[0]
    lines = body.split('\n')
    out = []
    in_body = False
    for line in lines[1:]:
        stripped = line.strip()
        if not in_body:
            if stripped == '' or '全球降臨' in stripped:
                continue
            if _re.match(r'^第[一二三四五六七八九十百千零\d]+章', stripped):
                continue
            in_body = True
        out.append(line)
    text = '\n'.join(out)
    text = _re.sub(r'([！？。，；：…—]+)\s*(\d{1,3})(?=\s|$)', r'\1', text)
    text = _re.sub(r'^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_unknown_terms(source_text: str, known_sources: _Iterable[str]) -> list[str]:
    """Extract CN terms from source that aren't in glossary."""
    known = set(known_sources)
    UI_NOISE = {
        '首頁', '科幻小說', '玄幻小說', '都市言情', '歷史軍事', '遊戲競技',
        '加入書籤', '小說報錯', '投票推薦', '字體', '上一章', '下一章', '目錄',
        '關燈', '開燈', '下載', '客戶端', '手機看書', '繁體', '簡體',
        '上一頁', '下一頁', '返回', '確定', '取消', '提交', '下載本章',
        '請先', '登錄', '註冊', '忘記密碼', '會員中心', '我的書架',
        '正在加載', '加載中', '請稍候', '暫無', '評論', '書友',
        '全球降臨', '帶著嫂嫂', '末世種田', '第', '章', '回', '節', '頁', '卷',
    }
    known |= UI_NOISE
    cleaned = _re.sub(r'【[^】]*】', '', source_text)
    cleaned = _re.sub(r'《[^》]*》', '', cleaned)
    cleaned = _re.sub(r'「[^」]*」', '', cleaned)
    cn_terms = _re.findall(r'[\u4e00-\u9fff]{2,}', cleaned)
    seen = set()
    unknown = []
    for term in cn_terms:
        if term not in known and term not in seen:
            seen.add(term)
            unknown.append(term)
    return unknown

SOURCE_DIR = NOVEL_ROOT / 'chapters' / 'source'


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
- Dialogue: convert to 「」, never use straight "
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


def load_glossary_context() -> str:
    """Load locked glossary terms for prompt injection (SQLite fallback)."""
    db = GLOSSARY_DIR / 'glossary.db'
    if not db.exists():
        return ''
    import sqlite3
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('''SELECT source_cn, thai, category, explanation
                   FROM terms
                   WHERE priority <= 2 AND status = "active"
                   ORDER BY priority, source_cn''')
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return ''
    lines = ['## Locked Glossary (MUST USE EXACT THAI):']
    for src, thai, cat, expl in rows:
        line = f'- {src} → {thai}'
        if expl:
            line += f'  ({expl[:80]})'
        lines.append(line)
    return '\n'.join(lines)


def load_style_context() -> str:
    """Load style guide for prompt injection."""
    style_path = NOVEL_ROOT / 'style.md'
    if not style_path.exists():
        return ''
    return style_path.read_text(encoding='utf-8')[:3000]  # truncate to fit


def get_glossary_context_from_lib(ch_num: int) -> str:
    """Get glossary terms that appear in this chapter (filtered for relevance).

    Uses the load_glossary library for richer term data.
    """
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


def web_search_term(cn_term: str) -> str:
    """No-op: web search is not available as a Python module.

    Mika should use the cheatsheet in TRANSLATION_GUIDE.md or
    the chat web_search tool directly.
    """
    return "(use web_search tool or check TRANSLATION_GUIDE.md cheatsheet)"


def get_unknown_terms_for_ch(ch_num: int) -> list[str]:
    """Extract unknown CN terms from a chapter's source text."""
    src_path = SOURCE_DIR / f'{ch_num:04d}.md'
    if not src_path.exists():
        return []
    source = clean_source(src_path.read_text(encoding='utf-8'))
    terms = load_terms()
    known = {t['source'] for t in terms}
    return extract_unknown_terms(source, known)


def build_prompt(ch_num: int, source_text: str, unknown_terms: list[str] | None = None) -> str:
    """Build the LLM prompt for translating one chapter.

    Combines glossary (SQLite + lib), style, format spec, and unknown terms.
    """
    glossary_sqlite = load_glossary_context()
    glossary_lib = get_glossary_context_from_lib(ch_num)
    style = load_style_summary()

    # Merge glossary sections (deduplicate by using both)
    glossary_sections = []
    if glossary_sqlite:
        glossary_sections.append(glossary_sqlite)
    if glossary_lib:
        glossary_sections.append(glossary_lib)
    glossary = '\n\n'.join(glossary_sections) if glossary_sections else '(no glossary loaded)'

    # Unknown terms section
    unknown_section = ''
    if unknown_terms:
        unknown_lines = ['## Unknown CN terms — need Thai equivalent:']
        for term in unknown_terms[:15]:
            web = web_search_term(term)
            unknown_lines.append(f'- {term}: {web}')
        unknown_section = '\n'.join(unknown_lines)

    return f"""You are a Thai translator for a Chinese web novel (全球降臨：帶著嫂嫂末世種田).

# Style Guide (applies to all chapters)
{style}

# Locked Glossary (use these Thai translations exactly — do NOT change)
{glossary}

# Format Spec
{get_format_summary()}

# Chapter {ch_num} source (Chinese):
```
{source_text}
```

# Unknown terms in this chapter
{unknown_section if unknown_section else '(none — all terms are in glossary)'}

# Your task
Translate the above Chinese chapter to Thai. Follow these RULES strictly:

1. **Output format**: structured JSON (see schema below). NO prose, NO markdown.
2. **Brackets** (mandatory — schema rejects otherwise):
   - Dialogue: 「...」 (full-width)
   - System messages: 【...】 (full-width)
   - Game titles: 《...》 (full-width)
3. **Translator transmittor principle**: TRANSMIT the source faithfully. Do NOT add,
   remove, or "improve" content. Keep the author's voice (ดังนั้น, ฉายแวว, etc.).
4. **Locked glossary**: use the exact Thai from the glossary above. Never use
   alternative Thai for locked terms.
5. **End marker**: include exactly one {{"type": "end", "text": "(จบบท)"}} block as the LAST block.
6. **CN leakage forbidden**: narration text must NOT contain raw CN chars (except
   inside 【】 system messages, which are translated as-is).
7. **Title**: "ตอนที่ {ch_num} <thai_title>" — derive from the first line of source.

# JSON schema (must match exactly):
```json
{{
  "schema_version": 2,
  "num": {ch_num},
  "title": "ตอนที่ {ch_num} <thai_title>",
  "blocks": [
    {{"type": "narration", "text": "..."}},
    {{"type": "dialogue", "text": "「...」"}},
    {{"type": "system", "text": "【...】"}},
    {{"type": "end", "text": "(จบบท)"}}
  ],
  "source": "ch {ch_num}",
  "notes": ["<optional translation notes>"]
}}
```

Output ONLY the JSON. No prose, no markdown fences.
"""


def get_chapter_context(ch_num: int, search_unknown: bool = True) -> str:
    """Build full context block for translating one chapter.

    Returns formatted string with:
    - Title
    - Source (cleaned)
    - Glossary terms in source
    - Style rules
    - Format spec
    - Unknown terms (if search_unknown)
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
        f"\n{get_glossary_context_from_lib(ch_num)}",
        f"\n{get_style_summary()}",
        f"\n{get_format_summary()}",
    ]

    # Unknown terms
    unknown = get_unknown_terms_for_ch(ch_num)
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


def _call_llm(prompt: str, model: str = "haiku") -> str:
    """Call the LLM via provider abstraction.

    Uses the provider system (haiku / gemini / claude).
    Falls back to mock output if provider is unavailable.
    """
    try:
        provider = get_provider(model)
        return provider.translate(prompt)
    except Exception as e:
        print(f"⚠ LLM error ({model}): {e}")
        print("⏭ Falling back to mock output...")
        return '{"mock": "no LLM configured"}'


def mock_translate(ch_num: int, source_text: str) -> dict:
    """Mock translation that creates a stub JSON chapter.

    Used when --mock is passed or when LLM is not configured.
    Produces a valid schema but with placeholder translation.
    """
    # Try to extract title from source
    title_match = re.match(r'# (.+)', source_text)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = f'ตอนที่ {ch_num}'

    # Convert title to Thai if it has Chinese
    if re.search(r'[\u4e00-\u9fff]', title):
        # Strip CN from title for now — real LLM would translate
        title = f'ตอนที่ {ch_num} [mock — needs real translation]'

    # Mock: one block saying "this is a mock"
    # Use a placeholder title that passes schema (must have something after "ตอนที่ N)")
    if not title or title == f'ตอนที่ {ch_num}':
        title = f'ตอนที่ {ch_num} [mock — needs real translation]'
    return {
        'schema_version': 1,
        'num': ch_num,
        'title': title,
        'blocks': [
            {'type': 'narration', 'text': f'[MOCK] ch {ch_num} translation — replace with real LLM call'},
            {'type': 'end', 'text': '(จบบท)'},
        ],
        'source': f'ch {ch_num}',
        'notes': ['[MOCK] generated by translate.py --mock, not real translation'],
    }


def parse_llm_output(output: str, ch_num: int) -> dict:
    """Parse LLM output (which may include prose) to extract JSON.

    LLM may output ```json ... ``` or just raw JSON or with prose around it.
    """
    # Strip markdown fences if present
    output = re.sub(r'^```(?:json)?\s*\n?', '', output.strip())
    output = re.sub(r'\n?```\s*$', '', output)
    # Find first { and last }
    start = output.find('{')
    end = output.rfind('}')
    if start == -1 or end == -1:
        raise ValueError(f'No JSON braces found in LLM output:\n{output[:200]}')
    json_str = output[start:end + 1]
    return json.loads(json_str)


def translate_one(
    ch_num: int,
    mock: bool = False,
    no_validate: bool = False,
    dry_run: bool = False,
    search: bool = False,
) -> bool:
    """Translate one chapter. Returns True on success.

    Args:
        ch_num: chapter number
        mock: use mock translation (no LLM call)
        no_validate: skip schema validation
        dry_run: show context only, don't translate or save
        search: include unknown term search in context
    """
    src_path = SOURCE_DIR / f'{ch_num:04d}.md'
    out_path = CHAPTERS_DIR / f'{ch_num:04d}.json'

    if not src_path.exists():
        print(f'❌ ch{ch_num}: source not found at {src_path}')
        return False

    if dry_run:
        print(get_chapter_context(ch_num, search_unknown=search))
        return True

    if out_path.exists():
        print(f'⚠ ch{ch_num}: output exists, skipping (delete to overwrite)')
        return False

    raw_src = src_path.read_text(encoding='utf-8')
    source = clean_source(raw_src)
    if not source:
        print(f'❌ ch{ch_num}: source is empty after cleaning')
        return False

    print(f'→ ch{ch_num}: source = {len(source)} chars')

    # Extract unknown terms for context
    unknown_terms = get_unknown_terms_for_ch(ch_num) if search else None
    if unknown_terms:
        print(f'  → {len(unknown_terms)} unknown terms detected')

    if mock:
        ch_data = mock_translate(ch_num, source)
    else:
        prompt = build_prompt(ch_num, source, unknown_terms=unknown_terms)
        output = _call_llm(prompt)
        try:
            ch_data = parse_llm_output(output, ch_num)
        except (json.JSONDecodeError, ValueError) as e:
            print(f'❌ ch{ch_num}: parse failed: {e}')
            return False

    # Validate via Pydantic schema
    if not no_validate:
        try:
            ch = Chapter(**ch_data)
        except Exception as e:
            print(f'❌ ch{ch_num}: schema validation failed: {str(e)[:200]}')
            return False
    else:
        ch = Chapter.construct(**ch_data)  # skip validation

    save_chapter(ch, out_path)
    n = len(ch.blocks)
    print(f'✓ ch{ch_num}: saved → {out_path.name} ({n} blocks)')
    return True


def search_term(term: str) -> None:
    """Search for a Thai equivalent of a CN term.

    Prints the term and guidance for finding its Thai translation.
    """
    # Check if term is in glossary
    terms = load_terms()
    matches = [t for t in terms if term in t['source']]
    if matches:
        print(f'✓ Found {len(matches)} glossary entries for "{term}":')
        for t in matches:
            expl = t.get('explanation') or t.get('notes') or ''
            print(f'  `{t["source"]}` → {t["thai"]}' + (f' — {expl[:80]}' if expl else ''))
    else:
        print(f'✗ "{term}" not found in glossary.')
        web = web_search_term(term)
        print(f'  {web}')


def main():
    ap = argparse.ArgumentParser(
        description='Translate CN source chapters to TH JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python tools/translate.py 113                    # translate ch 113
  python tools/translate.py 113-150                # batch translate range
  python tools/translate.py 113 --mock             # mock translation (no LLM)
  python tools/translate.py 113 --dry-run          # show context only
  python tools/translate.py 113 --search "招募"     # search Thai for term
  python tools/translate.py 113 --context          # print full context
  python tools/translate.py 113 --no-validate      # skip schema validation
        """,
    )
    ap.add_argument('chapters', help='Single (113) or range (113-150)')
    ap.add_argument('--mock', action='store_true', help='Use mock translation (no LLM call)')
    ap.add_argument('--no-validate', action='store_true', help='Skip schema validation')
    ap.add_argument('--dry-run', action='store_true', help='Show context only, no save')
    ap.add_argument('--context', action='store_true', help='Print full context for first ch')
    ap.add_argument('--search', type=str, metavar='TERM', help='Search Thai for a CN term')
    ap.add_argument('--search-unknown', action='store_true', help='Extract & search unknown terms during translation')
    args = ap.parse_args()

    # Term search mode
    if args.search:
        search_term(args.search)
        return

    # Parse chapter range
    if '-' in args.chapters:
        a, b = map(int, args.chapters.split('-'))
        ch_nums = list(range(a, b + 1))
    else:
        ch_nums = [int(args.chapters)]

    # Dry-run / context mode
    if args.dry_run or args.context:
        for ch in ch_nums:
            print(f'\n{"="*70}')
            print(get_chapter_context(ch, search_unknown=args.search_unknown))
            print(f'\n{"="*70}\n')
        return

    # Translation mode
    success = 0
    failed = 0
    for ch in ch_nums:
        if translate_one(
            ch,
            mock=args.mock,
            no_validate=args.no_validate,
            search=args.search_unknown,
        ):
            success += 1
        else:
            failed += 1
    print(f'\n{"=" * 50}')
    print(f'Total: {success} translated, {failed} failed out of {len(ch_nums)}')


if __name__ == '__main__':
    main()
