"""
tools/qa/script_policy.py — Target-language script allowlist policy.

Replaces blacklist-per-model approach with universal policy:
  If target_lang=th → only Thai script + digits + punctuation + allowlist tokens pass.
  Everything else (Han, Hiragana, Katakana, Hangul, Latin, Cyrillic, Arabic...) = FAIL.

Usage:
    from qa.script_policy import detect_script_leaks, format_leak_report
    leaks = detect_script_leaks("สวัสดี Open Beta 你好", target_lang="th")
    # → [Latin: "Open", Latin: "Beta", Han: "你好"]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Unicode script ranges (abbreviated for speed)
_SCRIPTS: dict[str, list[tuple[int, int]]] = {
    "Thai":      [(0x0E00, 0x0E7F)],
    "Han":       [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)],
    "Hiragana":  [(0x3040, 0x309F)],
    "Katakana":  [(0x30A0, 0x30FF)],
    "Hangul":    [(0xAC00, 0xD7AF)],
    "Latin":     [(0x0041, 0x005A), (0x0061, 0x007A)],
    "Cyrillic":  [(0x0400, 0x04FF)],
    "Arabic":    [(0x0600, 0x06FF)],
}

# ── Policy ────────────────────────────────────────────────────────────

TARGET_SCRIPT_POLICY: dict[str, dict[str, Any]] = {
    "th": {
        "allowed_scripts": {"Thai"},
        "allowed_latin_tokens": {
            "HP", "MP", "EXP", "SP", "ATK", "DEF", "STR", "INT", "AGI",
            "DPS", "PvP", "PvE", "NPC", "PC", "UI", "API", "ID", "VIP",
            "SSS", "SSR", "UR", "LV", "LVL", "S", "SS", "LR", "CD",
            "DMG", "BUFF", "DEBUFF", "AOE", "TPS", "ELITE",
            "No.", "no.",
        },
        "hard_fail_scripts": {"Han", "Hiragana", "Katakana", "Hangul",
                              "Latin", "Cyrillic", "Arabic"},
    },
    "en": {
        "allowed_scripts": {"Latin"},
        "allowed_latin_tokens": set(),
        "hard_fail_scripts": {"Han", "Hiragana", "Katakana", "Hangul", "Thai",
                              "Cyrillic", "Arabic"},
    },
    "zh": {
        "allowed_scripts": {"Han"},
        "allowed_latin_tokens": set(),
        "hard_fail_scripts": {"Latin", "Hiragana", "Katakana", "Hangul",
                              "Thai", "Cyrillic", "Arabic"},
    },
}

# Digits, whitespace, punctuation: always allowed
_ALLOWED_CHAR_CATS = {
    "Nd",    # digit
    "Zs",    # space separator
    "Zl",    # line separator
    "Zp",    # paragraph separator
    "Po",    # other punctuation
    "Pd",    # dash/punctuation
    "Ps",    # open punctuation
    "Pe",    # close punctuation
    "Pi",    # initial quote
    "Pf",    # final quote
    "Sc",    # currency symbol
    "Sm",    # math symbol
    "So",    # other symbol — brackets like 【】「」『』
}


# ── Results ───────────────────────────────────────────────────────────

@dataclass
class ScriptLeak:
    """A single script leak found in text."""
    script: str
    token: str
    index: int
    context: str
    severity: str  # "error" | "warning"
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "script": self.script,
            "token": self.token,
            "index": self.index,
            "context": self.context,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


@dataclass
class ScriptLeakResult:
    """Result of script leak detection."""
    ok: bool = True
    leaks: list[ScriptLeak] = field(default_factory=list)
    foreign_script_counts: dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0


# ── Detection ─────────────────────────────────────────────────────────

def _classify_char(cp: int) -> str | None:
    """Return script name for a codepoint, or None if undetected."""
    for script, ranges in _SCRIPTS.items():
        for lo, hi in ranges:
            if lo <= cp <= hi:
                return script
    return None  # unknown/digits/punct


_ALLOWED_PATTERN = re.compile(r'^[\s\d\u0E00-\u0E7F\u0021-\u002F\u003A-\u0040'
                              r'\u005B-\u0060\u007B-\u007E\u3000-\u303F'
                              r'\uFF00-\uFFEF\u2010-\u205E'
                              r'\u0022\u0027'
                              r'\u300C\u300D\u300E\u300F'
                              r'\u3010\u3011\u3014\u3015'
                              r'\u2032\u2033]+$')


def is_pure_target(text: str, target_lang: str = "th") -> bool:
    """Quick check: is text purely allowed for target language?"""
    return _ALLOWED_PATTERN.match(text) is not None


def detect_script_leaks(
    paragraphs: list[str],
    target_lang: str = "th",
    allowed_latin_tokens: set[str] | None = None,
) -> ScriptLeakResult:
    """Detect all script leaks in paragraphs for target language.

    Returns structured leaks with script, token, position, severity.
    """
    policy = TARGET_SCRIPT_POLICY.get(target_lang, TARGET_SCRIPT_POLICY["th"])
    allowed_scripts = policy["allowed_scripts"]
    hard_fail_scripts = policy["hard_fail_scripts"]
    if allowed_latin_tokens is None:
        allowed_latin_tokens = policy["allowed_latin_tokens"]

    result = ScriptLeakResult()
    char_counts: dict[str, int] = {}

    for para_idx, para in enumerate(paragraphs):
        # Skip end markers
        if para in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue

        # === Latin token check (skip if Latin is allowed script) ===
        if "Latin" not in allowed_scripts:
            for m in re.finditer(r'\b([A-Za-z][A-Za-z0-9.]*)\b', para):
                token = m.group(1)
                upper = token.upper()
                # Strip trailing punctuation
                upper = upper.rstrip("!?;:,.)]}").lstrip("([{")
                if upper and upper not in allowed_latin_tokens:
                    context_start = max(0, m.start() - 10)
                    context_end = min(len(para), m.end() + 10)
                    leak = ScriptLeak(
                        script="Latin",
                        token=m.group(1),
                        index=m.start(),
                        context=f"...{para[context_start:context_end]}...",
                        severity="error",
                    )
                    result.leaks.append(leak)
                    char_counts["Latin"] = char_counts.get("Latin", 0) + 1
                    result.error_count += 1

        # === CJK character check ===
        # Skip Latin chars (handled at token level below)
        for i, ch in enumerate(para):
            cp = ord(ch)
            script = _classify_char(cp)
            if script is None or script == "Latin":  # Latin handled by token regex
                continue
            if script in allowed_scripts:
                continue  # Thai in th target = OK
            if script in hard_fail_scripts:
                char_counts[script] = char_counts.get(script, 0) + 1
                # Only report first occurrence per paragraph for brevity
                if not any(l.script == script and l.index == para_idx for l in result.leaks):
                    context_start = max(0, i - 5)
                    context_end = min(len(para), i + 5)
                    leak = ScriptLeak(
                        script=script,
                        token=ch,
                        index=para_idx,
                        context=f"...{para[context_start:context_end]}...",
                        severity="error",
                    )
                    result.leaks.append(leak)
                    result.error_count += 1

    result.foreign_script_counts = char_counts
    result.ok = result.error_count == 0
    return result


def format_leak_report(result: ScriptLeakResult) -> str:
    """Format leak results as human-readable text."""
    if result.ok:
        return "✅ Script purity: no leaks"

    lines = [f"⚠️  Script leaks: {result.error_count} errors, {result.warning_count} warnings"]
    scripts = ", ".join(f"{s}×{c}" for s, c in result.foreign_script_counts.items())
    if scripts:
        lines.append(f"   Scripts: {scripts}")
    for leak in result.leaks[:8]:
        lines.append(f"   [{leak.severity.upper()}] {leak.script}: \"{leak.token}\" "
                     f"@{leak.index} ({leak.context[:50]})")
    if len(result.leaks) > 8:
        lines.append(f"   ... and {len(result.leaks) - 8} more")
    return "\n".join(lines)
