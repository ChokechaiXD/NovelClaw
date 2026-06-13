"""glossary_stats.py — Report glossary term usage statistics.

Scans all translated chapters and counts how often each glossary term is used.
Identifies:
  - Stale terms (0-1 uses) — candidates for pruning
  - Over-broad terms (50+ uses) — might be in the wrong tier
  - Tier imbalances

Usage:
  python glossary_stats.py                    # full report
  python glossary_stats.py --tier auto         # only one tier
  python glossary_stats.py --top 20            # show top 20 by usage
  python glossary_stats.py --stale             # only stale (0-1 uses) terms
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT  # noqa: E402

ROOT = NOVEL_ROOT
GLOSSARY_DIR = ROOT / 'glossary'
CHAPTERS_DIR = ROOT / 'chapters'

TIERS = ('locked', 'reference', 'auto')


def parse_glossary(tier: str) -> list[dict]:
    """Return list of {'source', 'thai', 'notes'} dicts for a tier."""
    path = GLOSSARY_DIR / f'{tier}.md'
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('| ') or line.startswith('|--') or 'Source' in line or 'Category' in line:
            continue
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 6 and cells[1] and cells[1] != '-':
            entries.append({
                'source': cells[1],
                'thai': cells[2],
                'notes': cells[5] if len(cells) > 5 else '',
            })
    return entries


def count_term_uses() -> dict[str, int]:
    """Count occurrences of each glossary term across all translated chapters.

    Strategy: for each Source term, count literal substring matches in the Thai body.
    Returns: dict mapping term -> use_count.
    """
    chapters = sorted(f for f in CHAPTERS_DIR.glob('[0-9]*.md') if f.is_file())
    # NOTE: explicitly scan chapters/ root only. Source files live in
    # chapters/source/ so they're already excluded by the non-recursive glob,
    # but pin the contract here in case the source layout changes.
    # Without this, a future refactor that moves source/*.md to chapters/
    # would silently double-count term usage.
    if not chapters:
        print('No translated chapters found.', file=sys.stderr)
        return {}

    # Build master text from all chapters
    master = ''
    for c in chapters:
        master += c.read_text(encoding='utf-8') + '\n'

    counts: dict[str, int] = {}
    for tier in TIERS:
        for e in parse_glossary(tier):
            term = e['thai']
            if not term or len(term) < 2:
                continue
            # count substring occurrences
            counts[(tier, term)] = master.count(term)
    return counts


def main():
    parser = argparse.ArgumentParser(description='Glossary usage statistics.')
    parser.add_argument('--tier', choices=TIERS, help='Show only this tier')
    parser.add_argument('--top', type=int, help='Show only top N by usage')
    parser.add_argument('--stale', action='store_true', help='Show only stale (0-1 use) terms')
    args = parser.parse_args()

    counts = count_term_uses()

    # Group by tier
    by_tier: dict[str, list[tuple[str, int]]] = {t: [] for t in TIERS}
    for (tier, term), n in counts.items():
        by_tier[tier].append((term, n))

    print('━' * 65)
    print(f'  Glossary usage statistics — global-descent')
    print('━' * 65)

    tiers_to_show = [args.tier] if args.tier else TIERS
    for tier in tiers_to_show:
        items = sorted(by_tier[tier], key=lambda x: -x[1])
        total = len(items)
        unused = sum(1 for _, n in items if n == 0)
        once = sum(1 for _, n in items if n == 1)
        heavy = sum(1 for _, n in items if n >= 50)

        print(f'\n  {tier}.md: {total} terms')
        print(f'    unused (0 uses):  {unused}')
        print(f'    used 1 time:     {once}')
        print(f'    used 50+ times:   {heavy}  (← these might be in wrong tier; should be locked)')

        if args.stale:
            items = [i for i in items if i[1] <= 1]

        if args.top:
            items = items[:args.top]

        for term, n in items[:15]:
            bar = '█' * min(n, 40)
            print(f'    {n:5d}  {term:40}  {bar}')
        if len(items) > 15 and not args.stale and not args.top:
            print(f'    ... and {len(items) - 15} more')

    print()
    print('━' * 65)
    total_terms = sum(len(by_tier[t]) for t in TIERS)
    total_unused = sum(1 for t in TIERS for _, n in by_tier[t] if n == 0)
    print(f'  Total: {total_terms} terms, {total_unused} unused ({100*total_unused/total_terms:.0f}%)')
    print('━' * 65)


if __name__ == '__main__':
    main()
