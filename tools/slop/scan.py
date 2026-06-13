"""scan.py — Orchestrator: scan chapters, aggregate, print report.

Wires together `anti_ai`, `text_stats`, and `paragraph_metrics`.
CLI: `python tools/slop_detector.py [args]`
"""
import re
import sys
import json
import math
import statistics
from collections import Counter
from pathlib import Path

# Make sibling tools/ importable (constants.NOVEL_ROOT)
sys.path.insert(0, str(Path(__file__).parent.parent))
from constants import NOVEL_ROOT  # noqa: E402

from .anti_ai import (
    find_tier1, find_tier2, find_tier3,
    find_mika_patterns, find_adenaufal,
)
from .text_stats import tokenize_th, get_ngrams
from .paragraph_metrics import (
    em_dash_stats, staccato_check, sentence_variety,
    burstiness, function_word_diversity, megumin_structural_check,
    paragraph_metrics,
)

CHAPTERS_DIR = NOVEL_ROOT / 'chapters'


# ── Per-chapter scan ───────────────────────────────────────────────

def scan_chapter(ch_file) -> dict:
    """Scan a single chapter. Returns dict of all stats."""
    text = ch_file.read_text(encoding='utf-8')

    tier1_hits = find_tier1(text)
    tier2_hits = find_tier2(text)
    tier3_hits = find_tier3(text)
    mika_pattern_hits = find_mika_patterns(text)
    adenaufal_hits = find_adenaufal(text)

    em = em_dash_stats(text)
    staccato = staccato_check(text)
    variety = sentence_variety(text)
    burst = burstiness(text)
    funcword = function_word_diversity(text)
    megumin = megumin_structural_check(text)
    para_metrics = paragraph_metrics(text)  # v3

    return {
        'file': ch_file.name,
        'chars': len(text),
        'tier1': tier1_hits,
        'tier2': tier2_hits,
        'tier3': tier3_hits,
        'mika': mika_pattern_hits,
        'adenaufal': adenaufal_hits,
        'em_dash': em,
        'staccato_runs': len(staccato),
        'staccato_examples': staccato[:3],
        'sentence_variety': variety,
        'burstiness': burst,
        'function_words': funcword,
        'megumin_issues': megumin,
        'paragraph_metrics': para_metrics,  # v3
    }


# ── Aggregate scan ─────────────────────────────────────────────────

