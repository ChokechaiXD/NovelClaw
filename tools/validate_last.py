"""validate_last.py — Validate the most recently translated chapter.

Runs validate_chapter.py on the latest translated chapter and formats
the result for Telegram delivery.

Usage:
  python validate_last.py                        # auto-detect last translated
  python validate_last.py 72                     # specific chapter
  python validate_last.py --novel global-descent 72
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def find_last_translated() -> int:
    """Find the highest chapter number with translated blocks."""
    best = 0
    for jp in CHAP_DIR.glob("*.json"):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if data.get("blocks") and data.get("num", 0) > best:
                best = data["num"]
        except Exception:
            pass
    if best == 0:
        sys.exit("No translated chapters found")
    return best


def run_validation(ch: int) -> str:
    """Run validate_chapter.py and capture output."""
    validate_script = Path(__file__).parent / "validate_chapter.py"
    if not validate_script.exists():
        sys.exit("validate_chapter.py not found")
    result = subprocess.run(
        [sys.executable, str(validate_script), str(ch)],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(Path(__file__).parent.parent),
    )
    return result.stdout + result.stderr


def format_for_telegram(ch: int, output: str) -> str:
    """Format validation output for Telegram."""
    # Extract key info
    passed = "PASSED" in output
    failed = "FAILED" in output

    # Extract warnings
    warnings = []
    for line in output.splitlines():
        if line.strip().startswith("⚠"):
            warnings.append(line.strip())

    # Extract stats
    stats = {}
    for line in output.splitlines():
        m = re.search(r"Paragraphs: source=(\d+) \| translation=(\d+)", line)
        if m:
            stats["src_para"] = m.group(1)
            stats["tgt_para"] = m.group(2)
        m = re.search(r"Length: source=(\d+) \| translation=(\d+) \| ratio=([\d.]+)", line)
        if m:
            stats["src_len"] = m.group(1)
            stats["tgt_len"] = m.group(2)
            stats["ratio"] = m.group(3)
        m = re.search(r"Numbers.*missing=(\d+)", line)
        if m:
            stats["num_missing"] = m.group(1)

    status = "✅ PASS" if passed else "❌ FAIL"
    warn_count = len(warnings)

    lines = [
        f"📋 Validation — Ch {ch}",
        f"Status: {status}",
        f"Warnings: {warn_count}",
    ]
    if stats:
        lines.append(
            f"Stats: {stats.get('src_len','?')}→{stats.get('tgt_len','?')} chars "
            f"(ratio {stats.get('ratio','?')}) | "
            f"para {stats.get('src_para','?')}→{stats.get('tgt_para','?')} | "
            f"nums missing: {stats.get('num_missing','?')}"
        )
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings[:10]:
            lines.append(f"  {w}")
        if len(warnings) > 10:
            lines.append(f"  ... +{len(warnings)-10} more")

    return "\n".join(lines)


def main():
    novel = NOVEL
    ch_arg = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            novel = args[i + 1]
            global ROOT, CHAP_DIR
            ROOT = get_novel_root(novel)
            CHAP_DIR = ROOT / "chapters"
            i += 2
        elif args[i] == "--novel":
            i += 1
        else:
            try:
                ch_arg = int(args[i])
            except ValueError:
                pass
            i += 1

    ch = ch_arg or find_last_translated()
    output = run_validation(ch)
    print(format_for_telegram(ch, output))


if __name__ == "__main__":
    main()
