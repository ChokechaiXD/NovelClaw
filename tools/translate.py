"""translate.py — Translate CN source chapters to TH JSON (end-to-end pipeline).

This is the unified translation tool combining the best of translate.py and translate_ch.py.

Pipeline:
  1. Read source/XXXX.md (cleaned CN)
  2. Auto-extract unknown CN terms (not in glossary)
  3. Build context: format spec + style + locked glossary + unknown terms
  4. Call LLM (or use mock translation)
  5. Parse LLM output → JSON blocks
  6. Validate via Pydantic schema
  7. Save chapters/NNNN.json

Usage:
  python tools/translate.py 113                    # translate ch 113
  python tools/translate.py 113-150                # batch translate range
  python tools/translate.py 113 --mock             # don't call LLM, use placeholder
  python tools/translate.py 113 --no-validate      # skip schema validation
  python tools/translate.py 113 --dry-run          # show context only, no save
  python tools/translate.py 113 --search "招募"     # search Thai for a term
  python tools/translate.py 113 --context          # print full context for ch

The LLM integration point is `_call_llm()`. The mock returns a placeholder;
the real integration uses hermes CLI or direct API.
"""

import argparse
import contextlib
import json
import re
import re as _re
import sys
from collections.abc import Iterable as _Iterable
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))
from chapter_io import save_chapter  # noqa: E402
from constants import CHAPTERS_DIR, NOVEL_ROOT  # noqa: E402
from glossary import load_style_rules, load_terms  # noqa: E402
from providers import get_provider  # noqa: E402
from schema import (  # noqa: E402
    Chapter,
)
from validation import (  # noqa: E402
    ALLOWED_LATIN_TOKENS,
    COMPLETENESS_MAX_RATIO,
    COMPLETENESS_MIN_RATIO,
    SOURCE_ARTIFACT_RE,
    get_bracket_profile,
    get_profile_lang,
    normalize_language_key,
    validate_translation_quality,
)

# ── Language Configurations ───────────────────────────────────────────
LANG_CONFIG = {
    "zh": {
        "name": "Chinese",
        "dialogue_open": "「",
        "dialogue_close": "」",
        "system_open": "【",
        "system_close": "】",
        "game_open": "《",
        "game_close": "》",
        "title_regex": r"第\s*(\d+)\s*章\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
    },
    "ja": {
        "name": "Japanese",
        "dialogue_open": "「",
        "dialogue_close": "」",
        "system_open": "【",
        "system_close": "】",
        "game_open": "『",
        "game_close": "』",
        "title_regex": r"第\s*(\d+)\s*[話章]\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
    },
    "en": {
        "name": "English",
        "dialogue_open": "“",
        "dialogue_close": "”",
        "system_open": "[",
        "system_close": "]",
        "game_open": '"',
        "game_close": '"',
        "title_regex": r"(?:Chapter|ch)\s*(\d+)\s*(?::|-)?\s*(.+)",
        "title_format": "ตอนที่ {num} {title}",
    },
    "th": {"name": "Thai", "end_marker": "(จบบท)", "title_format": "ตอนที่ {num} {title}"},
}


def get_lang_config_key(lang: str, default: str) -> str:
    normalized = normalize_language_key(lang, default)
    if normalized == "cn":
        return "zh"
    if normalized == "jp":
        return "ja"
    if normalized == "kr":
        return "kr" if "kr" in LANG_CONFIG else "ja"
    return normalized if normalized in LANG_CONFIG else default


