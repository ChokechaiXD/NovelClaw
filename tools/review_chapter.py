"""review_chapter.py — Generate Tier-2 review checklist for a chapter.

After Mika's translation passes Tier-1 validators, this tool generates a
review template using the MQM (Multidimensional Quality Metrics) framework:
  - Accuracy (numbers, names, plots)
  - Fluency (Thai reads natural)
  - Terminology (glossary consistency)
  - Style (matches last 1-2 chapters)
  - Locale convention (date/measurements)

Mika fills in the checklist manually. Output goes to novels/<slug>/reviews/NNNN.md

Usage:
  python review_chapter.py 81              # generate review for ch 81
  python review_chapter.py 81 --checklist   # just print the checklist
  python review_chapter.py 81 --context    # include source + last 2 ch summaries
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
NOVEL = 'global-descent'
NOVEL_DIR = ROOT / 'novels' / NOVEL
CHAPTERS = NOVEL_DIR / 'chapters'
REVIEWS = NOVEL_DIR / 'reviews'
SOURCE = CHAPTERS / 'source'
GLOSSARY_DIR = NOVEL_DIR / 'glossary'


def extract_h1_title(content: str) -> str:
    m = re.search(r'^#\s+(.+?)$', content, re.M)
    return m.group(1).strip() if m else ''


def extract_previous_chapters(num: int, count: int = 2) -> list[tuple[int, str]]:
    """Return [(num, title)] for the previous `count` translated chapters."""
    prevs = []
    for offset in range(count, 0, -1):
        target = num - offset
        path = CHAPTERS / f'{target:04d}.md'
        if path.exists():
            prevs.append((target, extract_h1_title(path.read_text(encoding='utf-8'))))
    return prevs


def extract_body(text: str) -> str:
    parts = text.split('\n---\n')
    return parts[0] if parts else text


def generate_template(num: int, with_context: bool = False) -> str:
    padded = f'{num:04d}'
    tr_path = CHAPTERS / f'{padded}.md'
    src_path = SOURCE / f'{padded}.md'

    if not tr_path.exists():
        sys.exit(f'Error: translated chapter not found: {tr_path}')

    tr_content = tr_path.read_text(encoding='utf-8')
    title = extract_h1_title(tr_content)
    body = extract_body(tr_content)
    body_len = len(body)
    word_count = len(body.split())

    # Length ratio
    ratio_str = 'N/A (no source)'
    if src_path.exists():
        src_content = src_path.read_text(encoding='utf-8')
        src_len = len(extract_body(src_content))
        if src_len:
            ratio_str = f'{body_len / src_len:.2f}x (TH/CN chars)'

    # Previous chapters for tone reference
    prevs = extract_previous_chapters(num)

    today = date.today().isoformat()

    lines = [
        f'# Review: ตอนที่ {num} — {title}',
        '',
        f'**Auto-generated:** {today}  ',
        f'**Translation length:** {body_len:,} chars / ~{word_count:,} words  ',
        f'**Source length ratio:** {ratio_str}  ',
        f'**Source file:** `chapters/source/{padded}.md`  ',
        f'**Translation file:** `chapters/{padded}.md`',
        '',
        '## 1. Pre-flight: Tier-1 validators (must all pass)',
        '',
        '- [ ] `python novelclaw.py validate --cjk` → clean',
        '- [ ] `python novelclaw.py validate {0}` → PASSED'.format(num),
        '- [ ] Source has no scrape artifacts (`python tools/clean_source.py {0}`)'.format(num),
        '',
        '## 2. Accuracy (correctness vs source)',
        '',
        '- [ ] All character names match the glossary locked (no 布洛特/曹星/CN)',
        '- [ ] All numbers (HP, levels, damage) match source exactly',
        '- [ ] All skill/item/place names match glossary (no 霜狼 vs 雪狼)',
        '- [ ] Timeline order correct (no chronology break vs source)',
        '- [ ] No facts invented or removed (compare paragraph-by-paragraph with source)',
        '',
        '## 3. Fluency (natural Thai)',
        '',
        '- [ ] Reads naturally when read aloud (no word-for-word translation smell)',
        '- [ ] Sentence flow matches Thai web-novel style (mixed short/long)',
        '- [ ] Dialogue feels like real speech (not formal/academic)',
        '- [ ] Idioms translated by meaning, not literally',
        '- [ ] No English/Chinese filler words leaked (果然, 原来如此, etc.)',
        '',
        '## 4. Terminology (glossary consistency)',
        '',
        '- [ ] All new terms added to glossary (locked > reference > auto)',
        '- [ ] Recurring terms use EXACT same spelling as earlier chapters',
        '- [ ] Character names are consistently the same Thai spelling',
        f'- [ ] `python tools/glossary_stats.py` shows no surprising heavy terms',
        '',
        '## 5. Style (matches last 1-2 chapters)',
        '',
    ]

    if prevs:
        for p_num, p_title in prevs:
            lines.append(f'- [ ] Tone matches ch {p_num}: {p_title}')
    else:
        lines.append('- [ ] Tone matches last 1-2 chapters')

    lines.extend([
        '',
        '## 6. Locale convention',
        '',
        '- [ ] No mixing of foreign scripts in body (CN/JP/KR only inside 《》 or as proper nouns)',
        '- [ ] Measurements in Thai unit if applicable (or kept as source with note)',
        '- [ ] System messages 【】 have Thai content (no CN inside)',
        '- [ ] Donor names in 《》 with 《 name 》 (legitimate CN user IDs)',
        '',
        '## 7. Sign-off',
        '',
        '- [ ] All Tier-1 validators passed',
        '- [ ] Accuracy check: source paragraph count == translation paragraph count',
        '- [ ] No 【】 block has CN inside',
        '- [ ] Notes / corrections:',
        '',
        '```',
        '',
        '```',
        '',
    ])

    if with_context:
        lines.append('## Appendix: source + 2 previous chapters for tone reference')
        lines.append('')
        if src_path.exists():
            lines.append(f'### Source ch {num} (first 60 lines)')
            lines.append('```')
            for ln in extract_body(src_path.read_text(encoding='utf-8')).split('\n')[:60]:
                lines.append(ln)
            lines.append('```')
            lines.append('')
        for p_num, p_title in prevs:
            p_path = CHAPTERS / f'{p_num:04d}.md'
            if p_path.exists():
                lines.append(f'### Previous ch {p_num}: {p_title} (first 30 lines)')
                lines.append('```')
                for ln in extract_body(p_path.read_text(encoding='utf-8')).split('\n')[:30]:
                    lines.append(ln)
                lines.append('```')
                lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Generate Tier-2 review checklist.')
    parser.add_argument('chapters', nargs='+', type=int, help='Chapter number(s) to review')
    parser.add_argument('--checklist', action='store_true', help='Print checklist only (no file)')
    parser.add_argument('--context', action='store_true', help='Include source + previous chapters in template')
    args = parser.parse_args()

    for n in args.chapters:
        template = generate_template(n, with_context=args.context)
        if args.checklist:
            print(template)
        else:
            REVIEWS.mkdir(parents=True, exist_ok=True)
            out_path = REVIEWS / f'{n:04d}.md'
            out_path.write_text(template, encoding='utf-8')
            print(f'  ✓ {out_path}')


if __name__ == '__main__':
    main()
