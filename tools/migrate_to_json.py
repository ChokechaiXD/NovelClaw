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
from constants import CHAPTERS_DIR, get_novel_root, NOVEL_ROOT# noqa: E402
from schema import Chapter, Dialogue, SystemMessage, GameTitle, Narration, EndMarker  # noqa: E402
from chapter_io import save_chapter  # noqa: E402


def md_to_blocks(md_text: str) -> tuple[str, list, list]:
    """Parse legacy .md to (title, blocks, notes) handling multiple dividers."""
    md_text = md_text.replace('\r\n', '\n')
    parts = re.split(r'\n-{3,}\n', md_text)
    
    body = ''
    meta_text = ''
    
    if len(parts) >= 3:
        first_part = parts[0].strip()
        lines = first_part.split('\n')
        if len(lines) <= 6:
            body = parts[1].strip()
            meta_text = '\n\n'.join(parts[2:])
        else:
            body = '\n\n---\n\n'.join(parts[:-1])
            meta_text = parts[-1]
    elif len(parts) == 2:
        first_part = parts[0].strip()
        lines = first_part.split('\n')
        if len(lines) <= 6:
            body = parts[1].strip()
            meta_text = ''
        else:
            body = parts[0].strip()
            meta_text = parts[1].strip()
    else:
        body = parts[0].strip()
        meta_text = ''
        
    title = ''
    # Extract title from body if present
    m = re.match(r'^#\s+(.+)', body)
    if m:
        title = m.group(1).strip()
        body = body[m.end():].strip()
    else:
        # Fallback to first part
        m = re.match(r'^#\s+(.+)', parts[0].strip())
        if m:
            title = m.group(1).strip()
            
    notes = []
    for line in meta_text.split('\n'):
        if line.strip().startswith('- '):
            notes.append(line.strip()[2:])
            
    blocks = []
    for line in body.split('\n'):
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
