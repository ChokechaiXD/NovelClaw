"""
tools/qa/validators.py — Canonical regex patterns and validator functions.

SSOT for all CJK/EN/Source-artifact detection regexes and shared validation logic.
All other modules import from here — no duplicate regex files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ── Re-export script policy ──────────────────────────────────────────

from qa.script_policy import (  # noqa: E402
    detect_script_leaks,
    ScriptLeak,
    ScriptLeakResult,
    format_leak_report,
    TARGET_SCRIPT_POLICY,
)


# ═══════════════════════════════════════════════════════════════════════
# SHARED REGEX PATTERNS (SSOT — import from here ONLY)
# ═══════════════════════════════════════════════════════════════════════

# CJK detection — covers Chinese, Japanese, Korean
CJK_LEAK_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)

# CJK punctuation detection — covers full-width Chinese quotation marks and punctuation
CJK_PUNCT_RE = re.compile(r"[「」《》，。！？」：；、]")

# Chinese-only detection (for source language validation)
CN_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
CN_WIDE_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
CN_INLINE_RE = re.compile(r"[\u4e00-\u9fff]{2,}")

# Source artifact patterns (donation requests, reader engagement prompts)
SOURCE_ARTIFACT_RE = re.compile(
    r"(求订阅|求追读|三更|月票|推荐票|GZ\b)",
    re.IGNORECASE,
)

# English token detection
LATIN_LEAK_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9.]*\b")
LOWER_LATIN_LEAK_RE = re.compile(
    r"\b(?:of|and|the|to|a|an|in|on|for|with|by|from|"
    r"lv|lvl|buff|debuff|first kill|militia|avatar|peek|panic|"
    r"level|recruiting|disrespect|mean|queen|erupt|continue|"
    r"blacklist|"
    r"momentarily|hollow)\b",
    re.IGNORECASE,
)

# EN words retained from Chinese source text
EN_RETENTION_RE = re.compile(
    r"\b(?:recruiting|level|disrespect|mean|queen|erupt|continue|"
    r"panic|momentarily|hollow|militia|avatar|blacklist|peek)\b",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════
# LATIN TOKEN ALLOW/REPLACE LISTS [DEPRECATED — RETAINED FOR BACKWARD COMPAT]
# ═══════════════════════════════════════════════════════════════════════
#
# These lists are DEPRECATED. Term decisions should be made via
# tools/config/term_policy.{lang}.yaml + tools/qa/term_policy.py
#
# All new code should import from term_policy:
#   from qa.term_policy import get_term_policy
#   tp = get_term_policy("th")
#   allowed = tp.preserve_tokens
#
# Keep minimal set here for backward compat with scorer.py / scripts
# that haven't migrated yet. ELITE removed.
# ═══════════════════════════════════════════════════════════════════════

# Dynamically synced from term_policy on module import
try:
    from qa.term_policy import get_term_policy
    _tp = get_term_policy("th")
    ALLOWED_LATIN_TOKENS: set[str] = _tp.preserve_tokens | {k.upper() for k in _tp.terms.keys()}
except Exception:
    # Fallback minimal set if term_policy unavailable
    ALLOWED_LATIN_TOKENS: set[str] = {
        "HP", "MP", "EXP", "SP", "ATK", "DEF", "STR", "INT", "AGI", "DPS",
        "DMG", "CD", "TPS", "PvP", "PvE", "AOE",
        "SSR", "SS", "SR", "UR", "LR", "VIP", "SSS",
        "NPC",
    }

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
    # Game terms that should be Thai
    "open", "beta",  # "Open Beta" → "โอเพนเบตา"
    "invite", "daily", "login", "reward",
}

LATIN_REPLACEMENT_HINTS: dict[str, str] = {
    "of": "ของ",
    "Lv": "เลเวล", "LVL": "เลเวล",
    "BUFF": "บัฟ", "DEBUFF": "ดีบัฟ",
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
    "Open Beta": "โอเพนเบตา",
    "open beta": "โอเพนเบตา",
}


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _latin_token_hint(token: str) -> str | None:
    """Get a Thai replacement hint for an English token."""
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


def _issue(block: int, btype: str, severity: str, kind: str,
            detail: str, text: str) -> dict[str, Any]:
    return {
        "block": block, "type": btype, "severity": severity,
        "kind": kind, "detail": detail, "text": text[:80],
    }


def check_file_for_cjk_leaks(filepath: str | Path) -> list[dict[str, Any]]:
    """Check a single chapter JSON file for CJK/source-artifact/EN leaks."""
    issues: list[dict[str, Any]] = []
    with Path(filepath).open(encoding="utf-8") as f:
        data = json.load(f)

    paragraphs = data.get("paragraphs", [])
    for i, para in enumerate(paragraphs):
        if para in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        text = para
        cn_matches = re.findall(r"[一-鿿㐀-䶿豈-﫿]", text)
        if cn_matches:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "CN",
                                 f"CN chars: {''.join(cn_matches[:5])}", text))
        jp_matches = re.findall(r"[぀-ゟ゠-ヿ]", text)
        if jp_matches:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "JP",
                                 f"JP chars: {''.join(jp_matches[:5])}", text))
        ko_matches = re.findall(r"[가-힯ᄀ-ᇿ]", text)
        if ko_matches:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "KO",
                                 f"KO chars: {''.join(ko_matches[:5])}", text))
        for pattern in (r"求订阅", r"求追读", r"三更", r"月票", r"推荐票", r"GZ\b", r"^\s*GZ\s*$"):
            if re.search(pattern, text):
                issues.append(_issue(i + 1, "paragraph", "FAIL", "ARTIFACT",
                                     f"Source artifact: {pattern}", text))
        _, blacklisted, unknown = check_en_terms(text)
        for word in blacklisted:
            issues.append(_issue(i + 1, "paragraph", "FAIL", "EN_BLACKLIST",
                                 f"Blacklisted EN: {word}", text))
        for word in unknown:
            issues.append(_issue(i + 1, "paragraph", "WARN", "EN_UNKNOWN",
                                 f"Unknown EN term: {word}", text))
    return issues
