"""translate_next.py — Prepare full translation context for the next chapter.

Prepares everything Mika needs to translate a chapter in one shot:
  1. Source text (from file, stdin, or chapter JSON)
  2. Glossary terms found in source (lazy-loaded via glossary_index)
  3. Last 2 chapter summaries (tone/continuity)
  4. Character quick-reference
  5. Style notes + format reminder
  6. Validation rules

Usage:
  python translate_next.py                        # auto-detect next from progress.md
  python translate_next.py 122                    # specific chapter number
  python translate_next.py 122 source.txt         # with source file
  python translate_next.py 122 -                  # read source from stdin
  echo "source text" | python translate_next.py 122 -
  python translate_next.py --novel global-descent 122
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root, GLOSSARY_DIR  # noqa: E402

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"
SUMMARY_FILE = ROOT / "summary.md"
CHAR_FILE = ROOT / "characters.md"
STYLE_FILE = ROOT / "style.md"
FORMAT_FILE = Path(__file__).parent.parent / "format_spec.md"


def read_progress() -> int:
    p = ROOT / "progress.md"
    if not p.exists():
        sys.exit("progress.md not found")
    m = re.search(
        r"Next chapter[:\\s]*\\*\\*\\s*ch\\s*(\\d+)",
        p.read_text(encoding="utf-8"), re.IGNORECASE,
    )
    if not m:
        sys.exit("Could not parse progress.md for 'Next chapter'")
    return int(m.group(1))


def load_source_from_arg(ch: int, source_arg: str | None) -> str:
    """Load source text from various sources."""
    if source_arg == "-":
        return sys.stdin.read()
    if source_arg:
        p = Path(source_arg)
        if not p.exists():
            sys.exit(f"Source file not found: {source_arg}")
        return p.read_text(encoding="utf-8")
    # Try chapter JSON
    jp = CHAP_DIR / f"{ch:04d}.json"
    if jp.exists():
        data = json.loads(jp.read_text(encoding="utf-8"))
        src = data.get("source", "")
        if isinstance(src, list):
            src = "\n".join(src)
        if len(str(src)) > 50:  # real source, not placeholder
            return str(src)
    # Try source.md in chapter folder
    sp = CHAP_DIR / f"{ch:04d}" / "source.md"
    if not sp.exists():
        sp = CHAP_DIR / str(ch) / "source.md"
    if sp.exists():
        return sp.read_text(encoding="utf-8")
    sys.exit(
        f"No source found for ch {ch}.\n"
        f"Provide source file: python translate_next.py {ch} source.txt\n"
        f"Or pipe: echo 'source' | python translate_next.py {ch} -"
    )


def get_chapter_title(ch: int) -> str:
    jp = CHAP_DIR / f"{ch:04d}.json"
    if jp.exists():
        data = json.loads(jp.read_text(encoding="utf-8"))
        return data.get("title", f"Ch {ch}")
    return f"Ch {ch}"


def build_glossary_context(source: str) -> str:
    try:
        sys.path.insert(0, str(GLOSSARY_DIR))
        from glossary_index import GlossaryIndex
        idx = GlossaryIndex()
        idx.build()
        terms = idx.lookup(text=source)
        if not terms:
            return "  (none found in source)"
        lines = []
        for src, thai, notes in terms[:40]:
            note_str = f" — {notes}" if notes else ""
            lines.append(f"  {src} → {thai}{note_str}")
        return "\n".join(lines)
    except Exception as e:
        return f"  (glossary lookup failed: {e})"


def get_last_summaries(n: int = 2) -> str:
    if not SUMMARY_FILE.exists():
        return "(no summary.md found)"
    text = SUMMARY_FILE.read_text(encoding="utf-8")
    sections = re.split(r"^## Ch ", text, flags=re.MULTILINE)
    rev = [s for s in sections if s.strip()][-n:]
    return "\n\n".join(rev[:n]) if rev else "(empty summary.md)"


def get_characters() -> str:
    if not CHAR_FILE.exists():
        return "(no characters.md)"
    text = CHAR_FILE.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith("- ") or line.startswith("| "):
            lines.append(line)
    return "\n".join(lines[:40]) if lines else "(empty)"


def get_style_notes() -> str:
    if STYLE_FILE.exists():
        return STYLE_FILE.read_text(encoding="utf-8")[:2000]
    return "(no style.md)"


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Prepare translation context for next chapter')
    ap.add_argument('chapter', type=int, nargs='?', help='Chapter number (default: from progress.md)')
    ap.add_argument('source_file', nargs='?', default=None, help='Source file path (or - for stdin)')
    ap.add_argument('--novel', type=str, default=None, help='Novel slug (default: global-descent or NOVEL_SLUG env)')
    ap.add_argument('--clear', action='store_true', help='Clear existing translation before preparing context')
    args = ap.parse_args()

    novel = args.novel or NOVEL
    global ROOT, CHAP_DIR, SUMMARY_FILE, CHAR_FILE, STYLE_FILE
    ROOT = get_novel_root(novel)
    CHAP_DIR = ROOT / "chapters"
    SUMMARY_FILE = ROOT / "summary.md"
    CHAR_FILE = ROOT / "characters.md"
    STYLE_FILE = ROOT / "style.md"

    ch = args.chapter or read_progress()

    # Clear existing translation if requested
    if args.clear:
        jp = CHAP_DIR / f"{ch:04d}.json"
        if jp.exists():
            data = json.loads(jp.read_text(encoding="utf-8"))
            if "blocks" in data:
                data["blocks"] = []
                data["notes"] = data.get("notes", []) + [{"note": "Cleared for re-translation"}]
                jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"✅ Cleared translation for ch {ch}")
        else:
            print(f"⚠️  No existing translation for ch {ch}")

    title = get_chapter_title(ch)
    source = load_source_from_arg(ch, args.source_file)
    glossary_ctx = build_glossary_context(source)
    recent_summaries = get_last_summaries(2)
    characters = get_characters()
    style = get_style_notes()

    sep = "━" * 60
    print(f"""
{sep}
📖 TRANSLATION CONTEXT — {novel} | Ch {ch}: {title}
{sep}

## SOURCE TEXT (CN)
{source}

## GLOSSARY TERMS IN SOURCE
{glossary_ctx}

## RECENT SUMMARIES (last 2 chapters)
{recent_summaries}

## CHARACTERS (quick reference)
{characters}

## STYLE NOTES
{style}

## FORMAT REMINDER
- Output Thai translation as plain text (one paragraph per block)
- Every source block → Thai block. No merging, no skipping.
- Dialogue: keep 「」 markers
- Numbers: MUST preserve all digits exactly
- No CJK characters in Thai output

## VALIDATION RULES (auto-checked after translation)
- Paragraph ratio: ≥1.0 (match or exceed source paragraph count)
- Numbers: ALL 2-3 digit numbers must carry over
- Length ratio: 1.0–4.0x CN source length
- ZERO CJK characters in Thai output
- All glossary P1 (locked) terms must use locked Thai

{sep}
""".strip())


if __name__ == "__main__":
    main()
