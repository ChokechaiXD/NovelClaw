#!/usr/bin/env python3
"""
prompt_builder.py — Universal translation prompt engine (v4).

Generates language-pair-specific prompts for novel translation.
Replaces PROMPT.md hardcode with a structured builder.

Usage:
    from prompt_builder import build_prompt
    prompt = build_prompt(source_lang="cn", target_lang="th",
                          source_text="...", ch_num=1)

Architecture:
    - build_prompt() → single call for everything
    - _lang_rules() → language-specific directives (leak, honorifics, tone)
    - _latin_policy() → game token allowlist (HP, MP, XP…) per target
    - _format_rules() → bracket mapping per source language
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ── Source language config ─────────────────────────────────────────────
# Each entry: bracket mapping + script rules + example for prompt

LANG_CONFIG: dict[str, dict[str, Any]] = {
    "cn": {
        "name": "Chinese",
        "dialogue_open": "「",
        "dialogue_close": "」",
        "system_open": "【",
        "system_close": "】",
        "thought_open": "『",
        "thought_close": "』",
        "game_open": "《",
        "game_close": "》",
        "title_regex": r"第\s*(\d+)\s*章\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
        "forbidden_scripts": ["Han"],
        "example_src": (
            "林凡深深吸了一口气，心中暗自思索。\n"
            "「看来这个末世并不简单。」\n"
            "【叮！系统正在加载中...】"
        ),
        "example_tgt": (
            "หลินฟานสูดหายใจเข้าลึกๆ ในใจลอบครุ่นคิด\n"
            "\"ดูเหมือนว่าวันสิ้นโลกนี้จะไม่ธรรมดาเสียแล้ว\"\n"
            "【ติ๊ง! ระบบกำลังโหลด...】"
        ),
        # CN→TH specific gotchas
        "leak_rule": (
            "- **Zero source-language characters (Chinese hanzi) in output.**\n"
            "  Every Chinese character must be translated to Thai.\n"
            "  This includes text inside 【】symbol brackets.\n"
            "- **Zero English/Latin game term leaks.**\n"
            "  Translate stat names (CON→ค่าพลัง, STAT→ค่าสถานะ, RES→ค่าต้านทาน) to Thai.\n"
            "  Only the allowed list in <format_rules> may stay in Latin script."
        ),
        "gotchas": (
            "- Chinese 就/也 → do NOT overuse ก็.\n"
            "  ก็ should appear in ≤20% of paragraphs in natural Thai narrative.\n"
            "  Simply DROP ก็ from most character-action sentences.\n"
            "  Use แล้ว, จึง, เลย sparingly where a connector is truly needed."
        ),
    },
    "jp": {
        "name": "Japanese",
        "dialogue_open": "「",
        "dialogue_close": "」",
        "system_open": "【",
        "system_close": "】",
        "thought_open": "『",
        "thought_close": "』",
        "game_open": "『",
        "game_close": "』",
        "title_regex": r"第\s*(\d+)\s*[話章]\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
        "forbidden_scripts": ["Hiragana", "Katakana", "Han"],
        "example_src": (
            "田中は深く息を吸い込み、心の中で考え込んだ。\n"
            "「この終末は簡単ではないようだ。」\n"
            "【チーン！システムがローディング中...】"
        ),
        "example_tgt": (
            "ทานากะสูดหายใจเข้าลึกๆ ครุ่นคิดในใจ\n"
            "『ดูเหมือนว่าวันสิ้นโลกนี้จะไม่ธรรมดา』\n"
            "【ติ๊ง! ระบบกำลังโหลด...】"
        ),
        "leak_rule": (
            "- **Zero Japanese characters (hiragana, katakana, kanji) in output.**\n"
            "  All Japanese text must be translated to Thai.\n"
            "  This includes text inside 【】symbol brackets."
        ),
        "gotchas": (
            "- Keep Japanese honorifics (-san, -kun, -chan, -sama, -senpai)\n"
            "  only in dialogue where context demands them.\n"
            "- Names: transliterate via standard Thai approximation.\n"
            "- Politeness level should match original speech register.\n"
            "- お前 → แก / เจ้า  depending on context.\n"
            "- 私 → ข้า / ฉัน / กระผม depending on speaker voice."
        ),
    },
    "kr": {
        "name": "Korean",
        "dialogue_open": "\"",
        "dialogue_close": "\"",
        "system_open": "【",
        "system_close": "】",
        "thought_open": "『",
        "thought_close": "』",
        "game_open": "<",
        "game_close": ">",
        "title_regex": r"제\s*(\d+)\s*[화장]\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
        "forbidden_scripts": ["Hangul", "Han"],
        "example_src": (
            "김철수는 깊게 숨을 들이마시며 마음속으로 생각했다.\n"
            "\"이 종말이 쉽지 않을 것 같다.\"\n"
            "【띵! 시스템 로딩 중...】"
        ),
        "example_tgt": (
            "คิมชอลซูสูดหายใจเข้าลึกๆ ครุ่นคิดในใจ\n"
            "『ดูเหมือนว่าวันสิ้นโลกนี้จะไม่ธรรมดา』\n"
            "【ติ๊ง! ระบบกำลังโหลด...】"
        ),
        "leak_rule": (
            "- **Zero Korean characters (hangul, hanja) in output.**\n"
            "  All Korean text must be translated to Thai.\n"
            "  This includes text inside 【】symbol brackets."
        ),
        "gotchas": (
            "- Korean honorifics (-nim, -ssi, -yang, -gun):\n"
            "  translate to Thai register equivalents (คุณ, นาย, เจ้า).\n"
            "- Names: transliterate via standard Thai approximation.\n"
            "- Speech levels (존댓말/반말) should match original tone.\n"
            "- 나/저 → ข้า / ฉัน / กระผม depending on speaker voice.\n"
            "- 너/당신 → เจ้า / แก / คุณ depending on relationship."
        ),
    },
    "en": {
        "name": "English",
        "dialogue_open": "\u201c",
        "dialogue_close": "\u201d",
        "system_open": "[",
        "system_close": "]",
        "thought_open": "*",
        "thought_close": "*",
        "game_open": "\"",
        "game_close": "\"",
        "title_regex": r"(?:Chapter|Ch|ch)\s*(\d+)\s*(?::|-)?\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
        "forbidden_scripts": ["Latin"],
        "example_src": (
            "Lin Fan took a deep breath, pondering inwardly.\n"
            "\u201cIt seems this apocalypse won't be simple.\u201d\n"
            "[Ding! System is loading...]"
        ),
        "example_tgt": (
            "หลินฟานสูดหายใจเข้าลึกๆ ครุ่นคิดในใจ\n"
            "『ดูเหมือนว่าวันสิ้นโลกนี้จะไม่ธรรมดา』\n"
            "【ติ๊ง! ระบบกำลังโหลด...】"
        ),
        "leak_rule": (
            "- **Minimal English in output — forbidden scripts not applicable.**\n"
            "  Only game UI tokens (HP, MP, EXP, etc.) are allowed.\n"
            "  English dialogue/names must be transliterated to Thai."
        ),
        "gotchas": (
            "- English → Thai tense: Thai has no tense markers.\n"
            "  Use context particles (แล้ว, กำลัง, จะ) where needed.\n"
            "- Articles (a, an, the): drop — Thai has no articles.\n"
            "- Names: transliterate phonetically to Thai script.\n"
            "- Pronoun mapping: I/you/he/she → ข้า/เจ้า/เขา/นาง by context.\n"
            "- Preserve all numbers exactly."
        ),
    },
}

# Default when source_lang not found
DEFAULT_SRC = "cn"

# ── Target language config ─────────────────────────────────────────────
# Per-target-language output formatting rules

TARGET_CONFIG: dict[str, dict[str, Any]] = {
    "th": {
        "name": "Thai",
        "end_marker": "(จบบท)",
        "dialogue_quotes": '"',
        "system_brackets": ("【", "】"),
        "thought_brackets": ("『", "』"),
        "latin_policy": (
            "- **Game UI tokens only**: HP, MP, EXP, SP, SSS, SSR, UR, LR, LV, LVL,\n"
            "  ATK, DEF, STR, INT, AGI, DPS, DMG, BUFF, DEBUFF, AOE, NPC, ID, VIP, ELITE\n"
            "- **Translate everything else** — no English words in body text.\n"
            "- Skill names, item names, status effects → Thai."
        ),
    },
    "en": {
        "name": "English",
        "end_marker": "(End)",
        "dialogue_quotes": '"',
        "system_brackets": ("[", "]"),
        "thought_brackets": ("*", "*"),
        "latin_policy": "",  # no latin restrictions for English target
    },
}

DEFAULT_TGT = "th"


def get_lang_config(source_lang: str) -> dict[str, Any]:
    """Get source language config, with fallback."""
    key = _normalize_lang(source_lang)
    return LANG_CONFIG.get(key, LANG_CONFIG[DEFAULT_SRC])


def get_target_config(target_lang: str) -> dict[str, Any]:
    """Get target language config, with fallback."""
    key = _normalize_lang(target_lang)
    return TARGET_CONFIG.get(key, TARGET_CONFIG[DEFAULT_TGT])


def _normalize_lang(lang: str) -> str:
    """Normalize language codes."""
    m = {
        "zh": "cn", "zh-cn": "cn", "chinese": "cn", "cn": "cn",
        "ja": "jp", "jp": "jp", "japanese": "jp",
        "ko": "kr", "kr": "kr", "korean": "kr",
        "en": "en", "english": "en", "en-us": "en",
        "th": "th", "thai": "th",
    }
    return m.get(lang.lower(), lang.lower())


def _build_title(source_text: str, source_lang: str, ch_num: int) -> str:
    """Extract or build chapter title."""
    cfg = get_lang_config(source_lang)
    title_regex = cfg["title_regex"]
    m = re.search(title_regex, source_text) if source_text else None
    title_text = m.group(2).strip() if m else f"ch {ch_num}"
    return cfg["title_format"].format(num=ch_num, title=title_text)


# ── Format rules per source language ────────────────────────────────────

def _format_rules(source_lang: str, target_lang: str) -> str:
    """Generate bracket/format mapping from source → target."""
    src = get_lang_config(source_lang)
    tgt = get_target_config(target_lang)

    lines = [
        "### Bracket Mapping (source → output)",
        f"- Dialogue: {src['dialogue_open']}...{src['dialogue_close']}  →  {tgt['dialogue_quotes']}...{tgt['dialogue_quotes']}",
        f"- System: {src['system_open']}...{src['system_close']}  →  {tgt['system_brackets'][0]}...{tgt['system_brackets'][1]}",
        f"- Thought: {src['thought_open']}...{src['thought_close']}  →  {tgt['thought_brackets'][0]}...{tgt['thought_brackets'][1]}",
    ]
    return "\n".join(lines)


# ── Build multilingual examples ────────────────────────────────────────

def _examples(source_lang: str, target_lang: str) -> str:
    """Generate language-pair-specific translation examples."""
    cfg = get_lang_config(source_lang)
    src_ex = cfg["example_src"]
    tgt_ex = cfg["example_tgt"]

    return f"""<examples>
