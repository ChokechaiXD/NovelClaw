"""dashboard.py — Single-command dashboard for NovelClaw translation status.

Combines: progress, validation summary, glossary coverage, recent activity.
Designed for Telegram — output is concise and scannable.

Usage:
  python dashboard.py                        # full dashboard
  python dashboard.py --novel global-descent
  python dashboard.py --brief                # one-liner summary
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"
PROGRESS_FILE = ROOT / "progress.md"
TOTAL_CHAPTERS = 1239


def get_translated_chapters() -> list[int]:
    chapters = []
    for jp in CHAP_DIR.glob("*.json"):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if data.get("blocks"):
                chapters.append(data["num"])
        except Exception:
            pass
    return sorted(chapters)


def get_progress_info() -> dict:
    last = get_translated_chapters()
    if not last:
        return {"count": 0, "last": 0, "next": 1, "pct": 0.0}
    count = len(last)
    pct = count / TOTAL_CHAPTERS * 100
    return {
        "count": count,
        "last": last[-1],
        "next": last[-1] + 1,
        "pct": pct,
        "remaining": TOTAL_CHAPTERS - count,
    }


def get_validation_summary(chapters: list[int]) -> dict:
    """Quick validation pass — sample every Nth chapter for speed."""
    if not chapters:
        return {"pass": 0, "fail": 0, "sampled": 0}

    validate_script = Path(__file__).parent / "validate_chapter.py"
    if not validate_script.exists():
        return {"pass": 0, "fail": 0, "sampled": 0, "error": "validate_chapter.py not found"}

    passed = 0
    failed = 0
    sampled = 0

    # Sample: check all if ≤20 chapters, else every 5th + first + last
    if len(chapters) <= 20:
        to_check = chapters
    else:
        to_check = [chapters[0]] + chapters[::5] + [chapters[-1]]
        to_check = sorted(set(to_check))

    for ch in to_check:
        result = subprocess.run(
            [sys.executable, str(validate_script), str(ch)],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(Path(__file__).parent.parent),
            timeout=30,
        )
        sampled += 1
        if "PASSED" in result.stdout:
            passed += 1
        elif "FAILED" in result.stdout:
            failed += 1

    return {"pass": passed, "fail": failed, "sampled": sampled}


def get_recent_activity() -> str:
    """Read last few lines from progress.md recent activity."""
    if not PROGRESS_FILE.exists():
        return "(no progress.md)"
    text = PROGRESS_FILE.read_text(encoding="utf-8")
    # Find recent activity section
    sections = re.split(r"^## ", text, flags=re.MULTILINE)
    if len(sections) >= 2:
        return sections[-1].strip()[:300]
    return text[:300]


def format_dashboard(progress: dict, validation: dict, activity: str, brief: bool = False) -> str:
    if brief:
        status = "✅" if validation.get("fail", 0) == 0 else "⚠️"
        return (
            f"{status} {progress['count']}/{TOTAL_CHAPTERS} ch "
            f"({progress['pct']:.1f}%) | "
            f"Next: ch {progress['next']} | "
            f"Val: ✅{validation.get('pass',0)} ❌{validation.get('fail',0)}"
        )

    bar_len = 25
    filled = int(bar_len * progress["pct"] / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    lines = [
        f"🦊 NovelClaw Dashboard — {NOVEL}",
        f"",
        f"📊 Progress: [{bar}] {progress['pct']:.1f}%",
        f"   Translated: {progress['count']}/{TOTAL_CHAPTERS} chapters",
        f"   Remaining: {progress['remaining']}",
        f"   Last: Ch {progress['last']}  →  Next: Ch {progress['next']}",
        f"",
        f"📋 Validation (sampled {validation.get('sampled', 0)} ch):",
        f"   ✅ Pass: {validation.get('pass', 0)}  |  ❌ Fail: {validation.get('fail', 0)}",
        f"",
        f"📝 Recent Activity:",
    ]

    # Add recent activity (indented)
    for line in activity.splitlines()[:8]:
        if line.strip():
            lines.append(f"   {line.strip()}")

    lines.append("")
    lines.append("Quick commands:")
    lines.append(f"  pre {progress['next']}     → prepare next chapter")
    lines.append(f"  val              → validate last")
    lines.append(f"  status           → full status")
    lines.append(f"  audit            → glossary coverage")

    return "\n".join(lines)


def main():
    global NOVEL, ROOT, CHAP_DIR, PROGRESS_FILE
    brief = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            NOVEL = args[i + 1]
            ROOT = get_novel_root(NOVEL)
            CHAP_DIR = ROOT / "chapters"
            PROGRESS_FILE = ROOT / "progress.md"
            i += 2
        elif args[i] == "--brief":
            brief = True
            i += 1
        else:
            i += 1

    chapters = get_translated_chapters()
    progress = get_progress_info()
    validation = get_validation_summary(chapters)
    activity = get_recent_activity()

    print(format_dashboard(progress, validation, activity, brief))


if __name__ == "__main__":
    main()
