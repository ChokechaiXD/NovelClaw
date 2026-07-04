#!/usr/bin/env python3
"""
pipeline.py — NovelClaw Translation Assembly Line

สายพานการผลิต 7 สถานี:
  Station 1: รับวัตถุดิบ (read source)
  Station 2: ทำความสะอาด (clean source)
  Station 3: ประกอบคำสั่ง (build prompt)
  Station 4: ส่งผลิต (call LLM)
  Station 5: แยกชิ้นงาน (parse output)
  Station 6: ตรวจสอบ (classify + quality gate)
  Station 7: ประกอบ+แพค (format + save)

Usage (via novelclaw.py CLI):
    python novelclaw.py translate 130
    python novelclaw.py translate 130-150
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = Path(__file__).parent

sys.path.insert(0, str(_TOOLS_DIR))

from classifier import classify_and_format, estimate_type_ratios  # noqa: E402
from atomic_io import atomic_write_json  # noqa: E402
from llm_rate_limit import limit_llm_call  # noqa: E402
from prompt_builder import build_prompt, get_lang_config  # noqa: E402
from scorer import PASS_THRESHOLD  # noqa: E402
from source_cleaner import clean_source  # noqa: E402
from quality_gate import evaluate_translation_quality  # noqa: E402
from glossary_pre import build_glossary_pre_chunk  # noqa: E402
from glossary_discovery import discover_and_save  # noqa: E402
from source_profile import build_source_profile, resolve_source_lang  # noqa: E402

# ── Station 1: Source Reader ─────────────────────────────────────────

_SOURCE_DIR = _PROJECT_ROOT / "novels" / "global-descent" / "chapters" / "source"
_CHAPTER_DIR = _PROJECT_ROOT / "novels" / "global-descent" / "chapters"

def read_source(ch_num: int, slug: str = "global-descent") -> str | None:
    """Station 1: Read source file. Supports .md and .cn.json."""
    src_dir = _PROJECT_ROOT / "novels" / slug / "chapters" / "source"
    src_json = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{ch_num:04d}.cn.json"

    if src_json.exists():
        data = json.loads(src_json.read_text(encoding="utf-8"))
        return "\n".join(data.get("paragraphs", []))

    src_md = src_dir / f"{ch_num:04d}.md"
    if src_md.exists():
        return src_md.read_text(encoding="utf-8")

    return None


# ── Station 3: Prompt Builder ─────────────────────────────────────────

def build_translate_prompt(
    source_text: str,
    ch_num: int,
    source_lang: str = "auto",
    target_lang: str = "th",
    slug: str = "global-descent",
    glossary_text: str = "",
    continuity_text: str = "",
    prompt_profile: str = "",
    source_profile: dict[str, Any] | None = None,
) -> str:
    """Station 3: Build prompt using prompt_builder + glossary_pre (char names)."""
    # Inject character voice map from glossary_pre
    char_context = build_glossary_pre_chunk(slug)
    if char_context:
        if glossary_text:
            glossary_text = char_context + "\n\n" + glossary_text
        else:
            glossary_text = char_context

    return build_prompt(
        source_text=source_text,
        ch_num=ch_num,
        source_lang=source_lang,
        target_lang=target_lang,
        novel_title=slug,
        glossary_text=glossary_text,
        continuity_text=continuity_text,
        profile=prompt_profile,
        source_profile=source_profile,
    )


# ── Station 4: LLM Caller (Direct HTTP) ──────────────────────────────

def _get_active_config(provider_name: str | None = None) -> dict[str, Any]:
    """Get active provider + model from config_providers."""
    from llm_router.config_providers import get_provider_config

    cfg = get_provider_config()
    active = provider_name or cfg.get("active", "openrouter")
    providers = cfg.get("providers", {})
    pcfg = providers.get(active, {})
    base_url = pcfg.get("base_url", "https://openrouter.ai/api/v1")
    api_key = pcfg.get("api_key", "")
    default_model = cfg.get("default_model", "google/gemma-4-26b-a4b-it:free")
    discovery_model = cfg.get("discovery_model", default_model)
    timeout = pcfg.get("timeout_sec", 90)
    max_tokens = pcfg.get("max_tokens", 4096)
    temperature = pcfg.get("temperature", 0.28)

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": default_model,
        "discovery_model": discovery_model,
        "timeout": timeout,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "provider_name": active,
    }


def call_llm(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    timeout: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[str, str, str]:
    """Station 4: Direct HTTP call to LLM provider.

    Returns:
        (response_text, provider_name, model_name)
    """
    cfg = _get_active_config(provider)
    if model:
        cfg["model"] = model
    if timeout is not None:
        cfg["timeout"] = timeout
    if max_tokens is not None:
        cfg["max_tokens"] = max_tokens
    if temperature is not None:
        cfg["temperature"] = temperature

    base_url = cfg["base_url"].rstrip("/")
    api_key = cfg["api_key"]
    model_name = cfg["model"]
    timeout_sec = cfg.get("timeout", 90)
    max_tok = cfg.get("max_tokens", 4096)
    temp = cfg.get("temperature", 0.28)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    url = f"{base_url}/chat/completions"
    body = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tok,
        "temperature": temp,
    }

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )

    try:
        with limit_llm_call(cfg["provider_name"]):
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode())
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content, cfg["provider_name"], model_name
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500] if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}") from e


# ── Station 5: Output Parser ──────────────────────────────────────────

def parse_output(output: str, ch_num: int) -> list[str]:
    """Station 5: Parse LLM plain text → list of paragraph strings."""
    # Strip markdown fences
    output = re.sub(r"^```[A-Za-z0-9_-]*\s*\n?", "", output.strip())
    output = re.sub(r"\n?```\s*$", "", output)
    # Strip control chars
    output = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", output)
    # Normalize line endings
    output = output.replace("\r\n", "\n")
    # Split by double newlines
    paragraphs = re.split(r"\n\n+", output.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Post-processing: split mixed paragraphs (narration + dialogue in same block)
    # LLM often puts narration and dialogue in the same \\n\\n block separated by \\n
    # e.g. "เฉาซิงลอบคิดในใจ\n\"ต้องใช้เวลา 45 นาที\""
    mixed = []
    for p in paragraphs:
        has_quote = '"' in p or '\u201c' in p or '\u201d' in p
        has_non_quote_text = bool(re.sub(r'[\s"\\u201c\\u201d\\u300c\\u300d]', '', p))
        if has_quote and has_non_quote_text and '\n' in p:
            # Split by single newline to separate narration from dialogue
            lines = [l.strip() for l in p.split('\n') if l.strip()]
            # Group consecutive lines of same type (quoted vs unquoted)
            for line in lines:
                mixed.append(line)
        else:
            mixed.append(p)
    paragraphs = mixed

    # Fallback: if too few paragraphs but text is long, split by single newline
    if len(paragraphs) <= 2 and any(len(p) > 2000 for p in paragraphs):
        giant = paragraphs[0] if paragraphs else ""
        parts = re.split(r"(?<=[.!?。！？])\s*|\n", giant)
        paragraphs = [p.strip() for p in parts if len(p.strip()) > 10]

    if not paragraphs:
        raise ValueError(f"Empty LLM output for ch {ch_num}")

    return paragraphs


# ── Station 5.5: Glossary Post-Process ──────────────────────────────────

def apply_glossary_post(
    paragraphs: list[str], target_lang: str = "th"
) -> list[str]:
    """Apply term_policy to replace known term tokens.

    LLM translates freely → Python ensures glossary compliance.
    This covers skill/item/system terms. Character names are handled
    via prompt injection (Station 3), not here.

    Returns modified paragraph list.
    """
    try:
        from qa.term_policy import get_term_policy

        tp = get_term_policy(target_lang)
        result = []
        for para in paragraphs:
            if para in ("(จบบท)", "(End)", "（終）", "(끝)"):
                result.append(para)
                continue
            applied = tp.apply_to_text(para)
            result.append(applied.text)
        return result
    except ImportError:
        return paragraphs


# ── Station 6.5: Scorer ─────────────────────────────────────────────────

def _score_and_report(
    classified: list[dict[str, str]],
    source_text: str,
    target_lang: str = "th",
    threshold: float = PASS_THRESHOLD,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score translation quality. Returns result dict with pass/fail."""
    return evaluate_translation_quality(classified, source_text, target_lang, threshold, source_profile)


