"""save_chapter.py — Auto-validate chapter on save.

Wraps the translation save flow with auto-doctor:
  1. Run glossary_doctor on the new ch
  2. If errors → BLOCK save (must fix first)
  3. If warnings → save anyway, but log to doctor_log + show summary
  4. Update ch_meta.validation_status

Usage:
  python tools/save_chapter.py 112                  # validate ch 112
  python tools/save_chapter.py 112 --strict         # block on warnings too
  python tools/save_chapter.py 112 --fix-suggestions  # show fix hints

Exit codes:
  0 = saved (clean or warnings-only)
  1 = save blocked (errors)
  2 = strict mode blocked (warnings)
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import CHAPTERS_DIR, GLOSSARY_DIR  # noqa: E402
from glossary_doctor import (  # noqa: E402
    load_glossary, validate_chapter, print_fix_hints
)

DB_PATH = GLOSSARY_DIR / 'glossary.db'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapter', type=int, help='Chapter number to validate')
    ap.add_argument('--strict', action='store_true', help='Block on warnings too')
    ap.add_argument('--fix-suggestions', action='store_true', help='Show fix hints')
    ap.add_argument('--gate-only', action='store_true', help='CI gate — no DB write')
    args = ap.parse_args()

    ch = args.chapter
    ch_path = CHAPTERS_DIR / f'{ch:04d}.md'
    if not ch_path.exists():
        print(f'❌ ch{ch}: file not found at {ch_path}')
        sys.exit(1)

    glossary, alias_map, style_rules = load_glossary()
    issues = validate_chapter(ch, glossary, alias_map, style_rules,
                              log_to_db=not args.gate_only)
    errors = [i for i in issues if i.get('severity') == 'error']
    warnings = [i for i in issues if i.get('severity') == 'warning']
    info = [i for i in issues if i.get('severity') == 'info']

    print(f'\n📋 ch{ch} doctor summary:')
    print(f'   ❌ errors:   {len(errors)}')
    print(f'   ⚠️  warnings: {len(warnings)}')
    print(f'   ℹ️  info:     {len(info)}')

    if errors:
        print(f'\n❌ ch{ch} BLOCKED — fix errors first:')
        for e in errors:
            print(f'   {e["rule_type"]}: {e.get("pattern", "")[:80]}')
            if e.get('explanation'):
                print(f'      Why: {e["explanation"][:100]}')
            if e.get('fix'):
                print(f'      → {e["fix"]}')
        if args.fix_suggestions:
            print_fix_hints(ch, issues)
        sys.exit(1)
    elif warnings and args.strict:
        print(f'\n⚠️  ch{ch} BLOCKED (--strict) — fix warnings:')
        for w in warnings[:10]:
            print(f'   {w["rule_type"]}: {w.get("pattern", "")[:80]}')
        sys.exit(2)
    else:
        if warnings:
            print(f'\n⚠️  ch{ch} saved with {len(warnings)} warning(s) — review when you can:')
            for w in warnings[:5]:
                print(f'   {w["rule_type"]}: {w.get("pattern", "")[:80]}')
            if len(warnings) > 5:
                print(f'   ... and {len(warnings) - 5} more')
        else:
            print(f'\n✓ ch{ch} clean — ready to commit')
        if args.fix_suggestions and issues:
            print_fix_hints(ch, issues)
        sys.exit(0)


if __name__ == '__main__':
    main()
