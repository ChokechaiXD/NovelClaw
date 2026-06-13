"""learn_slop.py — Dynamic ban list that learns from translated output.

Problem: static ban lists miss crutch phrases that develop in a specific
novel's voice. AI reuses "ยิ้มเย็น" / "ขมวดคิ้ว" / "ถอนหายใจ" 3+ times per
chapter after translating 50+ chapters — existing slop_detector only
catches known patterns.

Solution: scan translated chapters for repeated 2-grams (TH bigrams),
auto-add the top offenders to a per-novel dynamic ban list, and inject
that list into the pre_chapter context for future translations.

This is the post-process "self-correction loop" from Megumin's V7
Dynamic Ban List + Nemo's Prose Polisher (n-gram evidence from rejected
swipes) — adapted for the CN→TH translation pipeline.

Usage:
    python learn_slop.py                       # scan all translated ch, update bans
    python learn_slop.py --chapter 100         # scan single ch
    python learn_slop.py --min-count 4         # 4+ occurrences → ban
    python learn_slop.py --top 10              # show top 10 candidates
    python learn_slop.py --dry-run             # preview, don't write

Output:
    novels/{slug}/dynamic_bans.md  — auto-updated ban list (sorted by count)

Design notes:
- Bigrams (2-grams), not single words (too noisy: "เขา", "เธอ")
- Not trigrams+ (too sparse at chapter-level)
- Skip function words: คือ/ก็/ที่/ของ/ใน/กับ/และ/จะ/ได้/มา/ไป
- Skip dialogue-openers (": or " prefix)
- Skip proper nouns: ANY word appearing in glossary/* first
- Manual whitelist escape hatch: dynamic_bans.md has [whitelist] section
- 3+ occurrences in a single chapter = crutch for that novel
- Aggregated across all 31 ch = cross-chapter crutch (higher confidence)
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT  # noqa: E402


# ── Configuration ───────────────────────────────────────────────────
MIN_COUNT = 3          # 3+ occurrences in 1 ch = flag
MIN_CHAPTERS = 2       # OR appears in 2+ ch = cross-chapter crutch
TOP_N = 20             # candidates to surface
BAN_FILE = NOVEL_ROOT / 'dynamic_bans.md'

# Words to ignore: function words + common particles
STOPWORDS = {
    'คือ', 'ก็', 'ที่', 'ของ', 'ใน', 'กับ', 'และ', 'จะ', 'ได้', 'มา', 'ไป',
    'เขา', 'เธอ', 'ฉัน', 'ผม', 'เรา', 'คุณ', 'มัน', 'พวก', 'นี้', 'นั้น',
    'ไม่', 'ใช่', 'แล้ว', 'แต่', 'หรือ', 'ถ้า', 'ให้', 'โดย', 'จาก', 'ถึง',
    'อยู่', 'มี', 'เป็น', 'ทำ', 'ว่า', 'เมื่อ', 'เพราะ', 'เพื่อ', 'จน',
    'ตัว', 'คน', 'อย่าง', 'ทั้ง', 'เพียง', 'เหล่า', 'อีก', 'แค่', 'ใด',
}


def tokenize_th(text: str) -> list[str]:
    """Simple TH tokenization: split on whitespace + Thai punctuation.

    Keeps Thai words and CJK characters together, drops punctuation.
    Same approach as slop.text_stats for consistency.

    Skips content inside 【】 (system messages — legitimate repetition)
    and inside 《》 (game/donor titles — intentional format).
    """
    # Strip dialogue markers and meta
    text = re.sub(r'^\*Source:.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    # Remove system messages (【...】) and titles (《...》) — these are
    # legitimate format-driven repetition, not narrative crutch phrases
    text = re.sub(r'【[^】]*】', ' ', text)
    text = re.sub(r'《[^》]*》', ' ', text)
    # Normalize: remove all punctuation
    text = re.sub(r'[^\w\u0e00-\u0e7f\u4e00-\u9fff]', ' ', text)
    tokens = [t for t in text.split() if len(t) > 1]
    return tokens


def get_bigrams(tokens: list[str]) -> list[tuple[str, str]]:
    """Generate bigrams, skipping stopword-led and stopword-tailed."""
    bigrams = []
    for i in range(len(tokens) - 1):
        w1, w2 = tokens[i], tokens[i + 1]
        if w1 in STOPWORDS or w2 in STOPWORDS:
            continue
        if len(w1) < 2 or len(w2) < 2:
            continue
        bigrams.append((w1, w2))
    return bigrams


def is_glossary_term(word: str) -> bool:
    """Check if word appears in any glossary tier (proper noun detection)."""
    for tier in ('locked.md', 'reference.md', 'auto.md'):
        f = NOVEL_ROOT / 'glossary' / tier
        if f.exists() and word in f.read_text(encoding='utf-8'):
            return True
    return False


def load_existing_bans() -> set[str]:
    """Load already-banned bigrams from dynamic_bans.md.

    Format:
        - word1 word2   (auto-banned, 5x in ch 50,80,90)
    """
    if not BAN_FILE.exists():
        return set()
    text = BAN_FILE.read_text(encoding='utf-8')
    return set(re.findall(r'^- (\S+) (\S+)\s', text, flags=re.MULTILINE))


def load_whitelist() -> set[str]:
    """Load manually-whitelisted bigrams (escape hatch for false positives).

    dynamic_bans.md [whitelist] section:
        [whitelist]
        - ยิ้ม เย็น
        - ขมวด คิ้ว
    """
    if not BAN_FILE.exists():
        return set()
    text = BAN_FILE.read_text(encoding='utf-8')
    m = re.search(r'\[whitelist\](.*?)(?=\[|\Z)', text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'^- (\S+) (\S+)\s', m.group(1), flags=re.MULTILINE))


def scan_chapter(num: int) -> Counter:
    """Return Counter of (w1, w2) → count for a single chapter."""
    f = NOVEL_ROOT / 'chapters' / f'{num:04d}.md'
    if not f.exists():
        return Counter()
    text = f.read_text(encoding='utf-8')
    tokens = tokenize_th(text)
    return Counter(get_bigrams(tokens))


def aggregate_chapters(chapter_nums: list[int]) -> Counter:
    """Aggregate bigram counts across multiple chapters."""
    agg: Counter = Counter()
    for n in chapter_nums:
        agg.update(scan_chapter(n))
    return agg


def find_candidates(agg: Counter,
                    existing: set[str],
                    whitelist: set[str],
                    glossary_check: bool = True) -> list[tuple[tuple[str, str], int, int]]:
    """Find bigrams to ban.

    Returns list of ((w1, w2), total_count, chapter_count) sorted by total.

    Criteria:
      - total count >= MIN_COUNT AND chapter_count >= MIN_CHAPTERS, OR
      - chapter_count >= 5 (very repetitive across the novel)
      - NOT in existing bans
      - NOT in whitelist
      - NOT containing any proper noun (glossary term) — proper nouns are
        intentional repetition (character names, place names)
    """
    # Count chapters per bigram
    chapter_count: dict[tuple[str, str], int] = {}
    for n in TRANSLATED_CHAPTERS:
        ch_counter = scan_chapter(n)
        for bg in ch_counter:
            if bg in agg and agg[bg] >= MIN_COUNT:
                chapter_count[bg] = chapter_count.get(bg, 0) + 1

    candidates = []
    for bg, total in agg.most_common(TOP_N * 3):
        if bg in existing or bg in whitelist:
            continue
        w1, w2 = bg
        if glossary_check and (is_glossary_term(w1) or is_glossary_term(w2)):
            continue
        cc = chapter_count.get(bg, 0)
        if total >= MIN_COUNT and cc >= MIN_CHAPTERS:
            candidates.append((bg, total, cc))
        elif cc >= 5:
            candidates.append((bg, total, cc))
    return candidates[:TOP_N]


def format_ban_file(new_bans: list[tuple[tuple[str, str], int, int]],
                    existing_bans: set[str],
                    whitelist: set[str]) -> str:
    """Format the dynamic_bans.md file with new + existing + whitelist sections."""
    lines = [
        '# Dynamic Ban List — auto-learned from translation output',
        '',
        '> Generated by `tools/learn_slop.py`. Do NOT edit manually —',
        '> instead add false positives to the `[whitelist]` section below.',
        '',
        '**Criteria:** bigram appears 3+ times in 1 ch AND in 2+ chapters,',
        'OR appears in 5+ chapters. Excludes glossary terms and whitelist.',
        '',
        '## Banned (auto)',
        '',
    ]
    if new_bans:
        for (w1, w2), total, cc in new_bans:
            lines.append(f'- {w1} {w2}   ({total}x in {cc} ch)')
    else:
        lines.append('_(no new candidates)_')
    lines.append('')

    if existing_bans:
        lines.extend([
            '## Previously banned',
            '',
        ])
        for bg in sorted(existing_bans):
            lines.append(f'- {bg[0]} {bg[1]}')
        lines.append('')

    lines.extend([
        '## [whitelist]',
        '',
        '> Add `- word1 word2` lines here to exempt bigrams from auto-banning.',
        '> Use this for legitimate repeated phrases (signatures, format markers).',
        '',
    ])
    for bg in sorted(whitelist):
        lines.append(f'- {bg[0]} {bg[1]}')
    lines.append('')
    return '\n'.join(lines)


# Discover translated chapters
TRANSLATED_CHAPTERS = sorted([
    int(f.stem)
    for f in (NOVEL_ROOT / 'chapters').glob('*.md')
    if f.stem.isdigit() and len(f.stem) == 4
])


def main():
    import argparse
    p = argparse.ArgumentParser(description='Learn dynamic ban list from translated chapters')
    p.add_argument('--chapter', type=int, help='scan single chapter (default: all)')
    p.add_argument('--min-count', type=int, default=MIN_COUNT)
    p.add_argument('--top', type=int, default=TOP_N)
    p.add_argument('--dry-run', action='store_true', help='preview, don\'t write')
    args = p.parse_args()

    print(f'📚 Scanning {len(TRANSLATED_CHAPTERS)} translated chapters...')

    existing = load_existing_bans()
    whitelist = load_whitelist()
    print(f'   {len(existing)} existing bans, {len(whitelist)} whitelisted')

    if args.chapter:
        ch_nums = [args.chapter]
    else:
        ch_nums = TRANSLATED_CHAPTERS

    agg = aggregate_chapters(ch_nums)
    candidates = find_candidates(agg, existing, whitelist)
    candidates = candidates[:args.top]

    print(f'\\n🔍 Top {len(candidates)} candidates for banning:')
    print(f'   {"bigram":<30} {"total":>6}  {"chapters":>8}')
    print('   ' + '─' * 50)
    for (w1, w2), total, cc in candidates:
        print(f'   {w1} {w2:<22} {total:>6}  {cc:>8}')

    if args.dry_run:
        print('\\n(dry-run: not writing to file)')
        return

    if candidates:
        # Merge new candidates with existing
        all_banned = existing | {bg for bg, _, _ in candidates}
        new_only = [(bg, total, cc) for (bg, total, cc) in candidates
                    if bg not in existing]
        out = format_ban_file(new_only, all_banned, whitelist)
        BAN_FILE.write_text(out, encoding='utf-8')
        print(f'\\n✅ Updated {BAN_FILE}')
        print(f'   +{len(new_only)} new bans, {len(all_banned)} total')
    else:
        print('\\n✨ No new candidates — current translations are clean!')


if __name__ == '__main__':
    main()
