"""chapter_diff.py — Check glossary consistency across adjacent chapters.

Scans CN source of adjacent chapters to find terms that appear in
neighboring chapters but are missing in the target chapter.
This catches inconsistent term translation.

Usage:
  python chapter_diff.py 80                     # check ch 80 vs neighbors
  python chapter_diff.py 80 --window 3          # check ±3 chapters
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root, GLOSSARY_DIR  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def load_glossary() -> dict[str, str]:
    """Load {source_cn: thai} glossary."""
    try:
        sys.path.insert(0, str(GLOSSARY_DIR))
        from load_glossary import load_terms
        terms = load_terms()
        return {t["source"]: t["thai"] for t in terms}
    except Exception:
        return {}


def get_blocks_text(ch: int) -> str:
    """Get all text from chapter blocks (Thai translation)."""
    jp = CHAP_DIR / f"{ch:04d}.json"
    if not jp.exists():
        return ""
    try:
        data = json.loads(jp.read_text(encoding="utf-8"))
        parts = []
        for b in data.get("blocks", []):
            t = b.get("text", "")
            if isinstance(t, str):
                parts.append(t)
        return "\n".join(parts)
    except Exception:
        return ""


def find_cn_terms_in_text(text: str, glossary: dict[str, str]) -> dict[str, str]:
    """Find which CN glossary terms appear in Thai text (by Thai translation)."""
    found = {}
    for cn, thai in glossary.items():
        if thai in text:
            found[cn] = thai
    return found


def compute_diff(ch: int, window: int = 2, glossary: dict[str, str] = None) -> dict:
    if not glossary:
        glossary = load_glossary()

    current_text = get_blocks_text(ch)
    current_terms = find_cn_terms_in_text(current_text, glossary)

    # Get neighbor terms
    neighbor_terms: dict[str, list[int]] = {}
    for offset in range(-window, window + 1):
        if offset == 0:
            continue
        nb_ch = ch + offset
        text = get_blocks_text(nb_ch)
        terms = find_cn_terms_in_text(text, glossary)
        for cn, thai in terms.items():
            if cn not in neighbor_terms:
                neighbor_terms[cn] = []
            neighbor_terms[cn].append(nb_ch)

    # Terms in ≥2 neighbors but missing from current = suspicious
    missing = {
        cn: (thai, chs) for cn, (thai, chs) in (
            (cn, (thai, nb_chs)) for cn, thai in glossary.items()
            if (nb_chs := neighbor_terms.get(cn, [])) and cn not in current_terms and len(nb_chs) >= 2
        )
    }

    # Terms in current and at least 1 neighbor = consistent
    consistent = {cn: thai for cn, thai in current_terms.items() if cn in neighbor_terms}

    # Terms only in current (new) = OK
    new_terms = {cn: thai for cn, thai in current_terms.items() if cn not in neighbor_terms}

    return {
        "current_ch": ch,
        "current_count": len(current_terms),
        "consistent_count": len(consistent),
        "missing": missing,
        "new_terms": new_terms,
        "window": window,
    }


def format_diff(result: dict) -> str:
    ch = result["current_ch"]
    missing = result["missing"]
    new_terms = result["new_terms"]
    window = result["window"]

    lines = [
        f"📊 Chapter Diff — Ch {ch} (window ±{window})",
        f"",
        f"Glossary terms in ch {ch}: {result['current_count']}",
        f"Consistent (also in neighbors): {result['consistent_count']}",
        f"Missing (in ≥2 neighbors, not in current): {len(missing)}",
        f"New (only in current): {len(new_terms)}",
    ]

    if missing:
        lines.append("")
        lines.append("⚠️  Possibly missing glossary terms:")
        for cn, (thai, nb_chs) in sorted(missing.items(), key=lambda x: -len(x[1][1]))[:20]:
            nb_str = ", ".join(f"ch {c}" for c in nb_chs[:5])
            lines.append(f"    {cn} → {thai}  (in {nb_str})")
        if len(missing) > 20:
            lines.append(f"    ... +{len(missing) - 20} more")

    return "\n".join(lines)


def main():
    novel = NOVEL
    ch_arg = None
    window = 2
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            novel = args[i + 1]
            global ROOT, CHAP_DIR
            ROOT = get_novel_root(novel)
            CHAP_DIR = ROOT / "chapters"
            i += 2
        elif args[i] == "--window" and i + 1 < len(args):
            window = int(args[i + 1])
            i += 2
        else:
            try:
                ch_arg = int(args[i])
            except ValueError:
                pass
            i += 1

    if not ch_arg:
        sys.exit("Usage: python chapter_diff.py <chapter_number> [--window N]")

    glossary = load_glossary()
    if not glossary:
        sys.exit("Could not load glossary")

    result = compute_diff(ch_arg, window, glossary)
    print(format_diff(result))


if __name__ == "__main__":
    main()
