"""clean_source.py — Detect scrape artifacts and language contamination in source files.

The source files were scraped from hjwzw.com. Common artifacts:
  - Mixed-script garbage: Cyrillic + CJK (e.g., "окруж" + "围")
  - Encoding bugs (mojibake)
  - Other non-CJK scripts in source

This tool reports suspicious patterns BEFORE Mika translates, so we can
fix the source rather than translate garbage.

Usage:
  python clean_source.py                # check all source files
  python clean_source.py 82             # check specific chapter
  python clean_source.py --strict       # flag any non-CJK non-ASCII
  python clean_source.py --report       # full report with line numbers
"""
import argparse
import re
import sys
from pathlib import Path

_PROJECT_ROOT_DEFAULT = Path(__file__).parent.parent
NOVEL_DIR = _PROJECT_ROOT_DEFAULT / 'novels' / 'global-descent'
SOURCE_DIR = NOVEL_DIR / 'chapters' / 'source'

# CJK Unified Ideographs + Extension A
CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

# Non-CJK non-ASCII characters that should NOT appear in CN source
# (Russian/Cyrillic, Japanese, Korean, Arabic, etc.)
SUSPICIOUS_SCRIPT_PATTERN = re.compile(
    r'[\u0400-\u04ff'      # Cyrillic
    r'\u3040-\u309f'      # Hiragana
    r'\u30a0-\u30ff'      # Katakana
    r'\uac00-\ud7af'      # Hangul
    r'\u0600-\u06ff'      # Arabic
    r'\u0400-\u04ff'      # Cyrillic (already covered)
    r']'
)


def check_file(path: Path, strict: bool = False) -> list[str]:
    """Return list of issues found in the file. Empty = clean."""
    issues = []
    content = path.read_text(encoding='utf-8')
    lines = content.split('\n')

    for i, line in enumerate(lines, 1):
        # Check for non-CJK scripts
        for m in SUSPICIOUS_SCRIPT_PATTERN.finditer(line):
            char = m.group()
            # Russian (Cyrillic) is most common scrape artifact
            context_start = max(0, m.start() - 15)
            context_end = min(len(line), m.end() + 15)
            context = line[context_start:context_end]
            issues.append(f'  line {i}: pos {m.start()}: {char!r} in "…{context}…"')

        # In strict mode, flag any non-ASCII non-CJK
        if strict:
            # Whitelist of CJK / typographic punctuation (legitimate in Chinese sources).
            # Use codepoints explicitly to avoid editor smart-quote substitution.
            WHITELIST = ''.join([
                '\u2014',  # — em-dash
                '\u2026',  # … horizontal ellipsis
                '\u201c\u201d',  # " " curly double quotes (U+201C, U+201D)
                '\u2018\u2019',  # ' ' curly single quotes (U+2018, U+2019)
                '\u300c\u300d',  # 「 」 corner brackets (Japanese-style CJK)
                '\uff08\uff09',  # （ ） fullwidth parens
                '()',  # ASCII parens (allowed too)
                '\u3010\u3011',  # 【 】 black lenticular brackets
                '\u300a\u300b',  # 《 》 double angle brackets
                '\u3001',  # 、 ideographic comma
                '\uff0c',  # ， fullwidth comma
                '\uff01',  # ！ fullwidth exclam
                '\uff1f',  # ？ fullwidth question
                '\uff1a',  # ： fullwidth colon
                '\uff1b',  # ； fullwidth semicolon
                '\u3002',  # 。 ideographic full stop
            ])
            for j, char in enumerate(line):
                if ord(char) > 127 and not CJK_PATTERN.match(char) and not char.isspace():
                    if char in WHITELIST:
                        continue
                    issues.append(f'  line {i}: pos {j}: {char!r} (non-ASCII, non-CJK)')

    return issues


def main():
    parser = argparse.ArgumentParser(description='Detect scrape artifacts in source files.')
    parser.add_argument('chapters', nargs='*', type=int, help='Chapter numbers to check (default: all)')
    parser.add_argument('--strict', action='store_true', help='Flag any non-ASCII non-CJK character')
    parser.add_argument('--report', action='store_true', help='Show only files with issues')
    args = parser.parse_args()

    if args.chapters:
        files = [SOURCE_DIR / f'{n:04d}.md' for n in args.chapters]
    else:
        files = sorted(SOURCE_DIR.glob('*.md'))

    if not files:
        sys.exit(f'No source files found in {SOURCE_DIR}')

    print('━' * 60)
    print(f'  Source preprocessor — {len(files)} file(s)' + (' (strict)' if args.strict else ''))
    print('━' * 60)

    total_issues = 0
    dirty_files = 0
    for f in files:
        if not f.exists():
            print(f'  ⏭  {f.name} (not found)')
            continue
        issues = check_file(f, strict=args.strict)
        if issues:
            dirty_files += 1
            total_issues += len(issues)
            print(f'\n  ✗  {f.name}  ({len(issues)} issue(s)):')
            for iss in issues[:5]:
                print(iss)
            if len(issues) > 5:
                print(f'    ... and {len(issues) - 5} more')
        else:
            if not args.report:
                print(f'  ✓  {f.name}')

    print()
    print('━' * 60)
    if total_issues == 0:
        print(f'  ✅ PASSED — all {len(files)} file(s) clean')
    else:
        print(f'  ⚠  Found {total_issues} issue(s) in {dirty_files}/{len(files)} file(s)')
        print('     These are scrape artifacts. Fix in source/ before translating.')
    print('━' * 60)
    sys.exit(0 if total_issues == 0 else 1)


if __name__ == '__main__':
    main()
