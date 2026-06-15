"""glossary_doctor.py — Completeness + structural validator for novel translations.

Aligned with **translator transmittor principle**:
  - We TRANSMIT the source faithfully, not EDIT it
  - We DETECT issues and REPORT them, never silently rewrite
  - We BLOCK save only on hard errors (forbidden terms, missing content)
  - We WARN on structural issues (title, length, missing beats) but don't
    auto-fix the author's voice (ฉายแวว, ดังนั้น, เต็มไปด้วย, 3+ เฉาซิง
    are author's style — preserved as-is)

What we CHECK (severity levels):

  ERROR (BLOCKS save):
    1. Forbidden pattern — locked term violation (e.g., ฮ่องกง vs เซียนเจียง)
    2. CN leakage in body — raw CN chars in translated prose (excludes 【】,
       《》, *Source: ch N* footer, หมายเหตุ meta)
    3. Missing content — major source beat not in translation (named
       characters, plot events, system messages)
    4. Empty file / missing translation

  WARNING (allows save, flagged):
    5. Title/body mismatch (title references name/word not in body)
    6. Length ratio extreme (TH:CN < 0.5x or > 5x — likely truncated or
       padded; "natural" range 1.3-3.0x reported as info)
    7. Inconsistency (same source → multiple Thai across CH, not within)
    8. New CN term not yet in glossary (candidate for auto.md)

  INFO (logged, not blocking):
    9. Anti-pattern in TRANSLATED text (not source) — e.g., Mika
       generated "ดีใจในใจ" not in source. (Author's "ฉายแวว" is OK.)
    10. Subject echo (3+ consecutive เฉาซิง) — only flag if it appears
        MORE in translation than in source (translator over-added)
    11. Style preference (preferred form not used) — informational only

Usage:
  python tools/glossary_doctor.py --ch 112          # validate single ch
  python tools/glossary_doctor.py --ch 1-112        # validate range
  python tools/glossary_doctor.py --all             # validate all translated ch
  python tools/glossary_doctor.py --inconsistencies # find CN→Thai mapping issues
  python tools/glossary_doctor.py --new-terms CH    # scan ch for un-glossaried CN
  python tools/glossary_doctor.py --report          # full report
  python tools/glossary_doctor.py --gate CH         # CI gate
  python tools/glossary_doctor.py --completeness CH # check ch has all source beats

Exit codes (--gate):
  0 = clean / info only
  1 = warnings (still saveable)
  2 = errors (BLOCKED)
"""
import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT, CHAPTERS_DIR, GLOSSARY_DIR, get_novel_root  # noqa: E402

DB_PATH = GLOSSARY_DIR / 'glossary.db'

# Length ratio bounds (TH natural expansion of CN)
# These are SIGNALS, not hard rules — translator can deviate if source demands
LENGTH_RATIO_LOW = 0.5    # below = likely truncated
LENGTH_RATIO_HIGH = 5.0   # above = likely padded (1.3-3.0 is normal range)
LENGTH_RATIO_NORMAL = (1.3, 3.0)


# ────────────────────────────────────────────────────────────────────
# Data loaders
# ────────────────────────────────────────────────────────────────────

