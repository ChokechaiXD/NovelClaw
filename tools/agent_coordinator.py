"""agent_coordinator.py — Multi-agent translation orchestration.

Lightweight agent chain that wraps the existing translation pipeline:

  L1: Translator   → translate_one()  (existing pipeline)
  L2: Validator    → check consistency, entity, glossary compliance
  L3: Polisher     → refine naturalness, style (optional)

Controlled via `--passes N` (1 = translate only, 2 = +validate, 3 = +polish).

Each "agent" is a self-contained LLM prompt — no complex agent framework.
The orchestrator manages the chain, passing chapter data between stages.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from providers import call_llm
from validation import (
    get_bracket_profile,
    get_profile_lang,
    normalize_language_key,
)


# ── Validator Agent Prompt ───────────────────────────────────────────

VALIDATOR_PROMPT = """You are a translation quality validator for web novels (Chinese → Thai). Review the following translation and identify issues.

### Source (Chinese):
```text
{source_text}
```

### Translation (Thai) — JSON blocks:
```json
{chapter_json}
```

### Glossary terms (must use EXACTLY these Thai translations):
```text
{glossary_summary}
```

### What to check (in priority order):
1. **Entity consistency** — Are character names, place names, skill names consistent?
2. **Glossary compliance** — Are glossary terms used exactly as specified?
3. **CJK leakage** — Are there any remaining Chinese/Japanese/Korean characters in narration/dialogue/system blocks? (Block type `end` is exempt.)
4. **EN retention** — Are English words like "level", "recruiting", "continue" kept instead of translated to Thai?
5. **Hallucination** — Is there any content that doesn't exist in the source?
6. **End marker** — Is the last block exactly "{end_marker}" (type: "end")?
7. **Fluency** — Does the Thai feel natural? Identify any awkward phrasings.
8. **Completeness** — Is all source content preserved? Look for truncated or missing blocks.

### Output format (EXACT JSON, no markdown):
```json
{{
  "validation_summary": "<brief 1-2 sentence summary>",
  "issues": [
    {{
      "severity": "critical|major|minor|info",
      "category": "entity|glossary|cjk|en_retention|hallucination|end_marker|fluency|completeness",
      "block_index": <int, 0-based, or null>,
      "detail": "<specific issue description>",
      "suggestion": "<how to fix>"
    }}
  ],
  "can_auto_fix": <true|false>,
  "auto_fix_rules": [<list of simple find-replace rules, if can_auto_fix>]
}}
```

Respond ONLY with the JSON block. No other text."""


def _build_validator_prompt(
    source_text: str,
    chapter_data: dict[str, Any],
    glossary_terms: list[dict[str, Any]] | None = None,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> str:
    """Build validator agent prompt."""
    # Source (truncated)
    src = source_text[:2000]
    if len(source_text) > 2000:
        src += "\n...(truncated)"

    # Chapter JSON preview
    blocks = chapter_data.get("blocks", [])
    preview_blocks = []
    for i, b in enumerate(blocks[:40]):
        preview_blocks.append({"index": i, "type": b.get("type"), "text": b.get("text", "")[:200]})
    ch_json = {
        "num": chapter_data.get("num"),
        "title": chapter_data.get("title", ""),
        "blocks": preview_blocks,
        "lang": chapter_data.get("lang"),
        "output_lang": chapter_data.get("output_lang"),
    }
    if len(blocks) > 40:
        ch_json["_note"] = f"(...{len(blocks) - 40} more blocks truncated)"

    # Glossary summary
    if glossary_terms:
        locked = [t for t in glossary_terms if t.get("lock") == "locked"][:15]
        ref = [t for t in glossary_terms if t.get("lock") == "reference"][:10]
        glines = []
        for t in locked:
            glines.append(f"- {t['source']} → {t.get('thai', '?')}")
        if ref:
            glines.append("\n# Reference terms:")
            for t in ref:
                glines.append(f"- {t['source']} → {t.get('thai', '?')}")
        glossary_summary = "\n".join(glines) if glines else "(none specifically relevant)"
    else:
        glossary_summary = "(no glossary loaded)"

    # End marker
    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)
    end_marker = bracket_profile.get("end_marker", "(จบบท)")

    return VALIDATOR_PROMPT.format(
        source_text=src,
        chapter_json=json.dumps(ch_json, ensure_ascii=False, indent=2)[:3000],
        glossary_summary=glossary_summary[:1000],
        end_marker=end_marker,
    )


# ── Polisher Agent Prompt ────────────────────────────────────────────

POLISHER_PROMPT = """You are a Thai literary editor specializing in web novel translation. Polish the following translation to make it more natural and fluent while preserving ALL content.

