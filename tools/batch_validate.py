"""batch_validate.py — Validate all translated chapters and produce a summary report.

Runs validate_chapter.py on every translated chapter and outputs:
  - Total / pass / fail counts
  - List of failed chapters with reasons
  - Chapters with most warnings
  - Overall quality score

Usage:
  python batch_validate.py                        # all chapters
  python batch_validate.py --novel global-descent
  python batch_validate.py --failures-only       # show only failures
"""
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def get_translated_chapters() -> list[int]:
    """Get sorted list of translated chapter numbers."""
    chapters = []
    for jp in CHAP_DIR.glob("*.json"):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if data.get("blocks"):
                chapters.append(data["num"])
        except Exception:
            pass
    return sorted(chapters)


def validate_chapter(ch: int) -> dict:
    """Run validate_chapter.py on a chapter and parse results in-process."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    import validate_chapter as vc

    # Sync novel paths to validate_chapter module
    vc.ROOT = ROOT
    vc.GLOSSARY_DIR = ROOT / "glossary"

    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        try:
            exit_code = vc.validate(ch, do_fix=False)
        except SystemExit as e:
            exit_code = e.code or 0
        except Exception as e:
            print(f"FAILED: {e}")
            exit_code = 1

    output = f.getvalue()

    passed = exit_code == 0
    failed = exit_code != 0

    warnings = []
    for line in output.splitlines():
        w = line.strip()
        if w.startswith("⚠") or w.startswith("[WARN]"):
            warnings.append(w)

    # Extract stats
    stats = {}
    import re
    m = re.search(r"Length: source=(\d+) \| translation=(\d+) \| ratio=([\d.]+)", output)
    if m:
        stats["ratio"] = float(m.group(3))
    m = re.search(r"Numbers.*missing=(\d+)", output)
    if m:
        stats["num_missing"] = int(m.group(1))

    return {
        "ch": ch,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "warning_count": len(warnings),
        "stats": stats,
    }
def format_report(results: list[dict], failures_only: bool = False) -> str:
    total = len(results)
    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if r["failed"]]
    total_warnings = sum(r["warning_count"] for r in results)

    lines = [
        f"📊 Batch Validation Report — {NOVEL}",
        f"",
        f"Total chapters: {total}",
        f"✅ Passed: {len(passed)} ({len(passed)/total*100:.1f}%)" if total else "✅ Passed: 0",
        f"❌ Failed: {len(failed)} ({len(failed)/total*100:.1f}%)" if total else "❌ Failed: 0",
        f"Total warnings: {total_warnings}",
        f"",
    ]

    if failed:
        lines.append("Failed chapters:")
        for r in failed:
            warn_summary = f" ({r['warning_count']} warnings)" if r["warning_count"] else ""
            ratio = r["stats"].get("ratio", "?")
            lines.append(f"  ❌ Ch {r['ch']}{warn_summary} — ratio: {ratio}")
        lines.append("")

    # Top warning chapters
    by_warnings = sorted(results, key=lambda r: -r["warning_count"])[:5]
    if by_warnings and by_warnings[0]["warning_count"] > 0:
        lines.append("Most warnings:")
        for r in by_warnings:
            if r["warning_count"] > 0:
                lines.append(f"  ⚠️  Ch {r['ch']}: {r['warning_count']} warnings")
        lines.append("")

    # Quality score
    if total:
        # Score: 100 = all pass with 0 warnings
        warn_penalty = min(total_warnings * 0.5, 30)  # max 30pt penalty
        fail_penalty = len(failed) / total * 50  # max 50pt penalty
        score = max(0, 100 - warn_penalty - fail_penalty)
        lines.append(f"Quality Score: {score:.0f}/100")

    return "\n".join(lines)


def main():
    global NOVEL, ROOT, CHAP_DIR
    failures_only = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            NOVEL = args[i + 1]
            ROOT = get_novel_root(NOVEL)
            CHAP_DIR = ROOT / "chapters"
            i += 2
        elif args[i] == "--failures-only":
            failures_only = True
            i += 1
        else:
            i += 1

    chapters = get_translated_chapters()
    if not chapters:
        sys.exit("No translated chapters found")

    print(f"Validating {len(chapters)} chapters...")
    results = []
    for idx, ch in enumerate(chapters):
        r = validate_chapter(ch)
        results.append(r)
        # Progress indicator
        status = "✅" if r["passed"] else "❌"
        print(f"  [{idx+1}/{len(chapters)}] Ch {ch}: {status} ({r['warning_count']} warnings)")

    print("")
    print(format_report(results, failures_only))


if __name__ == "__main__":
    main()
