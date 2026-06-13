"""text_stats.py — Tokenization + n-gram analysis.

Pure data shaping, no slop judgments. Used by `slop.scan` for n-gram
detection across chapters.
"""
import re
from collections import Counter


# ── Tokenization helpers ────────────────────────────────────────────

def tokenize_th(text: str) -> list[str]:
    """Tokenize Thai text into word-ish units for n-gram analysis.

    Strips:
      - Zero-width chars (U+200B-U+200F, U+FEFF)
      - Markdown sigils (#*_~`>|)
      - Newlines → space
      - Non-Thai/non-word/punctuation (except .?!) → space

    Returns tokens longer than 1 char.
    """
    text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)
    text = re.sub(r'[#*_~`>|]+', ' ', text)
    text = re.sub(r'[\n\r]+', ' ', text)
    text = re.sub(r'[^\u0e00-\u0e7f\w\s\.?!]', ' ', text)
    return [t for t in re.split(r'\s+', text) if len(t) > 1]


def split_sentences_th(text: str) -> list[str]:
    """Split Thai text into sentences (TH punctuation boundaries).

    Strips 【】 system messages first (don't split on those).
    Returns sentences longer than 5 chars.
    """
    text = re.sub(r'【[^】]*】', ' ', text)
    sentences = re.split(r'[.!?。!?]+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def split_paragraphs(text: str) -> list[str]:
    """Split into paragraphs (double-newline)."""
    return [p.strip() for p in text.split('\n\n') if p.strip()]


# ── N-gram analysis ────────────────────────────────────────────────

def get_ngrams(tokens: list[str], n_min: int = 3, n_max: int = 7) -> Counter:
    """Return Counter of n-grams (n_min..n_max word sequences).

    Filters: keep only n-grams that contain Thai chars OR ≥2 word tokens.
    The word-count filter prevents 3-char CJK+punct triples from being
    flagged (too noisy).
    """
    ngrams = Counter()
    for n in range(n_min, n_max + 1):
        for i in range(len(tokens) - n + 1):
            ng = ' '.join(tokens[i:i + n])
            if re.search(r'[ก-๙]', ng) or len(re.findall(r'\w+', ng)) >= 2:
                ngrams[ng] += 1
    return ngrams
