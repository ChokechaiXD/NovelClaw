"""
LLM Router Validators — check output quality after each call.
"""

import json
import re
from typing import Any


class ValidationResult:
    """Result of output validation."""

    def __init__(self, ok: bool, reason: str = "", details: str = ""):
        self.ok = ok
        self.reason = reason
        self.details = details

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        if self.ok:
            return "ValidationResult(✅ PASS)"
        return f"ValidationResult(❌ {self.reason}: {self.details[:80]})"


# ── Translate profile validators ────────────────────────────────────────

def check_non_empty(text: str) -> ValidationResult:
    """Reject empty or whitespace-only output."""
    if not text or not text.strip():
        return ValidationResult(False, "empty_output", "Output is empty or whitespace-only")
    return ValidationResult(True)


def check_min_length(text: str, min_chars: int = 100) -> ValidationResult:
    """Reject suspiciously short output."""
    stripped = text.strip()
    if len(stripped) < min_chars:
        return ValidationResult(
            False, "too_short",
            f"Output has {len(stripped)} chars, minimum is {min_chars}"
        )
    return ValidationResult(True)


def check_no_llm_artifacts(text: str) -> ValidationResult:
    """Check for leftover LLM tags like </now_translate> or ```."""
    if "</now_translate>" in text or "<now_translate>" in text:
        return ValidationResult(False, "llm_artifact", "Contains </now_translate> or <now_translate>")
    # Check for markdown code blocks (LLM often wraps in ```)
    # But allow if it's genuinely markdown
    matches = re.findall(r"```", text)
    if len(matches) >= 2:
        return ValidationResult(False, "llm_artifact", "Contains ``` code blocks")
    return ValidationResult(True)


def check_has_real_content(text: str) -> ValidationResult:
    """Must have at least some Thai/natural language content beyond markers."""
    thai_chars = len(re.findall(r'[\u0e00-\u0e7f]', text))
    if thai_chars < 50:
        return ValidationResult(
            False, "no_thai_content",
            f"Only {thai_chars} Thai characters found (min 50)"
        )
    return ValidationResult(True)


def check_is_json(text: str) -> ValidationResult:
    """Check if text is valid JSON (for JSON-mode outputs)."""
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
        return ValidationResult(False, "too_few_paragraphs", f"Only {len(non_end)} non-end paragraphs")
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
    return ValidationResult(False, "missing_end_marker", f"Last paragraph is '{last[:30]}', not (จบบท)")


# ── Composite validators ─────────────────────────────────────────────────

def validate_translate_response(text: str) -> ValidationResult:
    """Full validate pipeline for a translate response."""
    checks = [
        check_non_empty(text),
        check_min_length(text, 100),
        check_no_llm_artifacts(text),
        check_has_real_content(text),
    ]
    for check in checks:
        if not check.ok:
            return check
    return ValidationResult(True)


def validate_chapter_json(data: dict) -> ValidationResult:
    """Validate parsed chapter JSON structure."""
    checks = [
        check_has_paragraphs(data),
        check_has_title(data),
        check_has_end_marker(data),
    ]
    for check in checks:
        if not check.ok:
            return check
    return ValidationResult(True)
