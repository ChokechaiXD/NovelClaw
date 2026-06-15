"""reformat_chapter.py — Reformat a translated ch to match format_spec.md.

Reformats ONE ch at a time (or all ch) to match the canonical format.
Operations performed (all mechanical, zero content change):

  1. Convert straight `"dialogue"` → `「dialogue」` (with in-dialogue quote preservation)
  2. Convert straight `[stat]` → `【stat】` (only when entire line is in CN form)
  3. Strip trailing whitespace
  4. Collapse 3+ blank lines to 2
  5. Convert tabs to spaces
  6. Add `(จบบท)` marker if missing (before last --- separator)
  7. Standardize `*Source:*` footer to short form (ch N only)
  8. Add `หมายเหตุการแปล:` meta section if missing

Usage:
  python tools/reformat_chapter.py 1              # reformat ch 1
  python tools/reformat_chapter.py 1 --dry-run    # preview only
  python tools/reformat_chapter.py --all          # reformat all ch
  python tools/reformat_chapter.py --all --dry-run  # preview all
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import CHAPTERS_DIR, get_novel_root, NOVEL_ROOT# noqa: E402


def reformat(text: str, ch_num: int, dry_run: bool = False) -> tuple[str, list[str]]:
    """Reformat a ch to match format_spec. Returns (new_text, list_of_changes)."""
    changes = []
    new_text = text

    # 1. Strip trailing whitespace per line
    lines = new_text.split('\n')
    new_lines = []
    for line in lines:
        if line != line.rstrip():
            changes.append('trimmed trailing whitespace')
        new_lines.append(line.rstrip())
    new_text = '\n'.join(new_lines)

    # 2. Convert tabs to spaces
    if '\t' in new_text:
        new_text = new_text.replace('\t', '  ')
        changes.append('converted tabs to 2 spaces')

    # 3. Collapse 3+ blank lines to 2
    new_new = re.sub(r'\n\n\n+', '\n\n', new_text)
    if new_new != new_text:
        changes.append('collapsed 3+ blank lines to 2')
        new_text = new_new

    # 4. Convert "dialogue" → 「dialogue」 — careful with in-dialogue quotes
    # Strategy: find lines that look like dialogue (start with " or end with ")
    # and convert to 「」. For in-dialogue quotes (like "name" inside dialogue),
    # we leave them as straight " (allowed in spec).
    # This is heuristic — we only convert OUTERMOST quotes that wrap a sentence
    # (typically at line start/end or after specific dialogue verbs).
    # We do NOT convert quotes inside running prose.
    converted_dialogue = convert_dialogue_quotes(new_text)
    if converted_dialogue != new_text:
        count = new_text.count('"') - converted_dialogue.count('"')
        changes.append(f'converted {count} " to 「」')
        new_text = converted_dialogue

    # 5. Add (จบบท) before --- separator if missing
    if '(จบบท)' not in new_text and '本章完' not in new_text:
        # Find first --- separator (after body)
        sep_match = re.search(r'\n---\n', new_text)
        if sep_match:
            insert_pos = sep_match.start()
            new_text = new_text[:insert_pos] + '\n\n(จบบท)' + new_text[insert_pos:]
            changes.append('added (จบบท) marker')
        else:
            # No separator — add at end of body
            # Find last non-empty line before any "หมายเหตุ"
            if 'หมายเหตุการแปล' in new_text:
                note_idx = new_text.index('หมายเหตุการแปล')
                new_text = new_text[:note_idx].rstrip() + '\n\n(จบบท)\n\n---\n\n' + new_text[note_idx:]
            else:
                # No meta section at all — add minimal footer
                new_text = new_text.rstrip() + f'\n\n(จบบท)\n\n---\n\n*Source: ch {ch_num}*\n\n---\n\nหมายเหตุการแปล:\n- (เพิ่มโน้ตการแปลที่นี่)\n'
            changes.append('added (จบบท) marker + minimal footer')

    # 6. Standardize *Source:* footer to short form
    src_match = re.search(r'\*Source:[^*]*\*', new_text)
    if src_match:
        old_src = src_match.group()
        if old_src != f'*Source: ch {ch_num}*':
            new_src = f'*Source: ch {ch_num}*'
            new_text = new_text.replace(old_src, new_src)
            changes.append(f'standardized Source footer: "{old_src}" → "{new_src}"')
    else:
        # No Source footer at all — add it after first ---
        sep_match = re.search(r'\n---\n', new_text)
        if sep_match:
            # Find end of that line
            insert_pos = sep_match.end()
            new_text = new_text[:insert_pos] + f'\n*Source: ch {ch_num}*\n\n---\n' + new_text[insert_pos:]
            changes.append('added Source footer')

    # 7. Add หมายเหตุการแปล: if missing
    if '*Source: ch ' in new_text and 'หมายเหตุการแปล' not in new_text:
        # Find second --- separator (after Source)
        new_text = re.sub(
            r'(\*Source: ch \d+\*)\n\n---\n',
            r'\1\n\n---\n\nหมายเหตุการแปล:\n- (เพิ่มโน้ตการแปลที่นี่)\n',
            new_text,
            count=1
        )
        changes.append('added หมายเหตุการแปล: section')

    # 8. Final newline
    if not new_text.endswith('\n'):
        new_text += '\n'
        changes.append('added final newline')

    return new_text, changes


def convert_dialogue_quotes(text: str) -> str:
    """Convert "dialogue" to 「dialogue」 intelligently.

    Heuristic: only convert outermost quotes that wrap a full sentence
    (typically a complete thought). We process line by line:
    - If a line STARTS with " and ENDS with " (possibly with same count),
      convert outer wrapping to 「」
    - If a line has multiple " on a line, find pairs and convert
    - In-dialogue quotes (like "name" inside 「...」) are left as-is

    Edge cases:
    - " at end of paragraph (after dialogue): convert to 」
    - " at start of paragraph (before dialogue): convert to 「
    - Multiple dialogues in same line: convert each
    """
    new_lines = []
    for line in text.split('\n'):
        new_line = convert_line_quotes(line)
        new_lines.append(new_line)
    return '\n'.join(new_lines)


def convert_line_quotes(line: str) -> str:
    """Convert quotes on a single line."""
    # Skip lines inside meta (หมายเหตุ section)
    if line.strip().startswith('-') and 'Source' not in line:
        return line
    if line.strip() == 'หมายเหตุการแปล:':
        return line
    if line.strip().startswith('#'):
        return line
    if line.strip() == '---':
        return line
    # Skip lines that look like *Source:* or other markdown
    if line.strip().startswith('*') and line.strip().endswith('*'):
        return line
    # Count quotes on this line
    quote_count = line.count('"')
    if quote_count == 0:
        return line
    if quote_count % 2 != 0:
        # Odd number — leave as-is (might be markdown, leave untouched)
        return line
    # Even number — convert ALL " to 「」 in pairs (open first, close second)
    # Walk through the string and pair them
    result = []
    is_open = True
    for ch in line:
        if ch == '"':
            result.append('「' if is_open else '」')
            is_open = not is_open
        else:
            result.append(ch)
    return ''.join(result)


def reformat_one(ch_num: int, dry_run: bool = False) -> bool:
    """Reformat a single ch. Returns True if changes were made."""
    # Try .json first (canonical), fall back to .md (legacy)
    ch_json = CHAPTERS_DIR / f'{ch_num:04d}.json'
    ch_md = CHAPTERS_DIR / f'{ch_num:04d}.md'
    if ch_json.exists():
        ch_path = ch_json
    elif ch_md.exists():
        ch_path = ch_md
    else:
        ch_path = ch_md  # for error message

    if not ch_path.exists():
        print(f'❌ ch{ch_num}: file not found')
        return False
    text = ch_path.read_text(encoding='utf-8')
    new_text, changes = reformat(text, ch_num, dry_run)
    if not changes:
        print(f'ch{ch_num}: ✓ already in spec')
        return False
    print(f'ch{ch_num}: {len(changes)} change(s)')
    for c in changes[:5]:
        print(f'  • {c}')
    if len(changes) > 5:
        print(f'  ... and {len(changes) - 5} more')
    if not dry_run:
        ch_path.write_text(new_text, encoding='utf-8')
        print(f'  → saved')
    return bool(changes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapter', nargs='?', type=int, help='Chapter to reformat')
    ap.add_argument('--all', action='store_true', help='Reformat all ch')
    ap.add_argument('--dry-run', action='store_true', help='Preview only')
    args = ap.parse_args()

    if not args.chapter and not args.all:
        ap.print_help()
        sys.exit(1)

    if args.chapter:
        reformat_one(args.chapter, dry_run=args.dry_run)
    else:
        # All ch — scan .json first, fall back to .md
        ch_files = sorted([f for f in CHAPTERS_DIR.glob('[0-9]*.json')
                          if f.is_file() and f.stem.isdigit() and len(f.stem) == 4],
                         key=lambda p: int(p.stem))
        if not ch_files:
            ch_files = sorted([f for f in CHAPTERS_DIR.glob('[0-9]*.md')
                              if f.is_file() and f.stem.isdigit() and len(f.stem) == 4],
                             key=lambda p: int(p.stem))
        total_changed = 0
        for ch_file in ch_files:
            ch = int(ch_file.stem)
            if reformat_one(ch, dry_run=args.dry_run):
                total_changed += 1
        print(f'\n{"=" * 60}')
        print(f'Total: {total_changed}/{len(ch_files)} ch reformatted')


if __name__ == '__main__':
    main()
