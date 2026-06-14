"""migrate_to_json.py — Convert legacy .md ch to .json (one-time migration).

Usage:
  python tools/migrate_to_json.py 1              # migrate ch 1
  python tools/migrate_to_json.py --all          # migrate all ch
  python tools/migrate_to_json.py 1-100          # migrate range
  python tools/migrate_to_json.py --all --dry-run  # preview only
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import CHAPTERS_DIR  # noqa: E402
from schema import Chapter, save_chapter, Dialogue, SystemMessage, GameTitle, Narration, EndMarker  # noqa: E402


def md_to_blocks(md_text: str) -> tuple[list, str, list]:
    """Parse legacy .md to (title, blocks, notes).

    Returns:
      title: extracted from # heading
      blocks: list of dict blocks
      notes: list of translation note strings

    Strategy: line-by-line, classify each line:
      - starts with 【 ends with 】 → system
      - starts with 「 ends with 」 → dialogue
      - starts with 《 ends with 》 → game_title (rare as standalone line)
      - other non-empty → narration
    Multi-line game titles or system messages get joined.
    """
    title = ''
    body_lines = []
    notes = []
    in_meta = False
    in_notes = False

    for line in md_text.split('\n'):
        # Title
        if line.startswith('# ') and not title:
            title = line[2:].strip()
            continue
        # Meta separator
        if re.match(r'^-{3,}$', line.strip()):
            in_meta = True
            continue
        # Source footer in meta
        if in_meta and line.strip().startswith('*Source:'):
            continue
        # Notes section
        if in_meta and ('หมายเหตุ' in line or 'Translation' in line.lower()):
            in_notes = True
            continue
        if in_meta and in_notes and line.strip().startswith('- '):
            notes.append(line.strip()[2:])
            continue
        # Skip meta lines we don't care about
        if in_meta:
            continue
        body_lines.append(line)

    # Classify body lines
    blocks = []
    for line in body_lines:
        line = line.rstrip()
        if not line:
            continue
        if line.strip() == '(จบบท)':
            blocks.append({'type': 'end', 'text': '(จบบท)'})
            continue
        if line.startswith('【') and line.endswith('】'):
            blocks.append({'type': 'system', 'text': line})
        elif line.startswith('「') and line.endswith('」'):
            blocks.append({'type': 'dialogue', 'text': line})
        elif line.startswith('《') and line.endswith('》'):
            blocks.append({'type': 'game_title', 'text': line})
        else:
            blocks.append({'type': 'narration', 'text': line})

    # Ensure end marker
    if not any(b['type'] == 'end' for b in blocks):
        blocks.append({'type': 'end', 'text': '(จบบท)'})

    return title, blocks, notes


def migrate(ch_num: int, dry_run: bool = False) -> tuple[bool, str]:
    """Migrate one ch from .md to .json. Returns (success, message)."""
    md_path = CHAPTERS_DIR / f'{ch_num:04d}.md'
    json_path = CHAPTERS_DIR / f'{ch_num:04d}.json'
    if not md_path.exists():
        return False, f'❌ ch{ch_num}: .md not found'
    if json_path.exists() and not dry_run:
        return False, f'⚠ ch{ch_num}: .json already exists, skipping'
    try:
        md_text = md_path.read_text(encoding='utf-8')
        title, blocks, notes = md_to_blocks(md_text)
        if not title:
            return False, f'❌ ch{ch_num}: no title found'
        # Try to build Chapter (validates)
        ch = Chapter(
            num=ch_num,
            title=title,
            blocks=blocks,
            source=f'ch {ch_num}',
            notes=notes,
        )
        if not dry_run:
            save_chapter(ch, json_path)
        n = sum(1 for b in blocks if b['type'] == 'narration')
        d = sum(1 for b in blocks if b['type'] == 'dialogue')
        s = sum(1 for b in blocks if b['type'] == 'system')
        g = sum(1 for b in blocks if b['type'] == 'game_title')
        e = sum(1 for b in blocks if b['type'] == 'end')
        return True, f'✓ ch{ch_num}: N={n} D={d} S={s} G={g} E={e}'
    except Exception as e:
        return False, f'❌ ch{ch_num}: {str(e)[:80]}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapters', nargs='?', help='Single ch (e.g., 1) or range (1-100)')
    ap.add_argument('--all', action='store_true', help='All ch')
    ap.add_argument('--dry-run', action='store_true', help='Preview only')
    args = ap.parse_args()

    if args.all:
        ch_nums = sorted([
            int(f.stem) for f in CHAPTERS_DIR.glob('[0-9]*.md')
            if f.stem.isdigit() and len(f.stem) == 4
        ])
    elif args.chapters:
        if '-' in args.chapters:
            a, b = map(int, args.chapters.split('-'))
            ch_nums = list(range(a, b + 1))
        else:
            ch_nums = [int(args.chapters)]
    else:
        ap.print_help()
        sys.exit(1)

    success = 0
    failed = 0
    skipped = 0
    for ch in ch_nums:
        ok, msg = migrate(ch, dry_run=args.dry_run)
        print(msg)
        if ok:
            success += 1
        elif 'CN leakage' in msg or 'no content blocks' in msg:
            skipped += 1
        else:
            failed += 1
    print(f'\n{"=" * 50}')
    print(f'Total: {success} migrated, {skipped} skipped (need manual), {failed} failed out of {len(ch_nums)}')


if __name__ == '__main__':
    main()