def clean_source(raw: str) -> str:
    """Strip line numbers, reader comments, duplicate title."""
    parts = raw.split("\n---\n")
    body = parts[0]
    lines = body.split("\n")
    out = []
    in_body = False
    for line in lines[1:]:
        stripped = line.strip()
        if not in_body:
            if stripped == "" or "全球降臨" in stripped:
                continue
            if _re.match(r"^第[一二三四五六七八九十百千零\d]+章", stripped):
                continue
            if SOURCE_ARTIFACT_RE.search(stripped):
                continue
            in_body = True
        if SOURCE_ARTIFACT_RE.search(stripped):
            continue
        out.append(line)
    text = "\n".join(out)
    text = _re.sub(r"([！？。，；：…—]+)\s*(\d{1,3})(?=\s|$)", r"\1", text)
    text = _re.sub(r"^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$", "", text, flags=_re.MULTILINE)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_unknown_terms(source_text: str, known_sources: _Iterable[str]) -> list[str]:
    """Extract CN terms from source that aren't in glossary."""
    known = set(known_sources)
    ui_noise = {
        "首頁",
        "科幻小說",
        "玄幻小說",
        "都市言情",
        "歷史軍事",
        "遊戲競技",
        "加入書籤",
        "小說報錯",
        "投票推薦",
        "字體",
        "上一章",
        "下一章",
        "目錄",
        "關燈",
        "開燈",
        "下載",
        "客戶端",
        "手機看書",
        "繁體",
        "簡體",
        "上一頁",
        "下一頁",
        "返回",
        "確定",
        "取消",
        "提交",
        "下載本章",
        "請先",
        "登錄",
        "註冊",
        "忘記密碼",
        "會員中心",
        "我的書架",
        "正在加載",
        "加載中",
        "請稍候",
        "暫無",
        "評論",
        "書友",
        "全球降臨",
        "帶著嫂嫂",
        "末世種田",
        "第",
        "章",
        "回",
        "節",
        "頁",
        "卷",
    }
    known |= ui_noise
    cleaned = _re.sub(r"【[^】]*】", "", source_text)
    cleaned = _re.sub(r"《[^》]*》", "", cleaned)
    cleaned = _re.sub(r"「[^」]*」", "", cleaned)
    cn_terms = _re.findall(r"[\u4e00-\u9fff]{2,}", cleaned)
    seen = set()
    unknown = []
    for term in cn_terms:
        if term not in known and term not in seen:
            seen.add(term)
            unknown.append(term)
    return unknown


SOURCE_DIR = NOVEL_ROOT / "chapters" / "source"


# === Format spec for quick reference ===
FORMAT_SPEC = """
# Format v2 Spec (P'Chok approved)

# Block types
- narration: regular text
- dialogue: must contain the target-language dialogue brackets from config/brackets.json
- system: must contain the target-language system brackets from config/brackets.json
- game_title: must contain the target-language game/title brackets from config/brackets.json
- end: exactly the target-language end marker, default "(จบบท)"

# Required structure
- title: "ตอนที่ N <thai_title>" (space between N and title)
- blocks: list of {type, text}
- source: "ch N" (short form)
- notes: optional list of translation notes in Thai

# Rules
- CN leakage forbidden in narration/dialogue/system blocks.
- Dialogue: use target-language quote style from config/brackets.json; for Thai this is curly quotes “...”.
- Transmittor principle: TRANSMIT source faithfully, don't edit.
- Keep author's voice: ดังนั้น, ฉายแวว, เต็มไปด้วย, subject echo.
- Em dash (—) for missing numbers in source.
- Allowed Latin tokens only: HP, MP, EXP, SSS, SSR, UR, SP, ID, VIP.
- Translate Lv/LVL as "เลเวล", BUFF as "บัฟ", DEBUFF as "ดีบัฟ", First Kill as "คิลแรก".
- Completeness target: Thai output length must be 0.90-3.20x the cleaned source length. Do not stop early.

# Schema enforces
- Title format: must match "ตอนที่ N ..."
- Dialogue: must contain configured dialogue brackets
- System: must contain configured system brackets
- End: exactly configured end marker
- Last block: end marker
- At least 1 content block before end
"""


def load_style_context() -> str:
    """Load style guide for prompt injection."""
    style_path = NOVEL_ROOT / "style.md"
    if not style_path.exists():
        return ""
    return style_path.read_text(encoding="utf-8")[:3000]  # truncate to fit


