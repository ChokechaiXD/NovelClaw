"""Glossary post-processing station for translated paragraphs."""

from __future__ import annotations

END_MARKERS = {"(จบบท)", "(End)", "（終）", "(끝)"}


def apply_glossary_post(
    paragraphs: list[str], target_lang: str = "th"
) -> list[str]:
    """Apply term_policy replacements to translated paragraph strings."""
    try:
        from qa.term_policy import get_term_policy

        tp = get_term_policy(target_lang)
        result = []
        for para in paragraphs:
            if para in END_MARKERS:
                result.append(para)
                continue
            applied = tp.apply_to_text(para)
            result.append(applied.text)
        return result
    except ImportError:
        return paragraphs
