"""status.py — Show translation progress for a novel.

Displays:
  - Total / translated / remaining chapters
  - Recent translation activity
  - Validation summary (pass/fail counts)
  - Next chapter to translate

Usage:
  python status.py                        # default novel
  python status.py --novel global-descent
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def get_progress() -> dict:
    """Gather progress data."""
    total_chapters = 1239  # from progress.md or config

    # Count translated chapters
    translated = []
    for jp in CHAP_DIR.glob("*.json"):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if data.get("blocks"):
                translated.append(data["num"])
        except Exception:
            pass

    translated.sort()

    # Read progress.md for next chapter and total
    progress_file = ROOT / "progress.md"
    next_ch = None
    last_translated = None
    if progress_file.exists():
        text = progress_file.read_text(encoding="utf-8")
        m = re.search(r"Next chapter[:\\s]*\\*\\*\\s*ch\\s*(\\d+)", text, re.IGNORECASE)
        if m:
            next_ch = int(m.group(1))
        m = re.search(r"Last translated[:\\s]*\\*\\*\\s*ch\\s*(\\d+)", text, re.IGNORECASE)
        if m:
            last_translated = int(m.group(1))
        m = re.search(r"Total progress[:\\s]*\\*\\*\\s*(\d+)/(\d+)", text, re.IGNORECASE)
        if m:
            total_chapters = int(m.group(2))

    # Validation summary
    pass_count = 0
    fail_count = 0
    validate_script = Path(__file__).parent / "validate_chapter.py"
    if validate_script.exists():
        for ch in translated:
            result = subprocess.run(
                [sys.executable, str(validate_script), str(ch)],
                capture_output=True, text=True, encoding="utf-8",
                cwd=str(Path(__file__).parent.parent),
                timeout=30,
            )
            if "PASSED" in result.stdout:
                pass_count += 1
            elif "FAILED" in result.stdout:
                fail_count += 1

    return {
        "total": total_chapters,
        "translated_count": len(translated),
        "translated": translated,
        "next_ch": next_ch or (translated[-1] + 1 if translated else 1),
        "last_translated": last_translated or (translated[-1] if translated else 0),
        "pass_count": pass_count,
        "fail_count": fail_count,
    }


def format_status(data: dict, novel: str) -> str:
    pct = data["translated_count"] / data["total"] * 100 if data["total"] > 0 else 0
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    lines = [
        f"📊 Translation Status — {novel}",
        f"",
        f"Progress: [{bar}] {pct:.1f}%",
        f"Translated: {data['translated_count']}/{data['total']} chapters",
        f"Remaining: {data['total'] - data['translated_count']} chapters",
        f"Next: Ch {data['next_ch']}",
        f"Last translated: Ch {data['last_translated']}",
        f"",
        f"Validation: ✅ {data['pass_count']} PASS | ❌ {data['fail_count']} FAIL",
    ]

    # Show recent chapters
    recent = data["translated"][-5:]
    if recent:
        lines.append(f"")
        lines.append(f"Recent chapters: {', '.join(f'ch {c}' for c in recent)}")

    return "\n".join(lines)


def main():
    novel = NOVEL
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            novel = args[i + 1]
            global ROOT, CHAP_DIR
            ROOT = get_novel_root(novel)
            CHAP_DIR = ROOT / "chapters"
            i += 2
        else:
            i += 1

    data = get_progress()
    print(format_status(data, novel))


if __name__ == "__main__":
    main()
