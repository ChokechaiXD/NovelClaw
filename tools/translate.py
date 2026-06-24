"""translate.py — Translate CN source chapters to TH JSON (end-to-end pipeline).

Pipeline: read source → LLM → parse → validate → save.
Uses argparse for CLI. Run `python tools/translate.py --help` for usage.
"""

import argparse
import contextlib
import json
import os
import re
import sys
from collections.abc import Callable, Iterable as _Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))
# Merged from chapter_io.py  # noqa: E402
from schema import CHAPTERS_DIR, NOVEL_ROOT  # noqa: E402
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
from providers import call_llm  # noqa: E402
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


def _get_source_dir() -> Path:
    """Get source directory dynamically (was hardcoded at module level)."""
    from schema import get_novel_root
    return get_novel_root() / "chapters" / "source"


# === Format spec for quick reference ===
FORMAT_SPEC = """
# New Format: Paragraphs with Inline Markers (v3 - P'Chok approved)

# Structure
- paragraphs: list of Thai text strings (no JSON blocks, no block types)
- Inline markers: use "..." for dialogue, 【...】 for system, 『...』 for thought
- End: last paragraph must be "(จบบท)"
- Title: "ตอนที่ N <thai_title>"

# Rules
- Translate faithfully, do NOT skip or summarize paragraphs
- Zero CJK characters allowed in translation
- Use straight "..." for dialogue (not 「」)
- System notifications: keep 【...】 brackets
- Completeness: Thai output should be ~1-3x source length
"""


def get_glossary_context_from_lib(ch_num: int, source: str | None = None) -> str:
    """Get glossary terms that appear in this chapter (filtered for relevance).

    Uses the load_glossary library for richer term data.
    If `source` is provided, skip reading/cleaning the file (avoid duplicate I/O).
    """
    if source is None:
        _sd = _get_source_dir()
        src_path = _sd / f"{ch_num:04d}.md"
        if not src_path.exists():
            return ""
        source = clean_source(src_path.read_text(encoding="utf-8"))

    terms = load_terms()
    # Filter to terms that appear in source
    in_source = [t for t in terms if t["source"] in source]
    # Prioritize: locked (priority 1-2) first
    in_source.sort(key=lambda t: (t.get("priority", 3), t["source"]))

    # Strip CN source from display — only show Thai equivalents
    # CN chars in prompt leak into LLM output (experiment confirmed)
    lines = ["## Glossary terms in this ch (use EXACT Thai):"]
    for t in in_source:
        expl = t.get("explanation") or t.get("notes") or ""
        line = f"- → {t['thai']}"
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
    # Merged from chapter_io.py — load_chapter defined above

    parts = []
    for i in range(max(1, ch_num - n), ch_num):
        ch_path = CHAPTERS_DIR / f"{i:04d}.json"
        if not ch_path.exists():
            continue
        try:
            ch = _load_ch(ch_path)
            parts.append(f"Ch {i}: {ch.title}")
            # Handle both paragraphs and blocks format
            if ch.paragraphs:
                for para in ch.paragraphs[:3]:
                    if para and len(para) > 20 and para != "(จบบท)":
                        txt = para[:200]
                        if len(para) > 200:
                            txt += "..."
                        parts.append(f"  >> {txt}")
                        break
            elif ch.blocks:
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
        _sd = _get_source_dir()
        src_path = _sd / f"{ch_num:04d}.md"
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
    """Build the LLM prompt for translating one chapter.

    New v3 format: LLM outputs plain Thai paragraphs, no JSON.
    Markers in text: "..." for dialogue, 【...】 for system, 『...』 for thought.
    """
    glossary_lib = get_glossary_context_from_lib(ch_num, source=source_cleaned)

    # Use chapter-filtered glossary only
    glossary = glossary_lib if glossary_lib else "(no glossary loaded)"
    # Load continuity context from previous chapters
    continuity = get_previous_chapter_context(ch_num, n=3)

    src_cfg = LANG_CONFIG.get(get_lang_config_key(source_lang, "zh"), LANG_CONFIG["zh"])
    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)
    end_marker = bracket_profile["end_marker"]

    # Extract title
    title_match = re.search(src_cfg["title_regex"], source_text)
    cn_title = title_match.group(2).strip() if title_match else f"ch {ch_num}"

    prompt = f"""<task>
You are a Chinese→Thai novel translator specializing in web novels.
Output only the Thai translation, one paragraph per line.
</task>

<glossary>
{glossary}
</glossary>

<style>
{get_style_summary()}
</style>

<rules>
- Translate faithfully, do NOT skip or edit paragraphs
- Zero CJK characters (Chinese characters) in output
- Use straight "..." for spoken dialogue
- Use 【...】 for system/game notifications
- Use 『...』 for inner thoughts
- Keep character names consistent with glossary
- Output length similar to source length
- Translate ALL monster/skill/item names to Thai — no English
- REMOVE Chinese web novel footer (donations, thanks, author notes)
- **No English words** — translate everything including "Open Beta", "Level", "Quest" etc
- **Minimize "ก็"** — Thai reads more natural without excessive "ก็" connectors
</rules>

<continuity_context>
{continuity}
</continuity_context>

<source_chapter>
{source_text}
</source_chapter>

<now_translate>
"""

    return prompt


