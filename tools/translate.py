"""translate.py — Translate CN source chapters to TH JSON (end-to-end pipeline).

Pipeline: read source → extract entities → LLM → parse → validate → save.
Uses argparse for CLI. Run `python tools/translate.py --help` for usage.
"""

import argparse
import contextlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable as _Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))
from chapter_io import save_chapter  # noqa: E402
from constants import CHAPTERS_DIR, NOVEL_ROOT  # noqa: E402
from glossary import load_style_rules, load_terms  # noqa: E402
from progress import (  # noqa: E402
    clear_progress,
    get_pending,
    get_summary,
    init_progress,
    load_progress,
    mark_done,
    mark_failed,
    mark_running,
    save_progress,
)
from extract_entities import (  # noqa: E402
    entity_extraction_pipeline,
    PLACEHOLDER_RE,
    restore_entities_from_map,
    verify_no_leaked_entities,
)
from providers import call_llm  # noqa: E402
from schema import (  # noqa: E402
    Chapter,
)
from translation_memory import (  # noqa: E402
    TranslationMemory,
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
validate_quality_gates = validate_translation_quality  # backward compat

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
            if re.match(r"^第[一二三四五六七八九十百千零\d]+章", stripped):
                continue
            if SOURCE_ARTIFACT_RE.search(stripped):
                continue
            in_body = True
        if SOURCE_ARTIFACT_RE.search(stripped):
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"([！？。，；：…—]+)\s*(\d{1,3})(?=\s|$)", r"\1", text)
    text = re.sub(r"^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
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
    cleaned = re.sub(r"【[^】]*】", "", source_text)
    cleaned = re.sub(r"《[^》]*》", "", cleaned)
    cleaned = re.sub(r"「[^」]*」", "", cleaned)
    cn_terms = re.findall(r"[\u4e00-\u9fff]{2,}", cleaned)
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


def get_glossary_context_from_lib(ch_num: int, source: str | None = None) -> str:
    """Get glossary terms that appear in this chapter (filtered for relevance).

    Uses the load_glossary library for richer term data.
    If `source` is provided, skip reading/cleaning the file (avoid duplicate I/O).
    """
    if source is None:
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




def get_unknown_terms_for_ch(ch_num: int, source: str | None = None) -> list[str]:
    """Extract unknown CN terms from a chapter's source text.
    If `source` is provided, skip reading/cleaning the file (avoid duplicate I/O).
    """
    if source is None:
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
    source_cleaned: str | None = None,
) -> str:
    """Build the LLM prompt for translating one chapter in XML format."""
    # ponytail: pass pre-cleaned source to avoid re-reading the file
    glossary_lib = get_glossary_context_from_lib(ch_num, source=source_cleaned)
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
|- Allowed Latin tokens only: {", ".join(sorted(ALLOWED_LATIN_TOKENS))}. Translate Lv/LVL as "เลเวล", BUFF as "บัฟ", DEBUFF as "ดีบัฟ", First Kill as "คิลแรก".
|- EN RETENTION FORBIDDEN: The Chinese source may contain English words (skill names, item names, interjections like "continue", "recruiting", "mean", "queen", "level", "panic", "erupt", "disrespect"). You MUST translate these to Thai. Do NOT keep any English words in the output. If unsure, translate literally.
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
            parts.append("(use web_search tool or check TRANSLATION_GUIDE.md cheatsheet)")

    return "\n".join(parts)


# ── Post-translation named functions (replacing walrus-operator lambdas) ──

def _post_tm(ch_data: dict, progress_slug: str, ch_num: int) -> None:
    """Update TranslationMemory after a successful translate."""
    from translation_memory import TranslationMemory
    tm = TranslationMemory(progress_slug)
    tm.load()
    added = tm.add_batch(ch_data.get("blocks", []), ch_num)
    if added > 0:
        tm.save()
    print(f"  💾 TM: +{added} new, {tm.stats()['cache_entries']} total")


