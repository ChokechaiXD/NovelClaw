"""chapter_search.py — SQLite FTS5 full-text search over translated chapters.

Problem: when translating ch 80, AI doesn't know what happened in ch 30.
Names of cities change, character status forgotten, subplot threads lost.

Solution: build an FTS5 index of all translated chapters. Before
translating ch N, search for top-K most relevant prior chapters and
inject their summaries into the pre-chapter context.

Why FTS5 over embeddings:
- Zero external API (offline, fast, no cost)
- Thai tokenizer available in SQLite (unicode61 + custom tokenchars)
- Sufficient for chapter-level retrieval (we only need "which prior
  chapter mentioned character X / place Y", not semantic similarity)
- Reuses the SQLite we already use for other tools

Inspired by:
- Megumin V7 "Long-Term Vault (Vector DB)" — but using FTS5 instead of
  actual vector embeddings (cheaper, simpler, no API dependency)
- Nemo Lore "Archive Retrieval: lexical search over entities, summaries,
  and raw text" — exact pattern adapted

Usage:
    python chapter_search.py index                    # build/rebuild FTS5 index
    python chapter_search.py search "曹星 蕾妮絲"     # find relevant chs
    python chapter_search.py context 80               # top-3 for ch 80's prep
    python chapter_search.py stats                    # index health
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT, get_novel_root# noqa: E402

# DB_FILE is the default. --novel-root <path> overrides (multi-novel support,
# added 2026-06-14 for Tier 3 #12 server endpoint).
def _resolve_db(novel_root: Path | None = None) -> Path:
    root = novel_root or NOVEL_ROOT
    return root / 'chapters' / 'fts_index.db'

# Backwards-compat: existing code uses DB_FILE constant. Most paths read this,
# so we keep it pointing at the default. --novel-root switches at call time.
DB_FILE = _resolve_db()


# ── Schema ─────────────────────────────────────────────────────────
SCHEMA = """
-- Virtual FTS5 table for full-text search
-- tokenize='unicode61 remove_diacritics 2' handles Thai/CJK/EN
CREATE VIRTUAL TABLE IF NOT EXISTS chapter_fts USING fts5(
    chapter_num UNINDEXED,
    title,
    body,
    tokenize='unicode61 remove_diacritics 2'
);

