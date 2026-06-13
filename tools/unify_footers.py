"""unify_footers.py — One-off migration: rewrite Source footers to the v2 format.

Old format (ch 1, 71-98):
  *Source: ch N (第N章 <CN TITLE>, Traditional Chinese from hjwzw.com)*
  *Translated: ...*

New format (ch 99-100 introduced in Session 8):
  *Source: ch N*

This tool rewrites ch 1 and ch 71-98 to the v2 format. Idempotent —
re-running on already-converted chapters is a no-op.

Usage:
  python unify_footers.py          # dry-run, print what would change
  python unify_footers.py --apply  # actually rewrite files
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import CHAPTERS_DIR  # noqa: E402

# Old footer regex matches either the verbose form OR the simple form.
# Capture: (1) full old line, (2) chapter number
OLD_FOOTER_RE = re.compile(
    r'\*Source: ch (\d+)(?: \([^)]*\))?\*\n\*Translated:[^\n]*\n?',
    re.MULTILINE,
)
# Simple v2 form (what ch 99-100 already use) — no action needed if matched
SIMPLE_FOOTER_RE = re.compile(r'^\*Source: ch (\d+)\*\s*$', re.MULTILINE)


def migrate(text: str, n: int) -> tuple[str, bool]:
    """Return (new_text, changed)."""
    # Already in v2 format? Skip.
    if SIMPLE_FOOTER_RE.search(text):
        return text, False
    # Has old-format footer? Rewrite.
    new_text, n_replacements = OLD_FOOTER_RE.subn(
        f'*Source: ch {n}*\n',
        text,
    )
    if n_replacements == 0:
        return text, False
    return new_text, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Actually rewrite files (default: dry-run)')
    args = ap.parse_args()

    # ch 1, 71-98
    targets = [1] + list(range(71, 99))
    changed_count = 0
    unchanged_count = 0
    missing = []

    for n in targets:
        f = CHAPTERS_DIR / f'{n:04d}.md'
        if not f.exists():
            missing.append(n)
            continue
        text = f.read_text(encoding='utf-8')
        new_text, changed = migrate(text, n)
        if changed:
            changed_count += 1
            action = 'WRITTEN' if args.apply else 'would write'
            print(f'  ch {n}: {action} ({len(text)} → {len(new_text)} bytes)')
            if args.apply:
                f.write_text(new_text, encoding='utf-8')
        else:
            unchanged_count += 1
            print(f'  ch {n}: already in v2 format')

    print()
    print(f'  Migration plan:')
    print(f'    To rewrite:  {changed_count}')
    print(f'    Unchanged:   {unchanged_count}')
    print(f'    Missing:     {missing or "none"}')
    if not args.apply and changed_count:
        print()
        print('  Re-run with --apply to actually rewrite files.')


if __name__ == '__main__':
    main()
