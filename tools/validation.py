"""
tools/validation.py — Shared chapter validation helpers. [THIN WRAPPER]

Canonical regex patterns and validator functions live in tools/qa/.
This module re-exports for backward compatibility.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from schema import BRACKETS, Chapter  # noqa: E402

# Import canonical definitions from tools/qa/validators.py
# (this is a thin re-export — SSOT is in tools/qa/)
from qa.validators import (  # noqa: E402, F401
    CJK_LEAK_RE,
    LATIN_LEAK_RE,
    LOWER_LATIN_LEAK_RE,
    SOURCE_ARTIFACT_RE,
    EN_RETENTION_RE,
    ALLOWED_LATIN_TOKENS,
    EN_BLACKLIST,
    LATIN_REPLACEMENT_HINTS,
    _latin_token_hint,
    check_en_terms,
    check_file_for_cjk_leaks,
)

# Language aliases
LANGUAGE_ALIASES = {
    "zh": "cn", "cn": "cn", "ja": "jp", "jp": "jp",
    "ko": "kr", "kr": "kr", "en": "en", "th": "th",
}
COMPLETENESS_MIN_RATIO = 0.90
COMPLETENESS_MAX_RATIO = 3.20


def normalize_language_key(lang: str | None, default: str = "cn") -> str:
    """Normalize CLI/data language keys to bracket profile keys."""
    if not lang:
        return default
    normalized = str(lang).strip().lower()
    return LANGUAGE_ALIASES.get(normalized, normalized or default)


def get_profile_lang(source_lang: str, target_lang: str, profile_lang: str | None = None) -> str:
    """Return the active output/profile language for validation and rendering."""
    if profile_lang:
        return normalize_language_key(profile_lang, target_lang)
    source = normalize_language_key(source_lang, "cn")
    target = normalize_language_key(target_lang, "th")
    if target in BRACKETS:
        return target
    if source in BRACKETS:
        return source
    return "cn"


def get_bracket_profile(
    source_lang: str, target_lang: str, profile_lang: str | None = None
) -> dict[str, str]:
    """Return the active bracket profile from config/brackets.json."""
    profile = get_profile_lang(source_lang, target_lang, profile_lang)
    return BRACKETS.get(profile, BRACKETS["cn"])


def _latin_token_hint(token: str) -> str | None:
    normalized = token.rstrip("!?;:,)]}").lstrip("([{")
    if normalized in LATIN_REPLACEMENT_HINTS:
        return LATIN_REPLACEMENT_HINTS[normalized]
    lower = normalized.lower()
    if lower in LATIN_REPLACEMENT_HINTS:
        return LATIN_REPLACEMENT_HINTS[lower]
    for phrase, thai in LATIN_REPLACEMENT_HINTS.items():
        if phrase.lower() in token.lower():
            return thai
    return None


def validate_translation_quality(
    ch: Chapter,
    source_text: str,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> tuple[bool, list[str]]:
    """Validate translation quality before saving a chapter.

    Returns:
        (is_ok, messages) where fatal messages are prefixed with ERROR.
    """
    messages: list[str] = []
    # Handle both paragraphs and blocks format
    if ch.paragraphs:
        target_text = "".join(p for p in ch.paragraphs if p != "(จบบท)")
    else:
        target_text = "".join(str(block.text) for block in ch.blocks) if ch.blocks else ""
    source_len = max(1, len(source_text))
    ratio = len(target_text) / source_len
    if ratio < COMPLETENESS_MIN_RATIO:
        messages.append(
            f"ERROR ch{ch.num}: incomplete translation length ratio {ratio:.2f} "
            f"below {COMPLETENESS_MIN_RATIO:.2f} ({len(target_text)}/{source_len} chars)"
        )
    elif ratio > COMPLETENESS_MAX_RATIO:
        messages.append(
            f"ERROR ch{ch.num}: suspiciously long translation length ratio {ratio:.2f} "
            f"above {COMPLETENESS_MAX_RATIO:.2f} ({len(target_text)}/{source_len} chars)"
        )

    output_lang_value = getattr(ch, "output_lang", None)
    if output_lang_value is not None:
        output_lang_value = getattr(output_lang_value, "value", output_lang_value)
    active_profile = profile_lang or output_lang_value or target_lang
    active_profile_key = get_profile_lang(source_lang, active_profile, profile_lang)
    bracket_profile = get_bracket_profile(source_lang, active_profile, profile_lang)

    if ch.paragraphs:
        # Paragraphs mode — check each paragraph directly (no block types)
        for i, para in enumerate(ch.paragraphs):
            if para == "(จบบท)":
                continue
            text = para
            cjk = CJK_LEAK_RE.findall(text)
            if cjk:
                messages.append(f"ERROR paragraph {i}: CJK leak chars {cjk[:8]}")
            if SOURCE_ARTIFACT_RE.search(text):
                messages.append(f"ERROR paragraph {i}: source artifact leaked into translation")
            for match in LATIN_LEAK_RE.finditer(text):
                token = match.group(0)
                if token in ALLOWED_LATIN_TOKENS:
                    continue
                hint = _latin_token_hint(token)
                if hint:
                    messages.append(f'ERROR paragraph {i}: Latin leak "{token}" -> {hint}')
                else:
                    messages.append(
                        f'WARNING paragraph {i}: Latin token "{token}" is not in allowed list'
                    )
            for match in LOWER_LATIN_LEAK_RE.finditer(text):
                token = match.group(0)
                hint = _latin_token_hint(token) or "review/translate this token"
                messages.append(
                    f'ERROR paragraph {i}: lowercase/mixed Latin leak "{token}" -> {hint}'
                )
        # Check end marker - last paragraph must be expected end marker
        expected_marker = bracket_profile.get("end_marker", "(จบบท)")
        if ch.paragraphs[-1] != expected_marker:
            messages.append(
                f'ERROR ch{ch.num}: last paragraph must be end marker "{expected_marker}"'
            )
    # (blocks mode removed in v3 — all chapters use paragraphs)

    return not any(message.startswith("ERROR") for message in messages), messages


def expected_end_marker(output_lang: str) -> str:
    """Read end marker from brackets.json. Falls back to (จบบท)."""
    try:
        _br = Path(__file__).resolve().parent.parent / "reader" / "config" / "brackets.json"
        _data = json.loads(_br.read_text(encoding="utf-8"))
        profile = _data.get(output_lang, {})
        return profile.get("end_marker", "(จบบท)")
    except Exception:
        return "(จบบท)"
