"""Convert straight quotes to CJK 「」 in legacy ch (102-110).

Pattern: only convert dialogue-like patterns (preceded by Thai text or speaker tag).
Skips: "..." inside the title, translator notes, donor names in 《》, etc.
"""
import re
import sys
from pathlib import Path

CHAPTERS_DIR = Path("novels/global-descent/chapters")


def convert_quotes(text: str) -> str:
    """Convert "dialogue" to 「dialogue」 in body text.

    Skips: title (# line), donor list, system messages 【...】, game titles 《...》.
    """
    lines = text.split('\n')
    out = []
    for line in lines:
        stripped = line.strip()
        # Skip donor list / title / separator
        if stripped.startswith('ขอบคุณ') or stripped.startswith('# '):
            out.append(line)
            continue
        if stripped == '---' or stripped == '(จบบท)':
            out.append(line)
            continue
        # Convert curly double quotes "..." / single quotes '...' to 「...」 in body
        has_curly = any(c in line for c in '“”‘’')
        has_straight = '"' in line
        if has_curly or has_straight:
            new_line = line
            # Curly double quotes
            new_line = re.sub(r'“([^“”]+)”', r'「\1」', new_line)
            # Curly single quotes
            new_line = re.sub(r'‘([^‘’]+)’', r'「\1」', new_line)
            # Straight double quotes
            new_line = re.sub(r'"([^"]+)"', r'「\1」', new_line)
            out.append(new_line)
        else:
            out.append(line)
    return '\n'.join(out)


def main():
    if len(sys.argv) < 2:
        print("Usage: convert_quotes.py <ch_num> [<ch_num> ...]")
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
            new_text = convert_quotes(text)
            if new_text == text:
                print(f"ch {ch}: no change")
                continue
            path.write_text(new_text, encoding='utf-8')
            print(f"ch {ch}: converted quotes ({len(text)} → {len(new_text)} bytes)")


if __name__ == '__main__':
    main()
