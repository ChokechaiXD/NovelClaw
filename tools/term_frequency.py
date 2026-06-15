"""term_frequency.py — Show glossary term usage frequency across all translated chapters.

Shows which glossary terms appear most often in translations,
helping identify over-used or under-used terms.

Usage:
  python term_frequency.py                        # all terms
  python term_frequency.py --locked               # only locked (P1) terms
  python term_frequency.py --top 20              # top 20
  python term_frequency.py --novel global-descent
"""
import json, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root, GLOSSARY_DIR  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def load_glossary() -> dict[str, str]:
    """Load glossary as {thai: source} for reverse lookup."""
    try:
        sys.path.insert(0, str(GLOSSARY_DIR))
        from load_glossary import load_terms
        terms = load_terms()
        return {t["thai"]: t["source"] for t in terms}
    except Exception:
        return {}


def count_term_usage(glossary: dict[str, str]) -> Counter:
    """Count how many chapters each Thai glossary term appears in."""
    term_chapters: dict[str, set[int]] = {}

    for jp in CHAP_DIR.glob("*.json"):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            ch = data.get("num", 0)
            # Get all Thai text from blocks
            thai_text = " ".join(
                b.get("text", "") for b in data.get("blocks", [])
                if b.get("type") in ("narration", "dialogue")
            )
            # Check each Thai glossary term
            for thai, source in glossary.items():
                if thai in thai_text:
                    if thai not in term_chapters:
                        term_chapters[thai] = set()
                    term_chapters[thai].add(ch)
        except Exception:
            pass

    return Counter({thai: len(chapters) for thai, chapters in term_chapters.items()})


def format_output(counter: Counter, glossary: dict, top: int = 50, locked_only: bool = False) -> str:
    lines = ["📊 Glossary Term Frequency", ""]

    if locked_only:
        # Filter to locked terms only
        try:
            sys.path.insert(0, str(GLOSSARY_DIR))
            from load_glossary import load_terms
            all_terms = load_terms()
            locked_thai = {t["thai"] for t in all_terms if t.get("priority") == 1}
            counter = Counter({k: v for k, v in counter.items() if k in locked_thai})
            lines.append("(Locked/P1 terms only)")
            lines.append("")
        except Exception:
            pass

    most_common = counter.most_common(top)
    if not most_common:
        return "No glossary terms found in translations."

    lines.append(f"{'Term (TH)':<30} {'Source (CN)':<15} {'Chapters':>8}")
    lines.append("─" * 55)
    for thai, count in most_common:
        source = glossary.get(thai, "?")
        lines.append(f"{thai:<30} {source:<15} {count:>8}")

    lines.append("")
    lines.append(f"Total unique terms used: {len(counter)}")
    total_mentions = sum(counter.values())
    lines.append(f"Total term-chapter mentions: {total_mentions}")

    return "\n".join(lines)


def main():
    novel = NOVEL
    top = 50
    locked_only = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            novel = args[i + 1]
            global ROOT, CHAP_DIR
            ROOT = get_novel_root(novel)
            CHAP_DIR = ROOT / "chapters"
            i += 2
        elif args[i] == "--top" and i + 1 < len(args):
            top = int(args[i + 1])
            i += 2
        elif args[i] == "--locked":
            locked_only = True
            i += 1
        else:
            i += 1

    glossary = load_glossary()
    if not glossary:
        sys.exit("Could not load glossary")

    counter = count_term_usage(glossary)
    print(format_output(counter, glossary, top, locked_only))


if __name__ == "__main__":
    main()
