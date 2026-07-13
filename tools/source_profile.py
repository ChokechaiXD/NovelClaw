"""Source profiling for quality-first translation.

The profile is deterministic metadata about the source chapter. It keeps
language detection, structure counting, and marker inventory outside the LLM so
the translator prompt can stay focused on translation quality.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LANG_ALIASES = {
    "zh": "cn",
    "zh-cn": "cn",
    "chinese": "cn",
    "cn": "cn",
    "ja": "jp",
    "jp": "jp",
    "japanese": "jp",
    "ko": "kr",
    "kr": "kr",
    "korean": "kr",
    "en": "en",
    "english": "en",
    "en-us": "en",
    "th": "th",
    "thai": "th",
}

AUTO_LANG_VALUES = {"", "auto", "detect", "unknown", "?"}

SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "Thai": ((0x0E00, 0x0E7F),),
    "Han": ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)),
    "Hiragana": ((0x3040, 0x309F),),
    "Katakana": ((0x30A0, 0x30FF),),
    "Hangul": ((0xAC00, 0xD7AF),),
    "Latin": ((0x0041, 0x005A), (0x0061, 0x007A)),
    "Cyrillic": ((0x0400, 0x04FF),),
    "Arabic": ((0x0600, 0x06FF),),
}

DIALOGUE_RE = re.compile(r'["\u201c\u201d\u300c\u300d]')
SYSTEM_MARKER_RE = re.compile(r"(?:\u3010[^\u3011]{1,160}\u3011|\[[^\]\n]{1,160}\])")
FRONTMATTER_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---\s*", re.DOTALL)
SPECIAL_SYMBOLS = set("【】「」『』《》[]()（）<>“”\"'—…•·☆★※→←↑↓")


def normalize_lang(lang: str | None) -> str:
    """Normalize user/config language names into NovelClaw language codes."""
    value = str(lang or "").strip().lower()
    return LANG_ALIASES.get(value, value)


def _script_for_char(ch: str) -> str | None:
    cp = ord(ch)
    for script, ranges in SCRIPT_RANGES.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return script
    return None


def script_mix(text: str) -> dict[str, int]:
    """Count known Unicode scripts in text."""
    counts: dict[str, int] = {}
    for ch in text:
        script = _script_for_char(ch)
        if script:
            counts[script] = counts.get(script, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _detect_source_lang_from_mix(counts: Mapping[str, int]) -> str:
    """Detect a source language from an already-counted script mix."""
    han = counts.get("Han", 0)
    kana = counts.get("Hiragana", 0) + counts.get("Katakana", 0)
    hangul = counts.get("Hangul", 0)
    latin = counts.get("Latin", 0)
    thai = counts.get("Thai", 0)

    if hangul and hangul >= max(han, kana, latin, thai):
        return "kr"
    if kana:
        return "jp"
    if han:
        return "cn"
    if latin >= max(20, thai):
        return "en"
    if thai:
        return "th"
    return "cn"


def detect_source_lang(text: str, *, script_counts: Mapping[str, int] | None = None) -> str:
    """Detect dominant source language from Unicode script mix.

    ``script_counts`` lets callers that also build a source profile reuse one
    Unicode scan. Omitting it preserves the original public behavior.
    """
    return _detect_source_lang_from_mix(script_counts if script_counts is not None else script_mix(text))


def _read_novel_meta_lang(slug: str) -> str:
    try:
        data = json.loads((PROJECT_ROOT / "novels" / slug / "novel.json").read_text(encoding="utf-8"))
    except Exception:
        return ""
    return normalize_lang(data.get("sourceLang") or data.get("source_lang"))


def _read_frontmatter_lang(raw_text: str) -> str:
    match = FRONTMATTER_RE.match(raw_text or "")
    if not match:
        return ""
    for line in match.group("body").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in {"source_lang", "sourceLang", "lang"}:
            return normalize_lang(value.strip().strip('"\''))
    return ""


def resolve_source_lang(
    raw_text: str,
    requested_lang: str | None = None,
    slug: str = "global-descent",
    *,
    script_counts: Mapping[str, int] | None = None,
) -> tuple[str, str]:
    """Resolve source language without silently assuming Chinese.

    Priority: explicit CLI/API value -> source frontmatter -> novel metadata ->
    Unicode auto-detect. The caller receives both the language and the source of
    that decision for saved metadata and debugging.
    """
    requested = normalize_lang(requested_lang)
    if requested not in AUTO_LANG_VALUES:
        return requested, "requested"

    frontmatter = _read_frontmatter_lang(raw_text)
    if frontmatter and frontmatter not in AUTO_LANG_VALUES:
        return frontmatter, "frontmatter"

    meta = _read_novel_meta_lang(slug)
    if meta and meta not in AUTO_LANG_VALUES:
        return meta, "novel_meta"

    return detect_source_lang(raw_text, script_counts=script_counts), "auto_detect"


def split_source_paragraphs(text: str) -> list[str]:
    """Split source into source-anchored logical paragraphs."""
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []
    blocks = [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
    if len(blocks) > 1:
        expanded: list[str] = []
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            expanded.extend(lines if len(lines) > 1 else [block])
        return expanded
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def _special_symbol_inventory(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ch in text:
        if ch in SPECIAL_SYMBOLS or unicodedata.category(ch).startswith("S"):
            counts[ch] = counts.get(ch, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:24])


def build_source_profile(
    source_text: str,
    source_lang: str,
    target_lang: str = "th",
    ch_num: int | None = None,
    lang_source: str = "",
    *,
    script_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Build the structure contract used by prompt, gate, and saved metadata."""
    paragraphs = split_source_paragraphs(source_text)
    text = source_text or ""
    counts = dict(script_counts) if script_counts is not None else script_mix(text)
    dialogue_count = sum(1 for para in paragraphs if DIALOGUE_RE.search(para))
    system_marker_count = len(SYSTEM_MARKER_RE.findall(text))
    return {
        "chapterNo": ch_num,
        "sourceLang": normalize_lang(source_lang) or _detect_source_lang_from_mix(counts),
        "targetLang": normalize_lang(target_lang) or "th",
        "sourceLangSource": lang_source or "unknown",
        "charCount": len(text),
        "paragraphCount": len(paragraphs),
        "dialogueCount": dialogue_count,
        "systemMarkerCount": system_marker_count,
        "sourceScriptMix": counts,
        "specialSymbolInventory": _special_symbol_inventory(text),
        "lengthTarget": {"minRatio": 0.85, "idealMinRatio": 1.0, "maxRatio": 3.5},
    }