def _post_glossary(ch_num: int, source: str, progress_slug: str) -> None:
    """Extract auto-glossary candidates after translating."""
    from cumulative_glossary import process_translation_candidates
    gt = load_terms()
    result = process_translation_candidates(
        ch_num=ch_num, source_text=source, glossary_terms=gt,
        slug=progress_slug, auto_rebuild=True,
    )
    if result["added"] > 0:
        print(f"  📖 +{result['added']} new glossary candidates")


def _post_score(source: str, ch_data: dict) -> None:
    """Run LLM Judge scoring after translating."""
    from quality_scorer import score_translation
    gt = load_terms()
    sr = score_translation(source, ch_data, gt, mock=False, model="haiku")
    if sr.parse_error:
        print(f"  ⚠ LLM Judge: {sr.parse_error[:100]}")
    else:
        print(f"  {'🏆' if sr.passed else '⚠'} LLM Judge: {sr.summary_string()}")


def _post_agent(ch_num: int, source: str, ch_data: dict, progress_slug: str,
                agent_passes: int, source_lang: str, target_lang: str,
                profile_lang: str | None, mock_agents: bool) -> None:
    """Run multi-agent chain for refinement."""
    from agent_coordinator import run_agent_chain, print_agent_report
    from schema import Chapter
    gt = load_terms()
    success, agent_results, final_ch = run_agent_chain(
        ch_num, lambda *a, **kw: True, source, ch_data, gt,
        passes=agent_passes, source_lang=source_lang,
        target_lang=target_lang, profile_lang=profile_lang,
        mock=mock_agents, model="haiku",
    )
    if not success:
        print(f"  ⚠ Agent chain flagged issues")
    print_agent_report(agent_results)
    if final_ch is not ch_data:
        save_chapter(Chapter(**final_ch), CHAPTERS_DIR / f"{ch_num:04d}.json")
        print(f"  ✓ Re-saved polished version")


def _run_after(flag: bool, mock: bool, name: str, fn: Callable[[], None]) -> None:
    """Run a post-translation step if flag is set and not mock."""
    if flag and not mock:
        try:
            fn()
        except Exception as e:
            print(f"  ⚠ {name} error: {e}")


def _call_llm(prompt: str, max_retries: int = 3) -> str:
    """Call the LLM via Hermes (api.py handles retry + fallback).

    api.py already retries 3 times internally and has CLI fallback.
    No need for additional retry loop here.
    """
    try:
        return call_llm(prompt, max_retries=max_retries)
    except RuntimeError as e:
        print(f"✗ LLM error after all retries: {e}")
        print("⏭ Falling back to mock output...")
        return '{"mock": "no LLM configured"}'
    except Exception as e:
        print(f"✗ Unexpected LLM error: {e}")
        print("⏭ Falling back to mock output...")
        return '{"mock": "no LLM configured"}'


