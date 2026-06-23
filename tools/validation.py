"""Shared chapter validation helpers for NovelClaw.

This module owns rules that are safe to share between the translation
pipeline, standalone leak checkers, and reader/admin validation paths.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from schema import BRACKETS, Chapter  # noqa: E402

LANGUAGE_ALIASES = {
    "zh": "cn",
    "cn": "cn",
    "ja": "jp",
    "jp": "jp",
    "ko": "kr",
    "kr": "kr",
    "en": "en",
    "th": "th",
}

SOURCE_ARTIFACT_RE = re.compile(
    r"(求订阅|求追读|三更|月票|推荐票|GZ\b)",
    re.IGNORECASE,
)
CJK_LEAK_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)
LOWER_LATIN_LEAK_RE = re.compile(
    r"\b(?:of|and|the|to|a|an|in|on|for|with|by|from|"
    r"lv|lvl|buff|debuff|first kill|militia|avatar|peek|panic|"
    r"level|recruiting|disrespect|mean|queen|erupt|continue|"
    r"blacklist|"
    r"momentarily|hollow)\b",
    re.IGNORECASE,
)
LATIN_LEAK_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9.]*\b")
# EN words retained from Chinese source text (CN novels often embed EN words
# like skill/item names). The LLM must translate these, not keep them.
EN_RETENTION_RE = re.compile(
    r"\b(?:recruiting|level|disrespect|mean|queen|erupt|continue|"
    r"panic|momentarily|hollow|militia|avatar|blacklist|peek)\b",
    re.IGNORECASE,
)
LATIN_REPLACEMENT_HINTS = {
    "of": "ของ",
    "Lv": "เลเวล",
    "LVL": "เลเวล",
    "BUFF": "บัฟ",
    "DEBUFF": "ดีบัฟ",
    "First Kill": "คิลแรก",
    "militia": "กองกำลังอาสาสมัคร",
    "avatar": "อวตาร",
    "blacklist": "บัญชีดำ",
    "recruiting": "รับสมัคร",
    "peek": "ชำเลืองมอง",
    "panic": "ตื่นตระหนก",
    "level": "ระดับ",
    "disrespect": "ดูหมิ่น",
    "mean": "หมายถึง",
    "queen": "ราชินี",
    "erupt": "ปะทุ",
    "continue": "กล่าวต่อ",
    "momentarily": "ชั่วขณะ",
    "hollow": "กลวง",
}
ALLOWED_LATIN_TOKENS = {
    "HP",
    "MP",
    "EXP",
    "SSS",
    "SSR",
    "UR",
    "SP",
    "ID",
    "VIP",
    "S",
    "SS",
    "LR",
    "CD",
    "NPC",
    "PVP",
    "PVE",
    "LV",
    "LVL",
    "ATK",
    "DEF",
    "DMG",
    "BUFF",
    "DEBUFF",
    "AOE",
    "DPS",
    "TPS",
    "ELITE",
    "BloodyLand",
    "Bloodyland",
    "C",
}

# EN blacklist — game terms that should be translated
EN_BLACKLIST: set[str] = {
    "recruiting", "level", "disrespect", "mean", "queen",
    "erupt", "continue", "panic", "momentarily", "hollow",
    "militia", "avatar", "blacklist", "peek",
    "first", "kill", "recruit", "loot", "skill", "quest", "boss",
    "dungeon", "party", "guild", "raid", "tank", "healer",
    "damage", "defense", "attack", "speed",
    "inventory", "equip", "item", "craft",
    "summon", "portal", "shield", "weapon", "armor",
    "pet", "mount", "crystal", "stone", "potion",
    "common", "uncommon", "rare", "epic", "legendary",
    "hybrid", "ancient", "elite", "melee", "ranged",
    "plants", "zombies",
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


def check_en_terms(text: str) -> tuple[list[str], list[str], list[str]]:
    """Check for EN game terms. Returns (whitelisted, blacklisted, unknown)."""
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9]{1,}\b", text)
    whitelisted: list[str] = []
    blacklisted: list[str] = []
    unknown: list[str] = []
    for word in words:
        upper = word.upper()
        if upper in ALLOWED_LATIN_TOKENS:
            whitelisted.append(word)
        elif upper == "GZ":
            blacklisted.append(word)
        elif word.isupper() and len(word) >= 2:
            unknown.append(word)
    return whitelisted, blacklisted, unknown


def _issue(
    block: int, btype: str, severity: str, kind: str, detail: str, text: str
) -> dict[str, Any]:
    return {
        "block": block,
        "type": btype,
        "severity": severity,
        "kind": kind,
        "detail": detail,
        "text": text[:80],
    }


def check_file_for_cjk_leaks(filepath: str | Path) -> list[dict[str, Any]]:
    """Check a single chapter JSON file for CJK/source-artifact/EN leaks.
    Uses v3 paragraphs format.
    """
    issues: list[dict[str, Any]] = []
    with Path(filepath).open(encoding="utf-8") as file_obj:
        data = json.load(file_obj)

    paragraphs = data.get("paragraphs", [])
    for i, para in enumerate(paragraphs):
        if para in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        text = para
        cn_matches = re.findall(r"[一-鿿㐀-䶿豈-﫿]", text)
        if cn_matches:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "CN", f"CN chars: {''.join(cn_matches[:5])}", text))
        jp_matches = re.findall(r"[぀-ゟ゠-ヿ]", text)
        if jp_matches:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "JP", f"JP chars: {''.join(jp_matches[:5])}", text))
        ko_matches = re.findall(r"[가-힯ᄀ-ᇿ]", text)
        if ko_matches:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "KO", f"KO chars: {''.join(ko_matches[:5])}", text))
        for pattern in (r"求订阅", r"求追读", r"三更", r"月票", r"推荐票", r"GZ", r"^\s*GZ\s*$"):
            if re.search(pattern, text):
                issues.append(_issue(i + 1, "paragraph", "FAIL", "ARTIFACT", f"Source artifact: {pattern}", text))
        _, blacklisted, unknown = check_en_terms(text)
        for word in blacklisted:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "EN_BLACKLIST", f"Blacklisted EN: {word}", text))
        for word in unknown:
            issues.append(_issue(i + 1, "paragraph", "WARN", "EN_UNKNOWN", f"Unknown EN term: {word}", text))
    return issues
