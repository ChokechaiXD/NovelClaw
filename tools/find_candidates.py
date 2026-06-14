"""find_candidates.py — Find chapters that may need re-translation.

Scans all chapters in novels/<slug>/chapters/ and flags:
  1. Wrong glossary names (e.g., "โจวซิง" instead of "เฉาซิง" for 曹星)
  2. Length ratio out of range (1.5-3.0x of CN)
  3. Missing 2-3 digit numbers from source
  4. Heavily paraphrased glossary terms (no exact Thai match for high-confidence terms)

Outputs a list of chapter numbers that should be reviewed for re-translation.

Usage:
  python find_candidates.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import LENGTH_RATIO_OK, NAME_CHECKS, NOVEL_ROOT  # noqa: E402

ROOT = NOVEL_ROOT
CHAPTERS_DIR = ROOT / 'chapters'
SOURCE_DIR = CHAPTERS_DIR / 'source'
GLOSSARY_DIR = ROOT / 'glossary'


def split_paragraphs(text: str) -> list[str]:
    parts = text.split('\n---\n')
    # Use the LONGEST part as body (handles both formats):
    # - source CN: no `---` → parts = [whole file]
    # - translation TH: `---` separates title, content, footer → parts[1] is content
    if len(parts) > 1:
        body = max(parts, key=len)
    else:
        body = parts[0]
    body = re.sub(r'^#\s+.*?\n', '', body, count=1)
    return [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]


def extract_numbers(text: str) -> set[str]:
    text_clean = re.sub(r'(\d),(\d)', r'\1\2', text)
    # Use lookbehind/lookahead instead of \b — \b is ASCII-only and
    # doesn't work at CJK↔digit boundaries (e.g. 他有15个苹果).
    return set(re.findall(r'(?<!\d)\d{2,3}(?!\d)', text_clean))


def load_glossary_main() -> dict[str, str]:
    out = {}
    for tier in ('locked.md', 'reference.md'):
        for line in (GLOSSARY_DIR / tier).read_text(encoding='utf-8').splitlines():
            if not line.startswith('| ') or line.startswith('|--') or 'Source' in line:
                continue
            cells = [c.strip() for c in line.split('|')]
            if len(cells) >= 6 and cells[1] and cells[1] != '-':
                out[cells[1]] = cells[2]
    return out


def find_chapter_files() -> list[Path]:
    ch_dir = ROOT / 'chapters'
    files = []
    for f in ch_dir.iterdir():
        if f.is_file() and re.match(r'^\d{4}\.md$', f.name):
            files.append(f)
    return sorted(files, key=lambda p: int(p.stem))


def main():
    glossary = load_glossary_main()
    ch_files = find_chapter_files()
    if not ch_files:
        print('No translated chapters found.')
        return

    flagged = []
    for f in ch_files:
        num = int(f.stem)
        tr = f.read_text(encoding='utf-8')
        src_path = ROOT / 'chapters' / 'source' / f.name
        if not src_path.exists():
            flagged.append((num, ['(no source for comparison)']))
            continue
        src = src_path.read_text(encoding='utf-8')
        issues = []

        # 1. Wrong-name variants
        for cn, correct, wrong in NAME_CHECKS:
            if cn in src and wrong in tr and correct not in tr:
                issues.append(f'Wrong name: {cn} → "{wrong}" in tr (should be "{correct}")')

        # 2. Length ratio
        src_paras = split_paragraphs(src)
        tr_paras = split_paragraphs(tr)
        src_len = sum(len(p) for p in src_paras)
        tr_len = sum(len(p) for p in tr_paras)
        if src_len:
            lr = tr_len / src_len
            if lr < LENGTH_RATIO_OK[0] or lr > LENGTH_RATIO_OK[1]:
                issues.append(f'Length ratio: {lr:.2f} (expected {LENGTH_RATIO_OK[0]}-{LENGTH_RATIO_OK[1]})')

        # 3. Missing 2-3 digit numbers
        src_nums = extract_numbers(src)
        tr_nums = extract_numbers(tr)
        missing = src_nums - tr_nums
        # Filter out year/known noise
        real_missing = [n for n in missing if n not in ('2026',)]
        if len(real_missing) >= 3:  # only flag if multiple missing
            issues.append(f'Missing {len(real_missing)} numbers: {real_missing[:5]}')

        # 4. Glossary: count terms in source that don't appear in translation (literal)
        used = [(s, t) for s, t in glossary.items() if s in src]
        not_literal = [(s, t) for s, t in used if t not in tr]
        if len(used) > 0 and len(not_literal) / len(used) > 0.5:
            issues.append(f'Glossary paraphrase: {len(not_literal)}/{len(used)} terms not literal')

        if issues:
            flagged.append((num, issues))

    if not flagged:
        print('━' * 60)
        print(f'  No issues found in {len(ch_files)} chapters ✓')
        print('━' * 60)
        return

    print('━' * 60)
    print(f'  RE-TRANSLATION CANDIDATES — {len(flagged)}/{len(ch_files)} chapters')
    print('━' * 60)
    for num, issues in sorted(flagged):
        print(f'\n  Ch {num}:')
        for i in issues:
            print(f'    - {i}')
    print('\n' + '━' * 60)
    print(f'  {len(flagged)} chapters may benefit from re-translation.')
    print('  Run: python validate_chapter.py <N> for details on each.')
    print('━' * 60)


if __name__ == '__main__':
    main()
