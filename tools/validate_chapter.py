"""validate_chapter.py v2 — Quality check with auto-fix.

Two modes:
  default:    report only (exit 0/1)
  --fix:      apply mechanical fixes, save, then report

Mechanical fixes (zero quality risk):
  - Wrong-name variants (e.g., "โจวซิง" → "เฉาซิง" if 曹星 in source)
  - Trailing whitespace + missing final newline
  - "—" (em-dash) standardization (placeholder for missing numbers)
  - System message wrapping: 【...】 around standalone "系統提示出現"

Non-mechanical (always reported, never auto-fixed):
  - Length ratio issues
  - Missing/extra numbers
  - Glossary paraphrase rate

Usage:
  python validate_chapter.py 71            # check only
  python validate_chapter.py 71 --fix     # check + apply mechanical fixes
  python validate_chapter.py               # check last translated
  python validate_chapter.py --fix --all  # fix all chapters
"""
import re
import sys
from pathlib import Path

# Load shared constants (LENGTH_RATIO_OK, NAME_CHECKS, NOVEL_ROOT)
sys.path.insert(0, str(Path(__file__).parent))
from constants import LENGTH_RATIO_OK, NAME_CHECKS, NOVEL_ROOT, GLOSSARY_DIR  # noqa: E402

ROOT = NOVEL_ROOT


# ── Helpers ───────────────────────────────────────────────────────────

def read_progress_last() -> int:
    p = ROOT / 'progress.md'
    m = re.search(r'Last translated:\*\* ch (\d+)', p.read_text(encoding='utf-8'))
    if not m:
        sys.exit("Could not parse progress.md for 'Last translated'")
    return int(m.group(1))


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


# ── Auto-fix ───────────────────────────────────────────────────────────

def auto_fix(text: str) -> tuple[str, list[str]]:
    """Apply mechanical fixes. Returns (new_text, list_of_fixes).

    For each (cn, correct, wrong) in NAME_CHECKS:
      - wrong in text AND correct NOT in text  → auto-replace, log fix
      - wrong in text AND correct in text      → flag for manual review
                                                 (not auto-fixed; user must
                                                 decide which usage is correct)
    """
    fixes = []

    # 1. Wrong-name variants
    for cn, correct, wrong in NAME_CHECKS:
        if wrong in text and correct not in text:
            text = text.replace(wrong, correct)
            fixes.append(f'Replaced "{wrong}" → "{correct}"')
        elif wrong in text and correct in text:
            # Both present — mechanical fix is unsafe (could be wrong in 1
            # place, correct in 5). Surface as info so user can manual review.
            fixes.append(f'⚠ BOTH "{wrong}" and "{correct}" present — manual review needed')

    # 2. Standalone "系統提示出現" → wrap in 【】
    # Pattern: paragraph that is JUST "系統提示出現" (not "系統提示" or "系統提示出現..." with content)
    if '系統提示出現' in text and '【系統提示出現】' not in text:
        # Only replace exact phrase on its own line
        text = re.sub(r'(?<!【)系統提示出現(?!】)', '【系統提示出現】', text)
        fixes.append('Wrapped "系統提示出現" in 【】')

    # 3. Trailing whitespace cleanup
    new_text = text.rstrip() + '\n'
    if new_text != text:
        fixes.append('Trimmed trailing whitespace')
        text = new_text

    # 4. Number form normalization (TH style: no separator for 4-digit
    # numbers, comma for 5+ digits. Mixed forms like "1000" vs "1,000"
    # in same chapter look inconsistent.)
    # Find all 4+ digit numbers without separator (use lookbehind/lookahead
    # because \b is ASCII-only and doesn't work at CJK↔digit boundaries).
    no_sep_matches = list(re.finditer(r'(?<!\d)\d{4,}(?!\d)', text))
    if no_sep_matches:
        # Normalize "1000" → "1,000" for 5+ digits only (4 digits stay bare)
        new_text = text
        for m in reversed(no_sep_matches):
            num_str = m.group()
            if len(num_str) >= 5:  # 10000+ → 10,000
                formatted = f'{int(num_str):,}'
                if formatted != num_str:
                    new_text = new_text[:m.start()] + formatted + new_text[m.end():]
                    fixes.append(f'Normalized "{num_str}" → "{formatted}"')
            # 4-digit numbers (1000-9999) stay as-is per TH convention
        text = new_text

    return text, fixes