def get_glossary_context_from_lib(ch_num: int) -> str:
    """Get glossary terms that appear in this chapter (filtered for relevance).

    Uses the load_glossary library for richer term data.
    """
    src_path = SOURCE_DIR / f"{ch_num:04d}.md"
    if not src_path.exists():
        return ""
    source = clean_source(src_path.read_text(encoding="utf-8"))

    terms = load_terms()
    # Filter to terms that appear in source
    in_source = [t for t in terms if t["source"] in source]
    # Prioritize: locked (priority 1-2) first
    in_source.sort(key=lambda t: (t.get("priority", 3), t["source"]))

    lines = ["## Glossary terms in this ch (use EXACT Thai):"]
    for t in in_source:
        expl = t.get("explanation") or t.get("notes") or ""
        line = f"- `{t['source']}` → {t['thai']}"
        if expl:
            line += f" — {expl[:80]}"
        lines.append(line)
    return "\n".join(lines)


def get_style_summary() -> str:
    """Compact style rules for prompt injection."""
    rules = load_style_rules()
    lines = ["## Style rules (apply):"]
    for section in ["term_choices", "punctuation", "naturalness", "policies"]:
        items = rules.get(section, [])
        if items:
            lines.append(f"\n### {section}:")
            for item in items[:10]:
                if "key" in item:
                    lines.append(f"- **{item['key']}** — {item['value'][:120]}")
                else:
                    lines.append(f"- {item['text'][:120]}")
    return "\n".join(lines)


def get_format_summary() -> str:
    """Compact format spec for prompt injection."""
    return FORMAT_SPEC


