"""backup.py — Lightweight zip snapshot of translated work.

Backs up only translated artifacts (no raw source/ which is 17MB and
recoverable from the scraper). Default destination: ../backups/

Usage:
  python backup.py                       # snapshot with auto-timestamp
  python backup.py --output /tmp/x.zip  # custom path
  python backup.py --include-source     # also include chapters/source/ (17MB extra)
  python backup.py --list                # show existing backups with sizes
"""
import argparse
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
NOVEL = 'global-descent'
NOVEL_DIR = ROOT / 'novels' / NOVEL
DEFAULT_BACKUP_DIR = ROOT / 'backups'

# Paths inside novel/ that should be backed up (translatable output)
BACKUP_PATHS = [
    'chapters/*.md',      # translated chapters (excludes source/ by glob)
    'glossary',           # 3-tier glossary
    'characters.md',
    'summary.md',
    'progress.md',
    'style.md',
    'meta.md',
    'reviews',            # Tier-2 review files (if any)
]


def make_zipname(prefix: str = '') -> str:
    ts = datetime.now().strftime('%Y%m%d-%H%M')
    return f'{prefix}{NOVEL}-{ts}.zip'


def list_backups(backup_dir: Path) -> None:
    if not backup_dir.exists():
        print(f'No backup directory: {backup_dir}')
        return
    zips = sorted(backup_dir.glob('*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        print(f'No backups in {backup_dir}')
        return
    print(f'━' * 60)
    print(f'  Backups in {backup_dir}')
    print(f'━' * 60)
    for z in zips:
        size_mb = z.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(z.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        print(f'  {z.name:50}  {size_mb:6.2f} MB  {mtime}')
    print(f'━' * 60)


def create_backup(out_path: Path, include_source: bool = False) -> None:
    if not NOVEL_DIR.exists():
        sys.exit(f'Error: novel dir not found: {NOVEL_DIR}')

    files = list(BACKUP_PATHS)
    if include_source:
        files.append('chapters/source/*.md')

    # Build list of actual files to include
    to_zip = []
    total_size = 0
    for pattern in files:
        for p in NOVEL_DIR.glob(pattern):
            if p.is_file():
                to_zip.append(p)
                total_size += p.stat().st_size
    translated_chs = sorted(NOVEL_DIR.glob('chapters/[0-9]*.md'))

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f'━' * 60)
    print(f'  Creating backup: {out_path.name}')
    print(f'━' * 60)
    print(f'  Source:  {NOVEL_DIR}')
    print(f'  Files:   {len(to_zip)}')
    print(f'  Size:    {total_size / 1024:.1f} KB ({len(translated_chs)} translated chapters)')
    if include_source:
        print(f'  NOTE:   --include-source adds ~17MB of raw scraped source')
    print()

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in to_zip:
            arcname = p.relative_to(ROOT)
            zf.write(p, arcname)
            print(f'  + {arcname}')

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print()
    print(f'  ✓ Created: {out_path}')
    print(f'  ✓ Size:   {size_mb:.2f} MB')
    print(f'━' * 60)


def main():
    parser = argparse.ArgumentParser(description='Lightweight zip snapshot of NovelClaw work.')
    parser.add_argument('--output', '-o', type=Path, help='Output zip path (default: backups/<auto>)')
    parser.add_argument('--include-source', action='store_true', help='Also include raw chapters/source/ (17MB extra)')
    parser.add_argument('--list', '-l', action='store_true', help='List existing backups')
    parser.add_argument('--backup-dir', type=Path, default=DEFAULT_BACKUP_DIR, help='Backup directory')
    args = parser.parse_args()

    if args.list:
        list_backups(args.backup_dir)
        return

    out = args.output or (args.backup_dir / make_zipname())
    create_backup(out, include_source=args.include_source)


if __name__ == '__main__':
    main()