def _build_repair_instruction(score_result: dict[str, Any]) -> str:
    notes = score_result.get("repair_notes") or score_result.get("errors") or []
    if not notes:
        return ""
    lines = [
        "",
        "",
        "<repair>",
        "The previous translation failed the deterministic quality gate.",
        "Rewrite the full chapter and fix these issues before returning the final Thai text:",
    ]
    lines.extend(f"- {note}" for note in notes[:5])
    lines.append("</repair>")
    return "\n".join(lines)


def _quality_summary(
    score_result: dict[str, Any],
    attempts: list[dict[str, Any]],
    judge_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "passed": bool(score_result.get("passed")),
        "score": score_result.get("score", 0),
        "threshold": score_result.get("threshold", PASS_THRESHOLD),
        "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
        "warnings": score_result.get("warnings", []),
        "repairNotes": score_result.get("repairNotes", score_result.get("repair_notes", [])),
        "lengthRatio": score_result.get("lengthRatio", 0.0),
        "scriptLeaks": score_result.get("scriptLeaks", 0),
        "structure": score_result.get("structure", {}),
        "judge": judge_result or {},
        "repairHistory": attempts,
        "attempts": attempts,
    }


# ── Station 6.75: LLM Judge ────────────────────────────────────────────

_JUDGE_SYSTEM = """You are a translation quality judge. Review a Thai novel translation.
Check for:
1. Naturalness — does it read like natural Thai?
2. Consistency — are character names/pronouns consistent?
3. Clarity — is there any confusing or ambiguous phrasing?
4. Flow — does the paragraph sequence flow naturally?

Rate each 1-10. If any score < 8, provide 1-2 specific improvement suggestions.
Keep response to 3-5 lines max."""


