"""repair_broken_json.py — Fix chapters whose .json files contain raw text instead of JSON.

Two scenarios:
  A) Chapters that have .md files: delete the corrupted .json, re-migrate from .md.
  B) Chapters that lack .md files: parse the raw text in .json using block parsing,
     construct a title from the chapter number, and overwrite with valid JSON.

Usage (from project root):
  python -m tools.repair_broken_json          # auto-detect and repair all broken chapters
  python -m tools.repair_broken_json --dry-run  # preview only
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Ensure project root is on path for absolute imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.constants import CHAPTERS_DIR  # noqa: E402
from tools.schema import Chapter  # noqa: E402
from tools.chapter_io import save_chapter  # noqa: E402


def parse_text(text: str) -> tuple[list[dict], list[str]]:
    """Parse raw Thai translated text into (blocks, notes).

    Splits on horizontal rule (---) to separate body from translation
    notes footer. CN characters in notes are expected and should NOT
    end up in narration blocks.
    """
    text = text.replace('\r\n', '\n')

    # Split body from footer on --- separator
    parts = re.split(r'\n-{3,}\n', text)
    if len(parts) >= 2:
        body = parts[0].strip()
        footer = '\n'.join(parts[1:]).strip()
    else:
        body = parts[0].strip()
        footer = ''

    # Parse notes from footer
    notes = []
    for line in footer.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            notes.append(line[2:])

    # Parse blocks from body
    blocks = []
    for line in body.split('\n'):
        line = line.rstrip()
        if not line:
            continue
        if line.startswith('# '):
            continue  # Title line, handled separately
        if line.strip() == '(จบบท)':
            blocks.append({'type': 'end', 'text': '(จบบท)'})
            continue
        if line.startswith('【') and line.endswith('】'):
            blocks.append({'type': 'system', 'text': line})
            continue
        if line.startswith('「') and line.endswith('」'):
            # Sanitize: replace straight " with curly \u201c\u201d inside dialogue
            sanitized = line.replace('"', '\u201c')
            blocks.append({'type': 'dialogue', 'text': sanitized})
            continue
        if line.startswith('《') and line.endswith('》'):
            blocks.append({'type': 'game_title', 'text': line})
            continue
        blocks.append({'type': 'narration', 'text': line})
    return blocks, notes


def find_broken_json() -> list[int]:
    """Return chapter numbers whose .json files don't contain valid JSON."""
    broken = []
    for f in sorted(CHAPTERS_DIR.glob('[0-9]*.json')):
        if not f.stem.isdigit():
            continue
        try:
            raw = f.read_text(encoding='utf-8-sig')
            json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            broken.append(int(f.stem))
    return broken


def extract_title_from_md(md_path: Path) -> str:
    """Extract the markdown title (# ...) from the first line of a .md file."""
    try:
        text = md_path.read_text(encoding='utf-8-sig')
        m = re.match(r'^#\s+(.+)', text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ''


def repair_with_md(ch_num: int, dry_run: bool = False) -> tuple[bool, str]:
    """Repair by deleting corrupted .json, then re-migrating from .md."""
    json_path = CHAPTERS_DIR / f'{ch_num:04d}.json'
    md_path = CHAPTERS_DIR / f'{ch_num:04d}.md'
    if not md_path.exists():
        return False, f'❌ ch{ch_num}: .md not found for re-migration'

    # Read and parse the .md file
    md_text = md_path.read_text(encoding='utf-8-sig')

    # Extract title
    title = extract_title_from_md(md_path)
    if not title:
        title = f'ตอนที่ {ch_num} (ไม่มีชื่อตอน)'

    # Parse blocks and notes (properly separating body from footer)
    blocks, notes = parse_text(md_text)
    blocks = [b for b in blocks if b.get('text', '').strip()]

    if not blocks:
        return False, f'❌ ch{ch_num}: no content blocks found in .md'

    # Ensure end marker
    if not any(b['type'] == 'end' for b in blocks):
        blocks.append({'type': 'end', 'text': '(จบบท)'})

    try:
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
        return True, f'✓ ch{ch_num} (from .md): N={n} D={d} S={s} G={g}'
    except Exception as e:
        return False, f'❌ ch{ch_num}: {str(e)[:120]}'


def repair_from_raw_text(ch_num: int, dry_run: bool = False) -> tuple[bool, str]:
    """Repair by parsing the raw text inside the .json file as if it were .md content."""
    json_path = CHAPTERS_DIR / f'{ch_num:04d}.json'
    raw_text = json_path.read_text(encoding='utf-8-sig')

    title = f'ตอนที่ {ch_num} (ไม่มีชื่อตอน)'

    # Parse blocks and notes
    blocks, notes = parse_text(raw_text)
    blocks = [b for b in blocks if b.get('text', '').strip()]

    if not blocks:
        return False, f'❌ ch{ch_num}: no content blocks found in raw text'

    # Ensure end marker
    if not any(b['type'] == 'end' for b in blocks):
        blocks.append({'type': 'end', 'text': '(จบบท)'})

    try:
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
        return True, f'✓ ch{ch_num} (from raw text): N={n} D={d} S={s} G={g}'
    except Exception as e:
        return False, f'❌ ch{ch_num}: {str(e)[:120]}'


def main():
    ap = argparse.ArgumentParser(description='Repair broken .json chapter files')
    ap.add_argument('--dry-run', action='store_true', help='Preview only, no writes')
    args = ap.parse_args()

    broken = find_broken_json()
    if not broken:
        print('✅ No broken .json files found — all chapters are valid!')
        return

    print(f'Found {len(broken)} broken .json files: {broken}\n')

    success = 0
    failed = 0
    for ch_num in broken:
        md_path = CHAPTERS_DIR / f'{ch_num:04d}.md'
        if md_path.exists():
            ok, msg = repair_with_md(ch_num, dry_run=args.dry_run)
        else:
            ok, msg = repair_from_raw_text(ch_num, dry_run=args.dry_run)
        print(msg)
        if ok:
            success += 1
        else:
            failed += 1

    print(f'\n{"=" * 50}')
    prefix = '[DRY RUN] ' if args.dry_run else ''
    print(f'{prefix}Repaired: {success}, Failed: {failed}, Total: {len(broken)}')


if __name__ == '__main__':
    main()