def build_translate_prompt_v4(
    ch_num: int,
    source_text: str,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
    slug: str = "global-descent",
    example: str = "",
) -> str:
    """Build a prompt with optimal prefix caching layout.

    ORDER (most cache-friendly):
      1. Static: task, style rules, format rules (IDENTICAL every call)
      2. Semi-static: full glossary (same per novel, not per-chapter filtered)
      3. Dynamic: chapter memory/TM context
      4. Most dynamic: source text

    This layout maximizes prefix caching: the first ~60% of the prompt
    is identical across all chapters of the same novel.
    """
    from glossary import load_terms, format_tm_prompt

    # Static parts (100% identical every call)
    static = """<task>
You are a Chinese→Thai novel translator specializing in web novels.
Output only the Thai translation, one paragraph per line.
</task>

<style>
{style}
</style>

<rules>
- Translate faithfully, do NOT skip or edit paragraphs
- Zero CJK characters (Chinese characters) in output
- Use straight "..." for spoken dialogue
- Use 【...】 for system/game notifications
- Use 『...』 for inner thoughts
- Keep character names consistent with glossary
- Output length similar to source length
- Translate ALL monster/skill/item names to Thai — no English
- REMOVE Chinese web novel footer (donations, thanks, author notes)
- **No English words** — translate everything including "Open Beta", "Level", "Quest" etc
- **Minimize "ก็"** — Thai reads more natural without excessive "ก็" connectors
</rules>

<glossary>
{glossary}
</glossary>
"""

    # Semi-static: full glossary (same for all chapters)
    terms = load_terms(slug)
    glossary_text = "\n".join(
        f'{t["source"]} → {t["thai"]}  ({t.get("category", "-")})'
        for t in terms[:100]
        if t.get("source") and t.get("thai")
    ) if terms else "(no glossary)"

    # Style summary
    from glossary import load_style_rules
    rules = load_style_rules(slug)
    style_text = "; ".join(
        item.get("text", "") for section in rules.values()
        for item in section
    ) if rules else "(default style)"

    # TM context (changes per chapter)
    tm_context = format_tm_prompt(slug, ch_num)

    # Build final prompt — static first, dynamic last
    prompt = static.format(style=style_text, glossary=glossary_text)

    if tm_context:
        prompt += f"\n<memory>\n{tm_context}\n</memory>\n"

    prompt += f"\n<source_chapter>\n{source_text}\n</source_chapter>\n\n<now_translate>\n"

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
    src_path = _get_source_dir() / f"{ch_num:04d}.md"
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


# ── LLM call ──


