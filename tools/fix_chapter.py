"""fix_chapter.py — Re-translate a specific chapter that failed validation.

Prepares the same context as translate_next.py but for a specific chapter.
Optionally clears existing translation first.

Usage:
  python fix_chapter.py 74                    # prepare context for ch 74
  python fix_chapter.py 74 --clear            # clear existing translation first
  python fix_chapter.py 74 --novel global-descent
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root  # noqa: E402
from translate_next import (
    load_source_from_arg, build_glossary_context,
    get_last_summaries, get_characters, get_style_notes,
    get_chapter_title,
)

NOVEL = "global-descent"
ROOT: Path = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"


def clear_translation(ch: int) -> bool:
    """Clear existing translation blocks from chapter JSON."""
    jp = CHAP_DIR / f"{ch:04d}.json"
    if not jp.exists():
        return False
    data = json.loads(jp.read_text(encoding="utf-8"))
    if "blocks" in data:
        # Save source before clearing
        if not data.get("source") or len(str(data.get("source", ""))) < 50:
            # blocks contain Thai translation, source is placeholder
            # We can't recover CN source from blocks
            pass
        data["blocks"] = []
        data["notes"] = data.get("notes", []) + [{
            "note": f"Cleared for re-translation by fix_chapter.py",
        }]
        jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    return False


def main():
    novel = NOVEL
    ch_arg = None
    do_clear = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--novel" and i + 1 < len(args):
            novel = args[i + 1]
            i += 2
        elif args[i] == "--clear":
            do_clear = True
            i += 1
        else:
            try:
                ch_arg = int(args[i])
            except ValueError:
                pass
            i += 1

    if not ch_arg:
        sys.exit("Usage: python fix_chapter.py <chapter_number> [--clear]")

    ch = ch_arg

    if do_clear:
        if clear_translation(ch):
            print(f"✅ Cleared translation for ch {ch}")
        else:
            print(f"⚠️  No translation found to clear for ch {ch}")

    # Delegate to translate_next context preparation
    from translate_next import ROOT, CHAP_DIR, SUMMARY_FILE, CHAR_FILE, STYLE_FILE
    import translate_next
    translate_next.ROOT = ROOT
    translate_next.CHAP_DIR = CHAP_DIR
    translate_next.SUMMARY_FILE = SUMMARY_FILE
    translate_next.CHAR_FILE = CHAR_FILE
    translate_next.STYLE_FILE = STYLE_FILE

    source = load_source_from_arg(ch, None)
    title = get_chapter_title(ch)
    glossary_ctx = build_glossary_context(source)
    recent_summaries = get_last_summaries(2)
    characters = get_characters()
    style = get_style_notes()

    sep = "━" * 60
    print(f"""
{sep}
🔧 RE-TRANSLATION CONTEXT — {novel} | Ch {ch}: {title}
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

## VALIDATION RULES
- Paragraph ratio: ≥1.0
- Numbers: ALL 2-3 digit numbers must carry over
- Length ratio: 1.0–4.0x CN source length
- ZERO CJK characters in Thai output
- All glossary P1 (locked) terms must use locked Thai

{sep}
""".strip())


if __name__ == "__main__":
    main()
