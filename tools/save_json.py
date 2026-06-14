"""save_json.py — Save chapter JSON with auto schema validation.

Mika แปลเอง → save as chapters/NNNN.json → schema validates automatically.

Usage:
    python tools/save_json.py 113                # validate + save ch 113 JSON
    python tools/save_json.py 113 --strict       # block on warnings too
    python tools/save_json.py 113 --dry-run      # validate only, don't save

Pipeline:
  1. Read chapters/NNNN.json
  2. Run schema validation (Pydantic)
  3. Run glossary doctor (transmittor principle: detect, don't fix)
  4. Block on errors; show warnings/info
  5. Save to chapters/fts_index.db (if not dry-run)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import CHAPTERS_DIR  # noqa: E402
from schema import Chapter, load_chapter, save_chapter  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapter', type=int, help='Chapter number to save')
    ap.add_argument('--strict', action='store_true', help='Block on warnings too')
    ap.add_argument('--dry-run', action='store_true', help='Validate only, do not save')
    ap.add_argument('--from-md', action='store_true', help='Read from .md then convert')
    args = ap.parse_args()

    ch = args.chapter
    json_path = CHAPTERS_DIR / f'{ch:04d}.json'
    md_path = CHAPTERS_DIR / f'{ch:04d}.md'

    if args.from_md:
        if not md_path.exists():
            print(f'❌ ch{ch}: .md not found at {md_path}')
            sys.exit(1)
        # Use migration tool
        sys.path.insert(0, str(Path(__file__).parent))
        from migrate_to_json import migrate
        ok, msg = migrate(ch, dry_run=True)
        if not ok:
            print(f'❌ ch{ch}: .md migration failed: {msg}')
            sys.exit(1)
        # Re-migrate to get the data (dry_run doesn't return it)
        # Read the .json that would have been written
        json_tmp = CHAPTERS_DIR / f'{ch:04d}.json'
        if not json_tmp.exists():
            ok2, msg2 = migrate(ch, dry_run=False)
            if not ok2:
                print(f'❌ ch{ch}: migrate failed: {msg2}')
                sys.exit(1)
        validated = load_chapter(json_tmp)
    else:
        if not json_path.exists():
            print(f'❌ ch{ch}: .json not found at {json_path}')
            sys.exit(1)
        validated = load_chapter(json_path)

    # 1. Schema validate (validated already set above)
    print(f'✓ ch{ch} schema valid ({len(validated.blocks)} blocks, title="{validated.title}")')

    # 2. Run doctor (transmittor principle: detect, don't fix)
    try:
        from glossary_doctor import load_glossary, validate_chapter
        glossary, alias_map, style_rules = load_glossary()
        issues = validate_chapter(ch, glossary, alias_map, style_rules, log_to_db=False)
    except Exception as e:
        issues = []
        print(f'⚠️  Doctor unavailable: {e}')

    errors = [i for i in issues if i.get('severity') == 'error']
    warnings = [i for i in issues if i.get('severity') == 'warning']
    info = [i for i in issues if i.get('severity') == 'info']

    print(f'📋 ch{ch} doctor: ❌{len(errors)} ⚠️{len(warnings)} ℹ️{len(info)}')

    if errors:
        print(f'\n❌ ch{ch} BLOCKED — fix errors first:')
        for e in errors:
            print(f'   {e.get("rule_type", "?")}: {e.get("pattern", "")[:80]}')
            if e.get('explanation'):
                print(f'      Why: {e["explanation"][:100]}')
        sys.exit(1)

    if warnings and args.strict:
        print(f'\n⚠️  ch{ch} BLOCKED (--strict) — fix warnings:')
        for w in warnings[:5]:
            print(f'   {w.get("rule_type", "?")}: {w.get("pattern", "")[:80]}')
        sys.exit(2)

    if warnings:
        print(f'\n⚠️  ch{ch} has {len(warnings)} warning(s) (transmittor — report, don\'t fix):')
        for w in warnings[:5]:
            print(f'   {w.get("rule_type", "?")}: {w.get("pattern", "")[:80]}')

    if info:
        print(f'ℹ️  ch{ch} info: {len(info)} notes')

    # 3. Save (unless dry-run)
    if args.dry_run:
        print(f'\n[dry-run] would save to {json_path}')
    else:
        save_chapter(validated, json_path)
        print(f'\n✓ ch{ch} saved → {json_path.name}')


if __name__ == '__main__':
    main()
