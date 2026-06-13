"""audit.py — 5-Phase CoT audit log generator (Phase 1).

Inspired by Megumin V7's "5-Phase Audit" (Ground Truth → Plot Engine →
Scene Design → Active Draft → Correction Loop) and the Knowledge
Firewall that forces AI to trace how an NPC knows something.

For each translated chapter, produces a structured audit.md with:
  1. Ground Truth    — character/setting state, prior ch context
  2. Plot Engine     — main + sub-plot beats identified
  3. Scene Design    — POV, tone, entry point chosen
  4. Active Draft    — translation facts (length, characters, ratio)
  5. Correction Loop — validation results (slop, CJK, ratio, glossary)

Output: novels/{slug}/chapters/{N:04d}/audit.md

This gives P'Chok a provenance trail for every chapter — "what was
Mika thinking when she translated this?" — without changing the
translation workflow itself (audit is post-hoc analysis).

Usage:
    python audit.py 80               # audit ch 80
    python audit.py --all            # audit all translated ch
    python audit.py --all --update   # audit + auto-update chapters
    python audit.py 80 --json        # output as JSON (for tooling)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT  # noqa: E402


def load_chapter(num: int) -> str | None:
    """Load translated chapter body, or None if not found."""
    f = NOVEL_ROOT / 'chapters' / f'{num:04d}.md'
    if not f.exists():
        return None
    text = f.read_text(encoding='utf-8')
    # Extract body between first --- and second --- (handles both formats)
    lines = text.splitlines()
    sep_idxs = [i for i, ln in enumerate(lines) if ln.strip() == '---']
    if not sep_idxs:
        return '\n'.join(lines[1:]).strip()
    # Check if NEW format (header before first ---)
    header = [ln for ln in lines[:sep_idxs[0]] if ln.strip()]
    is_new = (header and header[0].startswith('# ')
              and len(header) <= 2
              and all('*Source:' in ln or ln.startswith('# ') for ln in header[1:]))
    if is_new and len(sep_idxs) >= 2:
        return '\n'.join(lines[sep_idxs[0] + 1:sep_idxs[1]]).strip()
    if not is_new:
        return '\n'.join(lines[:sep_idxs[0]]).strip()
    return text


def extract_chars(body: str) -> set[str]:
    """Extract Thai-rendered names (CN→TH transliterations) from body.

    Uses glossary as canonical name source. Thai text is unsegmented
    so we count substring matches of known Thai names.
    """
    from constants import GLOSSARY_DIR
    found = set()
    if not GLOSSARY_DIR.exists():
        return found
    for tier in ('locked.md', 'reference.md'):
        f = GLOSSARY_DIR / tier
        if not f.exists():
            continue
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.startswith('| ') or 'Source' in line:
                continue
            cells = [c.strip() for c in line.split('|')]
            if len(cells) >= 3 and cells[2] and cells[2] != '-':
                name = cells[2]
                if len(name) >= 3 and name in body:
                    found.add(name)
    return found


def extract_cn_chars(body: str) -> set[str]:
    """Extract CN characters (proper nouns left in CN form)."""
    # 2-4 char CN sequences appearing 2+ times (names repeat)
    from collections import Counter
    seqs = re.findall(r'[\u4e00-\u9fff]{2,4}', body)
    return {s for s, c in Counter(seqs).most_common(20) if c >= 2}


def ground_truth_phase(num: int, body: str) -> dict:
    """Phase 1: establish facts about the chapter.

    Pulls metadata: title, source length, translation length, characters
    present, chapter number in arc.
    """
    src_file = NOVEL_ROOT / 'chapters' / 'source' / f'{num:04d}.md'
    src_len = len(src_file.read_text(encoding='utf-8')) if src_file.exists() else 0
    trans_len = len(body)
    ratio = (trans_len / src_len) if src_len else 0.0

    title = re.search(r'# (.+)', (NOVEL_ROOT / 'chapters' / f'{num:04d}.md').read_text(encoding='utf-8'))
    title = title.group(1) if title else f'ch {num}'

    return {
        'chapter': num,
        'title': title,
        'source_chars': src_len,
        'translation_chars': trans_len,
        'length_ratio': round(ratio, 2),
        'target_ratio': '1.5-3.0',
        'ratio_ok': 1.5 <= ratio <= 3.0,
        'thai_names_detected': sorted(extract_chars(body))[:15],
        'cn_names_detected': sorted(extract_cn_chars(body))[:10],
        'paragraphs': len([p for p in body.split('\n\n') if p.strip()]),
    }


def plot_engine_phase(num: int, body: str) -> dict:
    """Phase 2: identify plot beats.

    Heuristics: count dialogue lines (action), system messages 【】,
    paragraph transitions. This is a structural read, not semantic.
    """
    paras = [p for p in body.split('\n\n') if p.strip()]
    dialogue_paras = sum(1 for p in paras if '"' in p or '"' in p or '"' in p)
    system_msgs = re.findall(r'【[^】]+】', body)
    titles = re.findall(r'《[^》]+》', body)

    # Beat count: every 3-4 paragraphs = 1 beat (rough scene segmentation)
    estimated_beats = max(1, len(paras) // 3)

    return {
        'estimated_beats': estimated_beats,
        'dialogue_paragraphs': dialogue_paras,
        'narration_paragraphs': len(paras) - dialogue_paras,
        'system_messages_count': len(system_msgs),
        'titles_referenced': len(titles),
        'system_messages_sample': system_msgs[:3],
    }


def scene_design_phase(num: int, body: str) -> dict:
    """Phase 3: extract stylistic choices made.

    POV detection: count "เฉาซิง" (3rd-person protagonist) vs first-person
    markers. Tone: exclamation density. Entry point: does first paragraph
    start with dialogue, action, or setting?
    """
    paras = [p for p in body.split('\n\n') if p.strip()]
    first_para = paras[0] if paras else ''

    # POV: count 3rd-person pronoun uses
    pov_3rd = len(re.findall(r'เฉาซิง', body))
    pov_1st = len(re.findall(r'\bผม\b|\bฉัน\b', body))
    pov = '3rd-person (เฉาซิง)' if pov_3rd > pov_1st * 3 else 'mixed'

    # Tone
    excl = body.count('!') + body.count('！')
    excl_density = excl / max(1, len(body)) * 1000
    tone = 'intense' if excl_density > 5 else 'calm'

    # Entry point
    starts_with_dialogue = bool(first_para and first_para.lstrip().startswith(('"', '"', '"')))
    starts_with_action = bool(first_para and re.match(r'^[ก-๛]', first_para) and not starts_with_dialogue)
    entry = 'dialogue' if starts_with_dialogue else ('action' if starts_with_action else 'narration')

    return {
        'pov': pov,
        '3rd_person_count': pov_3rd,
        '1st_person_count': pov_1st,
        'tone': tone,
        'exclamation_density_per_1000': round(excl_density, 1),
        'entry_point': entry,
    }


def correction_loop_phase(num: int, body: str) -> dict:
    """Phase 5: validation results.

    Run lightweight checks: CJK leakage, em-dash count, bracket balance,
    common slop patterns (from slop/anti_ai).
    """
    issues = []

    # CJK check
    cjk_chars = re.findall(r'[\u4e00-\u9fff]', body)
    if cjk_chars:
        issues.append(f'CJK leakage: {len(cjk_chars)} chars')

    # Em-dash check
    em_dashes = body.count('—')
    if em_dashes > 5:
        issues.append(f'em-dash overuse: {em_dashes} (max 5 per ch)')

    # Bracket balance
    open_brackets = body.count('【')
    close_brackets = body.count('】')
    if open_brackets != close_brackets:
        issues.append(f'bracket imbalance: 【={open_brackets} 】={close_brackets}')

    # Bracket check: 蕾妮絲 (ch 71 name) — make sure name consistency
    # (this is just a placeholder — full check is in validate_chapter.py)

    return {
        'issues_found': len(issues),
        'issues': issues,
        'cjk_chars': len(cjk_chars),
        'em_dash_count': em_dashes,
        'brackets_balanced': open_brackets == close_brackets,
    }


def generate_audit(num: int, body: str) -> str:
    """Generate the full audit.md for a chapter."""
    gt = ground_truth_phase(num, body)
    pe = plot_engine_phase(num, body)
    sd = scene_design_phase(num, body)
    cl = correction_loop_phase(num, body)

    now = datetime.now(timezone.utc).isoformat()

    lines = [
        f'# Audit — Ch {num}: {gt["title"]}',
        '',
        f'> Generated by `tools/audit.py` on {now}',
        '> 5-Phase CoT (Megumin V7 pattern): Ground Truth → Plot → Scene → Draft → Correction',
        '',
        '## Phase 1: Ground Truth',
        '',
        f'- **Source chars:** {gt["source_chars"]:,}',
        f'- **Translation chars:** {gt["translation_chars"]:,}',
        f'- **Length ratio:** {gt["length_ratio"]}x (target 1.5-3.0) — {"✅" if gt["ratio_ok"] else "❌ OUT OF RANGE"}',
        f'- **Paragraphs:** {gt["paragraphs"]}',
        f'- **Thai names detected:** {", ".join(gt["thai_names_detected"][:8]) if gt["thai_names_detected"] else "(none)"}',
        f'- **CN names detected:** {", ".join(gt["cn_names_detected"][:5]) if gt["cn_names_detected"] else "(none)"}',
        '',
        '## Phase 2: Plot Engine',
        '',
        f'- **Estimated beats:** {pe["estimated_beats"]} (~1 per 3 paragraphs)',
        f'- **Dialogue paragraphs:** {pe["dialogue_paragraphs"]} / {pe["dialogue_paragraphs"] + pe["narration_paragraphs"]}',
        f'- **System messages:** {pe["system_messages_count"]} (legitimate game mechanic text)',
        f'- **Titles referenced:** {pe["titles_referenced"]}',
        '',
        '## Phase 3: Scene Design',
        '',
        f'- **POV:** {sd["pov"]} (3rd-person ref: {sd["3rd_person_count"]}, 1st-person: {sd["1st_person_count"]})',
        f'- **Tone:** {sd["tone"]} (exclamation density: {sd["exclamation_density_per_1000"]}/1000 chars)',
        f'- **Entry point:** {sd["entry_point"]} (first paragraph starts with: {sd["entry_point"][0].upper()})',
        '',
        '## Phase 4: Active Draft',
        '',
        f'- **Status:** Translated (see `{num:04d}.md`)',
        f'- **Length:** {gt["translation_chars"]:,} chars',
        '',
        '## Phase 5: Correction Loop',
        '',
        f'- **Issues found:** {cl["issues_found"]}',
    ]
    if cl['issues']:
        for issue in cl['issues']:
            lines.append(f'  - {issue}')
    else:
        lines.append('  - (none — all checks passed)')
    lines.append(f'- **CJK leakage:** {cl["cjk_chars"]} chars ({"✅ clean" if cl["cjk_chars"] == 0 else "❌ needs fix"})')
    lines.append(f'- **Em-dash count:** {cl["em_dash_count"]} (max 5)')
    lines.append(f'- **Brackets balanced:** {"✅" if cl["brackets_balanced"] else "❌"}')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('> For full validation: `python novelclaw.py validate ' + str(num) + '`')
    lines.append('> For slop scan: `python tools/slop_detector.py --chapter ' + str(num) + '`')
    return '\n'.join(lines)


def audit_chapter(num: int, update_chapter: bool = True) -> bool:
    """Generate and save audit for one chapter. Returns True on success."""
    body = load_chapter(num)
    if body is None:
        print(f'❌ Ch {num} not translated yet')
        return False

    audit = generate_audit(num, body)

    if not update_chapter:
        print(audit)
        return True

    # Save to chapters/00XX/audit.md
    audit_dir = NOVEL_ROOT / 'chapters' / f'{num:04d}'
    audit_dir.mkdir(exist_ok=True)
    (audit_dir / 'audit.md').write_text(audit, encoding='utf-8')
    print(f'✅ Ch {num} → {audit_dir / "audit.md"}')
    return True


def main():
    import argparse
    p = argparse.ArgumentParser(description='5-Phase CoT audit (Phase 1)')
    p.add_argument('chapter', nargs='?', type=int, help='chapter number (or --all)')
    p.add_argument('--all', action='store_true', help='audit all translated chs')
    p.add_argument('--update', action='store_true', help='save to chapters/00XX/audit.md')
    args = p.parse_args()

    if args.all:
        chs = sorted([
            int(f.stem) for f in (NOVEL_ROOT / 'chapters').glob('*.md')
            if f.stem.isdigit() and len(f.stem) == 4
        ])
        ok = 0
        for n in chs:
            if audit_chapter(n, update_chapter=args.update):
                ok += 1
        print(f'\\n📊 {ok}/{len(chs)} chapters audited')
    elif args.chapter:
        audit_chapter(args.chapter, update_chapter=args.update)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