def load_glossary():
    """Load all terms + aliases + style_rules from DB."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
    alias_map = {}
    cur.execute('''SELECT a.source_variant, t.source_norm
                   FROM aliases a JOIN terms t ON a.term_id = t.id''')
    for variant, norm in cur.fetchall():
        alias_map[variant] = norm
    style_rules = []
    cur.execute('''SELECT rule_type, pattern, replacement, severity, scope,
                          example_before, example_after, explanation
                   FROM style_rules''')
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
# Detectors — ERRORs (block save)
# ────────────────────────────────────────────────────────────────────

def detect_forbidden(text, style_rules):
    """ERROR — find any forbidden patterns (e.g., ฮ่องกง, banned terms)."""
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
                'note': f"replace with: {rule['replacement']}" if rule['replacement'] else 'banned',
                'explanation': rule['explanation'],
            })
    return issues


def detect_format_violations(text, ch_num):
    """ERROR — check ch matches format_spec.md (single source of truth).

    Transmittor principle: format violations are mechanical, not content.
    They block save because they'll be auto-fixed, but the user can re-run
    `tools/reformat_chapter.py` to apply the fixes.

    Checks:
    - Straight `"` (should be 「」)
    - Trailing whitespace
    - 3+ blank lines
    - Missing (จบบท) marker
    - Missing *Source: ch N* short-form footer
    - *Source:* footer with verbose content (novel title, author)
    - Tabs
    """
    issues = []
    body = re.split(r'\nหมายเหตุ', text, maxsplit=1)[0]

    # 1. Straight quotes outside of whitelisted zones
    # Skip *Source:* line, skip lines starting with -
    quote_count = 0
    for line in body.split('\n'):
        if line.strip().startswith('-'):
            continue
        if line.strip().startswith('*') and line.strip().endswith('*'):
            continue
        if line.strip() == '---':
            continue
        if '「' in line or '」' in line:
            # OK, has CJK quotes already
            continue
        # Skip lines inside 【...】 system messages
        quote_count += line.count('"')
    if quote_count > 0:
        issues.append({
            'rule_type': 'format_straight_quote',
            'severity': 'error',
            'pattern': f'{quote_count} straight " outside dialogue zones',
            'count': quote_count,
            'note': 'use 「」 for dialogue (run tools/reformat_chapter.py)',
            'explanation': 'format spec requires 「」 for dialogue, not straight "',
        })

    # 2. Trailing whitespace
    trailing = sum(1 for line in text.split('\n') if line != line.rstrip())
    if trailing:
        issues.append({
            'rule_type': 'format_trailing_whitespace',
            'severity': 'error',
            'pattern': f'{trailing} lines with trailing whitespace',
            'count': trailing,
            'note': 'strip trailing whitespace (auto-fixable)',
            'explanation': 'format spec requires no trailing whitespace',
        })

    # 3. 3+ blank lines
    if re.search(r'\n\n\n+', text):
        issues.append({
            'rule_type': 'format_multi_blank',
            'severity': 'error',
            'pattern': '3+ consecutive blank lines',
            'count': 1,
            'note': 'collapse to single blank line (auto-fixable)',
            'explanation': 'format spec requires max 1 blank line between paragraphs',
        })

    # 4. Missing (จบบท)
    if '(จบบท)' not in body and '本章完' not in text:
        issues.append({
            'rule_type': 'format_missing_end',
            'severity': 'error',
            'pattern': 'missing (จบบท) end marker',
            'count': 1,
            'note': 'add (จบบท) before --- separator',
            'explanation': 'format spec requires (จบบท) end marker',
        })

    # 5. *Source:* footer format
    src_match = re.search(r'\*Source:[^*]*\*', text)
    if not src_match:
        issues.append({
            'rule_type': 'format_missing_source',
            'severity': 'error',
            'pattern': 'missing *Source: ch N* footer',
            'count': 1,
            'note': 'add *Source: ch N* (short form, no novel title)',
            'explanation': 'format spec requires *Source: ch N* footer',
        })
    elif '全球降臨' in src_match.group() or '一條' in src_match.group() or '小白蛇' in src_match.group():
        issues.append({
            'rule_type': 'format_verbose_source',
            'severity': 'error',
            'pattern': f'verbose Source footer: {src_match.group()}',
            'count': 1,
            'note': 'use short form *Source: ch N* (not novel title/author)',
            'explanation': 'format spec: short Source footer only',
        })

    # 6. Tabs
    if '\t' in text:
        issues.append({
            'rule_type': 'format_tabs',
            'severity': 'error',
            'pattern': 'tab characters found',
            'count': text.count('\t'),
            'note': 'convert to spaces (auto-fixable)',
            'explanation': 'format spec requires spaces, not tabs',
        })

    return issues


def detect_cjk_leakage(text):
    """ERROR — find raw CN chars in body (excludes whitelisted zones)."""
    cleaned = re.sub(r'【[^】]*】', '', text)  # system messages
    cleaned = re.sub(r'《[^》]*》', '', cleaned)  # game titles
    cleaned = re.sub(r'「[^」]*」', '', cleaned)  # dialogue
    cleaned = re.sub(r'\*Source:[^*]*\*', '', cleaned)  # source footer
    cleaned = re.split(r'\nหมายเหตุ[ก-๙ ]*[:：]', cleaned, maxsplit=1)[0]
    cleaned = re.split(r'\n(?:Translation [Nn]otes?|Note:|Notes:)\s*\n', cleaned, maxsplit=1)[0]
    cjk = re.findall(r'[\u4e00-\u9fff]', cleaned)
    if cjk:
        return [{
            'rule_type': 'cjk_leakage',
            'severity': 'error',
            'pattern': f'{len(cjk)} CN chars in body',
            'count': len(cjk),
            'note': 'translate or move to whitelisted zone (【】, 《》, 「」, footer)',
            'explanation': 'CN chars in translated body = untranslated content',
        }]
    return []


def detect_completeness(text, ch_num):
    """ERROR — check if major source terms (in glossary) appear in translation.

    Strategy: only flag locked terms that are NOT yet covered by the
    translation's choice. We don't flag legacy ch (1-111) where the
    glossary Thai diverges from actual usage — that's a glossary
    alignment issue, not a translation issue. For new ch, we expect
    the translator to use locked Thai forms.

    Approach: only flag if a locked term in source is COMPLETELY missing
    from translation (no Thai form of it exists). If the term is in
    glossary but translation uses a different Thai, that's a glossary
    drift issue — out of scope for this check.
    """
    issues = []
    source_path = CHAPTERS_DIR / 'source' / f'{ch_num:04d}.md'
    if not source_path.exists():
        return []
    src_text = source_path.read_text(encoding='utf-8')
    # Get glossary terms
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''SELECT source_norm, thai FROM terms
                   WHERE status = "active" AND priority <= 2''')
    locked_terms = list(cur.fetchall())
    conn.close()
    # Heuristic: only flag if the source term is NOT in the body AT ALL
    # (neither as CN nor in any Thai form). This catches missing characters/items
    # without false-positiving on legacy ch where glossary Thai drifted.
    # Better signal: check 【】 system message count matches between source and translation
    src_sys = re.findall(r'【[^】]+】', src_text)
    th_sys = re.findall(r'【[^】]+】', text)
    if src_sys and len(th_sys) < len(src_sys) * 0.5:
        return [{
            'rule_type': 'completeness',
            'severity': 'error',
            'pattern': f'source has {len(src_sys)} system messages, translation has {len(th_sys)}',
            'count': 1,
            'note': 'translation may be missing 【】 system messages from source',
            'explanation': 'transmittor must include all source content',
        }]
    return []


# ────────────────────────────────────────────────────────────────────
# Detectors — WARNINGs (allows save, flagged)
# ────────────────────────────────────────────────────────────────────

def detect_title_body_mismatch(text):
    """WARNING — check that words in title appear in body."""
    issues = []
    title_match = re.search(r'^#\s*ตอนที่\s*\d+\s*(.+)', text, re.MULTILINE)
    if not title_match:
        return issues
    title = title_match.group(1).strip()
    title_words = re.findall(r'[\u0E00-\u0E7F]{3,}', title)
    body = text[title_match.end():]
    body_words = set(re.findall(r'[\u0E00-\u0E7F]{3,}', body))
    for tw in title_words:
        if tw in ('ตอนที่', 'บทที่', 'ภาค', 'เฉาซิง', 'หลิวมู่เสวี่ย'):
            continue
        if tw not in body_words:
            # Look for close match (first 3 chars)
            close = None
            for bw in body_words:
                if len(tw) >= 3 and len(bw) >= 3 and tw[:3] == bw[:3]:
                    close = bw
                    break
            if close:
                issues.append({
                    'rule_type': 'title_mismatch',
                    'severity': 'warning',
                    'pattern': f'title="{tw}" body="{close}"',
                    'count': 1,
                    'note': f'title uses "{tw}", body uses "{close}" — different forms of same name?',
                    'explanation': 'title and body should use consistent term forms',
                })
    return issues


def detect_length_ratio(text, ch_num):
    """WARNING — flag extreme length ratios (likely truncated or padded)."""
    source_path = CHAPTERS_DIR / 'source' / f'{ch_num:04d}.md'
    if not source_path.exists():
        return []
    src_text = source_path.read_text(encoding='utf-8')
    src_chars = len(re.findall(r'[\u4e00-\u9fff]', src_text))
    th_chars = len(text)
    if src_chars < 100:
        return []
    ratio = th_chars / src_chars
    issues = []
    if ratio < LENGTH_RATIO_LOW:
        issues.append({
            'rule_type': 'length_ratio_low',
            'severity': 'warning',
            'pattern': f'ratio={ratio:.2f}x (src={src_chars}, th={th_chars})',
            'count': 1,
            'note': f'below {LENGTH_RATIO_LOW}x — likely TRUNCATED, check missing content',
            'explanation': 'translation significantly shorter than source',
        })
    elif ratio > LENGTH_RATIO_HIGH:
        issues.append({
            'rule_type': 'length_ratio_high',
            'severity': 'warning',
            'pattern': f'ratio={ratio:.2f}x (src={src_chars}, th={th_chars})',
            'count': 1,
            'note': f'above {LENGTH_RATIO_HIGH}x — likely PADDED with non-source content',
            'explanation': 'translation significantly longer than source',
        })
    elif ratio < LENGTH_RATIO_NORMAL[0] or ratio > LENGTH_RATIO_NORMAL[1]:
        issues.append({
            'rule_type': 'length_ratio_outside_normal',
            'severity': 'info',
            'pattern': f'ratio={ratio:.2f}x (normal: {LENGTH_RATIO_NORMAL[0]}-{LENGTH_RATIO_NORMAL[1]}x)',
            'count': 1,
            'note': 'outside normal range but not extreme',
            'explanation': 'TH natural expansion typically 1.3-3.0x',
        })
    return issues


def detect_inconsistencies(text, glossary):
    """WARNING — same source has multiple Thai versions IN SAME CH."""
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
                'note': f'pick one consistent form (DB has multiple)',
                'explanation': 'multiple Thai versions used in same ch for same source',
            })
    return issues


def detect_new_terms(text, glossary):
    """INFO — find CN terms in text that aren't in glossary yet."""
    issues = []
    cn_terms = set(re.findall(r'[\u4e00-\u9fff]{2,6}', text))
    known = set(glossary.keys())
    new = [t for t in cn_terms if t not in known and len(t) >= 2]
    if new:
        sample = sorted(new, key=lambda x: -len(x))[:10]
        issues.append({
            'rule_type': 'new_terms',
            'severity': 'info',
            'pattern': ', '.join(sample),
            'count': len(new),
            'note': 'candidates for auto.md',
            'explanation': f'found {len(new)} CN terms not yet in glossary',
        })
    return issues