Example Input:
{src_ex}

Example Output:
{tgt_ex}
</examples>"""


# ── FULL PROMPT BUILDER ────────────────────────────────────────────────

def build_prompt(
    source_text: str,
    ch_num: int = 1,
    source_lang: str = "cn",
    target_lang: str = "th",
    novel_title: str = "",
    glossary_text: str = "",
    style_text: str = "",
    continuity_text: str = "",
    extra_rules: str = "",
    profile: str = "",
) -> str:
    """Build a complete translation prompt.

    Args:
        source_text: The raw source text to translate.
        ch_num: Chapter number.
        source_lang: Source language code (cn, jp, kr, en).
        target_lang: Target language code (th, en).
        novel_title: Novel name (for context).
        glossary_text: Glossary terms (from glossary loader).
        style_text: Style rules (from style loader).
        continuity_text: Previous chapter context.
        extra_rules: Any extra rules to inject.
        profile: Translation profile name (for logging).

    Returns:
        Complete prompt string ready for LLM.
    """
    cfg = get_lang_config(source_lang)
    tgt = get_target_config(target_lang)
    src_name = cfg["name"]
    tgt_name = tgt["name"]
    title = _build_title(source_text, source_lang, ch_num)

    # ── Build prompt parts ──────────────────────────────────────────

    # Static identity (prefix-caching friendly)
    identity = f"""<task>