def _call_llm(prompt: str, max_retries: int = 3, system: str | None = None, timeout: int = 120,
              model_override: str | None = None) -> str:
    """Call the LLM via NovelClaw Fallback Router (preferred) or legacy api.py.

    Router handles Z.AI → OpenRouter fallback chain with circuit breaker,
    output validation, and per-model logging.

    Args:
        prompt: The user text to send.
        max_retries: Ignored when router is used (router has its own retry).
        system: System prompt (optional).
        timeout: Overall timeout in seconds.
        model_override: Force specific model (e.g. "fallback:1" for first fallback).
    """
    # If model_override is set, use legacy call_llm (for retry scenarios)
    if model_override:
        from providers import call_llm as legacy_call
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exec:
            fut = exec.submit(legacy_call, prompt, max_retries, system, model_override)
            try:
                return fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print(f"✗ LLM timeout after {timeout}s")
                return '{"mock": "no LLM configured"}'
            except RuntimeError as e:
                print(f"✗ LLM error after all retries: {e}")
                print("⏭ Falling back to mock output...")
                return '{"mock": "no LLM configured"}'
            except Exception as e:
                print(f"✗ Unexpected LLM error: {e}")
                print("⏭ Falling back to mock output...")
                return '{"mock": "no LLM configured"}'

    # Default: use the NovelClaw LLM Router (translate_fast profile)
    try:
        from llm_router.router import call_profile

        # Use ThreadPoolExecutor to enforce overall timeout
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exec:
            fut = exec.submit(
                call_profile,
                "translate_fast",
                prompt,
                system,
            )
            try:
                result = fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print(f"✗ Router timeout after {timeout}s — falling back to mock")
                return '{"mock": "no LLM configured"}'

        if result.ok:
            print(f"  ✅ Router: {result.provider}:{result.model} ({result.elapsed_sec:.1f}s, {len(result.text)} chars)")
            return result.text

        # Router completely failed
        print(f"  ⚠ Router failed: {result.error}")
        # Write last-attempt info for debugging
        for attempt in result.attempts[-3:]:
            print(f"    → {attempt.get('provider', '?')}:{attempt.get('model', '?')} = "
                  f"{attempt.get('status', '?')} ({attempt.get('error', '')[:60]})")
        print("  ⏭ Falling back to mock output...")
        return '{"mock": "no LLM configured"}'
    except ImportError as e:
        print(f"  ⚠ llm_router not available ({e}) — using legacy call_llm")
        from providers import call_llm as legacy_call
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exec:
            fut = exec.submit(legacy_call, prompt, max_retries, system)
            try:
                return fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print(f"✗ LLM timeout after {timeout}s")
                return '{"mock": "no LLM configured"}'
    except Exception as e:
        print(f"✗ Router unexpected error: {e} — falling back to mock")
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
        "schema_version": 3,
        "num": ch_num,
        "title": title,
        "paragraphs": [narration_text, bracket_profile["end_marker"]],
        "source": f"ch {ch_num}",
        "notes": ["[MOCK] generated by translate.py --mock - needs real LLM translation"],
        "lang": normalize_language_key(source_lang, "cn"),
        "output_lang": normalize_language_key(target_lang, "th"),
    }


