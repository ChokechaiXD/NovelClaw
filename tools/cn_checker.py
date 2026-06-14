#!/usr/bin/env python3
"""
CN/JP leak checker for NovelClaw chapters.

Scans all JSON chapters for any Chinese/Japanese characters that leaked
into narration or dialogue blocks. System messages and game titles are
checked separately since they have specific whitelist rules.

Auto-strip patterns (P'Chok's choice, 2026-06-14):
- "ขอบคุณนักอ่าน" blocks (作者感谢书友) at end of chapter
  → author thanks, not narrative, contains CN usernames

Usage:
    python tools/cn_checker.py          # check all chapters
    python tools/cn_checker.py 116      # check one chapter
    python tools/cn_checker.py 116 117  # check specific chapters
    python tools/cn_checker.py --strict # fail on game_title/system with CN too
    python tools/cn_checker.py --strip  # AUTO-STRIP "ขอบคุณนักอ่าน" blocks

Exit code 0 = clean, 1 = leaks found.
"""
import json
import re
import sys
from pathlib import Path

CHAPTERS_DIR = Path("novels/global-descent/chapters")

# Unicode ranges
CN = re.compile(r'[\u4e00-\u9fff]')           # CJK Unified Ideographs (Chinese)
JP_KANA = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')  # Hiragana + Katakana

# Whitelist patterns inside system msgs and game titles
WHITELIST_ZONES = [
    re.compile(r'【[^】]*】'),  # 【...】 system zone
    re.compile(r'《[^》]*》'),  # 《...》 title zone
]

# Patterns to auto-strip (author's thanks / metadata, not story content)
# "ขอบคุณนักอ่าน..." with optional 《...》 usernames — common in CN web novels
# Also donation tips: "ขอบคุญ《username》500เหรียญ"
STRIP_PATTERNS = [
    re.compile(r'^\s*ขอบคุณ\s*นักอ่าน[:：]?.*$', re.MULTILINE),  # ขอบคุณนักอ่าน: ...
    re.compile(r'^\s*ขอบคุณ\s*《[^》]*》.*$', re.MULTILINE),     # ขอบคุญ《username》...
    re.compile(r'^\s*感谢书友.*$', re.MULTILINE),                  # 感谢书友
    re.compile(r'^\s*感谢.*的月票.*$', re.MULTILINE),              # 感谢...月票
    re.compile(r'^\s*感谢书友们的收藏和订阅.*$', re.MULTILINE),
    re.compile(r'^\s*感谢.*(?:收藏|订阅|打赏|月票).*$', re.MULTILINE),
]


def strip_whitelist(text):
    """Remove whitelisted zones so we only check the 'naked' text."""
    out = text
    for pattern in WHITELIST_ZONES:
        out = pattern.sub('', out)
    return out


def should_strip_block(text):
    """Return True if this block matches a 'strip pattern' (author's thanks)."""
    for pattern in STRIP_PATTERNS:
        if pattern.match(text.strip()):
            return True
    return False


def check_chapter(num, strict=False):
    """Check one chapter. Returns (leak_count, leak_details).

    Multi-language aware (Phase 2 — 2026-06-14): only scans chapters whose
    lang is 'cn' (or unknown / no lang field — backward compat). Other
    languages (en, jp, kr, th) don't leak CN because their source text
    IS in those languages, and the validation step already strips
    whitelisted zones.
    """
    padded = f"{num:04d}.json"
    path = CHAPTERS_DIR / padded
    if not path.exists():
        return 0, []

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Skip non-CN chapters — they don't leak CN by design
    lang = data.get('lang', 'cn')
    if lang not in ('cn', None, ''):
        return 0, []

    leaks = []
    for i, block in enumerate(data.get('blocks', [])):
        btype = block.get('type')
        text = block.get('text', '')

        # Skip non-text blocks
        if not text or btype == 'end_marker':
            continue

        # Skip blocks matching strip pattern (author's thanks)
        if should_strip_block(text):
            continue

        if btype in ('narration', 'dialogue'):
            for char in CN.findall(text):
                leaks.append((i, btype, char, text))
            for char in JP_KANA.findall(text):
                leaks.append((i, btype, char, text))

        elif btype == 'system':
            check_text = strip_whitelist(text)
            for char in CN.findall(check_text):
                leaks.append((i, btype, char, text))
            for char in JP_KANA.findall(check_text):
                leaks.append((i, btype, char, text))
            if strict:
                for char in CN.findall(text):
                    leaks.append((i, f"{btype}[strict]", char, text))

        elif btype == 'game_title':
            check_text = strip_whitelist(text)
            for char in CN.findall(check_text):
                leaks.append((i, btype, char, text))
            for char in JP_KANA.findall(check_text):
                leaks.append((i, btype, char, text))
            if strict:
                for char in CN.findall(text):
                    leaks.append((i, f"{btype}[strict]", char, text))

    return len(leaks), leaks


def strip_chapter(num, dry_run=True):
    """Remove 'author's thanks' blocks from chapter. Returns list of removed indices."""
    padded = f"{num:04d}.json"
    path = CHAPTERS_DIR / padded
    if not path.exists():
        return []

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    removed = []
    new_blocks = []
    for i, block in enumerate(data.get('blocks', [])):
        text = block.get('text', '')
        if should_strip_block(text):
            removed.append((i, text[:80]))
        else:
            new_blocks.append(block)

    if not dry_run and removed:
        data['blocks'] = new_blocks
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return removed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    strict = '--strict' in sys.argv
    strip = '--strip' in sys.argv
    dry_run = '--dry-run' in sys.argv or not strip

    if args:
        nums = [int(a) for a in args]
    else:
        nums = []
        for f in sorted(CHAPTERS_DIR.glob('0*.json')):
            m = re.match(r'0*(\d+)\.json', f.name)
            if m:
                nums.append(int(m.group(1)))

    # --strip mode: actually remove blocks
    if strip:
        print(f"Stripping 'author's thanks' blocks (dry_run={dry_run})...")
        total_removed = 0
        for num in nums:
            removed = strip_chapter(num, dry_run=dry_run)
            if removed:
                total_removed += len(removed)
                print(f"  ch {num}: removed {len(removed)} block(s)")
                for idx, snippet in removed:
                    print(f"    block {idx}: {snippet}...")
        if total_removed == 0:
            print("  nothing to strip")
        else:
            print(f"\nTotal removed: {total_removed} block(s)")
        sys.exit(0)

    # Check mode
    total_leaks = 0
    chapters_with_leaks = 0
    for num in nums:
        count, leaks = check_chapter(num, strict=strict)
        if count > 0:
            chapters_with_leaks += 1
            total_leaks += count
            print(f"\n❌ ch {num}: {count} CN/JP leak(s)")
            for i, btype, char, text in leaks[:5]:
                snippet = text[:80].replace('\n', ' ')
                print(f"   block {i} ({btype}): '{char}' in: {snippet}")
            if len(leaks) > 5:
                print(f"   ... +{len(leaks) - 5} more")
        else:
            print(f"✓ ch {num}: clean")

    print(f"\n{'='*50}")
    if total_leaks == 0:
        print(f"✅ ALL CLEAN — {len(nums)} chapter(s) checked, 0 leaks")
        sys.exit(0)
    else:
        print(f"❌ FOUND LEAKS — {chapters_with_leaks} chapter(s), {total_leaks} total")
        sys.exit(1)


if __name__ == '__main__':
    main()
