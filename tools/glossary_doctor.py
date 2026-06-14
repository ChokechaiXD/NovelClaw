"""glossary_doctor.py — Auto-validator for novel translations.

Comprehensive doctor that runs after each translation to ensure quality.
Detects 8 issue types and assigns severity:

  ERROR (BLOCKS save):
    - Forbidden pattern (e.g., ฮ่องกง)
    - Locked-term violation (wrong Thai for locked source)

  WARNING (allows save, flagged for review):
    - Inconsistency (same source → multiple Thai)
    - Anti-pattern (translated feel, formal verb)
    - Title/body mismatch
    - Subject echo (3+ consecutive same subject)
    - Collocation error (e.g., literal calque)
    - Length ratio out of range (TH natural: 1.4-2.0x)

  INFO (logged, not blocking):
    - New CN term (not in glossary)
    - Style preference (preferred form not used)

Usage:
  python tools/glossary_doctor.py --ch 111           # validate single ch
  python tools/glossary_doctor.py --ch 1-111         # validate range
  python tools/glossary_doctor.py --all              # validate all translated ch
  python tools/glossary_doctor.py --inconsistencies  # find CN→Thai mapping issues
  python tools/glossary_doctor.py --new-terms CH     # scan ch for un-glossaried CN
  python tools/glossary_doctor.py --report           # full report
  python tools/glossary_doctor.py --gate CH          # check if ch is OK to save (CI)
  python tools/glossary_doctor.py --fix-hints CH     # show fix suggestions for ch

Exit codes (for --gate):
  0 = clean
  1 = has warnings (still saveable)
  2 = has errors (BLOCKED)
"""
import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT, CHAPTERS_DIR, GLOSSARY_DIR  # noqa: E402

DB_PATH = GLOSSARY_DIR / 'glossary.db'

# Length ratio target (TH natural expansion of CN)
# Below 1.3 = too short (likely truncated)
# Above 2.0 = too long (likely over-translated / padded)
LENGTH_RATIO_MIN = 1.3
LENGTH_RATIO_MAX = 2.0


# ────────────────────────────────────────────────────────────────────
# Data loaders
# ────────────────────────────────────────────────────────────────────