def validate_quality_gates(
    ch: Chapter,
    source_text: str,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> tuple[bool, list[str]]:
    """Validate translation quality using the shared validator."""
    return validate_translation_quality(ch, source_text, source_lang, target_lang, profile_lang)


def get_previous_chapter_context(ch_num: int, n: int = 3) -> str:
    from chapter_io import load_chapter as _load_ch  # noqa: PLC0415

    parts = []
    for i in range(max(1, ch_num - n), ch_num):
        ch_path = CHAPTERS_DIR / f"{i:04d}.json"
        if not ch_path.exists():
            continue
        try:
            ch = _load_ch(ch_path)
            parts.append(f"Ch {i}: {ch.title}")
            for b in ch.blocks:
                if b.type == "narration" and len(b.text) > 20:
                    txt = b.text[:200]
                    if len(b.text) > 200:
                        txt += "..."
                    parts.append(f"  >> {txt}")
                    break
        except Exception:
            continue
    if not parts:
        return ""
    return "Previous chapters:" + chr(10) + chr(10).join(parts)


def web_search_term(_cn_term: str) -> str:
    """No-op: web search is not available as a Python module.

    Mika should use the cheatsheet in TRANSLATION_GUIDE.md or
    the chat web_search tool directly.
    """
    return "(use web_search tool or check TRANSLATION_GUIDE.md cheatsheet)"


def get_unknown_terms_for_ch(ch_num: int) -> list[str]:
    """Extract unknown CN terms from a chapter's source text."""
    src_path = SOURCE_DIR / f"{ch_num:04d}.md"
    if not src_path.exists():
        return []
    source = clean_source(src_path.read_text(encoding="utf-8"))
    terms = load_terms()
    known = {t["source"] for t in terms}
    return extract_unknown_terms(source, known)


def build_prompt(
    ch_num: int,
    source_text: str,
    unknown_terms: list[str] | None = None,
    source_lang: str = "zh",
    target_lang: str = "th",
    novel_title: str = "全球降臨：帶著嫂嫂末世種田",
    profile_lang: str | None = None,
) -> str:
    """Build the LLM prompt for translating one chapter in XML format."""
    glossary_lib = get_glossary_context_from_lib(ch_num)
    style = get_style_summary()

    # Use chapter-filtered glossary only (deduplicated — no SQLite fallback)
    glossary = glossary_lib if glossary_lib else "(no glossary loaded)"
    # Load continuity context from previous chapters
    continuity = get_previous_chapter_context(ch_num, n=3)

    src_cfg = LANG_CONFIG.get(get_lang_config_key(source_lang, "zh"), LANG_CONFIG["zh"])
    tgt_cfg = LANG_CONFIG.get(get_lang_config_key(target_lang, "th"), LANG_CONFIG["th"])
    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)

    active_profile = get_profile_lang(source_lang, target_lang, profile_lang)

    # XML configuration
    xml_config = f"""<translation_config>
  <source lang="{source_lang}" name="{src_cfg["name"]}"/>
  <target lang="{target_lang}" name="{tgt_cfg["name"]}"/>
  <profile lang="{active_profile}"/>
  <novel>
    <title>{novel_title}</title>
  </novel>
</translation_config>"""

    # Unknown terms XML
    xml_unknown = ""
    if unknown_terms:
        xml_unknown = "<unknown_terms>\n"
        for term in unknown_terms[:15]:
            xml_unknown += f'  <term source="{term}"/>\n'
        xml_unknown += "</unknown_terms>"

    # XML Envelope prompt structure
    prompt = f"""You are an expert translator. Follow the instructions inside the XML blocks below to translate the source chapter.

{xml_config}

<style_guide>
{style}
</style_guide>

<glossary>
{glossary}
</glossary>

<format_spec>
- Output must be valid JSON matching the schema inside <output_schema>. Do NOT include any markdown formatting, code block ticks (like ```json), or explanatory text outside the JSON.
- Dialogue brackets: {bracket_profile["dialogue_open"]}...{bracket_profile["dialogue_close"]}
- System message brackets: {bracket_profile["system_open"]}...{bracket_profile["system_close"]}
- Game title brackets: {bracket_profile["game_open"]}...{bracket_profile["game_close"]}
- End marker text: "{bracket_profile["end_marker"]}"
- The last block in the output list MUST be the end marker block: {{"type": "end", "text": "{bracket_profile["end_marker"]}"}}
- Transmittor principle: TRANSMIT the source content faithfully. Do NOT summarize, edit, or omit paragraphs.
- Zero source-language characters are allowed in narration/dialogue/system blocks.
- ANTI-HALLUCINATION: Do NOT add any narration, description, detail, or dialogue not present in the source. Do NOT invent internal monologue, character thoughts, or scene details. If the source is ambiguous, preserve the ambiguity. If unsure, translate literally rather than inventing content.
- Your translation must preserve the full length and detail of the source. Target {COMPLETENESS_MIN_RATIO:.2f}-{COMPLETENESS_MAX_RATIO:.2f}x source character count. Do NOT compress or summarize.
- Allowed Latin tokens only: {", ".join(sorted(ALLOWED_LATIN_TOKENS))}. Translate Lv/LVL as "เลเวล", BUFF as "บัฟ", DEBUFF as "ดีบัฟ", First Kill as "คิลแรก".
</format_spec>

<continuity_context>
{continuity}
</continuity_context>

<output_schema>
{{
  "schema_version": 2,
  "num": {ch_num},
  "title": "{tgt_cfg["title_format"].format(num=ch_num, title="<thai_title>")}",
  "blocks": [
    {{"type": "narration", "text": "..."}},
    {{"type": "dialogue", "text": "{bracket_profile["dialogue_open"]}...{bracket_profile["dialogue_close"]}"}},
    {{"type": "system", "text": "{bracket_profile["system_open"]}...{bracket_profile["system_close"]}"}},
    {{"type": "end", "text": "{bracket_profile["end_marker"]}"}}
  ],
  "source": "ch {ch_num}",
  "notes": ["<optional translation notes>"]
}}
</output_schema>

{xml_unknown}

<source_text>
{source_text}
</source_text>

Please output only the translated JSON. Start your response with {{ and end with }}.
"""
    return prompt