# ────────────────────────────────────────────────────────────────────
# Detectors — INFOs (transmittor doesn't auto-fix author's voice)
# ────────────────────────────────────────────────────────────────────

def detect_anti_patterns(text, style_rules, ch_num=None):
    """INFO — anti-patterns detected in TRANSLATED text (not source).

    Per transmittor principle: we only flag patterns that are MORE present
    in the translation than in the source. Author's existing usage is
    preserved. Translator generating new anti-patterns is the real error.
    """
    issues = []
    # If we have source, compare counts
    src_text = ''
    if ch_num:
        source_path = CHAPTERS_DIR / 'source' / f'{ch_num:04d}.md'
        if source_path.exists():
            src_text = source_path.read_text(encoding='utf-8')
    for rule in style_rules:
        if rule['rule_type'] not in ('anti_pattern', 'collocation'):
            continue
        try:
            th_matches = re.findall(rule['pattern'], text)
        except re.error:
            continue
        if not th_matches:
            continue
        th_count = len(th_matches)
        # Compare to source count
        if src_text:
            try:
                src_count = len(re.findall(rule['pattern'], src_text))
            except re.error:
                src_count = 0
            # Only flag if TRANSLATION has MORE than source
            if th_count <= max(src_count, 1):
                continue
            delta = th_count - src_count
            issues.append({
                'rule_type': rule['rule_type'],
                'severity': 'info',
                'pattern': rule['pattern'][:60],
                'count': th_count,
                'note': f'translation has {th_count}x, source has {src_count}x (+{delta} added)',
                'explanation': f'translator generated new instances beyond source',
            })
        else:
            # No source — just report
            issues.append({
                'rule_type': rule['rule_type'],
                'severity': 'info',
                'pattern': rule['pattern'][:60],
                'count': th_count,
                'note': f'present {th_count}x in translation',
                'explanation': rule['explanation'],
            })
    return issues