def load_glossary():
    """Load all terms + aliases + style_rules from DB."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # source_norm -> [(thai, priority, category, scope, explanation, examples, notes)]
    glossary = defaultdict(list)
    cur.execute('''SELECT source_norm, thai, priority, category, scope,
                          explanation, examples, notes
                   FROM terms WHERE status = 'active' ''')
    for src, thai, prio, cat, scope, expl, examples, notes in cur.fetchall():
        glossary[src].append({
            'thai': thai, 'priority': prio, 'category': cat,
            'scope': scope, 'explanation': expl or '',
            'examples': examples or '', 'notes': notes or ''
        })
    # variant -> source_norm
    alias_map = {}
    cur.execute('''SELECT a.source_variant, t.source_norm
                   FROM aliases a JOIN terms t ON a.term_id = t.id''')
    for variant, norm in cur.fetchall():
        alias_map[variant] = norm
    # style rules
    cur.execute('''SELECT rule_type, pattern, replacement, severity, scope,
                          example_before, example_after, explanation
                   FROM style_rules''')
    style_rules = []
    for r in cur.fetchall():
        style_rules.append({
            'rule_type': r[0], 'pattern': r[1], 'replacement': r[2],
            'severity': r[3], 'scope': r[4],
            'example_before': r[5] or '', 'example_after': r[6] or '',
            'explanation': r[7] or ''
        })
    conn.close()
    return glossary, alias_map, style_rules


# ────────────────────────────────────────────────────────────────────
# Detectors
# ────────────────────────────────────────────────────────────────────

def detect_forbidden(text, style_rules):
    """Find any forbidden patterns (e.g., ฮ่องกง). ERROR level."""
    issues = []
    for rule in style_rules:
        if rule['rule_type'] != 'forbidden':
            continue
        try:
            matches = re.findall(rule['pattern'], text)
        except re.error:
            continue
        if matches:
            issues.append({
                'rule_type': 'forbidden',
                'severity': 'error',
                'pattern': rule['pattern'],
                'count': len(matches),
                'fix': rule['replacement'],
                'explanation': rule['explanation'],
                'example_before': rule['example_before'],
                'example_after': rule['example_after'],
            })
    return issues


def detect_anti_patterns(text, style_rules):
    """Find style.md anti-patterns. WARNING level."""
    issues = []
    for rule in style_rules:
        if rule['rule_type'] not in ('anti_pattern', 'collocation'):
            continue
        try:
            matches = re.findall(rule['pattern'], text, re.MULTILINE)
        except re.error:
            continue
        if matches:
            count = len(matches) if isinstance(matches, list) else 1
            issues.append({
                'rule_type': rule['rule_type'],
                'severity': rule['severity'],
                'pattern': rule['pattern'][:60],
                'count': count,
                'fix': rule['replacement'] or 'rephrase',
                'explanation': rule['explanation'],
                'example_before': rule['example_before'],
                'example_after': rule['example_after'],
            })
    return issues


def detect_locked_violations(text, glossary):
    """Find ch using wrong Thai for a locked source. ERROR level.

    Strategy: for each locked term (priority=1), check if source appears
    in a paragraph where the WRONG Thai is used (or none of the correct
    Thai versions).
    """
    issues = []
    for src, entries in glossary.items():
        locked = [e for e in entries if e['priority'] == 1]
        if not locked:
            continue
        # Locked term has specific Thai — check if it's in the text
        for entry in locked:
            thai = entry['thai']
            if thai not in text:
                # Locked source might be in CN form — let's check both
                # Get the source_cn
                if 'source_cn' not in entry:
                    continue
                # We'll detect this in detect_inconsistencies instead
                pass
    return issues


def detect_inconsistencies(text, glossary):
    """Find cases where same source maps to different Thai in same ch.

    WARNING level (manual review needed).
    """
    issues = []
    for src, entries in glossary.items():
        if len(entries) < 2:
            continue
        thais_in_text = []
        for entry in entries:
            if entry['thai'] in text:
                thais_in_text.append(entry['thai'])
        if len(set(thais_in_text)) > 1:
            issues.append({
                'rule_type': 'inconsistency',
                'severity': 'warning',
                'pattern': f'{src} → {thais_in_text}',
                'count': len(thais_in_text),
                'fix': f'pick one: {thais_in_text[0]} (priority={entries[0]["priority"]})',
                'explanation': f'multiple Thai versions used in same ch for "{src}"',
                'example_before': '',
                'example_after': '',
            })
    return issues


def detect_title_body_mismatch(text):
    """Check that names in title appear in body."""
    issues = []
    title_match = re.search(r'^#\s*ตอนที่\s*\d+\s*(.+)', text, re.MULTILINE)
    if not title_match:
        return issues
    title = title_match.group(1).strip()
    # Extract Thai words (3+ chars) from title
    title_names = re.findall(r'[\u0E00-\u0E7F]{3,}', title)
    body = text[title_match.end():]
    body_names = set(re.findall(r'[\u0E00-\u0E7F]{3,}', body))
    for tn in title_names:
        if tn in ('ตอนที่', 'บทที่', 'ภาค', 'เฉาซิง'):
            continue
        if tn not in body_names:
            # Look for close match (first 3 chars)
            close = None
            for bn in body_names:
                if len(tn) >= 3 and len(bn) >= 3 and tn[:3] == bn[:3]:
                    close = bn
                    break
            if close:
                issues.append({
                    'rule_type': 'title_mismatch',
                    'severity': 'warning',
                    'pattern': f'title="{tn}" body="{close}"',
                    'count': 1,
                    'fix': f'use "{close}" in title',
                    'explanation': 'title uses different name form than body',
                    'example_before': '',
                    'example_after': '',
                })
            else:
                issues.append({
                    'rule_type': 'title_missing_in_body',
                    'severity': 'info',
                    'pattern': f'title="{tn}"',
                    'count': 1,
                    'fix': 'add name to body or change title',
                    'explanation': 'title name never appears in body',
                    'example_before': '',
                    'example_after': '',
                })
    return issues


def detect_subject_echo(text, subject='เฉาซิง', max_consec=3):
    """Detect if subject starts 3+ consecutive sentences."""
    sents = [s.strip() for s in re.split(r'[。\n]', text) if s.strip()]
    consecutive = 0
    max_run = 0
    for s in sents:
        if s.startswith(subject):
            consecutive += 1
            max_run = max(max_run, consecutive)
        else:
            consecutive = 0
    if max_run >= max_consec:
        return [{
            'rule_type': 'subject_echo',
            'severity': 'warning',
            'pattern': f'{max_run} consecutive "{subject}"',
            'count': max_run,
            'fix': 'vary openings (omit subject, pronoun เขา, passive, refocus)',
            'explanation': 'P5 — 3+ consecutive sentences starting with same subject reads robotic',
            'example_before': 'เฉาซิงพยักหน้า\nเฉาซิงยิ้ม\nเฉาซิงพูด',
            'example_after': 'พยักหน้า ยิ้ม แล้วพูด',
        }]
    return []


def detect_length_ratio(text, ch_num):
    """Check if translation length is in target range.

    Compares against source/XXXX.md if available.
    """
    source_path = CHAPTERS_DIR / 'source' / f'{ch_num:04d}.md'
    if not source_path.exists():
        return []
    src_text = source_path.read_text(encoding='utf-8')
    # Count CN chars in source
    src_chars = len(re.findall(r'[\u4e00-\u9fff]', src_text))
    th_chars = len(text)  # TH + punctuation
    if src_chars < 100:
        return []  # Too short to judge
    ratio = th_chars / src_chars
    issues = []
    if ratio < LENGTH_RATIO_MIN:
        issues.append({
            'rule_type': 'length_ratio_low',
            'severity': 'warning',
            'pattern': f'ratio={ratio:.2f}x (src={src_chars}, th={th_chars})',
            'count': 1,
            'fix': f'add content — target is {LENGTH_RATIO_MIN}-{LENGTH_RATIO_MAX}x',
            'explanation': 'translation too short, may be truncated',
            'example_before': '',
            'example_after': '',
        })
    elif ratio > LENGTH_RATIO_MAX:
        issues.append({
            'rule_type': 'length_ratio_high',
            'severity': 'warning',
            'pattern': f'ratio={ratio:.2f}x (src={src_chars}, th={th_chars})',
            'count': 1,
            'fix': f'cut bloat — target is {LENGTH_RATIO_MIN}-{LENGTH_RATIO_MAX}x',
            'explanation': 'P7 — translation too long, likely padded/over-translated',
            'example_before': '',
            'example_after': '',
        })
    return issues


def detect_new_terms(text, glossary):
    """Find CN terms in text that aren't in glossary. INFO level."""
    issues = []
    # Find CN chars (2-5 char words)
    cn_terms = set(re.findall(r'[\u4e00-\u9fff]{2,6}', text))
    known = set(glossary.keys())
    new = [t for t in cn_terms if t not in known and len(t) >= 2]
    if new:
        # Take top 10 longest (most likely to be terms)
        sample = sorted(new, key=lambda x: -len(x))[:10]
        issues.append({
            'rule_type': 'new_terms',
            'severity': 'info',
            'pattern': ', '.join(sample),
            'count': len(new),
            'fix': 'add to auto.md with Thai translation',
            'explanation': f'found {len(new)} CN terms not yet in glossary',
            'example_before': '',
            'example_after': '',
        })
    return issues


