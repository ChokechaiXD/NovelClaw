"""save_chapter.py — Unified chapter save + validate (replaces save_chapter.py + save_json.py).

Pipeline:
  1. Read chapter (.json canonical, .md legacy fallback)
  2. Schema validate (Pydantic) — JSON only; MD gets basic checks
  3. Glossary doctor (transmittor: detect, don't fix)
  4. Block on errors; report warnings
  5. Save (JSON format, with FTS index update)

Usage:
    python tools/save_chapter.py 113                  # validate + save
    python tools/save_chapter.py 113 --dry-run        # validate only
    python tools/save_chapter.py 113 --strict         # block on warnings too
    python tools/save_chapter.py 113 --from-md        # migrate .md → .json first
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import CHAPTERS_DIR, GLOSSARY_DIR

DB_PATH = GLOSSARY_DIR / 'glossary.db'


def main():
    ap = argparse.ArgumentParser(description='Save + validate chapter')
    ap.add_argument('chapter', type=int, help='Chapter number')
    ap.add_argument('--dry-run', action='store_true', help='Validate only, do not save')
    ap.add_argument('--strict', action='store_true', help='Block on warnings too')
    ap.add_argument('--from-md', action='store_true', help='Read from .md then convert to .json')
    args = ap.parse_args()

    ch = args.chapter
    json_path = CHAPTERS_DIR / f'{ch:04d}.json'
    md_path = CHAPTERS_DIR / f'{ch:04d}.md'

    # ── Resolve input file ────────────────────────────────────────────
    if args.from_md:
        if not md_path.exists():
            print(f'❌ ch{ch}: .md not found at {md_path}')
            sys.exit(1)
        # Use migration tool
        from migrate_to_json import migrate
        ok, msg = migrate(ch, dry_run=False)
        if not ok:
            print(f'❌ ch{ch}: migrate failed: {msg}')
            sys.exit(1)
        input_path = json_path
    elif json_path.exists():
        input_path = json_path
    elif md_path.exists():
        input_path = md_path
    else:
        print(f'❌ ch{ch}: no chapter file found (.json or .md)')
        sys.exit(1)

    # ── Schema validation (JSON only) ────────────────────────────────
    if input_path.suffix == '.json':
        from schema import Chapter, load_chapter as _load, save_chapter as _save
        try:
            validated = _load(input_path)
            print(f'✓ ch{ch} schema valid ({len(validated.blocks)} blocks, title="{validated.title}")')
        except Exception as e:
            print(f'❌ ch{ch} schema error: {e}')
            sys.exit(1)
    else:
        # MD: basic checks only (no Pydantic schema)
        content = input_path.read_text(encoding='utf-8')
        lines = content.splitlines()
        validated = None
        print(f'✓ ch{ch} MD loaded ({len(lines)} lines, basic checks only)')

    # ── Glossary doctor ───────────────────────────────────────────────
    issues = []
    try:
        from glossary_doctor import load_glossary, validate_chapter as _doctor
        glossary, alias_map, style_rules = load_glossary()
        issues = _doctor(ch, glossary, alias_map, style_rules, log_to_db=False)
    except Exception as e:
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
        for w in warnings[:5]:
            print(f'   ⚠ {w.get("rule_type", "?")}: {w.get("pattern", "")[:80]}')

    # ── Save ──────────────────────────────────────────────────────────
    if args.dry_run:
        print(f'\n[dry-run] would save to {json_path.name}')
    else:
        if validated is not None:
            _save(validated, json_path)
            # Also save to FTS index
            try:
                save_to_fts(validated, ch)
            except Exception:
                pass
            print(f'\n✓ ch{ch} saved → {json_path.name}')
        else:
            # MD: just validate, no save
            print(f'\n✓ ch{ch} validated (MD — no save)')


def save_to_fts(chapter, ch_num: int):
    """Update FTS index for this chapter."""
    try:
        import sqlite3
        fts_db = GLOSSARY_DIR.parent / 'chapters' / 'fts_index.db'
        conn = sqlite3.connect(str(fts_db))
        conn.execute('DELETE FROM chapters WHERE num = ?', (ch_num,))
        for block in chapter.blocks:
            text = getattr(block, 'text', str(block))
            if text:
                conn.execute(
                    'INSERT INTO chapters (num, type, text) VALUES (?, ?, ?)',
                    (ch_num, block.__class__.__name__, text[:2000])
                )
        conn.commit()
        conn.close()
    except Exception:
        pass  # FTS is optional


if __name__ == '__main__':
    main()