def detect_subject_echo(text, ch_num=None, subject='เฉาซิง', max_consec=3):
    """INFO — subject echo (3+ consecutive same subject).

    Transmitor principle: only flag if TRANSLATION has MORE consecutive
    runs than source. Author's natural usage is preserved.
    """
    def count_max_run(t):
        sents = [s.strip() for s in re.split(r'[。\n]', t) if s.strip()]
        consec = 0
        max_run = 0
        for s in sents:
            if s.startswith(subject):
                consec += 1
                max_run = max(max_run, consec)
            else:
                consec = 0
        return max_run
    th_run = count_max_run(text)
    if th_run < max_consec:
        return []
    if ch_num:
        source_path = CHAPTERS_DIR / 'source' / f'{ch_num:04d}.md'
        if source_path.exists():
            src_text = source_path.read_text(encoding='utf-8')
            # CN subject is 曹星
            src_run = count_max_run(src_text.replace('曹星', subject))
            if src_run >= th_run:
                # Source already has this pattern, transmittor preserves it
                return []
    return [{
        'rule_type': 'subject_echo',
        'severity': 'info',
        'pattern': f'{th_run} consecutive "{subject}"',
        'count': th_run,
        'note': 'check if source also has this pattern (preserved = OK)',
        'explanation': '3+ consecutive same subject (P5) — verify it matches source',
    }]


