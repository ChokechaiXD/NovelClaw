"""pre_chapter.py — Prep context for the NEXT chapter Mika will translate.

Output everything Mika needs to start a high-quality translation:
  1. Source text (cleaned of line numbers / reader comments)
  2. Glossary terms that appear in the source (so Mika doesn't miss any)
  3. Last 2 chapter summaries (tone consistency)
  4. Current summary entry (what happened so far)
  5. Style notes

Usage:
  python pre_chapter.py            # next chapter (from progress.md)
  python pre_chapter.py 81         # specific chapter number
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT, GLOSSARY_DIR  # noqa: E402

ROOT = NOVEL_ROOT



def read_progress() -> int:
    """Next chapter to translate from progress.md."""
    p = ROOT / 'progress.md'
    m = re.search(r'Next chapter[:\s]*\*\*\s*ch\s*(\d+)', p.read_text(encoding='utf-8'), re.IGNORECASE)
    if not m:
        sys.exit("Could not parse progress.md for 'Next chapter'")
    return int(m.group(1))


def load_glossary() -> list[tuple[str, str, str]]:
    """Load all locked+reference+auto terms as (source, thai, notes) tuples.

    Primary source: glossary.yml (canonical, git-tracked).
    Legacy fallback: .md table files (still works, used during migration).
    """
    from load_glossary import load_terms
    terms = load_terms()
    if terms:
        return [(t["source"], t["thai"], t.get("notes") or "") for t in terms]

    # Legacy fallback: parse .md tables
    rows = []
    for tier in ('locked.md', 'reference.md', 'auto.md'):
        for line in (GLOSSARY_DIR / tier).read_text(encoding='utf-8').splitlines():
            if not line.startswith('| ') or line.startswith('|--') or 'Source' in line:
                continue
            cells = [c.strip() for c in line.split('|')]
            if len(cells) >= 6 and cells[1] and cells[1] != '-':
                rows.append((cells[1], cells[2], cells[5]))
    return rows


def load_glossary_yml() -> list[dict]:
    """Load rich term data from glossary.yml (explanation, category, etc).

    Used for context injection — locked terms get full explanation;
    others just source+thai.
    """
    from load_glossary import load_terms
    return load_terms()


def find_terms_in_source(source: str, glossary: list) -> dict[str, str]:
    """Return {source_term: thai_translation} for glossary terms in source.

    Uses glossary_index for lazy lookup — only loads relevant terms
    instead of full 82KB glossary.
    """
    try:
        from glossary_index import GlossaryIndex
        idx = GlossaryIndex()
        idx.build()
        terms = idx.lookup(text=source)
        return {src: thai for src, thai, _ in terms}
    except Exception:
        # Fallback: scan all terms
        found = {}
        for src, thai, _ in glossary:
            if src in source:
                found[src] = thai
        return found


def clean_source(raw: str) -> str:
    """Strip line numbers, reader comments, duplicate title — same as scraper clean."""
    # Remove lines that are only reader comments (short Chinese lines with no period/punctuation, often meta)
    # Keep paragraphs separated by blank lines
    # Strip trailing meta footer
    parts = raw.split('\n---\n')
    body = parts[0]
    # Remove duplicate title (line 3-4 usually)
    lines = body.split('\n')
    # First line is title, second is blank, third+ is duplicate title in body
    # Skip until we find a real paragraph
    out = []
    in_body = False
    for line in lines[1:]:  # skip H1
        stripped = line.strip()
        if not in_body:
            # Skip empty lines, "全球降臨" tags, and chapter markers like "第XXX章"
            if stripped == '' or '全球降臨' in stripped:
                continue
            # Bug #19 regression: only skip lines that look like chapter markers
            # (e.g. "第五章 開局"), not arbitrary paragraphs that start with "第"
            # (e.g. "第一段落" = "first paragraph").
            if re.match(r'^第[一二三四五六七八九十百千零\d]+章', stripped):
                continue
            in_body = True
        out.append(line)
    text = '\n'.join(out)
    # Remove trailing line-number noise: "死了！11" → "死了！".
    # Real line numbers come from the scraper appending a number after
    # a CJK punctuation mark (！, 。, etc.) at end of a sentence. We must
    # NOT strip cases like "段落1" (paragraph 1) which is intentional content.
    # So require the preceding CJK char to be punctuation only (no CJK letters).
    # CJK punctuation: ！？。，；：…— (U+FF01-FF64 + U+3000-303F for CJK punct).
    text = re.sub(
        r'([！？。，；：…—]+)'  # CJK punctuation (no CJK letters)
        r'\s*'
        r'(\d{1,3})'
        r'(?=\s|$)',
        r'\1',
        text,
    )
    # Remove reader comment lines (short single-line meta — typically from
    # the source site like "求票求收藏！" / "本章未完待续"). Heuristic: a line
    # that is ONLY non-CJK characters, has no Thai letters, AND no common
    # Thai punctuation → drop. This is much safer than the old heuristic
    # that dropped any line without CJK punctuation, which would also drop
    # legitimate Thai-only paragraphs (e.g., stat screens, all-caps
    # headers, "Continue reading" prompts).
    text = re.sub(
        r'^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$',  # no CN AND no Thai
        '',
        text,
        flags=re.MULTILINE,
    )
    # Collapse 3+ blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def last_chapter_summaries(n: int) -> str:
    summary = (ROOT / 'summary.md').read_text(encoding='utf-8')
    m = re.search(r'(## Ch \d+.*?)(?=\n## |\Z)', summary, re.DOTALL)
    if m:
        return m.group(1).strip()
    return '(no summary)'


def get_chapter_title(num: int) -> str:
    f = ROOT / 'chapters' / f'{num:04d}.md'
    if not f.exists():
        return f'(ch {num} not yet translated)'
    raw = f.read_text(encoding='utf-8')
    m = re.match(r'# (.+)', raw)
    return m.group(1).strip() if m else '(no title)'


def load_dynamic_bans(limit: int = 10) -> list[str]:
    """Load top-N dynamic ban bigrams from learn_slop.py output.

    Sourced from `dynamic_bans.md` (auto-generated). Used to inject
    novel-specific crutch phrases into the pre-chapter context so
    Mika avoids them in the next translation.

    Returns list of `w1 w2` strings (sorted by frequency in source file).
    """
    f = ROOT / 'dynamic_bans.md'
    if not f.exists():
        return []
    text = f.read_text(encoding='utf-8')
    # Parse `## Banned (auto)` section, top entries
    m = re.search(r'## Banned \(auto\)(.*?)(?=\n## |\Z)', text, re.DOTALL)
    if not m:
        return []
    section = m.group(1)
    # Match `- w1 w2   (Nx in M ch)` — sort by total count desc
    entries = []
    for line in section.splitlines():
        m2 = re.match(r'^- (\S+) (\S+)\s+\((\d+)x in (\d+) ch\)', line)
        if m2:
            w1, w2, total, cc = m2.groups()
            entries.append((f'{w1} {w2}', int(total), int(cc)))
    entries.sort(key=lambda x: (-x[1], -x[2]))
    return [e[0] for e in entries[:limit]]


def main():
    # Determine target chapter
    if len(sys.argv) > 1:
        target = int(sys.argv[1])
    else:
        target = read_progress()

    # 1. Source
    src_file = ROOT / 'chapters' / 'source' / f'{target:04d}.md'
    if not src_file.exists():
        sys.exit(f'Source not found: {src_file}')
    raw_src = src_file.read_text(encoding='utf-8')
    source = clean_source(raw_src)

    # 2. Glossary terms in source (with explanations)
    # Primary: glossary.yml (git-tracked source of truth)
    # Optional: glossary.db adds explanations if it has them
    glossary_yml = load_glossary_yml()
    glossary_db_explanations: dict[str, str] = {}
    glossary_db_path = GLOSSARY_DIR / 'glossary.db'
    if glossary_db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(glossary_db_path)
            cur = conn.cursor()
            cur.execute('''SELECT source_norm, explanation FROM terms
                           WHERE status = "active" AND explanation IS NOT NULL''')
            for src, expl in cur.fetchall():
                if expl:
                    glossary_db_explanations[src] = expl
            conn.close()
        except Exception:
            pass

    # Find terms in source
    terms = find_terms_in_source(source, [(t["source"], t["thai"], "") for t in glossary_yml])
    if terms:
        # Build term_info from yml + (optional) db explanations
        term_info = {
            t["source"]: {
                "thai": t["thai"],
                "cat": t.get("category", "ทั่วไป"),
                "prio": t.get("priority", 3),
                "expl": glossary_db_explanations.get(t["source"], t.get("explanation", "") or ""),
            }
            for t in glossary_yml
        }
        terms_lines = []
        for src in sorted(terms.keys()):
            thai = terms[src]
            info = term_info.get(src, {})
            expl = info.get("expl", "")
            if expl and info.get("prio", 3) <= 2:
                # Locked/reference term — show explanation
                terms_lines.append(f'  {src:18} → {thai:30} [{info.get("cat", "ทั่วไป")}]')
                terms_lines.append(f'    📝 {expl[:100]}')
            else:
                terms_lines.append(f'  {src:18} → {thai:30} [{info.get("cat", "ทั่วไป")}]')
    else:
        terms_lines = ['  (none found in source)']

    # 3. Last chapter titles (for tone consistency)
    if target > 1:
        prev1 = get_chapter_title(target - 1)
        prev2 = get_chapter_title(target - 2) if target > 2 else '(n/a)'
    else:
        prev1 = prev2 = '(n/a)'

    # 4. Last summary entry
    summary_excerpt = last_chapter_summaries(target)

    # 5. Dynamic bans (Phase 3 — auto-learned crutch phrases)
    dynamic_bans = load_dynamic_bans(limit=10)

    # 6. Cross-chapter context (Phase 4 — FTS5 search)
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from chapter_search import format_context_block
        fts_context = format_context_block(target, top_k=3)
    except Exception as e:
        fts_context = f'(FTS5 context unavailable: {e})'

    # 7. NPC dossiers (Phase 2 — character voice consistency)
    try:
        from npc_bank import format_inject_block
        npc_block = format_inject_block(target, top_n=3)
    except Exception as e:
        npc_block = f'(NPC dossiers unavailable: {e})'

    # Output
    print('━' * 70)
    print(f'  PRE-CHAPTER CONTEXT — Ch {target}')
    print('━' * 70)
    print()
    print(f'📖 Previous chapters (for tone consistency):')
    print(f'   ch {target-2}: {prev2}')
    print(f'   ch {target-1}: {prev1}')
    print()
    print(f'📚 Last summary entry:')
    for line in summary_excerpt.splitlines()[:8]:
        print(f'   {line}')
    print('   ...')
    print()
    if dynamic_bans:
        print(f'🚫 Dynamic bans (avoid these crutch phrases — learned from prior ch):')
        for bg in dynamic_bans:
            print(f'   - {bg}')
        print()
    if fts_context:
        print(fts_context)
        print()
    if npc_block:
        print(npc_block)
        print()
    print(f'📝 SOURCE (ch {target}, cleaned):')
    print('─' * 70)
    print(source)
    print('─' * 70)
    print()
    print(f'🔤 Glossary terms in source ({len(terms)} found):')
    print('\n'.join(terms_lines))
    print()
    print('━' * 70)
    print(f'Ready to translate ch {target}. Save as:')
    print(f'  {ROOT}/chapters/{target:04d}.md')
    print('━' * 70)


if __name__ == '__main__':
    main()