MIKA — Cross-Language Novel Translation Specialist
Source: {src_name} → Target: {tgt_name}
Novel: {novel_title or "(unspecified)"}

Core identity: Transmittor — preserve the author's original voice,
scene order, sentence rhythm, and intentional flatness.
</task>"""

    # Universal rules (apply to ALL language pairs)
    universal_rules = """<rules>
[CORE: Transmittor Principle]
- **Preserve the author's voice.** Do NOT improve the author into a different writer.
- **Completeness:** translate every source beat. Do NOT omit, summarize,
  merge, or silently skip repeated lines.
|- **Output format:** Plain paragraphs separated by blank lines. One paragraph
  = one logical unit (scene beat, spoken line, or action).
|- **CRITICAL: Narration and dialogue MUST be separate paragraphs.**
  If a source paragraph has 「..."他说道」→ split into TWO paragraphs:
  nar: "เขาพูดเช่นนั้น"
  dia: "...."
  NEVER mix narration text with dialogue quotes in the same paragraph.
- **No JSON, XML, markdown fences, or any wrapper.**
- **End with end marker.** The last paragraph must be the end marker.
- **CRITICAL: Match source paragraph count exactly.** Each source paragraph = one output paragraph.
- **CRITICAL: Output length must be ≥70% of source.** Do NOT condense or summarize.
- Keep character names consistent with glossary.
- Character voices / pronoun usage should match the glossary's character voice map if provided.