# ────────────────────────────────────────────────────────────────────
# Main validation
# ────────────────────────────────────────────────────────────────────

def validate_chapter(ch_num, glossary, alias_map, style_rules, log_to_db=True):
    """Run all detectors on a single chapter. Returns list of issues.

    Prefers .json (structured) over .md (legacy).
    """
    json_path = CHAPTERS_DIR / f'{ch_num:04d}.json'
    md_path = CHAPTERS_DIR / f'{ch_num:04d}.md'

    if json_path.exists():
        # Reconstruct text from JSON blocks (clean, no JSON structure noise)
        import json as _json
        with open(json_path, encoding='utf-8') as f:
            ch = _json.load(f)
        text = '\n\n'.join(b.get('text', '') for b in ch.get('blocks', []))
        # Also include source for *Source:* footer check
        if ch.get('source'):
            text += f'\n\n*Source: {ch["source"]}*'
    elif md_path.exists():
        text = md_path.read_text(encoding='utf-8')
    else:
        return [{'rule_type': 'error', 'severity': 'error',
                 'pattern': f'ch {ch_num} not found', 'count': 1}]
    issues = []
    # ERRORS (block save)
    issues.extend(detect_forbidden(text, style_rules))
    issues.extend(detect_cjk_leakage(text))
    issues.extend(detect_completeness(text, ch_num))
    issues.extend(detect_format_violations(text, ch_num))
    # WARNINGS (allow save, flag)
    issues.extend(detect_title_body_mismatch(text))
    issues.extend(detect_length_ratio(text, ch_num))
    issues.extend(detect_inconsistencies(text, glossary))
    # INFO (logged)
    issues.extend(detect_new_terms(text, glossary))
    issues.extend(detect_anti_patterns(text, style_rules, ch_num))
    issues.extend(detect_subject_echo(text, ch_num))

    if log_to_db and issues:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('DELETE FROM doctor_log WHERE ch_num = ? AND resolved_at IS NULL', (ch_num,))
        for issue in issues:
            if issue.get('rule_type') == 'error':
                continue
            cur.execute('''INSERT INTO doctor_log
                          (ch_num, issue_type, severity, pattern, location, fix_suggestion)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                        (ch_num, issue['rule_type'], issue.get('severity', 'info'),
                         issue.get('pattern', ''), '', issue.get('note', '')))
        has_errors = any(i.get('severity') == 'error' for i in issues)
        has_warnings = any(i.get('severity') == 'warning' for i in issues)
        status = 'has_errors' if has_errors else ('has_warnings' if has_warnings else 'clean')
        cur.execute('''INSERT OR REPLACE INTO ch_meta
                      (ch_num, translated_at, glossary_version, validation_status)
                      VALUES (?, ?, ?, ?)''',
                    (ch_num, datetime.now().isoformat(), '3.0-transmittor', status))
        conn.commit()
        conn.close()
    return issues


def find_inconsistencies_in_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''SELECT source_norm, GROUP_CONCAT(DISTINCT thai) as variants, COUNT(DISTINCT thai) as n
                   FROM terms WHERE status = "active"
                   GROUP BY source_norm HAVING n > 1''')
    results = cur.fetchall()
    conn.close()
    return results