def get_chapter_context(
    ch_num: int,
    search_unknown: bool = True,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> str:
    """Build full context block for translating one chapter.

    Returns formatted string with:
    - Title
    - Source (cleaned)
    - Glossary terms in source
    - Style rules
    - Format spec
    - Unknown terms (if search_unknown)
    """
    src_path = SOURCE_DIR / f"{ch_num:04d}.md"
    if not src_path.exists():
        return f"❌ Source not found: {src_path}"

    raw = src_path.read_text(encoding="utf-8")
    source = clean_source(raw)
    if not source:
        return f"❌ ch {ch_num} source is empty"

    terms = load_terms()
    {t["source"] for t in terms}

    # Title
    src_cfg = LANG_CONFIG.get(get_lang_config_key(source_lang, "zh"), LANG_CONFIG["zh"])
    title_match = re.search(src_cfg["title_regex"], source)
    cn_title = title_match.group(2).strip() if title_match else f"ch {ch_num}"
    active_profile = get_profile_lang(source_lang, target_lang, profile_lang)
    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)

    parts = [
        f"# ch {ch_num} context",
        f"## Source language: {source_lang}",
        f"## Target/profile language: {active_profile}",
        f"## Dialogue brackets: {bracket_profile['dialogue_open']}...{bracket_profile['dialogue_close']}",
        f"## System brackets: {bracket_profile['system_open']}...{bracket_profile['system_close']}",
        f"## End marker: {bracket_profile['end_marker']}",
        f"\n## CN title: {cn_title}",
        f"\n## Source ({len(source)} chars):\n```\n{source}\n```",
        f"\n{get_glossary_context_from_lib(ch_num)}",
        f"\n{get_style_summary()}",
        f"\n{get_format_summary()}",
    ]

    # Unknown terms
    unknown = get_unknown_terms_for_ch(ch_num)
    if unknown and search_unknown:
        parts.append(f"\n## Unknown CN terms ({len(unknown)}) — need Thai equivalent:")
        for term in unknown[:15]:
            parts.append(f"\n### {term}")
            web = web_search_term(term)
            if web:
                parts.append(web)
            else:
                parts.append("(no web result — use Thai transliteration or best guess)")

    return "\n".join(parts)


def _call_llm(prompt: str, model: str = "haiku") -> str:
    """Call the LLM via provider abstraction.

    Uses the provider system (haiku / gemini / claude).
    Falls back to mock output if provider is unavailable.
    """
    try:
        provider = get_provider(model)
        return provider.translate(prompt)
    except Exception as e:
        print(f"⚠ LLM error ({model}): {e}")
        print("⏭ Falling back to mock output...")
        return '{"mock": "no LLM configured"}'


def mock_translate(
    ch_num: int,
    source_text: str,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> dict:
    """Mock translation with glossary hints + source preview."""
    title_match = re.search(r"[#第]\s*\d+\s*[章章節]?\s*(.+)", source_text)
    if title_match:
        cn_title = title_match.group(1).strip()[:60]
        title = f"ตอนที่ {ch_num} [CN: {cn_title}]"
    else:
        title = f"ตอนที่ {ch_num}"
    first_line = ""
    for line in source_text.splitlines()[:10]:
        stripped = line.strip()
        if len(stripped) > 15 and not stripped.startswith("#"):
            first_line = stripped[:150]
            break
    from glossary import load_terms as _load_g  # noqa: PLC0415

    terms = _load_g()
    glossary_hint = ""
    if terms:
        sample = [t for t in terms if t.get("priority", 3) <= 2][:5]
        if sample:
            glossary_hint = (
                " [Glossary: " + ", ".join(f"{t['source']}->{t['thai']}" for t in sample) + "]"
            )
    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)
    narration_text = f"[MOCK - needs real] {first_line}{glossary_hint}"
    if not first_line:
        narration_text = f"[MOCK] ch {ch_num} - translation pending{glossary_hint}"
    return {
        "schema_version": 2,
        "num": ch_num,
        "title": title,
        "blocks": [
            {"type": "narration", "text": narration_text},
            {"type": "end", "text": bracket_profile["end_marker"]},
        ],
        "source": f"ch {ch_num}",
        "notes": ["[MOCK] generated by translate.py --mock - needs real LLM translation"],
        "lang": normalize_language_key(source_lang, "cn"),
        "output_lang": normalize_language_key(target_lang, "th"),
    }