[ANTI-SLOP]
- No AI filler, over-explaining, academic padding, or artificial emotional rewriting.
- Do NOT add internal monologue where the source has none.
- Do NOT add explanations, commentary, or translator notes into body text.
- Do NOT change a deadpan scene into an emotional one.
- Remove web novel footer/site artifacts (donations, thanks, author notes, next-chapter links).
</rules>"""

    # Per-source-lang rules
    src_specific = f"""<source_language_rules>
[{src_name} → {tgt_name}]
- Preserve {src_name} formatting and spacing patterns (e.g., narration + dialogue in one line → same structure in translation).
{cfg['leak_rule']}
"""
    if cfg["gotchas"]:
        src_specific += f"\n{cfg['gotchas']}\n"
    src_specific += "</source_language_rules>"

    # Format + token rules (per target)
    format_section = f"""<format_rules>
{_format_rules(source_lang, target_lang)}

{_latin_policy(target_lang)}

- **Preserve numbers exactly.**
- **Match source paragraph count — CRITICAL.**
- **End marker:** `{tgt['end_marker']}` as the last paragraph.
- **Do NOT use `「」` CJK corner brackets for dialogue.**
</format_rules>"""

    # Self-review gate
    review_gate = f"""<self_review>
Before finishing, silently check:
- Every {cfg['name']} character is translated.
- Dialogue uses {tgt['dialogue_quotes']}...{tgt['dialogue_quotes']} throughout.
- System notifications keep correct brackets.
- No foreign scripts remain (except allowed game tokens).
- No paragraphs are skipped or merged.
- Translation is complete (similar length to source).
- Glossary terms are followed.
- End marker is present.
</self_review>"""

    # Unique meta per chapter (MUST come after static prefix to not break KV cache)
    chapter_meta = f"<chapter_meta>\nChapter: {title}\n</chapter_meta>"

    # ── Assembly (prefix-caching layout: static first, dynamic last) ──
    parts = [
        identity,
        "",
        chapter_meta,
        "",
        universal_rules,
        "",
        src_specific,
        "",
        format_section,
        "",
        review_gate,
        "",
        _examples(source_lang, target_lang),
    ]

    # Glossary (semi-static — changes per chapter but reuses prefix)
    if glossary_text:
        parts.extend(["", "<glossary>", glossary_text, "</glossary>"])

    # Style rules
    if style_text:
        parts.extend(["", "<style>", style_text, "</style>"])

    # Continuity context
    if continuity_text:
        parts.extend(["", "<continuity>", continuity_text, "</continuity>"])

    # Extra rules
    if extra_rules:
        parts.extend(["", extra_rules])

    # Source
    parts.extend([
        "",
        "<source_chapter>",
        source_text,
        "</source_chapter>",
        "",
        "<now_translate>",
    ])

    return "\n".join(parts)


# ── Latin policy generator ────────────────────────────────────────────

def _latin_policy(target_lang: str) -> str:
    """Generate Latin token policy for target language."""
    if target_lang == "en":
        return "- Latin script is native — no restriction."

    return (
        "- **Latin script restriction:** only the following game UI tokens are allowed.\n"
        "  HP, MP, EXP, SP, SSS, SSR, UR, LR, LV, LVL, ATK, DEF, STR, INT, AGI, CON,\n"
        "  DPS, PvP, PvE, NPC, PC, UI, API, ID, VIP, S, SS, CD, DMG, BUFF, STAT, RES,\n"
        "  DEBUFF, AOE, TPS, ELITE, RANK, MAX, MIN, SOLO, R, SR, G1, No., no.\n"
        "- **Translate ALL other English/foreign words to Thai.**\n"
        "  This includes skill names, item names, status effects, stat labels.\n"
        "- **NO raw English game terms outside the allowed list above.**\n"
        "  'CON', 'STAT', 'RES' → แก้เป็น 'ค่าพลัง', 'ค่าสถานะ', 'ค่าต้านทาน'\n"
        "- Exception: character/system names that are inherently Latin-script\n"
        "  (e.g., 'System A-001') may be kept with approval."
    )


# ── CLI test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick test
    test_source = "「你好吗？」他问道。\n【系统提示】你获得了100经验值。\n他深吸一口气。"
    prompt = build_prompt(
        source_text=test_source,
        ch_num=1,
        source_lang="cn",
        target_lang="th",
        novel_title="ทดสอบ",
    )
    print(prompt)
    print("\n\n" + "=" * 60)
    print(f"Prompt length: {len(prompt)} chars")