def summarize_structure_contract(profile: dict[str, Any] | None) -> str:
    """Human-readable prompt section for source-anchored translation."""
    if not profile:
        return ""
    symbols = profile.get("specialSymbolInventory") or {}
    symbol_text = ", ".join(f"{k}x{v}" for k, v in list(symbols.items())[:10]) or "none"
    mix = profile.get("sourceScriptMix") or {}
    mix_text = ", ".join(f"{k}:{v}" for k, v in mix.items()) or "unknown"
    target = profile.get("lengthTarget") or {}
    min_ratio = target.get("minRatio", 0.85)
    max_ratio = target.get("maxRatio", 3.5)
    return "\n".join(
        [
            "<structure_contract>",
            f"- Source language: {profile.get('sourceLang', 'auto')} ({profile.get('sourceLangSource', 'unknown')}).",
            f"- Source characters: {profile.get('charCount', 0)}.",
            f"- Source paragraphs: {profile.get('paragraphCount', 0)}. Stay close to this rhythm without forcing exact one-to-one paragraph count.",
            f"- Source dialogue paragraphs: {profile.get('dialogueCount', 0)}. Standalone source dialogue must remain visible as dialogue.",
            f"- Source system markers: {profile.get('systemMarkerCount', 0)}. Keep system/UI messages standalone.",
            f"- Source script mix: {mix_text}.",
            f"- Structural symbols seen: {symbol_text}. Preserve symbols when they are dialogue/system/game markers.",
            f"- Length target: output body should be >= {min_ratio:.0%} and <= {max_ratio:.1f}x source characters.",
            "</structure_contract>",
        ]
    )