-- Metadata table (chapter summaries, last update)
CREATE TABLE IF NOT EXISTS chapter_meta (
    chapter_num INTEGER PRIMARY KEY,
    title TEXT,
    summary TEXT,
    indexed_at TEXT
);
"""


def get_conn(db_file: Path | None = None) -> sqlite3.Connection:
    """Get SQLite connection (creates DB if needed).

    `db_file` lets callers point at a per-novel index (e.g.
    novels/<slug>/chapters/fts_index.db). Defaults to the global NOVEL_ROOT
    index for backwards compat.
    """
    target = db_file or DB_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.executescript(SCHEMA)
    return conn


def extract_chapter_text(filepath: Path) -> tuple[int, str, str]:
    """Extract (chapter_num, title, body) from a translated chapter file.

    Two supported formats:
        # Title
        <blank>
        BODY
        <blank>
        ---
        <blank>
        *Source: ch N*

    NEW format (ch 94+, post-Session 8 fix):
        # Title
        <blank>
        *Source: ch N*
        <blank>
        ---
        <blank>
        BODY
        <blank>
        ---
        <blank>
        (optional meta note)

    Strategy: find the FIRST '---' line. If the chunk BEFORE it starts
    with '# Title' (no body in between), body is everything AFTER first
    '---' up to second '---' or end. Otherwise (old format), the chunk
    BEFORE first '---' is the body, and the chunk AFTER is meta.
    """
    text = filepath.read_text(encoding='utf-8')
    m = re.match(r'# (.+)', text)
    title = m.group(1).strip() if m else filepath.stem

    lines = text.splitlines()
    sep_indices = [i for i, ln in enumerate(lines) if ln.strip() == '---']

    if not sep_indices:
        # No separator: whole file (minus title) is body
        body = '\n'.join(lines[1:]).strip()
        # Try to extract chapter_num from title or filename; default to 0
        try:
            num = int(filepath.stem)
        except ValueError:
            m2 = re.search(r'(\d+)', title)
            num = int(m2.group(1)) if m2 else 0
        return num, title, body

    first_sep = sep_indices[0]
    # Look at the chunk BEFORE first '---' — is it just header (title + Source)?
    # If the first non-empty line is H1 and the second is *Source*, it's NEW format
    header_lines = [ln for ln in lines[:first_sep] if ln.strip()]
    is_new_format = (
        len(header_lines) >= 1
        and header_lines[0].startswith('# ')
        and len(header_lines) <= 2  # title + optional Source line
        and all('*Source:' in ln or ln.startswith('# ') for ln in header_lines[1:])
    )

    if is_new_format:
        # Body is between first and second ---
        second_sep = sep_indices[1] if len(sep_indices) >= 2 else len(lines)
        body = '\n'.join(lines[first_sep + 1:second_sep]).strip()
    else:
        # OLD format: body is BEFORE first ---, meta is AFTER
        body = '\n'.join(lines[:first_sep]).strip()
        # Drop the H1 title from the body
        if body.startswith('# '):
            body = '\n'.join(body.splitlines()[1:]).strip()

    # Try to extract chapter_num from title or filename; default to 0
    try:
        num = int(filepath.stem)
    except ValueError:
        m2 = re.search(r'(\d+)', title)
        num = int(m2.group(1)) if m2 else 0
    return num, title, body


def extract_summary(body: str, max_chars: int = 300) -> str:
    """Extract a short summary (first 1-2 non-empty paragraphs)."""
    paras = [p.strip() for p in body.split('\n\n') if p.strip()]
    out = []
    total = 0
    for p in paras:
        if total + len(p) > max_chars:
            break
        out.append(p)
        total += len(p)
    return '\n\n'.join(out)


def build_index(novel_root: Path | None = None) -> int:
    """Build/rebuild the FTS5 index from all translated chapters.

    Supports BOTH .json (new canonical) and .md (legacy). For .json, we
    extract text from each block. For .md, we use the legacy separator
    parser.

    `novel_root` defaults to NOVEL_ROOT (global-descent). Pass an
    alternate root to build a per-novel index.

    Returns number of chapters indexed.
    """
    root = novel_root or NOVEL_ROOT
    db_file = _resolve_db(root)
    conn = get_conn(db_file)
    cur = conn.cursor()
    chapters_dir = root / 'chapters'
    # Accept both formats — sort by numeric stem
    files = sorted(
        list(chapters_dir.glob('*.md')) + list(chapters_dir.glob('*.json')),
        key=lambda p: (int(p.stem) if p.stem.isdigit() else 0, p.suffix),
    )

    # Clear existing
    cur.execute('DELETE FROM chapter_fts')
    cur.execute('DELETE FROM chapter_meta')

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    count = 0
    for f in files:
        try:
            num, title, body = _extract_text(f)
        except (ValueError, IndexError, json.JSONDecodeError):
            continue
        summary = extract_summary(body)
        # Strip 【】 from indexed body to reduce noise (game stats)
        clean_body = re.sub(r'【[^】]*】', ' ', body)
        cur.execute(
            'INSERT INTO chapter_fts (chapter_num, title, body) VALUES (?, ?, ?)',
            (num, title, clean_body),
        )
        cur.execute(
            'INSERT INTO chapter_meta (chapter_num, title, summary, indexed_at) VALUES (?, ?, ?, ?)',
            (num, title, summary, now),
        )
        count += 1

    conn.commit()
    conn.close()
    return count


def _extract_text(filepath: Path) -> tuple[int, str, str]:
    """Unified extractor — handles .json (new) and .md (legacy).

    Returns (chapter_num, title, body).
    """
    if filepath.suffix == '.json':
        return _extract_from_json(filepath)
    return extract_chapter_text(filepath)


def _extract_from_json(filepath: Path) -> tuple[int, str, str]:
    """Extract (num, title, body) from a .json chapter file.

    Body is reconstructed by joining all block.text values, since FTS5
    wants searchable text not metadata.
    """
    import json
    data = json.loads(filepath.read_text(encoding='utf-8'))
    num = int(filepath.stem)
    title = data.get('title') or f'ตอนที่ {num}'
    parts = []
    for b in data.get('blocks', []):
        text = b.get('text', '')
        if text:
            parts.append(text)
    return num, title, '\n\n'.join(parts)


def search(
    query: str,
    limit: int = 5,
    exclude_chapter: int | None = None,
    novel_root: Path | None = None,
) -> list[dict]:
    """Search for chapters matching query.

    Returns list of {chapter_num, title, snippet, score} sorted by relevance.

    `novel_root` lets callers target a per-novel FTS5 index.
    """
    root = novel_root or NOVEL_ROOT
    conn = get_conn(_resolve_db(root))
    cur = conn.cursor()

    # Sanitize query: FTS5 special chars can break; keep CN/TH/EN + spaces
    safe_q = re.sub(r'[^\w\u0e00-\u0e7f\u4e00-\u9fff ]', ' ', query).strip()
    if not safe_q:
        return []

    # Use FTS5 bm25 ranking (lower = more relevant)
    sql = """
        SELECT chapter_num, title, snippet(chapter_fts, 2, '<<', '>>', '...', 32) as snip,
               bm25(chapter_fts) as score
        FROM chapter_fts
        WHERE chapter_fts MATCH ?
    """
    params: list = [safe_q]
    if exclude_chapter is not None:
        sql += ' AND chapter_num < ?'
        params.append(exclude_chapter)
    sql += ' ORDER BY score LIMIT ?'
    params.append(limit)

    rows = cur.execute(sql, params).fetchall()
    conn.close()

    return [
        {'chapter_num': r[0], 'title': r[1], 'snippet': r[2], 'score': r[3]}
        for r in rows
    ]


def get_context(target_chapter: int, top_k: int = 3) -> list[dict]:
    """Get top-K prior chapters relevant to target_chapter.

    Strategy: extract proper nouns (CN names) from target chapter's source
    if available, then search. Fallback: use most recent N chapter summaries.
    """
    # Try to get source file for target
    src_file = NOVEL_ROOT / 'chapters' / 'source' / f'{target_chapter:04d}.md'
    if src_file.exists():
        source = src_file.read_text(encoding='utf-8')
        # Extract CN names (2-4 char Chinese sequences, 2+ occurrences)
        cn_names = re.findall(r'[\u4e00-\u9fff]{2,4}', source)
        from collections import Counter
        common = [n for n, c in Counter(cn_names).most_common(8) if c >= 2]
        if common:
            query = ' '.join(common)
            results = search(query, limit=top_k, exclude_chapter=target_chapter)
            if results:
                # Enrich with summary
                conn = get_conn()
                cur = conn.cursor()
                for r in results:
                    s = cur.execute(
                        'SELECT summary FROM chapter_meta WHERE chapter_num = ?',
                        (r['chapter_num'],),
                    ).fetchone()
                    r['summary'] = s[0] if s else ''
                conn.close()
                return results

    # Fallback: most recent N chapter summaries
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        'SELECT chapter_num, title, summary FROM chapter_meta '
        'WHERE chapter_num < ? ORDER BY chapter_num DESC LIMIT ?',
        (target_chapter, top_k),
    ).fetchall()
    conn.close()
    return [
        {'chapter_num': r[0], 'title': r[1], 'summary': r[2], 'score': 0.0}
        for r in rows
    ]


def format_context_block(target_chapter: int, top_k: int = 3) -> str:
    """Format top-K relevant chapters as a context block for pre_chapter."""
    results = get_context(target_chapter, top_k)
    if not results:
        return ''

    lines = [
        f'## Cross-Chapter Context (FTS5 search, top {len(results)} relevant prior ch)',
        '',
        '> Generated by `tools/chapter_search.py context N`. These chapters',
        '> contain names/concepts that may appear in ch N — review to avoid',
        '> continuity breaks (renamed characters, forgotten status, etc).',
        '',
    ]
    for r in results:
        lines.append(f"### Ch {r['chapter_num']}: {r['title']}")
        if r.get('summary'):
            lines.append(r['summary'])
        elif r.get('snippet'):
            lines.append(f'...{r["snippet"]}...')
        lines.append('')
    return '\n'.join(lines)


def get_stats() -> dict:
    """Return index health stats."""
    conn = get_conn()
    cur = conn.cursor()
    n_indexed = cur.execute('SELECT COUNT(*) FROM chapter_fts').fetchone()[0]
    last = cur.execute(
        'SELECT MAX(indexed_at) FROM chapter_meta'
    ).fetchone()[0]
    conn.close()
    return {'indexed': n_indexed, 'last_indexed': last}


def main():
    import argparse
    p = argparse.ArgumentParser(description='FTS5 chapter search (Phase 4 continuity)')
    p.add_argument(
        '--novel-root', type=Path, default=None,
        help='Override novel root (default: NOVEL_ROOT from constants). '
             'Use for multi-novel setups (e.g. --novel-root novels/<slug>).',
    )
    p.add_argument(
        '--json', action='store_true',
        help='Output search/stats as JSON (machine-readable for server.js).',
    )
    sub = p.add_subparsers(dest='cmd', required=True)

    sub.add_parser('index', help='build/rebuild FTS5 index')

    s_search = sub.add_parser('search', help='search by query')
    s_search.add_argument('query', help='search query (CN/TH/EN names or words)')
    s_search.add_argument('--limit', type=int, default=5)
    s_search.add_argument('--exclude', type=int, help='exclude chapter num (e.g. current)')

    s_ctx = sub.add_parser('context', help='top-K relevant prior ch for target')
    s_ctx.add_argument('chapter', type=int, help='target chapter number')
    s_ctx.add_argument('--top', type=int, default=3)

    sub.add_parser('stats', help='index health')

    args = p.parse_args()

    root = args.novel_root
    db_file = _resolve_db(root) if root else DB_FILE

    if args.cmd == 'index':
        n = build_index(novel_root=root)
        print(f'✅ Indexed {n} chapters → {db_file}')

    elif args.cmd == 'search':
        results = search(
            args.query, limit=args.limit,
            exclude_chapter=args.exclude, novel_root=root,
        )
        if args.json:
            import json as _json
            print(_json.dumps(results, ensure_ascii=False))
            return
        if not results:
            print('No matches.')
            return
        print(f'\n🔍 Top {len(results)} matches for: "{args.query}"')
        print('─' * 70)
        for r in results:
            print(f"\n  Ch {r['chapter_num']}: {r['title']}")
            print(f"  score: {r['score']:.2f}")
            print(f"  {r['snippet']}")

    elif args.cmd == 'context':
        block = format_context_block(args.chapter, top_k=args.top)
        if not block:
            print(f'No context found for ch {args.chapter}')
            return
        print(block)

    elif args.cmd == 'stats':
        s = get_stats()
        if args.json:
            import json as _json
            print(_json.dumps({**s, 'db_file': str(db_file)}, ensure_ascii=False))
            return
        print(f'Indexed chapters: {s["indexed"]}')
        print(f'Last indexed:     {s["last_indexed"] or "(never)"}')
        print(f'DB file:          {db_file}')


if __name__ == '__main__':
    main()