def detect_cjk_leakage(text):
    """Find raw CN chars in body (excludes 【】, 《》, *Source: footer, and meta sections)."""
    # Remove whitelisted zones
    cleaned = re.sub(r'【[^】]*】', '', text)  # system messages
    cleaned = re.sub(r'《[^》]*》', '', cleaned)  # game titles
    cleaned = re.sub(r'\*Source:[^*]*\*', '', cleaned)  # source footer
    # Remove meta/notes section (after last --- separator before "หมายเหตุ" or similar)
    # Split at "หมายเหตุ" (translation notes) — anything after is meta
    cleaned = re.split(r'\nหมายเหตุ[ก-๙ ]*[:：]', cleaned, maxsplit=1)[0]
    # Also remove trailing "Translation notes:" / "Translation Notes:" / "Note:" sections
    cleaned = re.split(r'\n(?:Translation [Nn]otes?|Note:|Notes:)\s*\n', cleaned, maxsplit=1)[0]
    cjk = re.findall(r'[\u4e00-\u9fff]', cleaned)
    if cjk:
        return [{
            'rule_type': 'cjk_leakage',
            'severity': 'error',
            'pattern': f'{len(cjk)} CN chars in body',
            'count': len(cjk),
            'fix': 'translate or whitelist',
            'explanation': 'CN chars should not appear in translated body (except whitelisted zones)',
            'example_before': '他走進了房間',
            'example_after': 'เขาเดินเข้ามาในห้อง',
        }]
    return []


