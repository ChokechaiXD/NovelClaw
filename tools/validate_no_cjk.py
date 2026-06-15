"""validate_no_cjk.py — Detect (and optionally strip) CJK character leakage in translated chapters.

The output of every translation MUST be Thai-only (Section 1a of PROMPT.md).
CJK characters (Chinese, Japanese, Korean) may only appear inside the optional
"*Source: ch N (<CN title for reference>)*" footer line at the very end
of a chapter file.

Auto-strip patterns (P'Chok's choice, 2026-06-14):
- "ขอบคุณนักอ่าน" blocks (作者感谢书友) at end of chapter
  → author thanks, not narrative, contains CN usernames

Usage:
  python validate_no_cjk.py                    # check all chapters
  python validate_no_cjk.py 71 72 80           # check specific chapters
  python validate_no_cjk.py --all              # explicit all
  python validate_no_cjk.py --strict           # also flag CJK in H1 title
  python validate_no_cjk.py --strip            # auto-strip "ขอบคุณนักอ่าน" blocks
  python validate_no-cjk.py --novel global-descent
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT = get_novel_root(NOVEL)
CHAPTERS = ROOT / "chapters"

# Match CJK characters: Chinese (incl. extension A), Hiragana, Katakana, Hangul.
# EXCLUDES the bracket/punctuation markers 【】《》 (allowed by Section 1 of PROMPT).
CJK_PATTERN = re.compile(
    r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af]'
)

# Auto-strip patterns (author's thanks / metadata, not story content)
STRIP_PATTERNS = [
    re.compile(r'^\s*ขอบคุณ\s*นักอ่าน[:：]?.*$', re.MULTILINE),
    re.compile(r'^\s*ขอบคุณ\s*《[^》]*》.*$', re.MULTILINE),
]


def extract_body_lines(content: str) -> list[str]:
    """Get all body lines, excluding the H1 title and the *Source:* footer."""
    lines = content.split('\n')
    body = []
    in_source_footer = False
    for line in lines:
        if line.startswith('# ') and not body and not in_source_footer:
            continue
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
    for m in re.finditer(r'[\u3010\u3011]([^\u3010\u3011]*)[\u3011]', text):
        inside = m.group(1)
        cjk = CJK_PATTERN.findall(inside)
        if cjk:
            issues.append(f'【...{",".join(sorted(set(cjk)))}...】')
    return issues


def check_chapter(num: int, strict: bool = False) -> tuple:
    """Return (body_cjk_strings, marker_cjk_strings). Empty if clean."""
    # Try .json first (canonical), then .md (legacy)
    f = CHAPTERS / f'{num:04d}.json'
    if not f.exists():
        f = CHAPTERS / f'{num:04d}.md'
    if not f.exists():
        return None, None

    if f.suffix == '.json':
        data = json.loads(f.read_text(encoding='utf-8'))
        content = '\n'.join(
            b.get('text', '') for b in data.get('blocks', [])
            if b.get('type') in ('narration', 'dialogue')
        )
    else:
        content = f.read_text(encoding='utf-8')

    # Strip out 【...】 and 《...》 blocks (markers + content both allowed)
    text_no_markers = re.sub(r'[\u3010\u3011][^\u3010\u3011]*[\u3011]', '', content)
    text_no_markers = re.sub(r'[\u300a\u300b][^\u300a\u300b]*[\u300b]', '', text_no_markers)

    if strict:
        text_to_scan = text_no_markers
    else:
        body_lines = extract_body_lines(text_no_markers)
        text_to_scan = '\n'.join(body_lines)

    body_matches = CJK_PATTERN.findall(text_to_scan)
    marker_issues = find_cjk_in_markers(content)

    return sorted(set(body_matches)), marker_issues


def strip_chapter(num: int) -> bool:
    """Auto-strip donor-thanks blocks from chapter. Returns True if stripped."""
    jp = CHAPTERS / f'{num:04d}.json'
    if not jp.exists():
        return False
    data = json.loads(jp.read_text(encoding='utf-8'))
    blocks = data.get('blocks', [])
    original_len = len(blocks)
    new_blocks = []
    for b in blocks:
        text = b.get('text', '')
        if any(p.search(text) for p in STRIP_PATTERNS):
            continue
        new_blocks.append(b)
    if len(new_blocks) < original_len:
        data['blocks'] = new_blocks
        data['notes'] = data.get('notes', []) + [{"note": f"Auto-stripped {original_len - len(new_blocks)} donor-thanks block(s)"}]
        jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description='CJK leakage check + auto-strip')
    ap.add_argument('chapters', nargs='*', help='Chapter numbers (default: all)')
    ap.add_argument('--novel', type=str, default=None, help='Novel slug')
    ap.add_argument('--strict', action='store_true', help='Also flag CJK in H1 title')
    ap.add_argument('--strip', action='store_true', help='Auto-strip donor-thanks blocks')
    ap.add_argument('--all', action='store_true', help='Check all chapters')
    args = ap.parse_args()

    global ROOT, CHAPTERS
    ROOT = get_novel_root(args.novel)
    CHAPTERS = ROOT / "chapters"

    if args.strip:
        # Strip mode
        if args.chapters:
            nums = [int(c) for c in args.chapters]
        else:
            nums = sorted([
                int(f.stem) for f in CHAPTERS.glob('*.json') if f.stem.isdigit()
            ])
        stripped = 0
        for num in nums:
            if strip_chapter(num):
                print(f'  ✂  ch {num:4d}  stripped donor-thanks block(s)')
                stripped += 1
            else:
                print(f'  ✓  ch {num:4d}  nothing to strip')
        print(f'\n  Stripped {stripped} chapter(s)')
        sys.exit(0)

    # Check mode
    if not args.chapters or args.all:
        chapter_files = sorted(CHAPTERS.glob('*.json'), key=lambda p: int(p.stem))
        chapter_files += sorted(CHAPTERS.glob('*.md'), key=lambda p: int(p.stem))
        chapter_files = list(dict.fromkeys(chapter_files))  # dedup
    else:
        chapter_files = [CHAPTERS / f'{int(a):04d}.json' for a in args.chapters]

    total = 0
    failed_body = 0
    failed_marker = 0
    print('━' * 70)
    print(f'  CJK leakage check — {len(chapter_files)} chapter(s)')
    print('  Allowed: 【】 system markers, 《》 titles + donor names, Source footer')
    print('━' * 70)

    for f in chapter_files:
        if not f.exists():
            continue
        num = int(f.stem)
        body_leaks, marker_leaks = check_chapter(num, strict=args.strict)
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
                print(f'  ✗  ch {num:4d}  in-marker: {len(marker_leaks)} CN inside 【】:')
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
