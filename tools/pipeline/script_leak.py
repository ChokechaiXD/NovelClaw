"""script_leak — Script leak detection and auto-correction (Station 6.6)."""
from __future__ import annotations
from typing import Any

from pipeline._shared import get_logger, call_llm


def _repair_script_leaks(
    paragraph_strings: list[str],
    target_lang: str,
    attempt_model: str | None = None,
    attempt_provider: str | None = None,
) -> list[str]:
    """Fix script leaks by re-translating only leaky paragraphs.

    Returns the fixed paragraph list (unchanged if no leaks found).
    """
    from qa.script_policy import detect_script_leaks

    result = detect_script_leaks(paragraph_strings, target_lang=target_lang)
    if result.ok:
        return paragraph_strings  # nothing to fix

    # Group leaks by paragraph index
    para_errors: dict[int, set[str]] = {}
    for leak in result.leaks:
        if leak.paragraph_index not in para_errors:
            para_errors[leak.paragraph_index] = set()
        para_errors[leak.paragraph_index].add(leak.script)

    # Fix only paragraphs with leaks
    fixed = list(paragraph_strings)
    leaked_indices = sorted(para_errors.keys())
    for pi in leaked_indices:
        if pi >= len(fixed) or fixed[pi] in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        scripts_desc = ", ".join(sorted(para_errors[pi]))
        old_text = fixed[pi]
        # Skip very short paragraphs where auto-repair is wasteful
        if len(old_text) < 15:
            continue
        system_prompt = (
            f"You are a literary translator. Fix ONLY the {scripts_desc} script "
            f"leaks in the following {target_lang} text. Replace foreign-script "
            f"words with natural {target_lang} equivalents. "
            f"Return ONLY the fixed text, nothing else."
        )
        try:
            resp, _, _ = call_llm(
                prompt=f"Fix script leaks in this paragraph:\n\n{old_text}",
                system=system_prompt,
                model=attempt_model,
                provider=attempt_provider,
                temperature=0.1,
                max_tokens=500,
            )
            candidate = resp.strip()
            # Ensure the repair didn't trash the paragraph
            if len(candidate) >= len(old_text) * 0.5 and len(candidate) <= len(old_text) * 3:
                fixed[pi] = candidate
        except Exception:
            pass  # fall through to original text
    return fixed

