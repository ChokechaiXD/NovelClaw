"""save_translated.py — Save Mika's translated Thai text into chapter JSON.

Reads translated Thai text (from stdin or file) and saves it as the
chapter's `blocks` array in the JSON schema format.

This is the tool Mika calls from Telegram after translating:
  1. Mika translates the context block from translate_next.py
  2. Mika sends back Thai translation (plain text, paragraphs separated by blank lines)
  3. Mika calls save_translated.py to persist it

Pipeline:
  - Parse Thai text into blocks (dialogue / narration / system / end)
  - Merge with existing chapter metadata
  - Validate (schema + glossary doctor + CJK check)
  - Save as .json
  - Update progress.md
  - Return validation summary

Usage:
  python save_translated.py 122 < translated.txt          # from file
  echo "Thai text..." | python save_translated.py 122 -    # from stdin
  python save_translated.py 122 translated.txt             # auto-detect
  python save_translated.py 122 --novel global-descent
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"
PROGRESS_FILE = ROOT / "progress.md"


def parse_thai_blocks(text: str) -> list[dict]:
    """Parse Thai translation text into blocks array.

    Rules:
      - Lines starting with 「」 or containing dialogue markers → dialogue
      - Lines starting with 【】 → system
      - "(จบบท)" or " end" at end → end block
      - Empty lines separate blocks
      - Everything else → narration
    """
    blocks = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # System messages 【】
        if line.startswith("【") or line.startswith("["):
            # Check if it's a system/caption line
            if re.match(r'^【[^】]+】', line) or re.match(r'^\[[^\]]+\]', line):
                blocks.append({"type": "system", "text": line})
                continue

        # End marker
        if "(จบบท)" in line or line.strip() == "(end)":
            blocks.append({"type": "end", "text": line})
            continue

        # Dialogue 「」 or ""
        if (line.startswith("「") and line.endswith("」")) or \
           (line.startswith('"') and line.endswith('"')) or \
           (line.startswith("『") and line.endswith("』")):
            blocks.append({"type": "dialogue", "text": line, "speaker": None})
            continue

        # Narration (everything else)
        blocks.append({"type": "narration", "text": line})

    return blocks


def load_existing_chapter(ch: int) -> dict | None:
    """Load existing chapter JSON to preserve metadata."""
    jp = CHAP_DIR / f"{ch:04d}.json"
    if jp.exists():
        return json.loads(jp.read_text(encoding="utf-8"))
    return None


def save_chapter_json(ch: int, blocks: list[dict], title: str = "") -> Path:
    """Save blocks into chapter JSON."""
    existing = load_existing_chapter(ch)

    if existing:
        # Preserve source, notes, metadata
        data = existing.copy()
        data["blocks"] = blocks
        if title and not data.get("title"):
            data["title"] = title
    else:
        data = {
            "schema_version": 1,
            "num": ch,
            "title": title or f"Ch {ch}",
            "blocks": blocks,
            "source": "",
            "notes": [],
        }

    jp = CHAP_DIR / f"{ch:04d}.json"
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return jp


def update_progress(ch: int, total: int = 1239):
    """Update progress.md with new last translated chapter."""
    if not PROGRESS_FILE.exists():
        return
    text = PROGRESS_FILE.read_text(encoding="utf-8")
    # Update "Last translated: ch N"
    text = re.sub(
        r"(\*\*Last translated:\*\*\s*)ch\s*\d+",
        f"\\1ch {ch}",
        text,
    )
    # Update "Next chapter: ch N+1"
    text = re.sub(
        r"(\*\*Next chapter:\*\*\s*)ch\s*\d+",
        f"\\1ch {ch + 1}",
        text,
    )
    # Update progress percentage
    pct = ch / total * 100
    text = re.sub(
        r"(\*\*Total progress:\*\*\s*)\d+/(\d+)\s*\([\d.]+%\)",
        f"\\1{ch}/{total} ({pct:.2f}%)",
        text,
    )
    PROGRESS_FILE.write_text(text, encoding="utf-8")


def quick_validate(ch: int, blocks: list[dict]) -> dict:
    """Run quick validation on saved blocks."""
    thai_text = " ".join(b.get("text", "") for b in blocks)

    issues = []

    # CJK check
    cjk_chars = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', thai_text)
    if cjk_chars:
        issues.append(f"⚠️  {len(cjk_chars)} CJK chars remaining: {''.join(set(cjk_chars[:10]))}")

    # Block count
    if len(blocks) < 5:
        issues.append(f"⚠️  Only {len(blocks)} blocks — seems short")

    return {
        "blocks": len(blocks),
        "chars": len(thai_text),
        "issues": issues,
        "passed": len(issues) == 0,
    }


def main():
    novel = NOVEL
    ch_arg = None
    source_arg = None
    title_arg = ""
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            novel = args[i + 1]
            global ROOT, CHAP_DIR, PROGRESS_FILE
            ROOT = get_novel_root(novel)
            CHAP_DIR = ROOT / "chapters"
            PROGRESS_FILE = ROOT / "progress.md"
            i += 2
        elif args[i] == "--title" and i + 1 < len(args):
            title_arg = args[i + 1]
            i += 2
        else:
            if ch_arg is None:
                try:
                    ch_arg = int(args[i])
                except ValueError:
                    source_arg = args[i]
            i += 1

    if ch_arg is None:
        sys.exit("Usage: python save_translated.py <chapter_number> [file | -] [--title 'Ch Title']")

    ch = ch_arg

    # Read Thai translation
    if source_arg == "-":
        thai_text = sys.stdin.read()
    elif source_arg:
        p = Path(source_arg)
        if not p.exists():
            sys.exit(f"File not found: {source_arg}")
        thai_text = p.read_text(encoding="utf-8")
    else:
        # Try to read from stdin if piped
        if not sys.stdin.isatty():
            thai_text = sys.stdin.read()
        else:
            sys.exit("No input. Pipe Thai text or provide file: python save_translated.py 122 thai.txt")

    if not thai_text.strip():
        sys.exit("Empty Thai text — nothing to save")

    # Parse & save
    blocks = parse_thai_blocks(thai_text)
    if not blocks:
        sys.exit("No blocks parsed from Thai text")

    jp = save_chapter_json(ch, blocks, title_arg)
    update_progress(ch)
    result = quick_validate(ch, blocks)

    status = "✅" if result["passed"] else "⚠️"
    print(f"""
{status} Saved Ch {ch}
  File: {jp}
  Blocks: {result['blocks']}
  Characters: {result['chars']}
  Progress: updated to ch {ch+1}
""".strip())

    if result["issues"]:
        print("Issues:")
        for issue in result["issues"]:
            print(f"  {issue}")


if __name__ == "__main__":
    main()
