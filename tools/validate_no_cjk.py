"""validate_no_cjk.py — Detect CJK character leakage in translated chapters.

The output of every translation MUST be Thai-only (Section 1a of PROMPT.md).
CJK characters (Chinese, Japanese, Korean) may only appear inside the optional
"*Source: ch N (<CN title for reference>)*" footer line at the very end
of a chapter file.

This tool scans all chapters and reports:
  - Which files have CJK in body (excluding the H1 title and Source footer)
  - Which specific CJK strings are present
  - A pass/fail summary

Usage:
  python validate_no_cjk.py            # check all chapters
  python validate_no_cjk.py 71 72 80  # check specific chapters
  python validate_no_cjk.py --all     # explicit all
  python validate_no_cjk.py --strict  # also flag CJK in H1 title
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent / 'novels' / 'global-descent'
CHAPTERS = ROOT / 'chapters'

# Match CJK characters: Chinese (incl. extension A), Hiragana, Katakana, Hangul.
# EXCLUDES the bracket/punctuation markers 【】《》 (allowed by Section 1 of PROMPT).
CJK_PATTERN = re.compile(
    r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af]'
)
# Bracket markers that are allowed even though they have CJK codepoints
MARKER_PATTERN = re.compile(r'[\u3000-\u303f\u3010\u3011\u300a\u300b]')
# CJK that would be inside markers (more strict)
INSIDE_MARKER_PATTERN = re.compile(
    r'[\u3010\u3011]'  # 【】
    r'|\u300a'           # 《》
)



def extract_body_lines(content: str) -> list[str]:
    """Get all body lines, excluding the H1 title and the *Source:* footer."""
    lines = content.split('\n')
    body = []
    in_source_footer = False
    for line in lines:
        # Skip H1 (first # line)
        if line.startswith('# ') and not body and not in_source_footer:
            continue
        # After we see the *---* separator, only the Source footer follows
        if line.strip() == '---' and not in_source_footer and body:
            in_source_footer = True
            continue
        if in_source_footer:
            continue
        body.append(line)
    return body


def find_cjk_in_markers(text: str) -> list[str]:
    """Find CJK characters INSIDE 【】 (system markers). 《》 is allowed fully
    (used for game titles AND donor names which are inherently CN user IDs)."""
    issues = []
    # 【...】 pattern
    for m in re.finditer(r'[\u3010\u3011]([^\u3010\u3011]*)[\u3011]', text):
        inside = m.group(1)
        cjk = CJK_PATTERN.findall(inside)
        if cjk:
            issues.append(f'【...{",".join(sorted(set(cjk)))}...】')
    return issues


def check_chapter(num: int, strict: bool = False) -> tuple[list[str], list[str]]:
    """Return (body_cjk_strings, marker_cjk_strings). Empty if clean."""
    padded = f'{num:04d}.md'
    f = CHAPTERS / padded
    if not f.exists():
        return None, None
    content = f.read_text(encoding='utf-8')

    # Strip out 【...】 and 《...》 blocks entirely (markers + content both allowed).
    # 【】  = system messages / game UI (per PROMPT Section 4)
    # 《》  = game titles (per PROMPT Section 4) AND donor name markers (thank-you footers).
    #          Donor names are legitimate Chinese web-novel user IDs and cannot be translated.
    text_no_markers = re.sub(r'[\u3010\u3011][^\u3010\u3011]*[\u3011]', '', content)
    text_no_markers = re.sub(r'[\u300a\u300b][^\u300a\u300b]*[\u300b]', '', text_no_markers)

    if strict:
        text_to_scan = re.sub(r'^#\s+.*\n', '', text_no_markers, count=1, flags=re.M)
    else:
        body_lines = extract_body_lines(text_no_markers)
        text_to_scan = '\n'.join(body_lines)

    body_matches = CJK_PATTERN.findall(text_to_scan)

    # Also check for CJK inside markers (always flagged, even in non-strict mode)
    marker_issues = find_cjk_in_markers(content)

    return sorted(set(body_matches)), marker_issues


def main():
    args = sys.argv[1:]
    strict = '--strict' in args
    args = [a for a in args if a != '--strict']

    if not args or '--all' in args:
        chapter_files = sorted(CHAPTERS.glob('*.md'), key=lambda p: int(p.stem))
    else:
        chapter_files = [CHAPTERS / f'{int(a):04d}.md' for a in args]

    total = 0
    failed_body = 0
    failed_marker = 0
    print('━' * 70)
    print(f'  CJK leakage check — {len(chapter_files)} chapter(s)')
    print('  Allowed: 【】 system markers, 《》 titles + donor names, Source footer')
    print('━' * 70)

    for f in chapter_files:
        if not f.exists():
            print(f'  ⏭  ch {f.stem} (file not found)')
            continue
        num = int(f.stem)
        body_leaks, marker_leaks = check_chapter(num, strict=strict)
        total += 1
        if body_leaks is None:
            print(f'  ⏭  ch {num:4d} (file not found)')
        elif not body_leaks and not marker_leaks:
            print(f'  ✓  ch {num:4d}  clean')
        else:
            if body_leaks:
                failed_body += 1
                print(f'  ✗  ch {num:4d}  body: {len(body_leaks)} CJK string(s):')
                for s in body_leaks[:6]:
                    print(f'        - {s}')
                if len(body_leaks) > 6:
                    print(f'        ... and {len(body_leaks) - 6} more')
            if marker_leaks:
                failed_marker += 1
                print(f'  ✗  ch {num:4d}  in-marker: {len(marker_leaks)} CN inside 【】/《》:')
                for s in marker_leaks[:4]:
                    print(f'        - {s}')

    print('━' * 70)
    if failed_body == 0 and failed_marker == 0:
        print(f'  ✅ PASSED — all {total} chapter(s) CJK-free')
        print('━' * 70)
        sys.exit(0)
    else:
        failed = failed_body + failed_marker
        print(f'  ❌ FAILED — {failed} issue(s) across {total} chapter(s)')
        print(f'       body leaks: {failed_body}, marker leaks: {failed_marker}')
        print('━' * 70)
        sys.exit(1)


if __name__ == '__main__':
    main()