def scan_chapters(chapter_filter=None):
    """Scan all (or one) translated chapters. Returns aggregate report."""
    if not CHAPTERS_DIR.exists():
        print(f"No chapters dir: {CHAPTERS_DIR}")
        return None

    ch_files = sorted([f for f in CHAPTERS_DIR.iterdir() if f.suffix == '.md'])
    if chapter_filter:
        ch_files = [f for f in ch_files if f.stem == f"{int(chapter_filter):04d}"]

    print(f"Scanning {len(ch_files)} chapters in {CHAPTERS_DIR}\n")

    all_tokens = []
    all_text = ""

    tier1_agg = Counter()
    tier2_agg = Counter()
    tier3_agg = Counter()
    mika_agg = []
    adenaufal_agg = []
    em_agg = {'total': 0, 'body': 0, 'placeholder': 0}
    staccato_agg = 0
    variety_agg = {'total': 0, 'types': Counter()}
    burst_lens = []
    funcword_agg = Counter()
    megumin_agg = []
    # v3 aggregates
    heavy_attr_total = 0
    split_brackets_total = 0
    number_forms_agg = Counter()
    attribution_agg_per_chapter = {}
    per_chapter = []

    for ch_file in ch_files:
        stats = scan_chapter(ch_file)
        per_chapter.append(stats)
        all_text += stats['chars'] and (ch_file.read_text(encoding='utf-8')) or ""
        all_tokens.extend(tokenize_th(ch_file.read_text(encoding='utf-8')))

        for k, v in stats['tier1'].items():
            tier1_agg[k] += v
        for k, v in stats['tier2'].items():
            tier2_agg[k] += v
        for k, v in stats['tier3'].items():
            tier3_agg[k] += v
        mika_agg.extend([(stats['file'], d, s) for d, s in stats['mika']])
        adenaufal_agg.extend([(stats['file'], d, s) for d, s in stats['adenaufal']])
        for k in em_agg:
            em_agg[k] += stats['em_dash'][k]
        staccato_agg += stats['staccato_runs']
        for k, v in stats['sentence_variety']['types'].items():
            variety_agg['types'][k] += v
        variety_agg['total'] += stats['sentence_variety']['total']
        burst_lens.append(stats['burstiness'])
        for k, v in stats['function_words']['function_words'].items():
            funcword_agg[k] += v
        megumin_agg.extend([(stats['file'], m) for m in stats['megumin_issues']])
        # v3 aggregation
        pm = stats['paragraph_metrics']
        heavy_attr_total += len(pm['heavy_attr_paras'])
        split_brackets_total += len(pm['split_brackets'])
        for k, v in pm['number_forms'].items():
            number_forms_agg[k] += v
        attribution_agg_per_chapter[stats['file']] = {
            'total_attr': sum(pm['attribution_per_para']),
            'heavy_paras': len(pm['heavy_attr_paras']),
        }

    # N-gram frequency
    print("Computing n-grams (3-7 word sequences)...")
    ngrams = get_ngrams(all_tokens, n_min=3, n_max=7)
    top_ngrams = [(ng, c) for ng, c in ngrams.most_common(50) if c >= 3]

    # Subject echo per chapter
    subject_echo = Counter()
    for ch_file in ch_files:
        text = ch_file.read_text(encoding='utf-8')
        sents = re.split(r'(?<=[。!?.])\s+', text)
        prev_start = None
        streak = 0
        for s in sents:
            s = s.strip()
            if not s:
                continue
            m = re.match(r'([ก-๙]{2,15})', s)
            subj = m.group(1) if m else None
            if subj and len(subj) >= 2:
                if subj == prev_start:
                    streak += 1
                    if streak >= 3:
                        subject_echo[(ch_file.name, prev_start)] += 1
                else:
                    streak = 1
                    prev_start = subj
            else:
                streak = 0
                prev_start = None

    # Aggregate sentence variety diversity
    total_types = sum(variety_agg['types'].values())
    entropy = 0.0
    for count in variety_agg['types'].values():
        if count > 0:
            p = count / total_types
            entropy -= p * math.log2(p)
    max_entropy = math.log2(max(1, len(variety_agg['types'])))
    diversity_score = entropy / max_entropy if max_entropy > 0 else 0.0

    # Aggregate burstiness
    burst_means = [b['mean'] for b in burst_lens if b['samples'] > 3]
    burst_sds = [b['sd'] for b in burst_lens if b['samples'] > 3]
    burstiness_agg = {
        'mean_sentence_len': statistics.mean(burst_means) if burst_means else 0,
        'mean_sd': statistics.mean(burst_sds) if burst_sds else 0,
    }

    return {
        'total_chapters': len(ch_files),
        'total_chars': sum(s['chars'] for s in per_chapter),
        'total_tokens': len(all_tokens),
        'tier1': tier1_agg.most_common(30),
        'tier2': tier2_agg.most_common(30),
        'tier3': tier3_agg.most_common(30),
        'top_ngrams': top_ngrams[:30],
        'subject_echo': subject_echo.most_common(15),
        'mika_patterns': mika_agg[:30],
        'adenaufal_hits': adenaufal_agg[:30],
        'em_dash': em_agg,
        'staccato_runs': staccato_agg,
        'sentence_variety_types': dict(variety_agg['types']),
        'sentence_variety_diversity': diversity_score,
        'burstiness_agg': burstiness_agg,
        'function_words_top': funcword_agg.most_common(15),
        'megumin_issues': megumin_agg[:20],
        'per_chapter': per_chapter,
        # v3 metrics
        'v3_heavy_attr_paras': heavy_attr_total,
        'v3_split_brackets': split_brackets_total,
        'v3_number_forms': dict(number_forms_agg),
        'v3_attribution_per_chapter': attribution_agg_per_chapter,
    }


# ── Reporting ──────────────────────────────────────────────────────