def parse_translation_output(output: str, ch_num: int) -> dict:
    """Parse LLM plain-text output into paragraphs format (no JSON).

    LLM outputs plain Thai text with:
    - "..." for dialogue
    - 【...】 for system notifications
    - 『...』 for inner thoughts
    - One paragraph per line

    Returns dict with paragraphs field ready for Chapter schema.
    """
    # Strip markdown fences if present
    output = re.sub(r"^```(?:text|markdown)?\s*\n?", "", output.strip())
    output = re.sub(r"\n?```\s*$", "", output)
    # Strip control characters
    output = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", output, flags=re.DOTALL)

    # Split by double newlines → paragraphs
    paragraphs = re.split(r"\n\n+", output.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Fallback: if LLM didn't paragraph (single giant block), split by sentences
    if len(paragraphs) <= 2 and any(len(p) > 3000 for p in paragraphs):
        giant = paragraphs[0] if paragraphs else ""
        # Split by Thai sentence endings or newlines
        parts = re.split(r"(?<=[.!?。！？])\s*|\n", giant)
        paragraphs = [p.strip() for p in parts if len(p.strip()) > 10]
        if not paragraphs:
            paragraphs = [giant]

    if not paragraphs:
        raise ValueError(f"Empty LLM output for ch{ch_num}")

    # Append end marker
    paragraphs.append("(จบบท)")

    return {
        "num": ch_num,
        "title": f"ตอนที่ {ch_num}",
        "paragraphs": paragraphs,
        "source": f"ch {ch_num}",
        "schema_version": 3,
        "lang": "cn",
        "output_lang": "th",
    }


# ── From chapter_io.py (merged) ──
def load_chapter(path) -> Chapter:
    """Load a ch from a .json file. Returns validated Chapter."""
    p = Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    return Chapter(**data)


def to_reader_canonical(ch: 'Chapter', slug: str) -> dict:
    """Convert Chapter model to reader canonical JSON format.

    Reader expects:
    {
      novelId, chapterNo, sourceLang, targetLang,
      title: {translated, source},
      status, paragraphs, updatedAt
    }
    """
    from datetime import datetime, timezone
    title_str = ch.title if isinstance(ch.title, str) else ""
    return {
        "novelId": slug,
        "chapterNo": ch.num,
        "sourceLang": "cn",
        "targetLang": "th",
        "title": {
            "translated": title_str,
            "source": "",
        },
        "status": "translated",
        "paragraphs": ch.paragraphs,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def save_chapter(ch: Chapter, path, slug: str = "global-descent") -> None:
    """Save a Chapter to a .json file using reader canonical format.

    Validates against chapter.schema.json BEFORE writing.
    Raises ValueError if schema validation fails.
    """
    p = Path(path)
    data = to_reader_canonical(ch, slug)

    # Schema validation gate — fail-fast before write
    schema_path = Path(__file__).parent / "schema" / "chapter.schema.json"
    if schema_path.exists():
        try:
            from jsonschema import Draft7Validator, FormatChecker
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator = Draft7Validator(schema, format_checker=FormatChecker())
            errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
            if errors:
                err_msgs = [f"[{' → '.join(str(p) for p in e.path)}] {e.message}" for e in errors]
                raise ValueError(
                    f"Schema validation failed for ch {ch.num}:\n"
                    + "\n".join(err_msgs)
                )
        except ImportError:
            pass  # jsonschema not installed — skip gate (degraded mode)

    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def chapter_path(novel_root, num: int) -> Path:
    """Get the canonical path for a chapter: chapters/NNNN.th.json"""
    return Path(novel_root) / 'chapters' / f'{num:04d}.th.json'


def _load_ch(path) -> Chapter:
    """Load a ch from a .json file. Returns validated Chapter."""
    p = Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    return Chapter(**data)


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
    agent_passes: int = 2,
    use_score: bool = False,
    json_mode: bool = False,
) -> bool:
    """Translate one chapter. Returns True on success.

    When json_mode=True, prints a single JSON line per chapter result
    instead of human-readable text.
    """
    normalized_source_lang = normalize_language_key(source_lang, "cn")
    normalized_target_lang = normalize_language_key(target_lang, "th")

    src_path = _get_source_dir() / f"{ch_num:04d}.md"
    out_path = CHAPTERS_DIR / f"{ch_num:04d}.th.json"

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

    placeholder_map = {}
    translate_source = source

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
        # ── LLM translate ──
        prompt = build_prompt(
            ch_num,
            translate_source,
            unknown_terms=unknown_terms,
            source_lang=source_lang,
            target_lang=target_lang,
            profile_lang=profile_lang,
            source_cleaned=source,
        )
        # Extract system prompt (rules + glossary) and user prompt (source + anchor)
        # System = everything before <continuity_context>
        # This separation uses the API's `system` field for better instruction following
        sys_end = prompt.find("<continuity_context>")
        if sys_end > 0:
            system_text = prompt[:sys_end].strip()
            user_text = prompt[sys_end:].strip()
        else:
            system_text = None
            user_text = prompt
        output = _call_llm(user_text, system=system_text)
        # Parse plain text output → paragraphs (no JSON, no parse errors)
        ch_data = parse_translation_output(output, ch_num)

    # ── Script purity gate (replaces silent CJK deletion) ──────────
    # Do NOT delete leaked characters — let retry/needs_review handle them
    paragraphs = ch_data.get("paragraphs", [])
    from qa.script_policy import detect_script_leaks as _dsl, format_leak_report as _flr
    _sl_result = _dsl(paragraphs, target_lang="th")
    if not _sl_result.ok:
        _sl_report = _flr(_sl_result)
        print(f"  ⚠️  Script leaks detected — {_sl_result.error_count} errors")
        for line in _sl_report.split("\n"):
            print(f"  {line}")
        ch_data["_warnings"] = ch_data.get("_warnings", []) + [
            f"Script leaks: {_sl_result.error_count} errors "
            f"({', '.join(f'{s}×{c}' for s,c in _sl_result.foreign_script_counts.items())})"]
        ch_data["_script_leaks"] = True

    # Validate via Pydantic schema
    # Ensure required top-level fields are set (LLM sometimes omits num)
    ch_data.setdefault("num", ch_num)
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
            # ── Save output before retry so repair can fix formatting ──
            try:
                save_chapter(ch, out_path, slug=progress_slug)
            except Exception:
                pass

            # ── Retry with translate_quality router profile ───────────
            fallback_retried = False
            print(f"  ⚠ Quality gate failed — retrying with translate_quality profile (router)")
            fb_prompt = build_prompt(
                ch_num,
                translate_source,
                unknown_terms=unknown_terms,
                source_lang=source_lang,
                target_lang=target_lang,
                profile_lang=profile_lang,
                source_cleaned=source,
            )
            sys_end = fb_prompt.find("<continuity_context>")
            if sys_end > 0:
                fb_system = fb_prompt[:sys_end].strip()
                fb_user = fb_prompt[sys_end:].strip()
            else:
                fb_system = None
                fb_user = fb_prompt

            # Use llm_router with translate_quality profile
            import concurrent.futures
            fb_result = None
            try:
                from llm_router.router import call_profile
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exec:
                    fut = exec.submit(call_profile, "translate_quality", fb_user, fb_system)
                    fb_result = fut.result(timeout=120)
            except ImportError:
                from providers import call_llm as legacy_call
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exec:
                    fut = exec.submit(legacy_call, fb_user, 3, fb_system, "fallback:1")
                    fb_raw = fut.result(timeout=120)
                fb_result = type('obj', (object,), {'ok': True, 'text': fb_raw})()

            if fb_result and fb_result.ok:
                fb_output = fb_result.text
                print(f"  ✅ Router (translate_quality): {fb_result.provider}:{fb_result.model}")
            else:
                print("  ⚠ Router translate_quality failed — using mock")
                fb_output = '{"mock": "no LLM configured"}'

            fb_ch_data = parse_translation_output(fb_output, ch_num) if not fb_output.startswith('{"mock"') else None
            if fb_ch_data:
                fb_paragraphs = fb_ch_data.get("paragraphs", [])
                # Check script purity on retry output
                from qa.script_policy import detect_script_leaks as _dsl2
                if not _dsl2(fb_paragraphs, target_lang="th").ok:
                    print(f"  ⚠️  Retry also has script leaks — marking needs_review")
                    fb_ch_data["_warnings"] = fb_ch_data.get("_warnings", []) + ["Script leaks after retry"]
                fb_ch_data.setdefault("num", ch_num)
                fb_ch_data.setdefault("lang", normalized_source_lang)
                fb_ch_data["output_lang"] = normalized_target_lang
                try:
                    ch = Chapter(**fb_ch_data)
                    fb_quality_ok, fb_quality_messages = validate_translation_quality(
                        ch, source,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        profile_lang=profile_lang,
                    )
                    if fb_quality_ok:
                        paragraph_blocks = fb_ch_data.get("paragraphs", [])
                        ch_data = fb_ch_data
                        quality_messages = ["✅ Fallback retry passed quality gate"]
                        fallback_retried = True
                        print(f"  ✅ ch{ch_num}: quality retry passed via translate_quality profile")
                    else:
                        print(f"  ⚠ translate_quality also failed quality gate — reporting original failure")
                except Exception as e:
                    print(f"  ⚠ translate_quality also failed schema: {str(e)[:200]}")
            else:
                print(f"  ⚠ translate_quality parse failed — reporting original failure")

            if not fallback_retried:
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

    save_chapter(ch, out_path, slug=progress_slug)
    n = len(ch.paragraphs) if ch.paragraphs else (len(ch.blocks) if ch.blocks else 0)
    if json_mode:
        import json as _json
        print(_json.dumps({"status": "ok", "ch": ch_num, "paragraphs": n,
                            "path": str(out_path)}, ensure_ascii=False))
    else:
        print(f"✓ ch{ch_num}: saved → {out_path.name} ({n} paragraphs)")
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
    ap.add_argument("--no-progress", action="store_true", help="Skip progress tracking")
    ap.add_argument("--dry-run", action="store_true", help="Show context only, no save")
    ap.add_argument("--context", action="store_true", help="Print full context")
    ap.add_argument("--search", type=str, metavar="TERM", help="Search Thai for a CN term")
    ap.add_argument("--search-unknown", action="store_true", help="Extract unknown CN terms")
    ap.add_argument("--source-lang", "--from", default="zh", help="Source language key")
    ap.add_argument("--target-lang", "--to", default="th", help="Target language key. Short: --to.")
    ap.add_argument(
        "--profile-lang",
        default=None,
        help="Override output/profile language for validation/rendering (e.g. th, en)",
    )
    ap.add_argument(
        "--score",
        action="store_true",
        help="Enable LLM-as-Judge quality scoring after translation",
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
    args = ap.parse_args()

    # Term search mode
    if args.search:
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
                    use_score=args.score,
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
                use_score=args.score,
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