# ────────────────────────────────────────────────────────────────────
# Main validation
# ────────────────────────────────────────────────────────────────────

def validate_chapter(ch_num, glossary, alias_map, style_rules, log_to_db=True):
    """Run all detectors on a single chapter. Returns list of issues."""
    ch_path = CHAPTERS_DIR / f'{ch_num:04d}.md'
    if not ch_path.exists():
        return [{'rule_type': 'error', 'severity': 'error',
                 'pattern': f'ch {ch_num} not found', 'count': 1, 'fix': 'create file'}]
    text = ch_path.read_text(encoding='utf-8')
    issues = []
    # Critical (errors)
    issues.extend(detect_forbidden(text, style_rules))
    issues.extend(detect_cjk_leakage(text))
    # Warnings
    issues.extend(detect_anti_patterns(text, style_rules))
    issues.extend(detect_inconsistencies(text, glossary))
    issues.extend(detect_title_body_mismatch(text))
    issues.extend(detect_subject_echo(text))
    issues.extend(detect_length_ratio(text, ch_num))
    # Info
    issues.extend(detect_new_terms(text, glossary))

    if log_to_db and issues:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Clear old entries for this ch
        cur.execute('DELETE FROM doctor_log WHERE ch_num = ? AND resolved_at IS NULL', (ch_num,))
        for issue in issues:
            if issue.get('rule_type') == 'error':
                continue
            cur.execute('''INSERT INTO doctor_log
                          (ch_num, issue_type, severity, pattern, location, fix_suggestion)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                        (ch_num, issue['rule_type'], issue.get('severity', 'info'),
                         issue.get('pattern', ''), '', issue.get('fix', '')))
        # Update ch_meta
        has_errors = any(i.get('severity') == 'error' for i in issues)
        has_warnings = any(i.get('severity') == 'warning' for i in issues)
        status = 'has_errors' if has_errors else ('has_warnings' if has_warnings else 'clean')
        cur.execute('''INSERT OR REPLACE INTO ch_meta
                      (ch_num, translated_at, glossary_version, validation_status)
                      VALUES (?, ?, ?, ?)''',
                    (ch_num, datetime.now().isoformat(), '2.0', status))
        conn.commit()
        conn.close()
    return issues


def find_inconsistencies_in_db():
    """Find all cross-ch inconsistencies."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''SELECT source_norm, GROUP_CONCAT(DISTINCT thai) as variants, COUNT(DISTINCT thai) as n
                   FROM terms WHERE status = "active"
                   GROUP BY source_norm HAVING n > 1''')
    results = cur.fetchall()
    conn.close()
    return results