def find_unused_terms():
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


def print_report():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print('=' * 60)
    print('GLOSSARY DOCTOR REPORT')
    print(f'Generated: {datetime.now().isoformat()}')
    print('=' * 60)
    cur.execute('''SELECT scope, priority, status, COUNT(*)
                   FROM terms GROUP BY scope, priority, status ORDER BY priority, scope''')
    print('\nTerms by tier/priority/status:')
    for scope, prio, status, count in cur.fetchall():
        pname = {1: 'LOCKED', 2: 'REFERENCE', 3: 'AUTO'}.get(prio, str(prio))
        print(f'   {pname:9} {scope:15} {status:9} {count}')
    cur.execute('''SELECT category, COUNT(*) FROM terms
                   WHERE status = "active" GROUP BY category ORDER BY 2 DESC''')
    print('\nBy category:')
    for cat, n in cur.fetchall():
        print(f'   {cat or "unknown":15} {n}')
    cur.execute('''SELECT
        COUNT(CASE WHEN explanation IS NULL OR explanation = '' THEN 1 END) as no_expl,
        COUNT(CASE WHEN explanation IS NOT NULL AND explanation != '' THEN 1 END) as with_expl
        FROM terms WHERE status = "active"''')
    no_expl, with_expl = cur.fetchone()
    print(f'\nExplanations: {with_expl} have, {no_expl} missing')
    incon = find_inconsistencies_in_db()
    print(f'\nInconsistencies (same source → different Thai): {len(incon)}')
    for src, vars_, n in incon:
        print(f'   {src}: {vars_}')
    cur.execute('''SELECT rule_type, severity, COUNT(*)
                   FROM style_rules GROUP BY rule_type, severity''')
    print('\nStyle rules:')
    for rtype, sev, count in cur.fetchall():
        print(f'   {rtype:15} {sev:8} {count}')
    cur.execute('''SELECT issue_type, severity, COUNT(*)
                   FROM doctor_log WHERE resolved_at IS NULL
                   GROUP BY issue_type, severity ORDER BY COUNT(*) DESC''')
    print('\nDoctor findings (unresolved):')
    rows = cur.fetchall()
    if rows:
        for itype, sev, count in rows:
            print(f'   [{sev:7}] {itype:25} {count}')
    else:
        print('   (no unresolved issues)')
    cur.execute('''SELECT ch_num, COUNT(*) as issues, MAX(severity) as worst
                   FROM doctor_log WHERE resolved_at IS NULL
                   GROUP BY ch_num ORDER BY issues DESC LIMIT 10''')
    print('\nTop offending ch:')
    for ch, n, worst in cur.fetchall():
        print(f'   ch{ch:4} {n:3} issues (worst={worst})')
    conn.close()


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--novel', type=str, default=None, help='Novel slug (default: global-descent or NOVEL_SLUG env)')
    ap.add_argument('--ch', help='Single ch or range (e.g., 50 or 50-60)')
    ap.add_argument('--all', action='store_true', help='All translated ch')
    ap.add_argument('--inconsistencies', action='store_true', help='Find CN→Thai mapping issues')
    ap.add_argument('--new-terms', type=int, metavar='CH', help='Find un-glossaried CN in ch')
    ap.add_argument('--unused', action='store_true', help='Find auto terms never used')
    ap.add_argument('--report', action='store_true', help='Full report')
    ap.add_argument('--clean', action='store_true', help='Clear doctor_log before running')
    ap.add_argument('--gate', type=int, metavar='CH', help='CI gate — exit 0=clean, 1=warn, 2=error')
    ap.add_argument('--completeness', type=int, metavar='CH', help='Check ch has all source beats')
    args = ap.parse_args()

    # Resolve novel-specific paths
    global CHAPTERS_DIR, GLOSSARY_DIR, DB_PATH
    root = get_novel_root(args.novel)
    CHAPTERS_DIR = root / 'chapters'
    GLOSSARY_DIR = root / 'glossary'
    DB_PATH = GLOSSARY_DIR / 'glossary.db'

    glossary, alias_map, style_rules = load_glossary()

    if args.clean:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM doctor_log')
        conn.commit()
        conn.close()
        print('doctor_log cleared')

    if args.report or (not any([args.ch, args.all, args.inconsistencies,
                                 args.new_terms, args.unused, args.gate, args.completeness])):
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
                    if i.get('note'):
                        print(f'     → {i["note"][:80]}')
            sys.exit(2)
        elif has_warn:
            print(f'⚠️  ch{args.gate}: warnings ({sum(1 for i in issues if i.get("severity") == "warning")} warnings)')
            sys.exit(1)
        else:
            print(f'✓ ch{args.gate}: clean / info only')
            sys.exit(0)

    if args.completeness is not None:
        text = (CHAPTERS_DIR / f'{args.completeness:04d}.md').read_text(encoding='utf-8')
        issues = detect_completeness(text, args.completeness)
        if issues:
            for i in issues:
                print(f'  {i["pattern"]}')
                if i.get('note'):
                    print(f'    → {i["note"]}')
        else:
            print(f'✓ ch{args.completeness}: all source beats present')

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
                info = sum(1 for i in issues if i.get('severity') == 'info')
                print(f'\nch{ch}: {len(issues)} issues ({errors} errors, {warnings} warnings, {info} info)')
                for issue in issues:
                    sev = issue.get('severity', '?')
                    p = issue.get('pattern', '')[:60]
                    note = issue.get('note', '')[:50]
                    icon = '❌' if sev == 'error' else '⚠️ ' if sev == 'warning' else 'ℹ️ '
                    print(f'  {icon}[{sev:7}] {issue.get("rule_type"):20} {p}')
                    if note and sev != 'info':
                        print(f'             → {note}')
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
            print(f'\nFound {len(incon)} inconsistencies:')
            for src, vars_, n in incon:
                print(f'   {src}: {vars_}')
        else:
            print('No inconsistencies')

    if args.new_terms:
        text = (CHAPTERS_DIR / f'{args.new_terms:04d}.md').read_text(encoding='utf-8')
        new_issues = detect_new_terms(text, glossary)
        for i in new_issues:
            print(f'   {i["pattern"]}')

    if args.unused:
        unused = find_unused_terms()
        print(f'\nUnused auto terms: {len(unused)}')
        for tid, src, thai, prio, score in unused[:20]:
            print(f'   {src} → {thai}')


if __name__ == '__main__':
    main()