def judge_translation(
    paragraphs: list[dict[str, str]],
    source_text: str,
    model: str | None = None,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM Judge — optional quality review after scoring passes."""
    try:
        content = [p for p in paragraphs if p.get("type") != "end"]
        sample_indexes = {0, 1, 2}
        if content:
            mid = len(content) // 2
            sample_indexes.update({max(0, mid - 1), mid, min(len(content) - 1, mid + 1)})
            sample_indexes.update({max(0, len(content) - 3), max(0, len(content) - 2), len(content) - 1})
        risky_indexes = [
            i for i, p in enumerate(content)
            if p.get("type") in {"dialogue", "system"} or re.search(r"[A-Za-z\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", p.get("text", ""))
        ][:4]
        sample_indexes.update(risky_indexes)
        text_preview = "\n".join(
            f"[{i + 1}:{content[i].get('type', 'narration')}] {content[i].get('text', '')[:180]}"
            for i in sorted(i for i in sample_indexes if 0 <= i < len(content))
        )
        structure = source_profile or {}
        prompt = f"""Review this Thai novel translation using sampled beginning/middle/end/risk paragraphs:

{text_preview}

Source (first 300 chars):
{source_text[:300]}

Source structure:
- paragraphs: {structure.get('paragraphCount', '?')}
- dialogue: {structure.get('dialogueCount', '?')}
- system markers: {structure.get('systemMarkerCount', '?')}

Rate each: Naturalness / Consistency / Clarity / Flow / Completeness
If any score < 8, start with FAIL: and give 1-2 specific repair suggestions.
Otherwise start with PASS: and keep feedback brief."""

        response, provider, model_name = call_llm(
            prompt=prompt, system=_JUDGE_SYSTEM,
            model=model, temperature=0.1, max_tokens=500,
        )
        feedback = response.strip()
        return {
            "ok": True,
            "passed": not feedback.upper().startswith("FAIL:"),
            "feedback": feedback,
            "model": model_name,
            "sampledParagraphs": len(sample_indexes),
        }
    except Exception as e:
        return {"ok": False, "passed": True, "feedback": str(e)[:200]}


def _get_title(source_text: str, ch_num: int, source_lang: str = "cn") -> str:
    """Extract chapter title from source."""
    cfg = get_lang_config(source_lang)
    title_regex = cfg.get("title_regex") or r"第\s*(\d+)\s*章\s*(.+)"
    m = re.search(title_regex, source_text[:300])
    title = m.group(2).strip() if m and m.lastindex and m.lastindex >= 2 else ""
    return f"ตอนที่ {ch_num} {title}".strip()


# ── Station 7: Save ───────────────────────────────────────────────────

def save_chapter(
    classified: list[dict[str, str]],
    ch_num: int,
    slug: str = "global-descent",
    source_text: str = "",
    source_lang: str = "cn",
    target_lang: str = "th",
    provider_name: str = "unknown",
    model_name: str = "unknown",
    prompt_profile: str = "",
    quality_record: dict[str, Any] | None = None,
    source_profile: dict[str, Any] | None = None,
) -> Path:
    """Station 7: Save classified paragraphs to .th.json."""
    chapter_dir = _PROJECT_ROOT / "novels" / slug / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)

    title = _get_title(source_text, ch_num, source_lang)

    data = {
        "novelId": slug,
        "chapterNo": ch_num,
        "sourceLang": source_lang,
        "targetLang": target_lang,
        "title": {
            "source": "",
            "translated": title,
        },
        "status": "needs_review" if quality_record and quality_record.get("passed") is False else "translated",
        "paragraphs": classified,
        "meta": {
            "provider": provider_name,
            "model": model_name,
            "promptProfile": prompt_profile or "faithful_default",
            "sourceProfile": source_profile or {},
        },
        "qualityRecord": quality_record or {},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    out_path = chapter_dir / f"{ch_num:04d}.th.json"
    atomic_write_json(out_path, data, ensure_ascii=False, indent=2)
    return out_path


# ── MASTER PIPELINE ───────────────────────────────────────────────────

def translate_one(
    ch_num: int,
    slug: str = "global-descent",
    source_lang: str = "auto",
    target_lang: str = "th",
    model_override: str | None = None,
    provider_override: str | None = None,
    prompt_profile: str = "",
    dry_run: bool = False,
    mock: bool = False,
) -> dict[str, Any]:
    """Run the full 7-station assembly line for one chapter.

    Returns:
        {"status": "ok", "ch": num, "paragraphs": N, "types": {...}, "path": "..."}
        or {"status": "failed", "ch": num, "reason": "..."}
    """
    try:
        # ── Station 1-2: Read + Clean ──
        raw = read_source(ch_num, slug)
        if raw is None:
            return {"status": "failed", "ch": ch_num, "reason": "source_not_found"}
        source_lang, source_lang_source = resolve_source_lang(raw, source_lang, slug)
        source = clean_source(raw)
        if not source:
            return {"status": "failed", "ch": ch_num, "reason": "empty_after_clean"}
        source_profile = build_source_profile(
            source,
            source_lang=source_lang,
            target_lang=target_lang,
            ch_num=ch_num,
            lang_source=source_lang_source,
        )

        if dry_run:
            return {
                "status": "dry_run", "ch": ch_num,
                "source_preview": source[:300],
                "source_chars": len(source),
                "sourceLang": source_lang,
                "sourceProfile": source_profile,
            }

        # ── Station 3: Build Prompt ──
        prompt = build_translate_prompt(
            source_text=source,
            ch_num=ch_num,
            source_lang=source_lang,
            target_lang=target_lang,
            slug=slug,
            prompt_profile=prompt_profile,
            source_profile=source_profile,
        )

        if mock:
            paragraph_strings = [
                f"[MOCK] ch {ch_num} — แปลด้วย {source_lang}→{target_lang}",
                "(จบบท)",
            ]
            provider_name = "mock"
            model_name = "mock"
            classified = classify_and_format(paragraph_strings)
            score_result = {"score": 100, "passed": True, "report": "(mock)", "dimensions": {}}
            judge_result = {"ok": True, "feedback": "(mock)"}
            discovery_result = {"discovered": 0, "saved": 0, "terms": []}
        else:
            # ── Retry policy: translate once, repair once on quality fail,
            #    fallback to discovery model only on provider/empty failures. ──
            cfg = _get_active_config(provider_override)
            primary_model = model_override or cfg.get("model", "google/gemma-4-26b-a4b-it:free")
            discovery_model = cfg.get("discovery_model") or primary_model
            primary_provider = cfg.get("provider_name", provider_override or "openrouter")

            attempts: list[dict[str, Any]] = []
            last_error = "unknown"
            repair_instruction = ""
            attempt_plan = [
                {"kind": "translate", "model": primary_model, "provider": primary_provider},
                {"kind": "repair", "model": primary_model, "provider": primary_provider},
                {"kind": "fallback", "model": discovery_model, "provider": primary_provider},
            ]
            allow_repair = True
            translation_ready = False
            for attempt_cfg in attempt_plan:
                if attempt_cfg["kind"] == "repair" and not allow_repair:
                    continue
                try:
                    # ── Station 4: Call LLM ──
                    split_point = prompt.find("<continuity>")
                    if split_point < 0:
                        split_point = prompt.find("<glossary>")
                    if split_point > 0 and split_point < len(prompt):
                        system_text = prompt[:split_point].strip()
                        user_text = prompt[split_point:].strip()
                    else:
                        system_text = None
                        user_text = prompt
                    if repair_instruction:
                        user_text += repair_instruction

                    response, provider_name, model_name = call_llm(
                        prompt=user_text,
                        system=system_text,
                        model=attempt_cfg["model"],
                        provider=attempt_cfg["provider"],
                    )

                    if not response or len(response.strip()) < 10:
                        last_error = "Empty LLM output"
                        attempts.append({
                            "kind": attempt_cfg["kind"],
                            "model": attempt_cfg["model"],
                            "provider": provider_name,
                            "status": "empty_output",
                        })
                        allow_repair = False
                        continue

                    # ── Station 5: Parse ──
                    paragraph_strings = parse_output(response, ch_num)
                    if paragraph_strings[-1] != "(จบบท)":
                        paragraph_strings.append("(จบบท)")

                    # ── Station 5.5: Glossary Post-Process ──
                    paragraph_strings = apply_glossary_post(paragraph_strings, target_lang)

                    # ── Station 6: Classify ──
                    classified = classify_and_format(paragraph_strings)

                    # ── Station 6.5: Scorer ──
                    score_result = _score_and_report(classified, source, target_lang, source_profile=source_profile)
                    attempts.append({
                        "kind": attempt_cfg["kind"],
                        "model": model_name,
                        "provider": provider_name,
                        "status": "passed" if score_result["passed"] else "quality_failed",
                        "score": score_result.get("score", 0),
                        "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
                        "structure": score_result.get("structure", {}),
                    })

                    if score_result["passed"]:
                        translation_ready = True
                        break  # success!

                    last_error = f"scorer: {score_result['score']}/100 < {PASS_THRESHOLD}"
                    repair_instruction = _build_repair_instruction(score_result)

                    if attempt_cfg["kind"] == "translate" and repair_instruction:
                        continue  # one targeted repair retry

                    return {
                        "status": "needs_review", "ch": ch_num,
                        "reason": f"quality gate failed after retry: {last_error}",
                        "score": score_result.get("score", 0),
                        "quality": _quality_summary(score_result, attempts),
                        "sourceLang": source_lang,
                        "sourceProfile": source_profile,
                    }

                except Exception as e:
                    last_error = str(e)[:100]
                    attempts.append({
                        "kind": attempt_cfg["kind"],
                        "model": attempt_cfg["model"],
                        "provider": attempt_cfg["provider"],
                        "status": "error",
                        "reason": last_error,
                    })
                    allow_repair = False
                    if attempt_cfg["kind"] != "fallback":
                        continue
                    return {"status": "failed", "ch": ch_num, "reason": str(e)[:300]}

            if not translation_ready:
                return {
                    "status": "failed",
                    "ch": ch_num,
                    "reason": last_error,
                    "quality": {"attempts": attempts, "repairHistory": attempts},
                    "sourceLang": source_lang,
                    "sourceProfile": source_profile,
                }

            # ── Station 6.75: LLM Judge ──
            judge_model = model_override or cfg.get("discovery_model") or primary_model
            judge_result = judge_translation(
                classified,
                source,
                judge_model,
                source_profile=source_profile,
            )
            if judge_result.get("ok") and judge_result.get("passed") is False:
                score_result = {
                    **score_result,
                    "passed": False,
                    "hardFailures": [
                        *score_result.get("hardFailures", []),
                        "LLM Judge: sampled review flagged quality risk.",
                    ],
                    "repairNotes": [
                        *score_result.get("repairNotes", score_result.get("repair_notes", [])),
                        str(judge_result.get("feedback", ""))[:240],
                    ],
                }

            # ── Station 6.8: Auto Glossary Discovery ──
            if source:
                cfg = _get_active_config()
                discovery_result = discover_and_save(
                    source_text=source,
                    slug=slug,
                    source_lang=source_lang,
                    discovery_model=model_override or cfg.get("discovery_model"),
                )
            else:
                discovery_result = {"discovered": 0, "saved": 0, "terms": []}

        quality_record = _quality_summary(score_result, attempts if not mock else [], judge_result)
        final_status = "needs_review" if quality_record.get("passed") is False else "ok"
        out_path = save_chapter(
            classified=classified,
            ch_num=ch_num,
            slug=slug,
            source_text=source,
            source_lang=source_lang,
            target_lang=target_lang,
            provider_name=provider_name,
            model_name=model_name,
            prompt_profile=prompt_profile,
            quality_record=quality_record,
            source_profile=source_profile,
        )

        return {
            "status": final_status,
            "ch": ch_num,
            "reason": "LLM judge flagged quality risk" if final_status == "needs_review" else "",
            "paragraphs": len(classified),
            "types": estimate_type_ratios(classified),
            "path": str(out_path),
            "provider": provider_name,
            "model": model_name,
            "promptProfile": prompt_profile or "faithful_default",
            "sourceLang": source_lang,
            "sourceProfile": source_profile,
            "score": score_result["score"],
            "quality": quality_record,
            "judge": judge_result["feedback"][:200] if judge_result.get("ok") else "judge_error",
            "discovery": f"{discovery_result['discovered']} found, {discovery_result['saved']} saved" if discovery_result['discovered'] > 0 else "none",
        }

    except Exception as e:
        return {"status": "failed", "ch": ch_num, "reason": str(e)[:300]}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    import argparse

    ap = argparse.ArgumentParser(description="Test pipeline")
    ap.add_argument("ch", type=int, help="Chapter number")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--from", dest="source_lang", default="auto")
    ap.add_argument("--slug", default="global-descent")
    args = ap.parse_args()

    result = translate_one(
        ch_num=args.ch,
        slug=args.slug,
        source_lang=args.source_lang,
        dry_run=args.dry_run,
        mock=args.mock,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