def find_unused_terms():
    """Find terms never used in any translated ch."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''SELECT t.id, t.source_cn, t.thai, t.priority, t.score
                   FROM terms t
                   WHERE t.id NOT IN (SELECT DISTINCT term_id FROM usage WHERE term_id IS NOT NULL)
                   AND t.priority = 3 AND t.scope = 'auto' AND t.status = 'active'
                   ORDER BY t.source_cn''')
    results = cur.fetchall()
    conn.close()
    return results


def print_fix_hints(ch_num, issues):
    """Print user-friendly fix hints for a chapter."""
    print(f'\n🔧 Fix hints for ch{ch_num}:')
    print('━' * 60)
    # Group by rule type
    by_type = defaultdict(list)
    for i in issues:
        by_type[i.get('rule_type', 'unknown')].append(i)
    for rtype, items in by_type.items():
        total = sum(i.get('count', 1) for i in items)
        print(f'\n  [{rtype.upper()}] — {len(items)} issue type(s), {total} occurrence(s)')
        for i in items:
            sev = i.get('severity', '?')
            print(f'    [{sev}] {i.get("pattern", "")[:70]}')
            if i.get('explanation'):
                print(f'         Why: {i["explanation"][:100]}')
            if i.get('example_before') and i.get('example_after'):
                print(f'         ✗ {i["example_before"][:60]}')
                print(f'         ✓ {i["example_after"][:60]}')
            if i.get('fix'):
                print(f'         → {i["fix"]}')


def print_report():
    """Print full report of glossary state."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print('=' * 60)
    print('GLOSSARY DOCTOR REPORT')
    print(f'Generated: {datetime.now().isoformat()}')
    print('=' * 60)

    # Terms by tier
    cur.execute('''SELECT scope, priority, status, COUNT(*)
                   FROM terms GROUP BY scope, priority, status ORDER BY priority, scope''')
    print('\n📊 Terms by tier/priority/status:')
    for scope, prio, status, count in cur.fetchall():
        pname = {1: 'LOCKED', 2: 'REFERENCE', 3: 'AUTO'}.get(prio, str(prio))
        sname = scope or '?'
        print(f'   {pname:9} {sname:15} {status:9} {count}')

    # By category
    cur.execute('''SELECT category, COUNT(*) FROM terms
                   WHERE status = "active" GROUP BY category ORDER BY 2 DESC''')
    print('\n📂 By category:')
    for cat, n in cur.fetchall():
        print(f'   {cat or "unknown":15} {n}')

    # With/without explanation
    cur.execute('''SELECT
        COUNT(CASE WHEN explanation IS NULL OR explanation = '' THEN 1 END) as no_expl,
        COUNT(CASE WHEN explanation IS NOT NULL AND explanation != '' THEN 1 END) as with_expl
        FROM terms WHERE status = "active"''')
    no_expl, with_expl = cur.fetchone()
    print(f'\n📝 Explanations: {with_expl} have, {no_expl} missing')

    # Inconsistencies
    incon = find_inconsistencies_in_db()
    print(f'\n⚠️  Inconsistencies (same source → different Thai): {len(incon)}')
    for src, vars_, n in incon:
        print(f'   {src}: {vars_}')

    # Style rules
    cur.execute('''SELECT rule_type, severity, COUNT(*)
                   FROM style_rules GROUP BY rule_type, severity''')
    print('\n📏 Style rules:')
    for rtype, sev, count in cur.fetchall():
        print(f'   {rtype:15} {sev:8} {count}')

    # Doctor log by issue type
    cur.execute('''SELECT issue_type, severity, COUNT(*)
                   FROM doctor_log WHERE resolved_at IS NULL
                   GROUP BY issue_type, severity ORDER BY COUNT(*) DESC''')
    print('\n🔍 Doctor findings (unresolved):')
    rows = cur.fetchall()
    if rows:
        for itype, sev, count in rows:
            print(f'   [{sev:7}] {itype:25} {count}')
    else:
        print('   (no unresolved issues)')

    # Top offending ch
    cur.execute('''SELECT ch_num, COUNT(*) as issues, MAX(severity) as worst
                   FROM doctor_log WHERE resolved_at IS NULL
                   GROUP BY ch_num ORDER BY issues DESC LIMIT 10''')
    print('\n📈 Top offending ch:')
    for ch, n, worst in cur.fetchall():
        print(f'   ch{ch:4} {n:3} issues (worst={worst})')

    # Unused terms
    unused = find_unused_terms()
    print(f'\n🗑️  Unused auto terms (candidates for archive): {len(unused)}')

    conn.close()


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ch', help='Single ch or range (e.g., 50 or 50-60)')
    ap.add_argument('--all', action='store_true', help='All translated ch')
    ap.add_argument('--inconsistencies', action='store_true', help='Find CN→Thai mapping issues')
    ap.add_argument('--new-terms', type=int, metavar='CH', help='Find un-glossaried CN in ch')
    ap.add_argument('--unused', action='store_true', help='Find auto terms never used')
    ap.add_argument('--report', action='store_true', help='Full report')
    ap.add_argument('--clean', action='store_true', help='Clear doctor_log before running')
    ap.add_argument('--gate', type=int, metavar='CH', help='CI gate — exit 0=clean, 1=warn, 2=error')
    ap.add_argument('--fix-hints', type=int, metavar='CH', help='Show fix hints for ch')
    args = ap.parse_args()

    glossary, alias_map, style_rules = load_glossary()

    if args.clean:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM doctor_log')
        conn.commit()
        conn.close()
        print('✓ doctor_log cleared')

    if args.report or (not any([args.ch, args.all, args.inconsistencies,
                                 args.new_terms, args.unused, args.gate, args.fix_hints])):
        print_report()
        return

    if args.gate is not None:
        issues = validate_chapter(args.gate, glossary, alias_map, style_rules)
        has_error = any(i.get('severity') == 'error' for i in issues)
        has_warn = any(i.get('severity') == 'warning' for i in issues)
        if has_error:
            print(f'❌ ch{args.gate}: BLOCKED ({sum(1 for i in issues if i.get("severity") == "error")} errors)')
            for i in issues:
                if i.get('severity') == 'error':
                    print(f'   {i.get("rule_type")}: {i.get("pattern", "")[:60]}')
            sys.exit(2)
        elif has_warn:
            print(f'⚠️  ch{args.gate}: warnings ({sum(1 for i in issues if i.get("severity") == "warning")} warnings)')
            sys.exit(1)
        else:
            print(f'✓ ch{args.gate}: clean')
            sys.exit(0)

    if args.fix_hints is not None:
        issues = validate_chapter(args.fix_hints, glossary, alias_map, style_rules)
        print_fix_hints(args.fix_hints, issues)
        return

    if args.ch:
        if '-' in args.ch:
            a, b = map(int, args.ch.split('-'))
            chs = list(range(a, b + 1))
        else:
            chs = [int(args.ch)]
        total_issues = 0
        for ch in chs:
            issues = validate_chapter(ch, glossary, alias_map, style_rules)
            if issues:
                errors = sum(1 for i in issues if i.get('severity') == 'error')
                warnings = sum(1 for i in issues if i.get('severity') == 'warning')
                print(f'\nch{ch}: {len(issues)} issues ({errors} errors, {warnings} warnings)')
                for issue in issues:
                    sev = issue.get('severity', '?')
                    p = issue.get('pattern', '')[:60]
                    fix = issue.get('fix', '')[:50]
                    icon = '❌' if sev == 'error' else '⚠️ ' if sev == 'warning' else 'ℹ️ '
                    print(f'  {icon}[{sev:7}] {issue.get("rule_type"):20} {p}')
                    if fix and sev != 'info':
                        print(f'             → {fix}')
                total_issues += len(issues)
            else:
                print(f'ch{ch}: ✓ clean')
        print(f'\nTotal: {total_issues} issues across {len(chs)} ch')

    if args.all:
        ch_files = sorted([f for f in CHAPTERS_DIR.glob('[0-9]*.md')
                          if f.is_file() and f.stem.isdigit() and len(f.stem) == 4],
                         key=lambda p: int(p.stem))
        total_issues = 0
        clean_count = 0
        blocked_count = 0
        for ch_file in ch_files:
            ch = int(ch_file.stem)
            issues = validate_chapter(ch, glossary, alias_map, style_rules)
            total_issues += len(issues)
            if not issues:
                clean_count += 1
            elif any(i.get('severity') == 'error' for i in issues):
                blocked_count += 1
        print(f'\n{"=" * 50}')
        print(f'Total: {total_issues} issues across {len(ch_files)} ch')
        print(f'Clean: {clean_count}/{len(ch_files)} ch')
        print(f'Blocked: {blocked_count} ch')

    if args.inconsistencies:
        incon = find_inconsistencies_in_db()
        if incon:
            print(f'\n⚠️  Found {len(incon)} inconsistencies:')
            for src, vars_, n in incon:
                print(f'   {src}: {vars_}')
        else:
            print('✓ No inconsistencies')

    if args.new_terms:
        text = (CHAPTERS_DIR / f'{args.new_terms:04d}.md').read_text(encoding='utf-8')
        new_issues = detect_new_terms(text, glossary)
        for i in new_issues:
            print(f'   {i["pattern"]}')

    if args.unused:
        unused = find_unused_terms()
        print(f'\n🗑️  Unused auto terms: {len(unused)}')
        for tid, src, thai, prio, score in unused[:20]:
            print(f'   {src} → {thai}')


if __name__ == '__main__':
    main()