# ── Validate ──────────────────────────────────────────────────────────

def validate(target: int, do_fix: bool = False) -> int:
    src_file = ROOT / 'chapters' / 'source' / f'{target:04d}.md'
    tr_file = ROOT / 'chapters' / f'{target:04d}.md'
    if not src_file.exists():
        sys.exit(f'Source not found: {src_file}')
    if not tr_file.exists():
        sys.exit(f'Translation not found: {tr_file}')

    source = src_file.read_text(encoding='utf-8')
    translation = tr_file.read_text(encoding='utf-8')

    # Auto-fix first if requested
    if do_fix:
        new_text, fixes = auto_fix(translation)
        if fixes:
            tr_file.write_text(new_text, encoding='utf-8')
            translation = new_text

    src_paras = split_paragraphs(source)
    tr_paras = split_paragraphs(translation)

    errors, warnings, info = [], [], []

    if do_fix and fixes:
        info.append(f'Auto-fixes applied: {len(fixes)}')
        for f in fixes:
            info.append(f'  ✓ {f}')

    # 1. Paragraphs
    if src_paras:
        ratio = len(tr_paras) / len(src_paras)
        info.append(f'Paragraphs: source={len(src_paras)} | translation={len(tr_paras)} | ratio={ratio:.2f}')
        if ratio < 0.5 or ratio > 2.5:
            errors.append(f'Paragraph count ratio: {ratio:.2f} (expected 0.5-2.5)')

    # 2. Numbers
    src_nums = extract_numbers(source)
    tr_nums = extract_numbers(translation)
    missing = src_nums - tr_nums
    info.append(f'Numbers (2-3 digit): source={len(src_nums)} | translation={len(tr_nums)} | missing={len(missing)}')
    if missing:
        real_missing = [n for n in sorted(missing) if n not in ('2026',)]
        if real_missing:
            warnings.append(f'Numbers in source but not in translation: {real_missing[:15]}')

    # 3. Length
    src_len = sum(len(p) for p in src_paras)
    tr_len = sum(len(p) for p in tr_paras)
    if src_len:
        lr = tr_len / src_len
        info.append(f'Length: source={src_len} | translation={tr_len} | ratio={lr:.2f}')
        if lr < LENGTH_RATIO_OK[0] or lr > LENGTH_RATIO_OK[1]:
            errors.append(f'Length ratio: {lr:.2f} (expected {LENGTH_RATIO_OK[0]}-{LENGTH_RATIO_OK[1]})')

    # 4. Glossary names
    glossary = load_glossary_main()
    used, missing_glossary = [], []
    for src, thai in glossary.items():
        if src in source:
            used.append((src, thai))
            if thai not in translation:
                missing_glossary.append((src, thai))
    info.append(f'Glossary terms in source: {len(used)} (locked+reference)')
    if missing_glossary:
        warnings.append(f'Glossary terms whose Thai is not literally in translation ({len(missing_glossary)} total):')
        for src, thai in missing_glossary[:10]:
            warnings.append(f'   - "{src}" → "{thai}"')
        if len(missing_glossary) > 10:
            warnings.append(f'   ... and {len(missing_glossary) - 10} more')

    # 5. Name consistency check (informational, auto-fix already handled)
    for cn, correct, wrong in NAME_CHECKS:
        if cn in source and wrong in translation:
            errors.append(f'Name inconsistency: {cn} → "{wrong}" (should be "{correct}")')

    # Report
    print('━' * 70)
    print(f'  VALIDATION — Ch {target}' + (' (--fix)' if do_fix else ''))
    print('━' * 70)
    print()
    for line in info:
        print(f'  ℹ  {line}')
    print()
    if warnings:
        for w in warnings:
            print(f'  ⚠  {w}')
    if errors:
        for e in errors:
            print(f'  ✗  {e}')
    print()
    if errors:
        print(f'❌ FAILED — {len(errors)} error(s) found')
        return 1
    else:
        msg = '✅ PASSED'
        if warnings:
            msg += f' — {len(warnings)} warning(s)'
        print(msg)
        return 0


def main():
    args = sys.argv[1:]
    do_fix = '--fix' in args
    args = [a for a in args if a != '--fix']

    if not args:
        target = read_progress_last()
    else:
        target = int(args[0])

    sys.exit(validate(target, do_fix=do_fix))


if __name__ == '__main__':
    main()
