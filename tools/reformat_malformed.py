"""Reformat malformed .md ch (body below notes).

Original structure (BROKEN):
  # title
  <blank>
  <blank>
  (จบบท)
  ---
  *Source: ch N*
  ---
  หมายเหตุการแปล: ...
  ตอนที่ N <title>
  <ACTUAL BODY>

Fixed structure:
  # title
  <blank>
  <ACTUAL BODY>
  <blank>
  (จบบท)
  ---
  *Source: ch N*
  ---
  หมายเหตุการแปล: ...
"""
import re
import sys
from pathlib import Path

CHAPTERS_DIR = Path("novels/global-descent/chapters")


def reformat_malformed(text: str, ch_num: int) -> str:
    """Move body content from below notes to before (จบบท)."""
    lines = text.split('\n')

    # Find the misplaced body: starts at line that begins with "ตอนที่ N" (not just "ตอนที่ N ")
    # in the body section (after the notes section header)
    body_start_idx = None
    for i, line in enumerate(lines):
        # Look for the "ตอนที่ N <title>" line that starts a duplicated body
        m = re.match(rf'^ตอนที่\s+{ch_num}\s+(.+)', line.strip())
        if m and i > 5:  # not the title
            body_start_idx = i
            break

    if body_start_idx is None:
        return text  # no misplaced body found

    # Extract the misplaced body (from body_start_idx to end of meaningful content)
    # Skip trailing empty lines
    body_lines = lines[body_start_idx:]
    # Trim trailing blanks
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    # Build the new structure
    # Original: title, blanks, blank, (จบบท), ---, source, ---, notes, body
    # New: title, blank, BODY, blank, (จบบท), ---, source, ---, notes

    # Find where title ends
    title_end = 0
    for i, line in enumerate(lines):
        if line.startswith('# '):
            title_end = i + 1
            break

    # Find (จบบท) line
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == '(จบบท)':
            end_idx = i
            break
    if end_idx is None:
        return text  # no end marker

    # Find "หมายเหตุการแปล" section
    notes_idx = None
    for i, line in enumerate(lines):
        if 'หมายเหตุการแปล' in line or 'Translation notes' in line:
            notes_idx = i
            break

    # Reconstruct: title block + body + end marker + footer + notes
    title_block = '\n'.join(lines[title_end:end_idx]).strip()
    footer = '\n'.join(lines[end_idx:body_start_idx]).rstrip()
    notes_section = ''
    if notes_idx and notes_idx < body_start_idx:
        # Notes start at notes_idx, body starts at body_start_idx
        notes_section = '\n'.join(lines[notes_idx:body_start_idx]).rstrip()

    new_text = (
        lines[0] +  # title
        '\n\n' +
        '\n'.join(body_lines).strip() +  # actual body
        '\n\n' +
        footer +
        ('\n\n' + notes_section if notes_section else '') +
        '\n'
    )

    # Clean: collapse 3+ blank lines
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)
    return new_text


def main():
    if len(sys.argv) < 2:
        print("Usage: reformat_malformed.py <ch_num> [<ch_num> ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        if '-' in arg:
            start, end = map(int, arg.split('-'))
            ch_nums = range(start, end + 1)
        else:
            ch_nums = [int(arg)]

        for ch in ch_nums:
            path = CHAPTERS_DIR / f'{ch:04d}.md'
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8')
            new_text = reformat_malformed(text, ch)
            if new_text == text:
                print(f"ch {ch}: no change needed")
                continue
            path.write_text(new_text, encoding='utf-8')
            print(f"ch {ch}: reformatted ({len(text)} → {len(new_text)} bytes)")


if __name__ == '__main__':
    main()
