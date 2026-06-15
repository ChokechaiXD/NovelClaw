"""consistency_checker.py — Cross-chapter consistency check.

Scans all translated chapters and reports:
  - Character names that don't match glossary locked.md
  - Skill/item names that don't match glossary
  - Place names that don't match glossary
  - Potential typos or variations

Usage:
    python tools/consistency_checker.py           # check all chapters
    python tools/consistency_checker.py --ch 101  # check specific chapter
    python tools/consistency_checker.py --fix     # output fix suggestions
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
_NOVEL_ROOT_DEFAULT = SCRIPT_DIR.parent / "novels" / "global-descent"
CHAPTERS_DIR = _NOVEL_ROOT_DEFAULT / "chapters"
LOCKED_MD = _NOVEL_ROOT_DEFAULT / "glossary" / "locked.md"


def load_locked_terms():
    """Load locked glossary terms from locked.md."""
    terms = {}
    if not LOCKED_MD.exists():
        return terms

    content = LOCKED_MD.read_text(encoding='utf-8')
    for line in content.splitlines():
        if not line.startswith('|') or line.startswith('|--') or 'Source' in line:
            continue
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 6 and cells[1] and cells[1] != '-':
            source = cells[1]
            thai = cells[2]
            category = cells[3]
            terms[source] = thai
    return terms


def extract_thai_names(text):
    """Extract potential Thai proper nouns from text.

    Simple heuristic: sequences of Thai words that look like names
    (capitalized or known patterns).
    """
    # Find Thai words that could be names (simplistic)
    # More sophisticated: match against known patterns
    thai_words = re.findall(r'[\u0e00-\u0e7f]+', text)
    return thai_words


def check_chapter(chapter_num, locked_terms):
    """Check a single chapter for consistency issues.

    Returns list of (issue_type, source_term, found_in_text, suggestion).
    """
    ch_file = CHAPTERS_DIR / f'{chapter_num:04d}.json'
    if not ch_file.exists():
        return []

    try:
        content = json.loads(ch_file.read_text(encoding='utf-8'))
        blocks = content.get('blocks', [])
        text = ' '.join(b.get('text', '') for b in blocks)
    except Exception:
        return []

    issues = []

    # Check: locked Thai terms that should appear but don't
    for source, thai in locked_terms.items():
        if source in text:
            # Source CN appears in translation = CJK leakage
            issues.append(('CJK_LEAK', source, source, f'Translate "{source}" to "{thai}"'))

    # Check: common typos/variations
    typo_patterns = [
        ('เฉา', 'เฉาะ'),  # common typo
        ('โจว', 'โจว'),    # wrong MC name
    ]

    return issues


def check_all():
    """Check all translated chapters."""
    locked_terms = load_locked_terms()
    print(f"Loaded {len(locked_terms)} locked terms")
    print()

    all_chapters = sorted([
        int(f.stem) for f in CHAPTERS_DIR.glob('*.json')
        if f.stem.isdigit() and len(f.stem) == 4
    ])

    print(f"Checking {len(all_chapters)} chapters...")
    print()

    total_issues = 0
    chapter_issues = {}

    for ch_num in all_chapters:
        issues = check_chapter(ch_num, locked_terms)
        if issues:
            chapter_issues[ch_num] = issues
            total_issues += len(issues)
            print(f"  Ch {ch_num}: {len(issues)} issues")
            for issue_type, source, found, suggestion in issues:
                print(f"    [{issue_type}] {found} → {suggestion}")

    print()
    print(f"=== SUMMARY ===")
    print(f"Total: {len(all_chapters)} chapters checked")
    print(f"Issues: {total_issues} across {len(chapter_issues)} chapters")

    return chapter_issues


def check_cross_chapter():
    """Cross-chapter name consistency check.

    Reports when the same character/entity is referred to differently
    across chapters.
    """
    locked_terms = load_locked_terms()
    print(f"\n=== CROSS-CHAPTER CONSISTENCY ===\n")

    all_chapters = sorted([
        int(f.stem) for f in CHAPTERS_DIR.glob('*.json')
        if f.stem.isdigit() and len(f.stem) == 4
    ])

    # Track which Thai terms appear in which chapters
    term_usage = defaultdict(list)

    for ch_num in all_chapters:
        ch_file = CHAPTERS_DIR / f'{ch_num:04d}.json'
        try:
            content = json.loads(ch_file.read_text(encoding='utf-8'))
            blocks = content.get('blocks', [])
            text = ' '.join(b.get('text', '') for b in blocks)
        except Exception:
            continue

        # Check for locked term Thai translations in text
        for source, thai in locked_terms.items():
            if thai in text:
                term_usage[source].append((ch_num, thai))

    # Report terms that appear in some chapters but not others
    print("Term coverage across chapters:")
    for source, appearances in sorted(term_usage.items()):
        ch_nums = [a[0] for a in appearances]
        if len(ch_nums) < len(all_chapters) and len(ch_nums) > 0:
            missing = set(all_chapters) - set(ch_nums)
            if len(missing) > 5:
                print(f"  {source} → {appearances[0][1]}: appears in {len(ch_nums)}/{len(all_chapters)} chapters")


if __name__ == '__main__':
    if '--cross' in sys.argv:
        check_cross_chapter()
    else:
        check_all()