def print_report(report, top_n=20, chapter_filter=None):
    if not report:
        return
    print("=" * 70)
    print("  SLOP DETECTOR REPORT v2")
    print("=" * 70)
    print(f"  Chapters: {report['total_chapters']}")
    print(f"  Total chars: {report['total_chars']:,}")
    print(f"  Total tokens: {report['total_tokens']:,}")
    print()

    def show(name, items, clean_msg="(clean)"):
        print(f"--- {name} ---")
        if items:
            for item in items[:top_n]:
                if isinstance(item, tuple) and len(item) == 2:
                    label, count = item
                    print(f"  {count:>3}x  {label}")
        else:
            print(f"  {clean_msg}")
        print()

    show("Tier 1 (kill on sight) — top N", report['tier1'])
    show("Tier 2 (clusters) — top N", report['tier2'])
    show("Tier 3 (filler phrases) — top N", report['tier3'])
    show("Top recurring n-grams (3+ word, 3+ occ)", report['top_ngrams'])

    # Subject echo
    print(f"--- Subject echo (3+ consecutive same-subject sentences) ---")
    if report['subject_echo']:
        for (ch, subj), count in report['subject_echo'][:top_n]:
            print(f"  {count:>3}x  {subj}  ({ch})")
    else:
        print("  (clean)")
    print()

    # Mika patterns
    print(f"--- Mika-specific pattern hits ---")
    if report['mika_patterns']:
        for ch, desc, snippet in report['mika_patterns'][:top_n]:
            print(f"  {ch}: {desc}")
            print(f"    → {snippet}")
    else:
        print("  (clean)")
    print()

    # ── v2: NEW METRICS ──────────────────────────────────────
    print("=" * 70)
    print("  v2 NEW METRICS (Adenaufal T4 + Megumin)")
    print("=" * 70)

    # Em dash
    em = report['em_dash']
    print(f"--- Em dash usage (Adenaufal T4.10/4.12) ---")
    print(f"  Total: {em['total']}  |  Body: {em['body']}  |  Placeholder: {em['placeholder']}")
    if em['body'] > 0:
        print(f"  ⚠ Body em dashes present: {em['body']} (target: 0)")
    if em['placeholder'] > 5:
        print(f"  ⚠ Placeholder em dashes high: {em['placeholder']} (target: ≤2/chapter)")
    print()

    # Staccato
    print(f"--- Staccato triplets (Adenaufal T4.13) ---")
    print(f"  Total runs: {report['staccato_runs']}")
    if report['staccato_runs'] > 5:
        print(f"  ⚠ High staccato count: {report['staccato_runs']} (target: <5/chapter)")
    print()

    # Sentence variety
    print(f"--- Sentence type variety (Adenaufal T4.14) ---")
    types = report['sentence_variety_types']
    total = sum(types.values())
    if total > 0:
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            pct = c / total * 100
            print(f"  {pct:5.1f}%  {t:<16}  ({c})")
        print(f"  Diversity score (Shannon): {report['sentence_variety_diversity']:.2f} / 1.0")
        if report['sentence_variety_diversity'] < 0.6:
            print(f"  ⚠ Low diversity: {report['sentence_variety_diversity']:.2f} (target: ≥0.6)")
    print()

    # Burstiness
    b = report['burstiness_agg']
    print(f"--- Burstiness (sentence length SD) ---")
    print(f"  Mean sentence len: {b['mean_sentence_len']:.1f}")
    print(f"  Mean SD: {b['mean_sd']:.1f}  (target: >12 for variety)")
    if b['mean_sd'] < 12:
        print(f"  ⚠ Low SD: {b['mean_sd']:.1f} (monotonous AI rhythm)")
    print()

    # Function words
    print(f"--- Function word diversity (Adenaufal T4.16) ---")
    if report['function_words_top']:
        for w, c in report['function_words_top']:
            print(f"  {c:>4}x  {w}")
    print()

    # Megumin
    print(f"--- Megumin structural checks (5-Phase anti-slop) ---")
    if report['megumin_issues']:
        for ch, issue in report['megumin_issues'][:top_n]:
            print(f"  {ch}: {issue}")
    else:
        print("  (clean)")
    print()

    # Adenaufal pattern hits
    print(f"--- Adenaufal T4.5-T4.11 structural ---")
    if report['adenaufal_hits']:
        for ch, desc, snippet in report['adenaufal_hits'][:top_n]:
            print(f"  {ch}: {desc}")
            print(f"    → {snippet}")
    else:
        print("  (clean)")

    # ── v3: NEW METRICS (paragraph-level) ─────────────────────
    print()
    print("=" * 70)
    print("  v3 NEW METRICS (dialogue attribution + paragraph)")
    print("=" * 70)

    # Heavy attribution paragraphs
    print(f"--- Dialogue attribution (3+ per paragraph) ---")
    print(f"  Total heavy paragraphs (≥3 attributions): {report['v3_heavy_attr_paras']}")
    if report['v3_attribution_per_chapter']:
        # Show top 5 chapters with most attributions
        top_attr = sorted(
            report['v3_attribution_per_chapter'].items(),
            key=lambda x: -x[1]['total_attr']
        )[:5]
        for ch, stats in top_attr:
            if stats['total_attr'] > 0:
                print(f"  {ch}: {stats['total_attr']} attributions, {stats['heavy_paras']} heavy paras")
    if report['v3_heavy_attr_paras'] > 5:
        print(f"  ⚠ {report['v3_heavy_attr_paras']} heavy attribution paragraphs (target: <3/chapter avg)")
    print()

    # Split brackets
    print(f"--- 【】 split across consecutive paragraphs ---")
    print(f"  Total split occurrences: {report['v3_split_brackets']}")
    if report['v3_split_brackets'] > 0:
        print(f"  ⚠ {report['v3_split_brackets']} 【】 blocks span 2+ paragraphs (likely split event)")
    print()

    # Number forms
    nf = report['v3_number_forms']
    print(f"--- Number form consistency ---")
    print(f"  With comma (1,000): {nf.get('with_comma', 0)}")
    print(f"  With period (1.000): {nf.get('with_period', 0)}")
    print(f"  No separator (1000): {nf.get('no_sep', 0)}")
    forms_used = sum(1 for v in nf.values() if v > 0)
    if forms_used > 1:
        print(f"  ⚠ {forms_used} number forms in use — pick one (TH style: no separator or comma)")
    print()


