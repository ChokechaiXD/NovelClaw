"""save.py — Unified chapter save + validate (merges save_chapter.py + save_translated.py).

Pipeline (when text input provided — from file or stdin):
  1. Read Thai text (from file argument, stdin pipe, or stdin `-`)
  2. Parse Thai text into blocks (dialogue / narration / system / end)
  3. Merge with existing chapter JSON metadata
  4. Schema validate (Pydantic)
  5. Glossary doctor (transmittor: detect, don't fix)
  6. Block on errors; report warnings
  7. Save as JSON format
  8. Update FTS index
  9. Update progress.md

Pipeline (when no text input — validate existing JSON):
  1. Read chapter (.json canonical, .md legacy fallback, --from-md migrate)
  2. Schema validate (Pydantic) — JSON only; MD gets basic checks
  3. Glossary doctor (transmittor: detect, don't fix)
  4. Block on errors; report warnings
  5. Save (JSON format, with FTS index update)

Usage:
    python tools/save.py 122 translated.txt           # from file
    echo "Thai text..." | python tools/save.py 122 -    # from stdin
    python tools/save.py 122                           # validate existing
    python tools/save.py 113 --dry-run                 # validate only
    python tools/save.py 113 --strict                  # block on warnings too
    python tools/save.py 113 --from-md                 # migrate .md → .json first
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root, CHAPTERS_DIR, GLOSSARY_DIR  # noqa: E402


# ────────────────────────────────────────────────────────────────────
# Block parsing (from save_translated.py)
# ────────────────────────────────────────────────────────────────────

def parse_thai_blocks(text: str) -> list[dict]:
    """Parse Thai translation text into blocks array.

    Rules:
      - Lines starting with 「」 or 『』or containing dialogue markers → dialogue
      - Lines starting with 【】 or [] → system
      - "(จบบท)" or "(end)" at end → end block
      - Empty lines separate blocks
      - Everything else → narration
    """
    blocks = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # System messages 【】[]
        if line.startswith("【") or line.startswith("["):
            if re.match(r'^【[^】]+】', line) or re.match(r'^\[[^\]]+\]', line):
                blocks.append({"type": "system", "text": line})
                continue

        # End marker
        if "(จบบท)" in line or line.strip() == "(end)":
            blocks.append({"type": "end", "text": line})
            continue

        # Dialogue 「」 or 『』or ""
        if (line.startswith("「") and line.endswith("」")) or \
           (line.startswith("『") and line.endswith("』")) or \
           (line.startswith('"') and line.endswith('"')):
            blocks.append({"type": "dialogue", "text": line, "speaker": None})
            continue

        # Narration (everything else)
        blocks.append({"type": "narration", "text": line})

    return blocks


# ────────────────────────────────────────────────────────────────────
# Chapter JSON merge / save (from save_translated.py, adapted)
# ────────────────────────────────────────────────────────────────────

def load_existing_chapter_json(ch: int, chapters_dir: Path) -> dict | None:
    """Load existing chapter JSON to preserve metadata."""
    jp = chapters_dir / f"{ch:04d}.json"
    if jp.exists():
        return json.loads(jp.read_text(encoding="utf-8"))
    return None


def build_chapter_json(ch: int, blocks: list[dict], title: str,
                       chapters_dir: Path) -> dict:
    """Build chapter JSON data from parsed blocks, merging with existing."""
    existing = load_existing_chapter_json(ch, chapters_dir)

    if existing:
        data = existing.copy()
        data["blocks"] = blocks
        if title and not data.get("title"):
            data["title"] = title
    else:
        data = {
            "schema_version": 2,
            "num": ch,
            "title": title or f"Ch {ch}",
            "blocks": blocks,
            "source": f"ch {ch}",
            "notes": [],
        }
    return data


def write_chapter_json(data: dict, ch: int, chapters_dir: Path) -> Path:
    """Write chapter JSON to disk."""
    jp = chapters_dir / f"{ch:04d}.json"
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                  encoding="utf-8")
    return jp


# ────────────────────────────────────────────────────────────────────
# Short-validation (from save_translated.py)
# ────────────────────────────────────────────────────────────────────

def quick_validate(blocks: list[dict]) -> dict:
    """Run quick structural validation on parsed blocks."""
    all_text = " ".join(b.get("text", "") for b in blocks)

    issues = []

    # CJK check
    cjk_chars = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', all_text)
    if cjk_chars:
        issues.append(
            f"\u26a0\ufe0f  {len(cjk_chars)} CJK chars remaining: "
            f"{''.join(set(cjk_chars[:10]))}"
        )

    # Block count
    if len(blocks) < 5:
        issues.append(f"\u26a0\ufe0f  Only {len(blocks)} blocks \u2014 seems short")

    return {
        "blocks": len(blocks),
        "chars": len(all_text),
        "issues": issues,
        "passed": len(issues) == 0,
    }


# ────────────────────────────────────────────────────────────────────
# Progress update (from save_translated.py)
# ────────────────────────────────────────────────────────────────────

def update_progress(ch: int, progress_file: Path, total: int = 1239):
    """Update progress.md with new last translated chapter."""
    if not progress_file.exists():
        return
    text = progress_file.read_text(encoding="utf-8")
    # Update "Last translated: ch N"
    text = re.sub(
        r"(\*\*Last translated:\*\*\s*)ch\s*\d+",
        f"\\1ch {ch}",
        text,
    )
    # Update "Next chapter: ch N+1"
    text = re.sub(
        r"(\*\*Next chapter:\*\*\s*)ch\s*\d+",
        f"\\1ch {ch + 1}",
        text,
    )
    # Update progress percentage
    pct = ch / total * 100
    text = re.sub(
        r"(\*\*Total progress:\*\*\s*)\d+/(\d+)\s*\([\d.]+%\)",
        f"\\1{ch}/{total} ({pct:.2f}%)",
        text,
    )
    progress_file.write_text(text, encoding="utf-8")


# ────────────────────────────────────────────────────────────────────
# FTS index (from save_chapter.py)
# ────────────────────────────────────────────────────────────────────

def save_to_fts(chapter, ch_num: int, glossary_dir: Path):
    """Update FTS index for this chapter."""
    fts_db = glossary_dir.parent / 'chapters' / 'fts_index.db'
    conn = sqlite3.connect(str(fts_db))
    conn.execute('DELETE FROM chapter_fts WHERE num = ?', (ch_num,))
    for block in chapter.blocks:
        text = getattr(block, 'text', str(block))
        if text:
            conn.execute(
                'INSERT INTO chapter_fts (num, type, text) VALUES (?, ?, ?)',
                (ch_num, block.__class__.__name__, text[:2000])
            )
    conn.commit()
    conn.close()


# ────────────────────────────────────────────────────────────────────
# Glossary doctor (from save_chapter.py)
# ────────────────────────────────────────────────────────────────────

def run_glossary_doctor(ch: int, glossary_dir: Path):
    """Run glossary doctor, returns list of issues."""
    db_path = glossary_dir / 'glossary.db'
    try:
        from glossary_doctor import load_glossary, validate_chapter as _doctor
        glossary, alias_map, style_rules = load_glossary()
        return _doctor(ch, glossary, alias_map, style_rules, log_to_db=False)
    except Exception as e:
        print(f'\u26a0\ufe0f  Doctor unavailable: {e}')
        return []


# ────────────────────────────────────────────────────────────────────
# Schema validation (from save_chapter.py)
# ────────────────────────────────────────────────────────────────────

def validate_and_save_json(ch: int, data: dict, json_path: Path,
                           dry_run: bool, strict: bool,
                           glossary_dir: Path):
    """Validate chapter dict against schema, run doctor, save."""
    from schema import Chapter
    from chapter_io import save_chapter as _save

    # Schema validation
    try:
        validated = Chapter(**data)
        print(f'\u2713 ch{ch} schema valid ({len(validated.blocks)} blocks, '
              f'title="{validated.title}")')
    except Exception as e:
        print(f'\u274c ch{ch} schema error: {e}')
        sys.exit(1)

    # Glossary doctor
    issues = run_glossary_doctor(ch, glossary_dir)
    errors = [i for i in issues if i.get('severity') == 'error']
    warnings = [i for i in issues if i.get('severity') == 'warning']
    info = [i for i in issues if i.get('severity') == 'info']

    print(f'\U0001f4cb ch{ch} doctor: \u274c{len(errors)} '
          f'\u26a0\ufe0f{len(warnings)} \u2139\ufe0f{len(info)}')

    if errors:
        print(f'\n\u274c ch{ch} BLOCKED \u2014 fix errors first:')
        for e in errors:
            print(f'   {e.get("rule_type", "?")}: {e.get("pattern", "")[:80]}')
            if e.get('explanation'):
                print(f'      Why: {e["explanation"][:100]}')
        sys.exit(1)

    if warnings and strict:
        print(f'\n\u26a0\ufe0f  ch{ch} BLOCKED (--strict) \u2014 fix warnings:')
        for w in warnings[:5]:
            print(f'   {w.get("rule_type", "?")}: {w.get("pattern", "")[:80]}')
        sys.exit(2)

    if warnings:
        for w in warnings[:5]:
            print(f'   \u26a0 {w.get("rule_type", "?")}: {w.get("pattern", "")[:80]}')

    # Save
    if dry_run:
        print(f'\n[dry-run] would save to {json_path.name}')
    else:
        _save(validated, json_path)
        try:
            save_to_fts(validated, ch, glossary_dir)
        except Exception:
            pass
        print(f'\n\u2713 ch{ch} saved \u2192 {json_path.name}')

    return validated


# ────────────────────────────────────────────────────────────────────
# Text-input pipeline (save_translated.py mode)
# ────────────────────────────────────────────────────────────────────

def pipeline_from_text(ch: int, thai_text: str, title_arg: str,
                       chapters_dir: Path, glossary_dir: Path,
                       progress_file: Path,
                       dry_run: bool, strict: bool):
    """Parse Thai text, validate, save, update progress."""
    # Parse
    blocks = parse_thai_blocks(thai_text)
    if not blocks:
        sys.exit("No blocks parsed from Thai text")

    # Quick validate
    qv = quick_validate(blocks)
    if qv["issues"]:
        for issue in qv["issues"]:
            print(f"  {issue}")

    # Build + validate + save
    data = build_chapter_json(ch, blocks, title_arg, chapters_dir)
    json_path = chapters_dir / f"{ch:04d}.json"
    validate_and_save_json(ch, data, json_path, dry_run, strict, glossary_dir)

    # Update progress
    if not dry_run:
        update_progress(ch, progress_file)
        print(f"  Progress: updated to ch {ch + 1}")

    # Final summary
    status = "\u2705" if qv["passed"] else "\u26a0\ufe0f"
    print(f"""
{status} Saved Ch {ch}
  File: {json_path}
  Blocks: {qv['blocks']}
  Characters: {qv['chars']}