def parse_llm_output(output: str, _ch_num: int) -> dict:
    """Parse LLM output (which may include prose) to extract JSON.

    LLM may output ```json ... ``` or just raw JSON or with prose around it.
    """
    # Strip markdown fences if present
    output = re.sub(r"^```(?:json)?\s*\n?", "", output.strip())
    output = re.sub(r"\n?```\s*$", "", output)
    # Find first { and last }
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON braces found in LLM output:\n{output[:200]}")
    json_str = output[start : end + 1]
    return json.loads(json_str)


def translate_one(
    ch_num: int,
    mock: bool = False,
    no_validate: bool = False,
    dry_run: bool = False,
    search: bool = False,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> bool:
    """Translate one chapter. Returns True on success.

    Args:
        ch_num: chapter number
        mock: use mock translation (no LLM call)
        no_validate: skip schema validation
        dry_run: show context only, don't translate or save
        search: include unknown term search in context
        source_lang: source language key
        target_lang: target language key
        profile_lang: optional override for output/profile language
    """
    src_path = SOURCE_DIR / f"{ch_num:04d}.md"
    out_path = CHAPTERS_DIR / f"{ch_num:04d}.json"
    normalized_source_lang = normalize_language_key(source_lang, "cn")
    normalized_target_lang = normalize_language_key(target_lang, "th")

    if not src_path.exists():
        print(f"❌ ch{ch_num}: source not found at {src_path}")
        return False

    if dry_run:
        print(
            get_chapter_context(
                ch_num,
                search_unknown=search,
                source_lang=source_lang,
                target_lang=target_lang,
                profile_lang=profile_lang,
            )
        )
        return True

    if out_path.exists():
        print(f"⚠ ch{ch_num}: output exists, skipping (delete to overwrite)")
        return False

    raw_src = src_path.read_text(encoding="utf-8")
    source = clean_source(raw_src)
    if not source:
        print(f"❌ ch{ch_num}: source is empty after cleaning")
        return False

    print(f"→ ch{ch_num}: source = {len(source)} chars")

    # Extract unknown terms for context
    unknown_terms = get_unknown_terms_for_ch(ch_num) if search else None
    if unknown_terms:
        print(f"  → {len(unknown_terms)} unknown terms detected")

    if mock:
        ch_data = mock_translate(
            ch_num,
            source,
            source_lang=source_lang,
            target_lang=target_lang,
            profile_lang=profile_lang,
        )
    else:
        prompt = build_prompt(
            ch_num,
            source,
            unknown_terms=unknown_terms,
            source_lang=source_lang,
            target_lang=target_lang,
            profile_lang=profile_lang,
        )
        output = _call_llm(prompt)
        try:
            ch_data = parse_llm_output(output, ch_num)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ ch{ch_num}: parse failed: {e}")
            return False

    # Validate via Pydantic schema
    if not no_validate:
        ch_data.setdefault("lang", normalized_source_lang)
        ch_data["output_lang"] = normalized_target_lang
        try:
            ch = Chapter(**ch_data)
        except Exception as e:
            print(f"❌ ch{ch_num}: schema validation failed: {str(e)[:200]}")
            return False
    else:
        ch_data.setdefault("lang", normalized_source_lang)
        ch_data["output_lang"] = normalized_target_lang
        ch = Chapter.construct(**ch_data)  # skip validation

    if not mock and not no_validate:
        quality_ok, quality_messages = validate_quality_gates(
            ch,
            source,
            source_lang=source_lang,
            target_lang=target_lang,
            profile_lang=profile_lang,
        )
        if not quality_ok:
            print(f"  Quality Gate failed for ch{ch_num}:")
            for msg in quality_messages:
                print(f"  {msg}")
            return False
    else:
        quality_messages = []

    save_chapter(ch, out_path)
    n = len(ch.blocks)
    print(f"✓ ch{ch_num}: saved → {out_path.name} ({n} blocks)")
    if not mock and not no_validate:
        warnings = [m for m in quality_messages if m.startswith("WARNING")]
        if warnings:
            print(f"  Quality Report for ch{ch_num}:")
            for w in warnings:
                print(w)
        else:
            print("  OK Quality: clean")

    return True


def search_term(term: str) -> None:
    """Search for a Thai equivalent of a CN term.

    Prints the term and guidance for finding its Thai translation.
    """
    # Check if term is in glossary
    terms = load_terms()
    matches = [t for t in terms if term in t["source"]]
    if matches:
        print(f'✓ Found {len(matches)} glossary entries for "{term}":')
        for t in matches:
            expl = t.get("explanation") or t.get("notes") or ""
            print(f"  `{t['source']}` → {t['thai']}" + (f" — {expl[:80]}" if expl else ""))
    else:
        print(f'✗ "{term}" not found in glossary.')
        web = web_search_term(term)
        print(f"  {web}")


def main():
    import sys  # noqa: PLC0415

    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="Translate CN source chapters to TH JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python tools/translate.py 113                    # translate ch 113
  python tools/translate.py 113-150                # batch translate range
  python tools/translate.py 113 --mock             # mock translation (no LLM)
  python tools/translate.py 113 --dry-run          # show context only
  python tools/translate.py 113 --search "招募"     # search Thai for term
  python tools/translate.py 113 --context          # print full context
  python tools/translate.py 113 --no-validate      # skip schema validation
        """,
    )
    ap.add_argument("chapters", help="Single (113) or range (113-150)")
    ap.add_argument("--mock", action="store_true", help="Use mock translation (no LLM call)")
    ap.add_argument("--no-validate", action="store_true", help="Skip schema validation")
    ap.add_argument("--dry-run", action="store_true", help="Show context only, no save")
    ap.add_argument("--context", action="store_true", help="Print full context")
    ap.add_argument("--search", type=str, metavar="TERM", help="Search Thai for a CN term")
    ap.add_argument(
        "--search-unknown",
        action="store_true",
        help="Extract & search unknown terms during translation",
    )
    ap.add_argument("--source-lang", default="zh", help="Source language key (e.g. zh, ja, en)")
    ap.add_argument("--target-lang", default="th", help="Target language key (e.g. th, en)")
    ap.add_argument(
        "--profile-lang",
        default=None,
        help="Override output/profile language for validation/rendering (e.g. th, en)",
    )
    args = ap.parse_args()

    # Term search mode
    if args.search:
        search_term(args.search)
        return

    # Parse chapter range
    if "-" in args.chapters:
        a, b = map(int, args.chapters.split("-"))
        ch_nums = list(range(a, b + 1))
    else:
        ch_nums = [int(args.chapters)]

    # Dry-run / context mode
    if args.dry_run or args.context:
        for ch in ch_nums:
            print(f"\n{'=' * 70}")
            print(
                get_chapter_context(
                    ch,
                    search_unknown=args.search_unknown,
                    source_lang=args.source_lang,
                    target_lang=args.target_lang,
                    profile_lang=args.profile_lang,
                )
            )
            print(f"\n{'=' * 70}\n")
        return

    # Translation mode
    success = 0
    failed = 0
    for ch in ch_nums:
        if translate_one(
            ch,
            mock=args.mock,
            no_validate=args.no_validate,
            search=args.search_unknown,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            profile_lang=args.profile_lang,
        ):
            success += 1
        else:
            failed += 1
    print(f"\n{'=' * 50}")
    print(f"Total: {success} translated, {failed} failed out of {len(ch_nums)}")


if __name__ == "__main__":
    main()
