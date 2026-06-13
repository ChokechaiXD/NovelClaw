"""npc_bank.py — NPC Dossier Bank (Phase 2).

Inspired by Megumin V7's "Automated NPC Bank" — auto-extract character
dossiers (Name, Appearance, Speech Pattern, Agenda) when a significant
NPC is introduced, and inject dossiers into the prompt only for NPCs
relevant to the current chapter.

Storage layout:
    novels/{slug}/npc_bank/
        ├── index.md              — list of all dossiers
        ├── เฉาซิง.md             — main protagonist
        ├── หลิวมู่เสวี่ย.md        — sister-in-law
        └── ...

Each dossier:
    # <Thai name>
    - **CN name:** <source>  (cross-ref for grep)
    - **Gender:** male/female
    - **Role:** protagonist / antagonist / supporting / mob
    - **First appearance:** ch N
    - **Speech pattern:** short / verbose / sarcastic / etc.
    - **Relationships:** ...
    - **Agenda:** ...

Workflow:
    python npc_bank.py extract 80     # extract NPCs from ch 80
    python npc_bank.py inject 80      # show dossiers for NPCs in ch 80
    python npc_bank.py list           # list all known NPCs
    python npc_bank.py add เฉาซิง     # manually add/edit dossier

For now, extraction is RULE-BASED (proper noun detection + dialogue
speaker inference). The plan is to add LLM-based extraction later, but
rule-based gives us a working foundation that doesn't require API calls.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT  # noqa: E402

NPC_DIR = NOVEL_ROOT / 'npc_bank'
INDEX_FILE = NPC_DIR / 'index.md'


# ── Extraction (rule-based) ────────────────────────────────────────
def load_chapter(num: int) -> str | None:
    """Load translated chapter body."""
    f = NOVEL_ROOT / 'chapters' / f'{num:04d}.md'
    if not f.exists():
        return None
    text = f.read_text(encoding='utf-8')
    lines = text.splitlines()
    sep_idxs = [i for i, ln in enumerate(lines) if ln.strip() == '---']
    if not sep_idxs:
        return '\n'.join(lines[1:]).strip()
    header = [ln for ln in lines[:sep_idxs[0]] if ln.strip()]
    is_new = (header and header[0].startswith('# ')
              and len(header) <= 2
              and all('*Source:' in ln or ln.startswith('# ') for ln in header[1:]))
    if is_new and len(sep_idxs) >= 2:
        return '\n'.join(lines[sep_idxs[0] + 1:sep_idxs[1]]).strip()
    if not is_new:
        return '\n'.join(lines[:sep_idxs[0]]).strip()
    return text


def extract_npcs(body: str, top_n: int = 20) -> list[tuple[str, int]]:
    """Extract likely NPC names from Thai text.

    Thai text is unsegmented, so generic regex over Thai tokens returns
    compound words like "เฉาซิงพูดต่อ" (name + verb). The reliable
    approach: load the project's glossary (locked + reference tiers)
    which contains all known CN→TH name pairs, then count occurrences
    of each Thai name in the body.

    For source (CN) text: count CN names directly.
    """
    from constants import GLOSSARY_DIR

    # Load known name pairs: (cn, thai) from glossary
    pairs: list[tuple[str, str]] = []
    if GLOSSARY_DIR.exists():
        for tier in ('locked.md', 'reference.md'):
            f = GLOSSARY_DIR / tier
            if f.exists():
                for line in f.read_text(encoding='utf-8').splitlines():
                    if not line.startswith('| ') or 'Source' in line:
                        continue
                    cells = [c.strip() for c in line.split('|')]
                    if len(cells) >= 3 and cells[1] and cells[2] and cells[2] != '-':
                        pairs.append((cells[1], cells[2]))

    # Detect which side to count (TH rendering vs CN source)
    is_thai = any(ord(c) >= 0x0E00 and ord(c) <= 0x0E7F for c in body[:1000])
    is_cn = any(ord(c) >= 0x4E00 and ord(c) <= 0x9FFF for c in body[:1000])

    found = []
    for cn, th in pairs:
        # Pick the right name to count
        if is_thai and not is_cn:
            name = th
        elif is_cn and not is_thai:
            name = cn
        else:
            # Mixed (e.g., translated ch with CN names still in 《》) — count both
            if th in body:
                found.append((th, body.count(th)))
            if cn in body:
                found.append((cn, body.count(cn)))
            continue
        if name and len(name) >= 2:
            count = body.count(name)
            if count > 0:
                found.append((name, count))

    # Dedupe (in mixed case)
    seen = set()
    deduped = []
    for n, c in found:
        if n not in seen:
            seen.add(n)
            deduped.append((n, c))

    # Sort by count desc
    deduped.sort(key=lambda x: -x[1])
    return deduped[:top_n]


def is_existing_npc(name: str) -> bool:
    """Check if dossier exists for this name."""
    return (NPC_DIR / f'{name}.md').exists()


# ── Dossier I/O ────────────────────────────────────────────────────
def create_dossier(name: str, cn_name: str = '',
                   first_ch: int = 0, role: str = 'supporting',
                   gender: str = 'unknown', speech: str = '',
                   relationships: str = '', agenda: str = '') -> str:
    """Create a new dossier template. Returns markdown content."""
    return f'''# {name}

> Auto-generated by `tools/npc_bank.py`. Edit as you learn more.

- **CN name:** {cn_name or '_(unknown)_'}
- **Gender:** {gender}
- **Role:** {role}
- **First appearance:** ch {first_ch}
- **Speech pattern:** {speech or '_(not yet observed)_'}
- **Relationships:** {relationships or '_(not yet mapped)_'}
- **Agenda:** {agenda or '_(not yet known)_'}

## Notes

_(free-form observations from translation — append as you translate more chapters)_
'''


def add_dossier(name: str, **kwargs) -> Path:
    """Add a new dossier. Skips if already exists."""
    NPC_DIR.mkdir(parents=True, exist_ok=True)
    path = NPC_DIR / f'{name}.md'
    if path.exists():
        return path
    content = create_dossier(name, **kwargs)
    path.write_text(content, encoding='utf-8')
    return path


def update_index():
    """Regenerate index.md with all known NPCs."""
    NPC_DIR.mkdir(parents=True, exist_ok=True)
    dossiers = sorted(NPC_DIR.glob('*.md'))
    dossiers = [d for d in dossiers if d.name != 'index.md']

    lines = [
        '# NPC Bank — global-descent',
        '',
        '> Auto-generated index. Each entry links to the dossier.',
        '',
        f'**Total NPCs:** {len(dossiers)}',
        '',
        '| Thai name | Role | First ch |',
        '|-----------|------|----------|',
    ]
    for d in dossiers:
        text = d.read_text(encoding='utf-8')
        # Parse role + first ch
        role_m = re.search(r'\*\*Role:\*\*\s*(\S+)', text)
        ch_m = re.search(r'\*\*First appearance:\*\*\s*ch\s*(\d+)', text)
        role = role_m.group(1) if role_m else '?'
        ch = ch_m.group(1) if ch_m else '?'
        lines.append(f'| [{d.stem}]({d.name}) | {role} | {ch} |')

    INDEX_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')


# ── Inject (for pre_chapter) ──────────────────────────────────────
def get_dossiers_for_chapter(num: int, body: str | None = None,
                              top_n: int = 10) -> list[Path]:
    """Get NPC dossiers for NPCs appearing in chapter N.

    Tries translated body first, then source body. Maps CN names (in
    source) to Thai dossier filenames via glossary.

    Returns paths to dossier files, sorted by relevance (count in body).
    """
    # Load CN→TH map from glossary
    from constants import GLOSSARY_DIR
    cn_to_th: dict[str, str] = {}
    if GLOSSARY_DIR.exists():
        for tier in ('locked.md', 'reference.md'):
            f = GLOSSARY_DIR / tier
            if f.exists():
                for line in f.read_text(encoding='utf-8').splitlines():
                    if not line.startswith('| ') or 'Source' in line:
                        continue
                    cells = [c.strip() for c in line.split('|')]
                    if len(cells) >= 3 and cells[1] and cells[2] and cells[2] != '-':
                        cn_to_th[cells[1]] = cells[2]

    if body is None:
        body = load_chapter(num)
    if body is None:
        # Try source file (CN text — names appear in CN)
        src_file = NOVEL_ROOT / 'chapters' / 'source' / f'{num:04d}.md'
        if src_file.exists():
            body = src_file.read_text(encoding='utf-8')
    if body is None:
        return []

    npcs = extract_npcs(body, top_n=top_n * 2)  # Get more candidates, filter by dossier

    dossiers = []
    for name, count in npcs:
        # If name is CN, look up Thai dossier name
        dossier_name = cn_to_th.get(name, name)
        path = NPC_DIR / f'{dossier_name}.md'
        if path.exists():
            dossiers.append(path)
        if len(dossiers) >= top_n:
            break
    return dossiers


def format_inject_block(num: int, top_n: int = 5) -> str:
    """Format dossier injection block for pre_chapter output."""
    body = load_chapter(num)
    dossiers = get_dossiers_for_chapter(num, body, top_n=top_n)
    if not dossiers:
        return ''

    lines = [
        f'## NPC Dossiers (top {len(dossiers)} NPCs in ch {num})',
        '',
        '> Phase 2: character voice + relationship context for consistency.',
        '> Edit dossiers in `novels/global-descent/npc_bank/` to refine.',
        '',
    ]
    for d in dossiers:
        text = d.read_text(encoding='utf-8')
        # Take first 8 non-empty lines (header + key fields)
        body_lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith('>')][:8]
        lines.append('```')
        lines.extend(body_lines)
        lines.append('```')
        lines.append('')
    return '\n'.join(lines)


# ── CLI ────────────────────────────────────────────────────────────
def main():
    import argparse
    p = argparse.ArgumentParser(description='NPC Dossier Bank (Phase 2)')
    sub = p.add_subparsers(dest='cmd', required=True)

    s_extract = sub.add_parser('extract', help='extract NPCs from a chapter')
    s_extract.add_argument('chapter', type=int)

    s_inject = sub.add_parser('inject', help='show dossiers for NPCs in ch')
    s_inject.add_argument('chapter', type=int)
    s_inject.add_argument('--top', type=int, default=5)

    sub.add_parser('list', help='list all NPCs')
    sub.add_parser('index', help='regenerate index.md')

    s_add = sub.add_parser('add', help='manually add/edit a dossier')
    s_add.add_argument('name', help='Thai name (no .md)')
    s_add.add_argument('--cn', default='', help='CN name')
    s_add.add_argument('--ch', type=int, default=0, help='first appearance ch')
    s_add.add_argument('--role', default='supporting', help='role')
    s_add.add_argument('--gender', default='unknown', help='gender')
    s_add.add_argument('--speech', default='', help='speech pattern')
    s_add.add_argument('--agenda', default='', help='agenda')

    args = p.parse_args()

    if args.cmd == 'extract':
        body = load_chapter(args.chapter)
        if body is None:
            print(f'❌ Ch {args.chapter} not found')
            return
        npcs = extract_npcs(body, top_n=20)
        print(f'\\n🔍 Top NPCs in ch {args.chapter}:')
        print(f'   {"name":<25} {"count":>5}  {"dossier":>8}')
        print('   ' + '─' * 45)
        new = 0
        for name, count in npcs:
            has = is_existing_npc(name)
            print(f'   {name:<25} {count:>5}  {"✅" if has else "❌ new"}')
            if not has and count >= 3:  # auto-suggest dossiers for frequent names
                new += 1
        print(f'\\n💡 {new} new NPCs with 3+ mentions (run `add` to create dossiers)')

    elif args.cmd == 'inject':
        block = format_inject_block(args.chapter, top_n=args.top)
        if not block:
            print(f'No dossiers for ch {args.chapter}')
            return
        print(block)

    elif args.cmd == 'list':
        if not NPC_DIR.exists():
            print('No NPC bank yet. Run `extract` on a chapter first.')
            return
        dossiers = sorted(NPC_DIR.glob('*.md'))
        dossiers = [d for d in dossiers if d.name != 'index.md']
        print(f'\\n📚 {len(dossiers)} NPC dossiers:')
        for d in dossiers:
            print(f'   - {d.stem}')

    elif args.cmd == 'index':
        update_index()
        print(f'✅ Updated {INDEX_FILE}')

    elif args.cmd == 'add':
        path = add_dossier(
            args.name,
            cn_name=args.cn,
            first_ch=args.ch,
            role=args.role,
            gender=args.gender,
            speech=args.speech,
            agenda=args.agenda,
        )
        update_index()
        print(f'✅ {path}')


if __name__ == '__main__':
    main()
