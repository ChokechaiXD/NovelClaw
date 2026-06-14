"""novelclaw.py — Unified CLI for the NovelClaw project.

Single entry point. Discovers and dispatches to existing tools.

Usage:
  python novelclaw.py status                    # show translation progress + glossary stats
  python novelclaw.py prep [N]                  # pre_chapter.py for next (or Nth) chapter
  python novelclaw.py validate [N]               # validate_chapter.py for last (or Nth) chapter
  python novelclaw.py validate N --fix          # apply mechanical fixes + re-validate
  python novelclaw.py validate --cjk [N...]     # CJK leakage check (all or specific chapters)
  python novelclaw.py candidates                 # find chapters that may need re-translation
  python novelclaw.py backup [--list]            # create or list zip snapshots
  python novelclaw.py clean [N...]              # check source for scrape artifacts
  python novelclaw.py stats                      # glossary usage statistics
  python novelclaw.py review N [--context]       # generate Tier-2 review checklist for ch N
  python novelclaw.py health                     # quick health: candidates + cjk + stale glossary
  python novelclaw.py scrape                     # scrape source chapters
  python novelclaw.py test [-v]                  # run pytest suite (validates parse + auto_fix)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
NOVEL = 'global-descent'


def cmd_status():
    """Show translation progress + glossary stats."""
    p = ROOT / 'novels' / NOVEL / 'progress.md'
    if not p.exists():
        print('progress.md not found')
        return
    text = p.read_text(encoding='utf-8')
    import re
    m = re.search(r'Last translated:\*\* ch (\d+)', text)
    last = int(m.group(1)) if m else 0
    # Look for "/ 1,239" or "/1239" in the progress line (e.g. "31/1,239 (2.50%)")
    m2 = re.search(r'(?:Total\s+)?[Pp]rogress:?\s*(\d+)\s*/\s*([\d,]+)', text)
    if m2:
        done, total_raw = int(m2.group(1)), m2.group(2).replace(',', '')
        total = int(total_raw)
    else:
        done = total = 0

    # Glossary
    gdir = ROOT / 'novels' / NOVEL / 'glossary'
    counts = {}
    for tier in ('locked.md', 'reference.md', 'auto.md'):
        path = gdir / tier
        if not path.exists():
            counts[tier] = 0
            continue
        n = 0
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('| ') and not line.startswith('|--') and 'Source' not in line and 'Category' not in line:
                n += 1
        counts[tier] = n

    print('━' * 60)
    print(f'  NovelClaw status — {NOVEL}')
    print('━' * 60)
    print(f'  Last translated: ch {last}')
    print(f'  Progress:        {done}/{total} ({100*done/total:.2f}%)' if total else f'  Progress:        {done}/???')
    print(f'  Next chapter:    ch {last + 1}')
    print()
    print(f'  Glossary:')
    for tier, n in counts.items():
        print(f'    {tier:14} {n:4} terms')
    print(f'    {"total":14} {sum(counts.values()):4} terms')
    print()
    remaining = total - done
    if done > 0:
        print(f'  Remaining: {remaining} chapters')
    print('━' * 60)


def cmd_prep(n=None):
    args = [sys.executable, str(ROOT / 'tools' / 'pre_chapter.py')]
    if n is not None:
        args.append(str(n))
    sys.exit(subprocess.call(args))


def cmd_validate(n=None, fix=False):
    args = [sys.executable, str(ROOT / 'tools' / 'validate_chapter.py')]
    if n is not None:
        args.append(str(n))
    if fix:
        args.append('--fix')
    sys.exit(subprocess.call(args))


def cmd_candidates():
    args = [sys.executable, str(ROOT / 'tools' / 'find_candidates.py')]
    sys.exit(subprocess.call(args))


def cmd_validate_cjk(chapters=None):
    """Run tools/validate_no_cjk.py to check for source-language leakage."""
    args = [sys.executable, str(ROOT / 'tools' / 'validate_no_cjk.py')]
    if chapters:
        args.extend(str(c) for c in chapters)
    else:
        args.append('--all')
    sys.exit(subprocess.call(args))


def cmd_scrape():
    """Re-scrape chapters from source. Passes through --list/--ch/--missing/--all."""
    args = [sys.executable, str(ROOT / 'tools' / 'rescrape_chapters.py')]
    passthrough = [a for a in sys.argv[2:] if a != 'scrape']
    args.extend(passthrough)
    sys.exit(subprocess.call(args))


def cmd_backup():
    args = [sys.executable, str(ROOT / 'tools' / 'backup.py')]
    passthrough = []
    if '--list' in sys.argv:
        passthrough.append('--list')
    args.extend(passthrough)
    sys.exit(subprocess.call(args))


def cmd_clean(chapters):
    args = [sys.executable, str(ROOT / 'tools' / 'clean_source.py')]
    if chapters:
        args.extend(str(c) for c in chapters)
    if '--strict' in sys.argv:
        args.append('--strict')
    sys.exit(subprocess.call(args))


def cmd_stats():
    args = [sys.executable, str(ROOT / 'tools' / 'glossary_stats.py')]
    passthrough = [a for a in sys.argv[2:] if a not in ('stats',)]
    args.extend(passthrough)
    sys.exit(subprocess.call(args))


def cmd_review(chapters):
    args = [sys.executable, str(ROOT / 'tools' / 'review_chapter.py')]
    args.extend(str(c) for c in chapters)
    if '--context' in sys.argv:
        args.append('--context')
    if '--checklist' in sys.argv:
        args.append('--checklist')
    sys.exit(subprocess.call(args))


def cmd_test(verbose=False):
    """Run pytest suite. Verifies parse helpers + auto_fix logic."""
    args = [sys.executable, '-m', 'pytest', str(ROOT / 'tests')]
    if verbose or '-v' in sys.argv:
        args.append('-v')
    sys.exit(subprocess.call(args))


def cmd_learn():
    """Phase 3: scan translated chapters, auto-update dynamic ban list.

    Usage:
        python novelclaw.py learn               # scan all + update dynamic_bans.md
        python novelclaw.py learn --dry-run     # preview candidates only
        python novelclaw.py learn --chapter 100 # scan single chapter
    """
    args = [sys.executable, str(ROOT / 'tools' / 'learn_slop.py')]
    # Forward all flags/args (--dry-run, --chapter N, --top N, etc.)
    args.extend(a for a in sys.argv[2:] if a != 'learn')
    sys.exit(subprocess.call(args))


def cmd_search_index():
    """Phase 4: build/rebuild FTS5 index over translated chapters."""
    args = [sys.executable, str(ROOT / 'tools' / 'chapter_search.py'), 'index']
    sys.exit(subprocess.call(args))


def cmd_search(query=None, limit=5):
    """Phase 4: search translated chapters by CN/TH/EN name or concept."""
    args = [sys.executable, str(ROOT / 'tools' / 'chapter_search.py'), 'search']
    if query:
        args.append(query)
    args += ['--limit', str(limit)]
    sys.exit(subprocess.call(args))


def cmd_audit(chapter=None, all_chapters=False):
    """Phase 1: generate 5-Phase CoT audit log for chapter(s)."""
    args = [sys.executable, str(ROOT / 'tools' / 'audit.py')]
    if all_chapters:
        args.append('--all')
        args.append('--update')  # Always update when running --all
    elif chapter:
        args.append(str(chapter))
        args.append('--update')  # Save audit.md when running single ch
    else:
        print('Usage: python novelclaw.py audit N | --all')
        sys.exit(1)
    sys.exit(subprocess.call(args))


def cmd_npc(*args_list):
    """Phase 2: NPC dossier bank — extract / list / inject / add."""
    args = [sys.executable, str(ROOT / 'tools' / 'npc_bank.py')]
    args.extend(args_list)
    sys.exit(subprocess.call(args))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sub = sys.argv[1]
    if sub == 'status':
        cmd_status()
    elif sub == 'prep':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_prep(n)
    elif sub == 'validate':
        # Two modes: chapter quality (existing) or CJK check (--cjk flag)
        if '--cjk' in sys.argv:
            args = [a for a in sys.argv[2:] if a != '--cjk']
            chapters = [int(a) for a in args if a.isdigit()] or None
            cmd_validate_cjk(chapters)
        else:
            fix = '--fix' in sys.argv
            args = [a for a in sys.argv[2:] if a != '--fix']
            n = int(args[0]) if args else None
            cmd_validate(n, fix=fix)
    elif sub == 'candidates':
        cmd_candidates()
    elif sub == 'scrape':
        cmd_scrape()
    elif sub == 'backup':
        cmd_backup()
    elif sub == 'clean':
        chapters = [int(a) for a in sys.argv[2:] if a.isdigit()]
        cmd_clean(chapters)
    elif sub == 'stats':
        cmd_stats()
    elif sub == 'review':
        chapters = [int(a) for a in sys.argv[2:] if a.isdigit()]
        if not chapters:
            print('Usage: python novelclaw.py review N [N...] [--context] [--checklist]')
            sys.exit(1)
        cmd_review(chapters)
    elif sub == 'health':
        # Quick health check: candidates + cjk + stale glossary
        print('━' * 60)
        print('  NovelClaw health check')
        print('━' * 60)
        cmd_candidates()
        print()
        cmd_validate_cjk(None)
        print()
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'glossary_stats.py'), '--stale', '--top', '10'])
    elif sub == 'test':
        cmd_test()
    elif sub == 'learn':
        cmd_learn()
    elif sub == 'search-index':
        cmd_search_index()
    elif sub == 'search':
        # search QUERY [--limit N]
        args = sys.argv[2:]
        query = args[0] if args and not args[0].startswith('--') else None
        limit = 5
        if '--limit' in args:
            i = args.index('--limit')
            if i + 1 < len(args):
                limit = int(args[i + 1])
        if not query:
            print('Usage: python novelclaw.py search "蕾妮絲 ฮอว์อาย" [--limit 5]')
            sys.exit(1)
        cmd_search(query, limit)
    elif sub == 'audit':
        if '--all' in sys.argv[2:]:
            cmd_audit(all_chapters=True)
        else:
            args = sys.argv[2:]
            n = int(args[0]) if args and args[0].isdigit() else None
            if not n:
                print('Usage: python novelclaw.py audit N | --all')
                sys.exit(1)
            cmd_audit(chapter=n)
    elif sub == 'npc':
        cmd_npc(*sys.argv[2:])
    else:
        print(f'Unknown subcommand: {sub}')
        print('Available: status, prep, validate [--cjk|chapter], candidates, scrape,')
        print('             backup, clean, stats, review, health, test,')
        print('             learn, search-index, search, audit, npc')
        sys.exit(1)


if __name__ == '__main__':
    main()