### Rules:
1. Do NOT add, remove, or change any meaning from the source.
2. Do NOT change character names, place names, or fixed terminology.
3. Focus on: natural Thai phrasing, improved flow, better word choice.
4. Maintain the same block structure (same number of blocks).
5. Keep the exact same block types (narration/dialogue/system/end).
6. Keep the end marker exactly as "{end_marker}".
7. Preserve ALL dialogue quotes exactly as they are (do not change 「」 to "" or vice versa).
8. Preserve ALL speaker attributions if present.

### Source (Chinese):
```text
{source_text}
```

### Current Translation (Thai):
```json
{chapter_json}
```

### Output format (EXACT JSON — the entire chapter JSON with polished text):
```json
{{
  "schema_version": <int>,
  "num": <int>,
  "title": "<title>",
  "lang": "<lang>",
  "output_lang": "<output_lang>",
  "blocks": [
    {{"type": "narration", "text": "<polished text>"}},
    ...
    {{"type": "end", "text": "{end_marker}"}}
  ],
  "source": "<source>"
}}
```

Respond ONLY with the JSON block. No other text."""


def _build_polisher_prompt(
    source_text: str,
    chapter_data: dict[str, Any],
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
) -> str:
    """Build polisher agent prompt."""
    src = source_text[:1500]
    if len(source_text) > 1500:
        src += "\n...(truncated)"

    # Show blocks compactly
    blocks = chapter_data.get("blocks", [])
    preview = blocks[:30]
    ch_json = {
        "schema_version": chapter_data.get("schema_version", 2),
        "num": chapter_data.get("num"),
        "title": chapter_data.get("title", ""),
        "lang": chapter_data.get("lang"),
        "output_lang": chapter_data.get("output_lang"),
        "blocks": [
            {"type": b.get("type"), "text": b.get("text", "")}
            for b in preview
        ],
        "source": chapter_data.get("source"),
    }
    if len(blocks) > 30:
        ch_json["_note"] = f"(...{len(blocks) - 30} more blocks)"

    bracket_profile = get_bracket_profile(source_lang, target_lang, profile_lang)
    end_marker = bracket_profile.get("end_marker", "(จบบท)")

    return POLISHER_PROMPT.format(
        source_text=src,
        chapter_json=json.dumps(ch_json, ensure_ascii=False, indent=2)[:4000],
        end_marker=end_marker,
    )


# ── Agent Result ─────────────────────────────────────────────────────

class AgentResult:
    """Result from a single agent pass."""
    
    def __init__(
        self,
        agent_name: str,
        success: bool,
        chapter_data: dict[str, Any] | None = None,
        issues: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ):
        self.agent_name = agent_name
        self.success = success
        self.chapter_data = chapter_data
        self.issues = issues or []
        self.error = error


# ── Agent Functions ──────────────────────────────────────────────────

def translator_agent(
    translate_fn: Callable,
    ch_num: int,
    source_lang: str = "zh",
    target_lang: str = "th",
    **kwargs: Any,
) -> AgentResult:
    """Agent L1: Translate chapter using the existing pipeline.

    Args:
        translate_fn: Callable that takes (ch_num, **kwargs) and returns bool
        ch_num: Chapter number
        **kwargs: Additional args for translate_one (mock, no_validate, etc.)

    Returns:
        AgentResult with success flag
    """
    try:
        success = translate_fn(ch_num, **kwargs)
        return AgentResult("translator", success, error=None if success else "Translation failed")
    except Exception as e:
        return AgentResult("translator", False, error=str(e))


def validator_agent(
    source_text: str,
    chapter_data: dict[str, Any] | None,
    glossary_terms: list[dict[str, Any]] | None = None,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
    mock: bool = True,
    model: str = "haiku",
) -> AgentResult:
    """Agent L2: Validate translation quality via LLM review.

    Args:
        source_text: Cleaned source text
        chapter_data: Chapter dict from translator
        glossary_terms: Glossary terms for compliance check
        mock: Use mock validator (always passes)
        model: LLM model for validation

    Returns:
        AgentResult with issues list
    """
    if not chapter_data:
        return AgentResult("validator", False, error="No chapter data to validate")

    if mock:
        # Mock: always passes unless obvious issues
        issues = []
        blocks = chapter_data.get("blocks", [])
        
        # Check end marker exists
        if blocks and blocks[-1].get("type") != "end":
            issues.append({
                "severity": "critical",
                "category": "end_marker",
                "block_index": len(blocks) - 1,
                "detail": "Last block is not an end marker",
                "suggestion": "Add end marker block",
            })
        
        return AgentResult("validator", True if not issues else False, 
                          chapter_data=chapter_data, issues=issues)

    try:
        prompt = _build_validator_prompt(
            source_text, chapter_data, glossary_terms,
            source_lang, target_lang, profile_lang,
        )
        output = call_llm(prompt)

        # Parse response
        cleaned = output.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            return AgentResult("validator", True, chapter_data=chapter_data,
                              error="No JSON in validator response")

        data = json.loads(cleaned[start:end + 1])
        issues = data.get("issues", [])
        
        # Auto-fix: apply simple find-replace rules if available
        can_auto_fix = data.get("can_auto_fix", False)
        result_data = chapter_data
        if can_auto_fix and data.get("auto_fix_rules"):
            rules = data["auto_fix_rules"]
            for rule in rules:
                old = rule.get("old", "")
                new = rule.get("new", "")
                block_idx = rule.get("block_index")
                if old and new and block_idx is not None:
                    blocks = result_data.get("blocks", [])
                    if 0 <= block_idx < len(blocks):
                        text = blocks[block_idx].get("text", "")
                        blocks[block_idx]["text"] = text.replace(old, new)

        has_critical = any(i.get("severity") in ("critical", "major") for i in issues)
        return AgentResult("validator", not has_critical, 
                          chapter_data=result_data, issues=issues)

    except Exception as e:
        return AgentResult("validator", True, chapter_data=chapter_data,
                          error=f"Validation error: {e}")


def polisher_agent(
    source_text: str,
    chapter_data: dict[str, Any] | None,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
    mock: bool = True,
    model: str = "haiku",
) -> AgentResult:
    """Agent L3: Polish translation for naturalness.

    Args:
        source_text: Cleaned source text
        chapter_data: Chapter dict from previous agent
        mock: Use mock polisher (no-op)
        model: LLM model for polishing

    Returns:
        AgentResult with refined chapter_data
    """
    if not chapter_data:
        return AgentResult("polisher", False, error="No chapter data to polish")

    if mock:
        return AgentResult("polisher", True, chapter_data=chapter_data)

    try:
        prompt = _build_polisher_prompt(
            source_text, chapter_data, source_lang, target_lang, profile_lang,
        )
        output = call_llm(prompt)

        # Parse the full chapter JSON response
        cleaned = output.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            return AgentResult("polisher", True, chapter_data=chapter_data,
                              error="No JSON in polisher response")

        polished_data = json.loads(cleaned[start:end + 1])

        # Validate structure
        if not polished_data.get("blocks"):
            return AgentResult("polisher", True, chapter_data=chapter_data,
                              error="Polisher returned no blocks")

        # Verify end marker preserved
        if polished_data["blocks"][-1].get("type") != "end":
            # Keep original end marker
            polished_data["blocks"][-1] = chapter_data["blocks"][-1]

        return AgentResult("polisher", True, chapter_data=polished_data)

    except Exception as e:
        return AgentResult("polisher", True, chapter_data=chapter_data,
                          error=f"Polish error: {e}")


# ── Orchestrator ─────────────────────────────────────────────────────

INVALIDATE_ON_CRITICAL = True  # If True, stop chain on critical validator issues


def run_agent_chain(
    ch_num: int,
    translate_fn: Callable,
    source_text: str,
    chapter_data: dict[str, Any] | None,
    glossary_terms: list[dict[str, Any]] | None = None,
    passes: int = 1,
    source_lang: str = "zh",
    target_lang: str = "th",
    profile_lang: str | None = None,
    mock: bool = True,
    model: str = "haiku",
    **translate_kwargs: Any,
) -> tuple[bool, list[AgentResult], dict[str, Any] | None]:
    """Run the full multi-agent chain for a chapter.

    Passes:
      1: Translate only
      2: Translate → Validate (stop on critical issues)
      3: Translate → Validate → Polish

    Args:
        ch_num: Chapter number
        translate_fn: translate_one (or mock)
        source_text: Cleaned source text
        chapter_data: Pre-existing chapter data (None if new translation)
        glossary_terms: Optional glossary terms for validation
        passes: Number of agent passes (1-3)
        mock: Use mock agents (cheap, no LLM calls)
        model: LLM model for agents
        **translate_kwargs: Additional kwargs for translate_one

    Returns:
        (overall_success, agent_results_list, final_chapter_data_or_None)
    """
    results: list[AgentResult] = []
    current_chapter: dict[str, Any] | None = chapter_data

    # L1: Translator
    if passes >= 1 and current_chapter is None:
        r1 = translator_agent(translate_fn, ch_num, source_lang, target_lang, **translate_kwargs)
        results.append(r1)
        if not r1.success:
            return False, results, None
        # Load the chapter data from disk (translate_one saved it)
        from constants import CHAPTERS_DIR
        json_path = CHAPTERS_DIR / f"{ch_num:04d}.json"
        if json_path.exists():
            current_chapter = json.loads(json_path.read_text(encoding="utf-8"))
    
    # L2: Validator
    if passes >= 2 and current_chapter:
        r2 = validator_agent(
            source_text, current_chapter, glossary_terms,
            source_lang, target_lang, profile_lang, mock=mock, model=model,
        )
        results.append(r2)
        if r2.chapter_data:
            current_chapter = r2.chapter_data
        if INVALIDATE_ON_CRITICAL and not r2.success:
            # Save validator findings alongside chapter
            from constants import CHAPTERS_DIR
            from chapter_io import save_chapter
            from schema import Chapter
            try:
                ch = Chapter(**current_chapter)
                save_chapter(ch, CHAPTERS_DIR / f"{ch_num:04d}.json")
            except Exception:
                pass
            return False, results, current_chapter
    
    # L3: Polisher
    if passes >= 3 and current_chapter:
        r3 = polisher_agent(
            source_text, current_chapter,
            source_lang, target_lang, profile_lang, mock=mock, model=model,
        )
        results.append(r3)
        if r3.chapter_data:
            current_chapter = r3.chapter_data
            # Save polished version
            try:
                from constants import CHAPTERS_DIR
                from chapter_io import save_chapter
                from schema import Chapter
                ch = Chapter(**current_chapter)
                save_chapter(ch, CHAPTERS_DIR / f"{ch_num:04d}.json")
            except Exception as e:
                results.append(AgentResult("polisher", True, chapter_data=current_chapter,
                                          error=f"Save failed: {e}"))
    
    return True, results, current_chapter


def print_agent_report(results: list[AgentResult]) -> None:
    """Print a human-readable agent chain report."""
    for r in results:
        status = "✅" if r.success else "❌"
        issue_count = len(r.issues)
        error_msg = f" — {r.error[:100]}" if r.error else ""
        print(f"  {status} {r.agent_name}: {'pass' if r.success else 'fail'}"
              f"{f' ({issue_count} issues)' if issue_count else ''}{error_msg}")
        
        # Show top issues
        for issue in r.issues[:3]:
            sev = issue.get("severity", "info")
            cat = issue.get("category", "?")
            detail = issue.get("detail", "")[:80]
            print(f"    [{sev}/{cat}] {detail}")
        if len(r.issues) > 3:
            print(f"    ... and {len(r.issues) - 3} more issues")
