"""glossary_gate.py — Pre-translate guard: ensure all CN terms are in glossary.

Workflow (P'Chok's standard, 2026-06-14):
  1. Before translating ch N, run this gate on source N
  2. Gate scans for CN "words" (2-4 char sequences, 2+ occurrences)
  3. Cross-references with glossary.yml + dynamic_bans.md
  4. Reports: known, new (not in glossary), banned (use as-is)
  5. Exits 1 if NEW terms found (must add to glossary first)
  6. Exits 0 if all terms known

This catches CN-leak candidates BEFORE Mika translates, not after
(cn_checker is post-translate). Combined, they form a defense-in-depth
strategy.

Usage:
  python tools/glossary_gate.py 122                # gate ch 122
  python tools/glossary_gate.py 122 --suggest     # also print glossary entry suggestions
  python tools/glossary_gate.py 122 --strict      # also fail on 1-occurrence terms
  python tools/glossary_gate.py 122 --min-occ 3   # only flag terms appearing 3+ times
  python tools/glossary_gate.py                   # gate all untranslated ch
  python tools/glossary_gate.py --json            # output as JSON (for tooling)

Exit codes:
  0 = gate passed (all terms known)
  1 = gate failed (new terms need glossary entries)
  2 = source not found
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Make load_glossary importable
sys.path.insert(0, str(Path(__file__).parent))

from load_glossary import load_terms  # noqa: E402

# Reuse source-path logic from constants
sys.path.insert(0, str(Path(__file__).parent))
from constants import GLOSSARY_DIR, NOVEL_ROOT, get_novel_root# noqa: E402

SOURCE_DIR = NOVEL_ROOT / 'chapters' / 'source'
CHAPTERS_DIR = NOVEL_ROOT / 'chapters'
DYNAMIC_BANS_FILE = NOVEL_ROOT / 'dynamic_bans.md'

# CN character class: CJK Unified Ideographs (Chinese) + Hiragana + Katakana
CN_CHAR = r'\u4e00-\u9fff'
JP_KANA = r'\u3040-\u309f\u30a0-\u30ff'

# Default: extract 2-4 char CN sequences (typical term length)
# We use a flat range, not a nested set (avoids regex FutureWarning).
TERM_PATTERN = re.compile(r'[\u4e00-\u9fff]{2,4}')

# Stopwords: common Chinese particles/connectors that are not "terms"
# (proper nouns, technical words). Excluding these reduces false positives
# in the gate. Sourced from common CN web novel frequency lists.
# Add more as we encounter them in real translations.
STOPWORDS = frozenset({
    # ── Common adverbs / conjunctions
    '然後', '不過', '與此同時', '與此', '同時', '已經', '突然', '果然',
    '真的', '其實', '所以', '因為', '因此', '雖然', '但是', '然而',
    '如果', '或是', '或者', '不只', '不止', '畢竟', '難怪', '可惜',
    # ── Common particles / suffixes
    '不已', '的話', '的極地', '在上', '在下', '之中', '之間',
    '的上', '之下', '左右', '上下', '前後', '其中', '此外', '另外',
    # ── Common verbs
    '點頭', '看著', '說道', '笑道', '問道', '喊道', '吼道', '喝道',
    '怒道', '冷道', '沉聲', '低聲', '大聲', '心中', '眼中', '臉上',
    '手中', '身上', '身體', '不會', '不能', '可以', '想要', '需要',
    '應該', '必須', '就是', '這是', '那是', '這裡', '那裡', '這個',
    '那個', '什麼', '怎麼', '為什麼', '現在', '以前', '剛才', '馬上',
    '立即', '直接', '立刻', '一起', '一樣', '一直', '一定',
    # ── Common nouns
    '眾人', '所有人', '大家', '別人', '自己', '他們', '她們', '它們',
    '成員', '成員們', '獲得', '提升', '增加', '減少', '書友', '朋友',
    '不禁', '到了', '下來', '前進', '大人', '咚咚',
    '沒錯', '天啊', '繼續前進', '曹星目前', '一條系統', '提示出現',
    '是否開啟', '開啟成功', '發現領主', '這位天選',
    # ── Resource acquisition (system messages, not glossary terms)
    '獲得木材', '獲得石塊', '獲得食物', '獲得冰晶',
    # ── Common word: 領地 (territory) — too generic alone
    '領地', '這個領地', '張偉領主', '元素結晶', '女王意志',
    # ── Common narrative phrases
    '沒過多久', '也就是說', '爭取明天', '曹星一樂', '大佬和慕',
    '戰鬥人員', '倖存者們', '殺了冰巢', '柳慕雪身', '而且', '除了',
    '曹星欣喜',
    # ── Common descriptive phrases
    '四個極地', '這些極地', '其他極地', '的提升', '的領主', '你的領地',
    '個領地', '曹星點了', '曹星直接', '帶著嫂嫂', '的力量', '的實力',
    '聽著曹星', '的目光中',
    # ── Site navigation (scraped HTML noise)
    '首頁', '科幻小說', '投票推薦', '加入書籤', '小說報錯',
    '關燈', '字體', '上一章', '下一章', '目錄',
    # ── Author / thanks patterns (already stripped by cn_checker)
    '感謝', '張月票', '獲得經驗', '獲得初級',
    # ── Book / meta terms (handled by schema, not glossary)
    '全球降臨', '末世種田', '踏平領地', '搶走他們', '的極地人',
    '大地母神', '你的領地', '與此同時', '已成', '已成為', '力量之心',
    '級了', '慕雪', '張偉',
})


def extract_cn_terms(text: str, min_len: int = 2, max_len: int = 4) -> Counter:
    """Extract CN term candidates from text, counted by occurrence.

    A "term" is a 2-4 char CJK sequence. Single chars are skipped
    (too noisy — usually particles like 的/了/是).

    Returns Counter: {term: count}

    For text "曹星走路" with min=2, max=4:
      {"曹星": 1, "曹星走": 1, "曹星走路": 1, "星走": 1, "星走路": 1, "走路": 1}

    Callers should filter by frequency (min_occurrences >= 2) to keep
    meaningful terms. The overlap is intentional — it catches terms that
    appear in different contexts throughout the chapter.
    """
    counts: Counter = Counter()
    # Match runs of CJK characters
    cjk_runs = re.findall(r'[\u4e00-\u9fff]+', text)
    for run in cjk_runs:
        # For each position, extract substrings of min_len..max_len chars
        n = len(run)
        for i in range(n):
            for length in range(min_len, max_len + 1):
                if i + length > n:
                    break
                term = run[i:i + length]
                counts[term] += 1
    return counts


def load_glossary_source_set() -> set[str]:
    """Load all CN source terms from glossary.yml (locked + reference + auto)."""
    return {t['source'] for t in load_terms()}


def load_dynamic_bans() -> set[str]:
    """Load banned CN terms (use as-is, don't translate).

    dynamic_bans.md format:
      ## Banned (auto)
      - 领主
      - 香江
    """
    if not DYNAMIC_BANS_FILE.exists():
        return set()
    bans = set()
    in_banned = False
    for line in DYNAMIC_BANS_FILE.read_text(encoding='utf-8').splitlines():
        if 'Banned (auto)' in line:
            in_banned = True
            continue
        if in_banned and line.startswith('## '):  # next section
            break
        if in_banned:
            m = re.match(r'[-\s]*([\u4e00-\u9fff]{2,})', line)
            if m:
                bans.add(m.group(1))
    return bans


def scan_chapter(num: int, min_occurrences: int = 2) -> dict:
    """Scan source chapter N for CN terms.

    Returns dict:
      {
        'num': N,
        'source_chars': int,
        'cn_char_count': int,
        'terms_total': int,        # unique CN sequences
        'terms_known': [...],      # in glossary
        'terms_banned': [...],     # in dynamic_bans
        'terms_new': [...],        # NOT in glossary or bans
        'gate_passed': bool,       # True if no new terms
      }
    """
    src_path = SOURCE_DIR / f'{num:04d}.md'
    if not src_path.exists():
        return {'error': f'Source not found: {src_path}', 'num': num}

    text = src_path.read_text(encoding='utf-8')
    terms = extract_cn_terms(text)
    # Filter: min occurrences AND not in stopwords
    frequent = {t: c for t, c in terms.items()
                if c >= min_occurrences and t not in STOPWORDS}

    glossary = load_glossary_source_set()
    bans = load_dynamic_bans()

    known = sorted([(t, c) for t, c in frequent.items() if t in glossary],
                   key=lambda x: -x[1])
    banned = sorted([(t, c) for t, c in frequent.items() if t in bans],
                    key=lambda x: -x[1])

    # Filter out "new" terms that are substrings of known glossary terms.
    # extract_cn_terms generates all overlapping 2-4 char substrings,
    # so a known term like "曹星" produces noise like "曹星走", "星走".
    # Remove candidates that are partial matches of any known term:
    #   - term is a proper substring of a known term, OR
    #   - a known term is a proper substring of term
    known_for_noise = {g for g in glossary if len(g) >= 2}
    def is_substring_noise(term: str) -> bool:
        """Return True if `term` partially overlaps any known glossary term."""
        for g in known_for_noise:
            if term == g:
                continue
            if term in g or g in term:
                return True
        return False

    new = sorted([(t, c) for t, c in frequent.items()
                  if t not in glossary and t not in bans
                  and not is_substring_noise(t)],
                 key=lambda x: -x[1])

    return {
        'num': num,
        'source_chars': len(text),
        'cn_char_count': len(re.findall(r'[\u4e00-\u9fff]', text)),
        'terms_total': len(terms),
        'terms_frequent': len(frequent),
        'min_occurrences': min_occurrences,
        'terms_known': known,
        'terms_banned': banned,
        'terms_new': new,
        'gate_passed': len(new) == 0,
    }


def suggest_glossary_entry(term: str, num: int) -> str:
    """Suggest a glossary entry for a new CN term.

    Looks for previous chapters' translations of this term in the
    registry (if any) — else suggests a placeholder.
    """
    # Future: search registry for previous usage
    return f'  - source: \'{term}\'\n    thai: \'??? NEEDS TRANSLATION\'\n    category: \'ทั่วไป\'\n    priority: \'3\'\n    lock: \'auto\'\n'


def format_report(result: dict, suggest: bool = False) -> str:
    """Pretty-print gate result."""
    if 'error' in result:
        return f"❌ {result['error']}"

    lines = [
        f"=== ch {result['num']}: Glossary Gate ===",
        f"Source: {result['source_chars']:,} chars "
        f"({result['cn_char_count']:,} CN, {result['terms_total']} unique 2-4 char terms)",
        f"Scanning terms with ≥{result['min_occurrences']} occurrences "
        f"({result['terms_frequent']} terms)",
        '',
    ]

    if result['terms_known']:
        lines.append(f"✅ Known ({len(result['terms_known'])}):")
        for term, count in result['terms_known'][:15]:
            lines.append(f"  - {term} ({count}x)")
        if len(result['terms_known']) > 15:
            lines.append(f"  ... +{len(result['terms_known']) - 15} more")
        lines.append('')

    if result['terms_banned']:
        lines.append(f"🚫 Banned — use as-is ({len(result['terms_banned'])}):")
        for term, count in result['terms_banned'][:10]:
            lines.append(f"  - {term} ({count}x)")
        lines.append('')

    if result['terms_new']:
        lines.append(f"🆕 NEW — not in glossary ({len(result['terms_new'])}):")
        for term, count in result['terms_new']:
            lines.append(f"  - {term} ({count}x)")
        if suggest:
            lines.append('')
            lines.append('Suggested glossary entries:')
            for term, _ in result['terms_new']:
                lines.append(suggest_glossary_entry(term, result['num']))
        lines.append('')

    if result['gate_passed']:
        lines.append('✅ GATE PASSED — all terms known')
    else:
        lines.append(f"❌ GATE FAILED — {len(result['terms_new'])} new terms need glossary entries")
        lines.append('')
        lines.append('How to fix:')
        lines.append(f'  1. Add new terms to: {GLOSSARY_DIR.relative_to(NOVEL_ROOT)}/locked.md or reference.md')
        lines.append(f"  2. Run: python tools/build_yaml.py  (regenerates glossary.yml)")
        lines.append(f"  3. Re-run: python tools/glossary_gate.py {result['num']}")

    return '\n'.join(lines)


def gate_all_untranslated() -> list[dict]:
    """Find all source chapters without a .json translation and gate them."""
    results = []
    for src in sorted(SOURCE_DIR.glob('0*.md')):
        num = int(src.stem)
        json_path = CHAPTERS_DIR / f'{num:04d}.json'
        if json_path.exists():
            continue  # already translated
        results.append(scan_chapter(num))
    return results


def main():
    p = argparse.ArgumentParser(description='Glossary gate (pre-translate guard)')
    p.add_argument('chapter', nargs='?', type=int, help='Chapter number to gate')
    p.add_argument('--suggest', action='store_true',
                   help='Also print suggested glossary entries for new terms')
    p.add_argument('--strict', action='store_true',
                   help='Also fail on terms with 1 occurrence (default: 2+)')
    p.add_argument('--min-occ', type=int, default=2,
                   help='Minimum occurrences to consider a term (default: 2)')
    p.add_argument('--all', action='store_true',
                   help='Gate all untranslated chapters')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    args = p.parse_args()

    min_occ = 1 if args.strict else args.min_occ

    if args.all:
        results = gate_all_untranslated()
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            failed = 0
            for r in results:
                print(format_report(r, suggest=args.suggest))
                print()
                if not r.get('gate_passed', False):
                    failed += 1
            print('━' * 60)
            print(f'  Gated {len(results)} chapters, {failed} failed')
            print('━' * 60)
            sys.exit(1 if failed > 0 else 0)
    elif args.chapter is not None:
        result = scan_chapter(args.chapter, min_occurrences=min_occ)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_report(result, suggest=args.suggest))
        if 'error' in result:
            sys.exit(2)
        sys.exit(0 if result.get('gate_passed', False) else 1)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
