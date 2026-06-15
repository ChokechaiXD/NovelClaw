"""update_progress.py — Update progress.md with current translation status.

Scans chapter files to determine actual progress and updates:
  - Last translated chapter
  - Next chapter
  - Total progress percentage

Usage:
  python update_progress.py                        # auto-detect
  python update_progress.py --novel global-descent
  python update_progress.py --reset               # reset to ch 0
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"
PROGRESS_FILE = ROOT / "progress.md"
TOTAL_CHAPTERS = 1239


def scan_progress() -> dict:
    """Scan chapter files to determine actual progress."""
    translated = []
    for jp in CHAP_DIR.glob("*.json"):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if data.get("blocks"):
                translated.append(data["num"])
        except Exception:
            pass
    translated.sort()

    if not translated:
        return {"last": 0, "next": 1, "count": 0}

    # Find the highest consecutive chapter from 1
    consecutive = 0
    for ch in translated:
        if ch == consecutive + 1:
            consecutive = ch
        elif ch > consecutive + 1:
            break

    return {
        "last": translated[-1],
        "next": translated[-1] + 1,
        "count": len(translated),
        "consecutive": consecutive,
        "translated": translated,
    }


def update_progress_file(data: dict, total: int = TOTAL_CHAPTERS):
    """Update progress.md with scanned data."""
    if not PROGRESS_FILE.exists():
        sys.exit("progress.md not found")

    text = PROGRESS_FILE.read_text(encoding="utf-8")

    last = data["last"]
    next_ch = data["next"]
    count = data["count"]
    pct = count / total * 100

    # Update fields
    text = re.sub(
        r"(\*\*Last translated:\*\*\s*)ch\s*\d+",
        f"\\1ch {last}",
        text,
    )
    text = re.sub(
        r"(\*\*Next chapter:\*\*\s*)ch\s*\d+",
        f"\\1ch {next_ch}",
        text,
    )
    text = re.sub(
        r"(\*\*Total progress:\*\*\s*)\d+/[\d,]+\s*\([\d.]+%\)",
        f"\\1{count}/{total} ({pct:.2f}%)",
        text,
    )

    PROGRESS_FILE.write_text(text, encoding="utf-8")
    return last, next_ch, count, pct


def format_report(last: int, next_ch: int, count: int, pct: float, total: int) -> str:
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    return (
        f"📊 Progress Updated\n"
        f"\n"
        f"[{bar}] {pct:.1f}%\n"
        f"Translated: {count}/{total}\n"
        f"Last: Ch {last}\n"
        f"Next: Ch {next_ch}\n"
        f"\n"
        f"progress.md updated ✅"
    )


def main():
    global NOVEL, ROOT, CHAP_DIR, PROGRESS_FILE
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            NOVEL = args[i + 1]
            ROOT = get_novel_root(NOVEL)
            CHAP_DIR = ROOT / "chapters"
            PROGRESS_FILE = ROOT / "progress.md"
            i += 2
        else:
            i += 1

    data = scan_progress()
    last, next_ch, count, pct = update_progress_file(data)
    print(format_report(last, next_ch, count, pct, TOTAL_CHAPTERS))


if __name__ == "__main__":
    main()
