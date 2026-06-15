"""slop — Anti-slop pattern detection for NovelClaw translations.

4 modules:

  - `slop.anti_ai`          — tier lists (TIER1/2/3/ADENAUFAL/MIKA) + matchers
  - `slop.text_stats`       — tokenize_th / split_sentences_th / get_ngrams
  - `slop.paragraph_metrics`— em_dash / staccato / variety / burstiness /
                              function_word / megumin / paragraph_metrics
  - `slop.scan`             — scan_chapter + report + CLI

Public re-exports here keep the old `from slop import X` import paths
working during the transition.
"""
from .anti_ai import (
    TIER1,
    TIER1_VARIANTS,
    TIER2,
    TIER3_PHRASES,
    ADENAUFAL_T4,
    MIKA_PATTERNS,
    find_tier1,
    find_tier2,
    find_tier3,
    find_mika_patterns,
    find_adenaufal,
)
from .text_stats import (
    tokenize_th,
    split_sentences_th,
    split_paragraphs,
    get_ngrams,
)
from .paragraph_metrics import (
    em_dash_stats,
    staccato_check,
    sentence_variety,
    burstiness,
    function_word_diversity,
    megumin_structural_check,
    paragraph_metrics,
    FUNC_WORDS,
)

__all__ = [
    # anti_ai
    'TIER1', 'TIER1_VARIANTS', 'TIER2', 'TIER3_PHRASES',
    'ADENAUFAL_T4', 'MIKA_PATTERNS',
    'find_tier1', 'find_tier2', 'find_tier3',
    'find_mika_patterns', 'find_adenaufal',
    # text_stats
    'tokenize_th', 'split_sentences_th', 'split_paragraphs', 'get_ngrams',
    # paragraph_metrics
    'em_dash_stats', 'staccato_check', 'sentence_variety', 'burstiness',
    'function_word_diversity', 'megumin_structural_check', 'paragraph_metrics',
    'FUNC_WORDS',
]
