"""
tools/qa/deterministic.py — Pre-LLM deterministic checks.

These checks run BEFORE the LLM call to validate input quality,
and AFTER the LLM call to validate output structure.
No LLM calls — pure deterministic logic.
"""

from __future__ import annotations

import json
import re


class ValidationResult:
    """Result of a deterministic check."""
    def __init__(self, ok: bool, reason: str = "", details: str = ""):
        self.ok = ok
        self.reason = reason
        self.details = details

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        return f"ValidationResult(✅ PASS)" if self.ok else f"ValidationResult(❌ {self.reason})"


def check_non_empty(text: str) -> ValidationResult:
    """Reject empty or whitespace-only output."""
    if not text or not text.strip():
        return ValidationResult(False, "empty_output", "Output is empty or whitespace-only")
    return ValidationResult(True)


def check_min_length(text: str, min_chars: int = 100) -> ValidationResult:
    """Reject suspiciously short output."""
    stripped = text.strip()
    if len(stripped) < min_chars:
        return ValidationResult(False, "too_short",
                                f"Output has {len(stripped)} chars, minimum is {min_chars}")
    return ValidationResult(True)


def check_no_llm_artifacts(text: str) -> ValidationResult:
    """Check for leftover LLM tags."""
    if "</now_translate>" in text or "<now_translate>" in text:
        return ValidationResult(False, "llm_artifact", "Contains </now_translate> or <now_translate>")
    matches = re.findall(r"```", text)
    if len(matches) >= 2:
        return ValidationResult(False, "llm_artifact", "Contains ``` code blocks")
    return ValidationResult(True)


def check_has_real_content(text: str) -> ValidationResult:
    """Must have at least some Thai/natural language content."""
    thai_chars = len(re.findall(r'[\u0e00-\u0e7f]', text))
    if thai_chars < 50:
        return ValidationResult(False, "no_thai_content",
                                f"Only {thai_chars} Thai characters found (min 50)")
    return ValidationResult(True)


def check_is_json(text: str) -> ValidationResult:
    """Check if text is valid JSON."""
    try:
        json.loads(text)
        return ValidationResult(True)
    except json.JSONDecodeError as e:
        return ValidationResult(False, "invalid_json", str(e))


def check_has_paragraphs(data: dict) -> ValidationResult:
    """Check parsed chapter JSON has non-empty paragraphs."""
    paragraphs = data.get("paragraphs", [])
    if not paragraphs:
        return ValidationResult(False, "no_paragraphs", "No paragraphs in output")
    non_end = [p for p in paragraphs if p.strip() not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if len(non_end) < 3:
        return ValidationResult(False, "too_few_paragraphs",
                                f"Only {len(non_end)} non-end paragraphs")
    return ValidationResult(True)


def check_has_title(data: dict) -> ValidationResult:
    """Check chapter has title."""
    title = data.get("title", {})
    if isinstance(title, dict):
        if title.get("translated") or title.get("source"):
            return ValidationResult(True)
    elif isinstance(title, str) and title.strip():
        return ValidationResult(True)
    return ValidationResult(False, "no_title", "Chapter has no title")


def check_has_end_marker(data: dict) -> ValidationResult:
    """Check chapter ends with a known end marker."""
    paragraphs = data.get("paragraphs", [])
    if not paragraphs:
        return ValidationResult(False, "no_end_marker", "No paragraphs to check")
    last = paragraphs[-1].strip()
    if last in ("(จบบท)", "(End)", "（終）", "(끝)"):
        return ValidationResult(True)
    return ValidationResult(False, "missing_end_marker",
                            f"Last paragraph is '{last[:30]}', not (จบบท)")


def validate_translate_response(text: str) -> ValidationResult:
    """Full validate pipeline for a translate response."""
    for check in [check_non_empty, check_min_length, check_no_llm_artifacts, check_has_real_content]:
        r = check(text)
        if not r.ok:
            return r
    return ValidationResult(True)


def validate_chapter_json(data: dict) -> ValidationResult:
    """Validate parsed chapter JSON structure."""
    for check in [check_has_paragraphs, check_has_title, check_has_end_marker]:
        r = check(data)
        if not r.ok:
            return r
    return ValidationResult(True)
