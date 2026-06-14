"""translate.py — Translate CN source ch to TH JSON (end-to-end pipeline).

This is the new way to translate. One command per ch, fully automatic.

Pipeline:
  1. Read source/XXXX.md (cleaned CN)
  2. Inject context: format spec + style + locked glossary + previous ch summary
  3. Call LLM (or use cached/manual translation)
  4. Parse LLM output → JSON blocks
  5. Validate via Pydantic schema
  6. Save chapters/NNNN.json

Usage:
  python tools/translate.py 113                    # translate ch 113
  python tools/translate.py 113-150                # batch translate range
  python tools/translate.py 113 --from-md source/0113.md  # use specific source
  python tools/translate.py 113 --mock             # don't call LLM, use placeholder
  python tools/translate.py 113 --no-validate      # skip schema validation

The LLM integration point is `_call_llm()`. For now, the mock returns
a placeholder; the real integration uses hermes CLI or direct API.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT, CHAPTERS_DIR, GLOSSARY_DIR  # noqa: E402
from schema import Chapter, save_chapter, Narration, Dialogue, SystemMessage, GameTitle, EndMarker  # noqa: E402

SOURCE_DIR = NOVEL_ROOT / 'chapters' / 'source'


def clean_source(raw: str) -> str:
    """Strip line numbers, reader comments, duplicate title (same as pre_chapter)."""
    parts = raw.split('\n---\n')
    body = parts[0]
    lines = body.split('\n')
    out = []
    in_body = False
    for line in lines[1:]:  # skip H1
        stripped = line.strip()
        if not in_body:
            if stripped == '' or '全球降臨' in stripped:
                continue
            if re.match(r'^第[一二三四五六七八九十百千零\d]+章', stripped):
                continue
            in_body = True
        out.append(line)
    text = '\n'.join(out)
    text = re.sub(
        r'([！？。，；：…—]+)\s*(\d{1,3})(?=\s|$)',
        r'\1',
        text,
    )
    text = re.sub(
        r'^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$',
        '',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def load_glossary_context() -> str:
    """Load locked glossary terms for prompt injection."""
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


def build_prompt(ch_num: int, source_text: str) -> str:
    """Build the LLM prompt for translating one chapter."""
    glossary = load_glossary_context()
    style = load_style_context()
    return f"""You are a Thai translator for a Chinese web novel (全球降臨：帶著嫂嫂末世種田).

# Style Guide (applies to all ch)
{style}

# Locked Glossary (use these Thai translations exactly — do NOT change)
{glossary}

# Chapter {ch_num} source (Chinese):
```
{source_text}
```

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
  "schema_version": 1,
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


def _call_llm(prompt: str, model: str = 'haiku') -> str:
    """Call the LLM. Returns the raw text response.

    For now, this is a MOCK that returns placeholder JSON. Replace with
    real implementation:
      - via hermes CLI subprocess, or
      - via direct API call (anthropic, openai, etc.)
    """
    # Real implementation: subprocess.run(['hermes', 'chat', '--model', model], input=prompt)
    # For now, return mock
    return '{"mock": "no LLM configured — pass --mock to skip LLM call"}'


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
    # Use a placeholder title that passes schema (must have something after "ตอนที่ N")
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


def translate_one(ch_num: int, mock: bool = False, no_validate: bool = False) -> bool:
    """Translate one ch. Returns True on success."""
    src_path = SOURCE_DIR / f'{ch_num:04d}.md'
    out_path = CHAPTERS_DIR / f'{ch_num:04d}.json'
    if not src_path.exists():
        print(f'❌ ch{ch_num}: source not found at {src_path}')
        return False
    if out_path.exists():
        print(f'⚠ ch{ch_num}: output exists, skipping (delete to overwrite)')
        return False
    raw_src = src_path.read_text(encoding='utf-8')
    source = clean_source(raw_src)
    if not source:
        print(f'❌ ch{ch_num}: source is empty after cleaning')
        return False
    print(f'→ ch{ch_num}: source = {len(source)} chars')
    if mock:
        ch_data = mock_translate(ch_num, source)
    else:
        prompt = build_prompt(ch_num, source)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapters', help='Single (113) or range (113-150)')
    ap.add_argument('--mock', action='store_true', help='Use mock translation (no LLM call)')
    ap.add_argument('--no-validate', action='store_true', help='Skip schema validation')
    args = ap.parse_args()

    if '-' in args.chapters:
        a, b = map(int, args.chapters.split('-'))
        ch_nums = list(range(a, b + 1))
    else:
        ch_nums = [int(args.chapters)]

    success = 0
    failed = 0
    for ch in ch_nums:
        if translate_one(ch, mock=args.mock, no_validate=args.no_validate):
            success += 1
        else:
            failed += 1
    print(f'\n{"=" * 50}')
    print(f'Total: {success} translated, {failed} failed out of {len(ch_nums)}')


if __name__ == '__main__':
    main()