""".strip())

    if qv["issues"]:
        print("Issues:")
        for issue in qv["issues"]:
            print(f"  {issue}")


# ────────────────────────────────────────────────────────────────────
# Existing-file pipeline (save_chapter.py mode)
# ────────────────────────────────────────────────────────────────────

def pipeline_from_existing(ch: int, chapters_dir: Path, glossary_dir: Path,
                           dry_run: bool, strict: bool, from_md: bool):
    """Validate and re-save an existing chapter file."""
    json_path = chapters_dir / f'{ch:04d}.json'
    md_path = chapters_dir / f'{ch:04d}.md'

    # Resolve input file
    if from_md:
        if not md_path.exists():
            print(f'\u274c ch{ch}: .md not found at {md_path}')
            sys.exit(1)
        from migrate_to_json import migrate
        ok, msg = migrate(ch, dry_run=False)
        if not ok:
            print(f'\u274c ch{ch}: migrate failed: {msg}')
            sys.exit(1)
        input_path = json_path
    elif json_path.exists():
        input_path = json_path
    elif md_path.exists():
        input_path = md_path
    else:
        print(f'\u274c ch{ch}: no chapter file found (.json or .md)')
        sys.exit(1)

    # Load data
    if input_path.suffix == '.json':
        data = json.loads(input_path.read_text(encoding='utf-8'))
        validate_and_save_json(ch, data, json_path, dry_run, strict, glossary_dir)
    else:
        # MD: basic checks only, no schema validation
        content = input_path.read_text(encoding='utf-8')
        lines = content.splitlines()
        print(f'\u2713 ch{ch} MD loaded ({len(lines)} lines, basic checks only)')

        # Glossary doctor on raw MD
        issues = run_glossary_doctor(ch, glossary_dir)
        errors = [i for i in issues if i.get('severity') == 'error']
        warnings = [i for i in issues if i.get('severity') == 'warning']
        info = [i for i in issues if i.get('severity') == 'info']
        print(f'\U0001f4cb ch{ch} doctor: \u274c{len(errors)} '
              f'\u26a0\ufe0f{len(warnings)} \u2139\ufe0f{len(info)}')

        if errors:
            print(f'\n\u274c ch{ch} BLOCKED \u2014 fix errors first:')
            for e in errors:
                print(f'   {e.get("rule_type", "?")}: {e.get("pattern", "")[:80]}')
                if e.get('explanation'):
                    print(f'      Why: {e["explanation"][:100]}')
            sys.exit(1)

        if not dry_run:
            print(f'\n\u2713 ch{ch} validated (MD \u2014 no save in MD mode; '
                  f'run --from-md to migrate)')
        else:
            print(f'\n[dry-run] would validate {md_path.name}')


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Save + validate chapter (unified save tool)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python tools/save.py 122 translated.txt           from file
  echo "Thai text" | python tools/save.py 122 -      from stdin
  python tools/save.py 122                           validate existing
  python tools/save.py 113 --dry-run                 validate only
  python tools/save.py 113 --strict                  block on warnings
  python tools/save.py 113 --from-md                 migrate .md → .json
  python tools/save.py 122 thai.txt --title "Ch 122" with title
""")
    ap.add_argument('chapter', type=int, help='Chapter number')
    ap.add_argument('text_file', nargs='?', default=None,
                    help='Thai text file, or - for stdin. '
                         'If omitted, validates existing chapter.')
    ap.add_argument('--novel', type=str, default=None,
                    help='Novel slug (default: global-descent or NOVEL_SLUG env)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Validate only, do not save')
    ap.add_argument('--strict', action='store_true',
                    help='Block on warnings too')
    ap.add_argument('--from-md', action='store_true',
                    help='Read from .md then convert to .json')
    ap.add_argument('--title', type=str, default='',
                    help='Chapter title (used when saving new translation)')
    args = ap.parse_args()

    # Resolve novel-specific paths
    root = get_novel_root(args.novel)
    glossary_dir = root / 'glossary'
    chapters_dir = root / 'chapters'
    progress_file = root / 'progress.md'

    ch = args.chapter

    # ── Determine mode ──────────────────────────────────────────────
    # If text_file is provided (or stdin is piped), use text-input pipeline
    # Otherwise, use existing-file pipeline

    thai_text = None
    if args.text_file == '-':
        thai_text = sys.stdin.read()
    elif args.text_file is not None:
        p = Path(args.text_file)
        if not p.exists():
            sys.exit(f"File not found: {args.text_file}")
        thai_text = p.read_text(encoding='utf-8')
    elif not sys.stdin.isatty():
        # stdin is piped but no text_file arg given
        thai_text = sys.stdin.read()

    if thai_text is not None and thai_text.strip():
        # Text-input pipeline (save_translated.py mode)
        pipeline_from_text(
            ch=ch,
            thai_text=thai_text,
            title_arg=args.title,
            chapters_dir=chapters_dir,
            glossary_dir=glossary_dir,
            progress_file=progress_file,
            dry_run=args.dry_run,
            strict=args.strict,
        )
    else:
        # Existing-file pipeline (save_chapter.py mode)
        pipeline_from_existing(
            ch=ch,
            chapters_dir=chapters_dir,
            glossary_dir=glossary_dir,
            dry_run=args.dry_run,
            strict=args.strict,
            from_md=args.from_md,
        )


if __name__ == '__main__':
    main()