def analysis_pass(
    ch_num: int,
    source_text: str,
    source_lang: str = "zh",
    target_lang: str = "th",
) -> dict:
    """Pass 1: Analyze chapter content, extract entities, generate summary.

    This builds the context for Pass 2 translation by:
    1. Extracting entities (bracket-based + frequency)
    2. Cross-referencing with glossary
    3. Generating a short summary in target language style

    Returns dict with:
      - entities: list of detected proper nouns
      - placeholder_map: {placeholder: entity_info}
      - placeheld_text: source with entities replaced
      - summary: short chapter summary
    """
    glossary_terms = load_terms()

    # Run entity pipeline
    pipeline_result = entity_extraction_pipeline(
        ch_num, source_text, glossary_terms, min_freq=2,
    )

    # Generate summary (first ~500 chars as summary)
    summary = source_text[:300] + ("..." if len(source_text) > 300 else "")

    return {
        "entities": pipeline_result["entities"],
        "placeholder_map": pipeline_result["placeholder_map"],
        "placeheld_text": pipeline_result["placeheld_text"],
        "summary": summary,
        "entity_count": pipeline_result["count"],
        "replaced_count": pipeline_result.get("replaced_count", 0),
    }


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
        title = f"ตอนที่ {ch_num} [MOCK]"
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
            glossary_hint = " [Glossary hints loaded: " + ", ".join(t["thai"] for t in sample) + "]"
    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)
    narration_text = f"[MOCK - needs real] บทนี้มีต้นฉบับ {len(source_text)} ตัวอักษร{glossary_hint}"
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
    progress_state: dict | None = None,
    progress_slug: str = "global-descent",
    use_entities: bool = False,
    two_pass: bool = False,
    auto_glossary: bool = False,
    use_score: bool = False,
    use_tm: bool = False,
    agent_passes: int = 2,
    mock_agents: bool = False,
    json_mode: bool = False,
) -> bool:
    """Translate one chapter. Returns True on success.

    When json_mode=True, prints a single JSON line per chapter result
    instead of human-readable text.
    """
    normalized_source_lang = normalize_language_key(source_lang, "cn")
    normalized_target_lang = normalize_language_key(target_lang, "th")

    src_path = SOURCE_DIR / f"{ch_num:04d}.md"
    out_path = CHAPTERS_DIR / f"{ch_num:04d}.json"

    if not src_path.exists():
        if json_mode:
            print(json.dumps({"status": "failed", "ch": ch_num, "reason": "source_not_found",
                                "path": str(src_path)}, ensure_ascii=False))
        else:
            print(f"❌ ch{ch_num}: source not found at {src_path}")
        if progress_state is not None:
            mark_failed(ch_num, progress_slug, progress_state)
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

    # Mark as running in progress tracker
    if progress_state is not None:
        mark_running(ch_num, progress_slug, progress_state)

    raw_src = src_path.read_text(encoding="utf-8")
    source = clean_source(raw_src)
    if not source:
        if json_mode:
            print(json.dumps({"status": "failed", "ch": ch_num, "reason": "empty_source"},
                               ensure_ascii=False))
        else:
            print(f"❌ ch{ch_num}: source is empty after cleaning")
        if progress_state is not None:
            mark_failed(ch_num, progress_slug, progress_state)
        return False

    if not json_mode:
        print(f"→ ch{ch_num}: source = {len(source)} chars")

    # ── Phase 2: Entity pipeline + two-pass ──────────────────────
    placeholder_map = {}
    translate_source = source
    if two_pass or use_entities:
        analysis = analysis_pass(ch_num, source, source_lang, target_lang)
        if analysis["entity_count"] > 0:
            print(f"  → {analysis['entity_count']} entities detected ({analysis.get('replaced_count', 0)} non-glossary)")
        if use_entities and analysis["placeholder_map"]:
            placeholder_map = analysis["placeholder_map"]
            translate_source = analysis["placeheld_text"]
            print(f"  → {len(placeholder_map)} entities replaced with placeholders")

    # Extract unknown terms for context
    unknown_terms = get_unknown_terms_for_ch(ch_num, source=source) if search else None
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
        # ── TM skip-LLM: check if source already translated ────
        tm_cached = None
        if use_tm:
            try:
                tm_check = TranslationMemory(progress_slug)
                tm_cached = tm_check.get_source_translation(translate_source)
                if tm_cached:
                    print(f"  💡 TM cache HIT — skipping LLM for ch{ch_num}")
                    ch_data = tm_cached
                    ch_data["num"] = ch_num  # ensure num is correct
            except Exception:
                pass  # TM fail → just call LLM

        if tm_cached is None:
            prompt = build_prompt(
                ch_num,
                translate_source,
                unknown_terms=unknown_terms,
                source_lang=source_lang,
                target_lang=target_lang,
                profile_lang=profile_lang,
                source_cleaned=source,
            )
            output = _call_llm(prompt)
            try:
                ch_data = parse_llm_output(output, ch_num)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"❌ ch{ch_num}: parse failed: {e}")
                if progress_state is not None:
                    mark_failed(ch_num, progress_slug, progress_state)
                return False

            # Cache translation for future skip-LLM
            if use_tm:
                try:
                    tm_put = TranslationMemory(progress_slug)
                    tm_put.put_source_translation(translate_source, ch_data)
                except Exception:
                    pass

    # ── Restore entities from placeholder map ────────────────────
    if placeholder_map and not mock:
        for block in ch_data.get("blocks", []):
            if block.get("text"):
                block["text"] = restore_entities_from_map(block["text"], placeholder_map)
        # Verify no leaked entities
        all_text = "".join(b.get("text", "") for b in ch_data.get("blocks", []))
        leaked = verify_no_leaked_entities(all_text, placeholder_map)
        if leaked:
            print(f"  ⚠ {len(leaked)} entities leaked: {leaked[:3]}")

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
        ch = Chapter.model_construct(**ch_data)  # skip validation

    if not mock and not no_validate:
        quality_ok, quality_messages = validate_translation_quality(
            ch,
            source,
            source_lang=source_lang,
            target_lang=target_lang,
            profile_lang=profile_lang,
        )
        if not quality_ok:
            if json_mode:
                import json as _json
                print(_json.dumps({"status": "failed", "ch": ch_num,
                                    "reason": "quality_gate", "messages": quality_messages},
                                   ensure_ascii=False))
            else:
                print(f"  Quality Gate failed for ch{ch_num}:")
                for msg in quality_messages:
                    print(f"  {msg}")
            if progress_state is not None:
                mark_failed(ch_num, progress_slug, progress_state)
            return False
    else:
        quality_messages = []

    save_chapter(ch, out_path)
    n = len(ch.blocks)
    if json_mode:
        import json as _json
        print(_json.dumps({"status": "ok", "ch": ch_num, "blocks": n,
                            "path": str(out_path)}, ensure_ascii=False))
    else:
        print(f"✓ ch{ch_num}: saved → {out_path.name} ({n} blocks)")
    if progress_state is not None:
        mark_done(ch_num, progress_slug, progress_state)
    if not mock and not no_validate:
        warnings = [m for m in quality_messages if m.startswith("WARNING")]
        if not json_mode:
            if warnings:
                print(f"  Quality Report for ch{ch_num}:")
                for w in warnings:
                    print(w)
            else:
                print("  OK Quality: clean")

    # ── Post-translation steps (consolidated) ──────────────────
    _run_after(use_tm, mock, "TM", lambda: _post_tm(ch_data, progress_slug, ch_num))
    _run_after(auto_glossary, mock, "auto-glossary", lambda: _post_glossary(ch_num, source, progress_slug))
    _run_after(use_score and not no_validate, mock, "LLM Judge", lambda: _post_score(source, ch_data))
    _run_after(agent_passes >= 2 and not no_validate and bool(ch_data), mock, "agent-chain",
               lambda: _post_agent(ch_num, source, ch_data, progress_slug,
                                   agent_passes, source_lang, target_lang,
                                   profile_lang, mock_agents))

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
        print("  Use web_search tool or check TRANSLATION_GUIDE.md cheatsheet")


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
  novelclaw-translate 113                          # via global entry point
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
    ap.add_argument("--source-lang", "--from", default="zh", help="Source language key (e.g. zh, ja, en). Short: --from.")
    ap.add_argument("--target-lang", "--to", default="th", help="Target language key (e.g. th, en). Short: --to.")
    ap.add_argument(
        "--profile-lang",
        default=None,
        help="Override output/profile language for validation/rendering (e.g. th, en)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output JSON for agent consumption (parseable by MIKA)",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted batch from saved progress file",
    )
    ap.add_argument(
        "--concurrent",
        type=int,
        default=1,
        metavar="N",
        help="Translate N chapters concurrently (default: 1, max: 5)",
    )
    ap.add_argument(
        "--no-progress",
        action="store_true",
        help="Skip progress file tracking",
    )
    ap.add_argument(
        "--entities",
        action="store_true",
        help="Enable entity placeholder pipeline (extract → hash → translate → restore)",
    )
    ap.add_argument(
        "--two-pass",
        action="store_true",
        help="Enable two-pass translation (analysis → summary + entities → translate)",
    )
    ap.add_argument(
        "--auto-glossary",
        action="store_true",
        help="Auto-discover new glossary terms from translated chapters and append to auto.md",
    )
    ap.add_argument(
        "--score",
        action="store_true",
        help="Enable LLM-as-Judge quality scoring after translation",
    )
    ap.add_argument(
        "--tm",
        action="store_true",
        help="Enable Translation Memory (cache blocks for future reuse)",
    )
    ap.add_argument(
        "--passes",
        type=int,
        default=2,
        choices=[1, 2, 3],
        help="Multi-agent passes: 1=translate, 2=translate+validate (default), 3=translate+validate+polish",
    )
    ap.add_argument(
        "--mock-agents",
        action="store_true",
        help="Use mock agent responses (no LLM calls for validate/polish)",
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
    # Determine novel slug for progress tracking
    slug = os.environ.get("NOVEL_SLUG", "global-descent")
    
    # Resume: filter to pending chapters
    use_progress = not args.no_progress and not args.mock
    progress_state = None
    
    if args.resume and use_progress:
        progress_state = load_progress(slug)
        ch_nums_orig = ch_nums
        pending_keys = get_pending(progress_state)
        ch_nums = sorted([int(k) for k in pending_keys if k in [str(c) for c in ch_nums_orig]])
        if not ch_nums:
            if args.json:
                print(json.dumps({"status": "ok", "note": "nothing to resume"}, ensure_ascii=False))
            else:
                print("✓ All chapters already processed (nothing to resume)")
            return
        if not args.json:
            print(f"⏯ Resume mode: {len(ch_nums_orig)} total → {len(ch_nums)} pending")
    elif use_progress:
        progress_state = init_progress(ch_nums, slug)
    
    concurrent_n = max(1, min(args.concurrent, 5))
    
    if concurrent_n > 1:
        if not args.json:
            print(f"⚡ Batch translating {len(ch_nums)} chapters ({concurrent_n} concurrent)...")
        n_workers = min(concurrent_n, len(ch_nums))
        success = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            fut_to_ch = {
                executor.submit(
                    translate_one,
                    ch,
                    mock=args.mock,
                    no_validate=args.no_validate,
                    search=args.search_unknown,
                    source_lang=args.source_lang,
                    target_lang=args.target_lang,
                    profile_lang=args.profile_lang,
                    progress_state=progress_state,
                    progress_slug=slug,
                    use_entities=args.entities,
                    two_pass=args.two_pass,
                    auto_glossary=args.auto_glossary,
                    use_score=args.score,
                    use_tm=args.tm,
                    json_mode=args.json,
                ): ch
                for ch in ch_nums
            }
            for fut in as_completed(fut_to_ch):
                ch = fut_to_ch[fut]
                try:
                    if fut.result():
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    if args.json:
                        print(json.dumps({"status": "failed", "ch": ch, "reason": "exception",
                                            "detail": str(e)}, ensure_ascii=False))
                    else:
                        print(f"❌ ch{ch}: unexpected error: {e}")
                    failed += 1
                    if progress_state is not None:
                        mark_failed(ch, slug, progress_state)
    else:
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
                progress_state=progress_state,
                progress_slug=slug,
                use_entities=args.entities,
                two_pass=args.two_pass,
                auto_glossary=args.auto_glossary,
                use_score=args.score,
                use_tm=args.tm,
                json_mode=args.json,
                ):
                success += 1
            else:
                failed += 1
    
    if not args.json:
        print(f"\n{'=' * 50}")
    if args.json:
        import json as _json
        batch_summary = {"status": "ok" if failed == 0 else "partial" if success > 0 else "failed",
                          "total": len(ch_nums), "success": success, "failed": failed}
        if progress_state is not None:
            s = get_summary(progress_state)
            batch_summary["progress"] = {"done": s.get("done", 0), "failed": s.get("failed", 0),
                                          "pending": s.get("pending", 0)}
        print(_json.dumps(batch_summary, ensure_ascii=False))
    else:
        print(f"Total: {success} translated, {failed} failed out of {len(ch_nums)}")
        if progress_state is not None:
            summary = get_summary(progress_state)
            print(f"Progress: {summary.get('done', 0)} done / "
                  f"{summary.get('failed', 0)} failed / "
                  f"{summary.get('pending', 0)} pending")


if __name__ == "__main__":
    main()