# ── CLI ───────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    save = '--save' in args
    json_out = None
    top_n = 20
    chapter_filter = None
    for i, a in enumerate(args):
        if a == '--json' and i + 1 < len(args):
            json_out = args[i + 1]
        elif a == '--top' and i + 1 < len(args):
            top_n = int(args[i + 1])
        elif a == '--chapter' and i + 1 < len(args):
            chapter_filter = args[i + 1]

    report = scan_chapters(chapter_filter=chapter_filter)
    if not report:
        return 1

    if json_out:
        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"Saved JSON: {json_out}")
    else:
        print_report(report, top_n=top_n)

    if save and not chapter_filter:
        # Append to style.md
        banned = []
        for word, count in report['tier1'][:10]:
            banned.append(f"- `{word}` (Tier 1 — {count}x)")
        for phrase, count in report['tier3'][:10]:
            banned.append(f"- \"{phrase}\" (Tier 3 — {count}x)")
        for (ch, subj), count in report['subject_echo'][:5]:
            banned.append(f"- Subject echo: `{subj}...` x3+ in {ch} ({count}x)")
        # v2: add v2 metrics to banned list
        for w, c in report['function_words_top'][:5]:
            banned.append(f"- Function word: `{w}` ({c}x — check overuse)")
        if report['megumin_issues']:
            for ch, issue in report['megumin_issues'][:5]:
                banned.append(f"- {issue} ({ch})")
        if banned:
            appendix = "\n\n## Auto-detected slop candidates (slop_detector v2)\n\n" + "\n".join(banned)
            style_path = NOVEL_ROOT / 'style.md'
            if style_path.exists():
                with open(style_path, 'a', encoding='utf-8') as f:
                    f.write(appendix)
                print(f"\nAppended {len(banned)} items to {style_path}")
            else:
                print(f"\n(no style.md to append to)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
