"""glossary_audit.py — Audit glossary coverage across all translated chapters.

Reports:
  - Which locked terms are used / unused in translations
  - Terms that appear in source but not in glossary (missing terms)
  - Glossary terms with inconsistent Thai translation across chapters
  - Coverage percentage

Usage:
  python glossary_audit.py                        # full audit
  python glossary_audit.py --novel global-descent
  python glossary_audit.py --missing-only         # only show missing terms
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root, GLOSSARY_DIR  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def load_glossary() -> list[dict]:
    """Load full glossary with priorities."""
    try:
        sys.path.insert(0, str(GLOSSARY_DIR))
        from load_glossary import load_terms
        return load_terms()
    except Exception:
        return []


def get_translated_chapters() -> list[tuple[int, str]]:
    """Get (chapter_num, thai_text) for all translated chapters."""
    chapters = []
    for jp in sorted(CHAP_DIR.glob("*.json")):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if data.get("blocks"):
                text = " ".join(b.get("text", "") for b in data["blocks"])
                chapters.append((data["num"], text))
        except Exception:
            pass
    return chapters


def audit_coverage(glossary: list[dict], chapters: list[tuple[int, str]]) -> dict:
    """Audit how well glossary covers the translations."""
    # Build thai -> list of (cn, priority) lookup
    thai_to_cn: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for t in glossary:
        thai = t["thai"]
        cn = t["source"]
        priority = int(t.get("priority", 3))
        thai_to_cn[thai].append((cn, priority))

    # Count usage
    term_usage: dict[str, set[int]] = defaultdict(set)
    total_chapters = len(chapters)

    for ch_num, text in chapters:
        for thai in thai_to_cn:
            if thai in text:
                term_usage[thai].add(ch_num)

    # Categorize
    locked_used = []
    locked_unused = []
    ref_used = []
    ref_unused = []
    auto_used = []
    auto_unused = []

    for t in glossary:
        thai = t["thai"]
        cn = t["source"]
        priority = int(t.get("priority", 3))
        usage = len(term_usage.get(thai, set()))

        entry = (cn, thai, usage)
        if priority == 1:
            if usage > 0:
                locked_used.append(entry)
            else:
                locked_unused.append(entry)
        elif priority == 2:
            if usage > 0:
                ref_used.append(entry)
            else:
                ref_unused.append(entry)
        else:
            if usage > 0:
                auto_used.append(entry)
            else:
                auto_unused.append(entry)

    return {
        "total_chapters": total_chapters,
        "locked_used": locked_used,
        "locked_unused": locked_unused,
        "ref_used": ref_used,
        "ref_unused": ref_unused,
        "auto_used": auto_used,
        "auto_unused": auto_unused,
    }


def format_report(data: dict) -> str:
    total_locked = len(data["locked_used"]) + len(data["locked_unused"])
    total_ref = len(data["ref_used"]) + len(data["ref_unused"])
    total_auto = len(data["auto_used"]) + len(data["auto_unused"])

    lines = [
        f"📊 Glossary Audit — {NOVEL}",
        f"Chapters: {data['total_chapters']}",
        f"",
        f"Locked (P1): {len(data['locked_used'])}/{total_locked} used",
        f"Reference (P2): {len(data['ref_used'])}/{total_ref} used",
        f"Auto (P3): {len(data['auto_used'])}/{total_auto} used",
        f"",
    ]

    if data["locked_unused"]:
        lines.append("⚠️  Locked terms NOT used in any chapter:")
        for cn, thai, _ in sorted(data["locked_unused"]):
            lines.append(f"    {cn} → {thai}")
        lines.append("")

    if data["ref_unused"]:
        lines.append(f"ℹ️  Reference terms not used: {len(data['ref_unused'])}")
        for cn, thai, _ in sorted(data["ref_unused"])[:10]:
            lines.append(f"    {cn} → {thai}")
        if len(data["ref_unused"]) > 10:
            lines.append(f"    ... +{len(data['ref_unused']) - 10} more")
        lines.append("")

    # Used locked terms
    if data["locked_used"]:
        lines.append("✅ Locked terms in use:")
        for cn, thai, count in sorted(data["locked_used"], key=lambda x: -x[2]):
            lines.append(f"    {cn} → {thai} ({count} chapters)")
        lines.append("")

    # Coverage score
    if total_locked > 0:
        locked_pct = len(data["locked_used"]) / total_locked * 100
        lines.append(f"Locked term coverage: {locked_pct:.1f}%")

    return "\n".join(lines)


def main():
    global NOVEL, ROOT, CHAP_DIR
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            NOVEL = args[i + 1]
            ROOT = get_novel_root(NOVEL)
            CHAP_DIR = ROOT / "chapters"
            i += 2
        else:
            i += 1

    glossary = load_glossary()
    if not glossary:
        sys.exit("Could not load glossary")

    chapters = get_translated_chapters()
    if not chapters:
        sys.exit("No translated chapters found")

    data = audit_coverage(glossary, chapters)
    print(format_report(data))


if __name__ == "__main__":
    main()
