"""slop_detector.py — Backward-compatible shim.

The original 858-LOC file has been split into 4 modules under `slop/`:
  - slop.anti_ai           — tier lists + matchers
  - slop.text_stats        — tokenize + n-grams
  - slop.paragraph_metrics — em_dash / staccato / variety / burstiness / etc.
  - slop.scan              — scan_chapter + report + CLI

This shim keeps the public API stable so callers using:
  - `from slop_detector import find_tier1, em_dash_stats, scan_chapter, ...`
  - `python tools/slop_detector.py --chapter 80`
  - `subprocess.call([..., 'tools/slop_detector.py', ...])`
all keep working without change.

CLI is delegated to `slop.scan.main`.
"""
import sys
from pathlib import Path

# Make sure tools/ is on sys.path (for `from constants import NOVEL_ROOT`)
sys.path.insert(0, str(Path(__file__).parent))

# Re-export everything from the slop package
from slop import (  # noqa: F401  (re-exports)
    TIER1, TIER1_VARIANTS, TIER2, TIER3_PHRASES,
    ADENAUFAL_T4, MIKA_PATTERNS,
    find_tier1, find_tier2, find_tier3,
    find_mika_patterns, find_adenaufal,
    tokenize_th, split_sentences_th, split_paragraphs, get_ngrams,
    em_dash_stats, staccato_check, sentence_variety, burstiness,
    function_word_diversity, megumin_structural_check, paragraph_metrics,
    FUNC_WORDS,
)
from slop.scan import scan_chapter, scan_chapters, print_report  # noqa: F401

# Alias for old name (some callers may use split_paragraphs_from_slop)
from slop.text_stats import split_paragraphs as split_paragraphs  # noqa: F811

__all__ = [
    'TIER1', 'TIER1_VARIANTS', 'TIER2', 'TIER3_PHRASES',
    'ADENAUFAL_T4', 'MIKA_PATTERNS',
    'find_tier1', 'find_tier2', 'find_tier3',
    'find_mika_patterns', 'find_adenaufal',
    'tokenize_th', 'split_sentences_th', 'split_paragraphs', 'get_ngrams',
    'em_dash_stats', 'staccato_check', 'sentence_variety', 'burstiness',
    'function_word_diversity', 'megumin_structural_check', 'paragraph_metrics',
    'FUNC_WORDS',
    'scan_chapter', 'scan_chapters', 'print_report',
]


if __name__ == '__main__':
    # Delegate to slop.scan.main so `python tools/slop_detector.py`
    # behaves identically to before.
    from slop.scan import main
    sys.exit(main())
