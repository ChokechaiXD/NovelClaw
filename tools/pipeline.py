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
import os
import re
import sys
import time
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
from prompt_builder import build_prompt  # noqa: E402

# ── Station 1: Source Reader ─────────────────────────────────────────

_SOURCE_DIR = _PROJECT_ROOT / "novels" / "global-descent" / "chapters" / "source"
_CHAPTER_DIR = _PROJECT_ROOT / "novels" / "global-descent" / "chapters"

_SOURCE_ARTIFACT_RE = re.compile(
    r"(?:ขอบคุณ|感谢|หน้าที่|上一頁|下一頁|หน้าแรก|ลงทะเบียน|สมัครสมาชิก)"
    r"|(?:Loading|กำลังโหลด)"
)


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


# ── Station 2: Source Cleaner ────────────────────────────────────────

def clean_source(raw: str) -> str:
    """Station 2: Remove artifacts, line numbers, site noise."""
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
            if _SOURCE_ARTIFACT_RE.search(stripped):
                continue
            in_body = True
        if _SOURCE_ARTIFACT_RE.search(stripped):
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"([！？。，；：…—])\s*(\d{1,3})(?=\s|$)", r"\1", text)
    text = re.sub(r"^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Station 3: Prompt Builder ─────────────────────────────────────────

def build_translate_prompt(
    source_text: str,
    ch_num: int,
    source_lang: str = "cn",
    target_lang: str = "th",
    slug: str = "global-descent",
    glossary_text: str = "",
    continuity_text: str = "",
) -> str:
    """Station 3: Build prompt using prompt_builder."""
    return build_prompt(
        source_text=source_text,
        ch_num=ch_num,
        source_lang=source_lang,
        target_lang=target_lang,
        novel_title=slug,
        glossary_text=glossary_text,
        continuity_text=continuity_text,
    )


# ── Station 4: LLM Caller (Direct HTTP) ──────────────────────────────

def _get_active_config() -> dict[str, Any]:
    """Get active provider + model from config_providers."""
    from llm_router.config_providers import get_provider_config

    cfg = get_provider_config()
    active = cfg.get("active", "openrouter")
    providers = cfg.get("providers", {})
    pcfg = providers.get(active, {})
    base_url = pcfg.get("base_url", "https://openrouter.ai/api/v1")
    api_key = pcfg.get("api_key", "")
    default_model = cfg.get("default_model", "google/gemma-4-26b-a4b-it:free")
    timeout = pcfg.get("timeout_sec", 90)
    max_tokens = pcfg.get("max_tokens", 4096)
    temperature = pcfg.get("temperature", 0.28)

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": default_model,
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
    cfg = _get_active_config()
    if model:
        cfg["model"] = model
    if provider:
        cfg["base_url"] = provider
    if timeout:
        cfg["timeout"] = timeout

    base_url = cfg["base_url"].rstrip("/")
    api_key = cfg["api_key"]
    model_name = cfg["model"]
    timeout_sec = cfg.get("timeout", 90)
    max_tok = max_tokens or cfg.get("max_tokens", 4096)
    temp = temperature or cfg.get("temperature", 0.28)

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
    output = re.sub(r"^```(?:text|markdown)?\s*\\n?", "", output.strip())
    output = re.sub(r"\\n?```\s*$", "", output)
    # Strip control chars
    output = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", output)
    # Normalize line endings
    output = output.replace("\r\n", "\n")
    # Split by double newlines
    paragraphs = re.split(r"\n\n+", output.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Fallback: if too few paragraphs but text is long, split by single newline
    if len(paragraphs) <= 2 and any(len(p) > 2000 for p in paragraphs):
        giant = paragraphs[0] if paragraphs else ""
        parts = re.split(r"(?<=[.!?。！？])\s*|\n", giant)
        paragraphs = [p.strip() for p in parts if len(p.strip()) > 10]

    if not paragraphs:
        raise ValueError(f"Empty LLM output for ch {ch_num}")

    return paragraphs


# ── Station 6: Quality Gate (lightweight) ─────────────────────────────

def _quick_script_check(paragraphs: list[dict[str, str]], target_lang: str = "th") -> list[str]:
    """Quick script purity check — catch obvious leaks."""
    from qa.script_policy import detect_script_leaks

    texts = [p["text"] for p in paragraphs if p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not texts:
        return []

    try:
        from qa.term_policy import get_term_policy

        tp = get_term_policy(target_lang)
        allowed = tp.preserve_tokens | {t.upper() for t in tp.terms.keys()}
    except ImportError:
        allowed = set()

    # Run pattern-based preservation
    full_text = "\n".join(texts)
    if tp:
        for patterns in tp.preserve_patterns.values():
            for pat in patterns:
                for m in pat.finditer(full_text):
                    allowed.add(m.group(0))
                    allowed.add(m.group(0).upper())

    result = detect_script_leaks(texts, target_lang=target_lang, allowed_latin_tokens=allowed)
    if result.ok:
        return []
    return [
        f"{leak.script}: '{leak.token}'" for leak in result.leaks[:5]
    ]


def _get_title(source_text: str, ch_num: int) -> str:
    """Extract chapter title from source."""
    m = re.search(r"第\s*(\d+)\s*章\s*(.+)", source_text[:200])
    title = m.group(2).strip() if m else ""
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
) -> Path:
    """Station 7: Save classified paragraphs to .th.json."""
    chapter_dir = _PROJECT_ROOT / "novels" / slug / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)

    title = _get_title(source_text, ch_num)

    data = {
        "novelId": slug,
        "chapterNo": ch_num,
        "sourceLang": source_lang,
        "targetLang": target_lang,
        "title": {
            "source": "",
            "translated": title,
        },
        "status": "translated",
        "paragraphs": classified,
        "meta": {
            "provider": provider_name,
            "model": model_name,
        },
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    out_path = chapter_dir / f"{ch_num:04d}.th.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


# ── MASTER PIPELINE ───────────────────────────────────────────────────

def translate_one(
    ch_num: int,
    slug: str = "global-descent",
    source_lang: str = "cn",
    target_lang: str = "th",
    model_override: str | None = None,
    provider_override: str | None = None,
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
        source = clean_source(raw)
        if not source:
            return {"status": "failed", "ch": ch_num, "reason": "empty_after_clean"}

        if dry_run:
            return {
                "status": "dry_run", "ch": ch_num,
                "source_preview": source[:300],
                "source_chars": len(source),
            }

        # ── Station 3: Build Prompt ──
        prompt = build_translate_prompt(
            source_text=source,
            ch_num=ch_num,
            source_lang=source_lang,
            target_lang=target_lang,
            slug=slug,
        )

        if mock:
            paragraphs = [
                f"[MOCK] ch {ch_num} — แปลด้วย {source_lang}→{target_lang}",
                "(จบบท)",
            ]
            provider_name = "mock"
            model_name = "mock"
        else:
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

            response, provider_name, model_name = call_llm(
                prompt=user_text,
                system=system_text,
                model=model_override,
                provider=provider_override,
            )

            # ── Station 5: Parse ──
            paragraph_strings = parse_output(response, ch_num)
            # Append end marker
            if paragraph_strings[-1] != "(จบบท)":
                paragraph_strings.append("(จบบท)")

        if mock:
            paragraph_strings = paragraphs

        # ── Station 6: Classify ──
        classified = classify_and_format(paragraph_strings)

        if not mock:
            # Quick quality check (skip in mock mode)
            leaks = _quick_script_check(classified, target_lang)
            if leaks:
                return {
                    "status": "failed", "ch": ch_num,
                    "reason": f"script_leak: {'; '.join(leaks[:3])}",
                    "leaks": leaks,
                }

        # ── Station 7: Save ──
        out_path = save_chapter(
            classified=classified,
            ch_num=ch_num,
            slug=slug,
            source_text=source,
            source_lang=source_lang,
            target_lang=target_lang,
            provider_name=provider_name,
            model_name=model_name,
        )

        type_ratios = estimate_type_ratios(classified)

        return {
            "status": "ok",
            "ch": ch_num,
            "paragraphs": len(classified),
            "types": type_ratios,
            "path": str(out_path),
            "provider": provider_name,
            "model": model_name,
        }

    except Exception as e:
        return {"status": "failed", "ch": ch_num, "reason": str(e)[:300]}


# ── CLI Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Test pipeline")
    ap.add_argument("ch", type=int, help="Chapter number")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--from", dest="source_lang", default="cn")
    args = ap.parse_args()

    result = translate_one(
        ch_num=args.ch,
        source_lang=args.source_lang,
        dry_run=args.dry_run,
        mock=args.mock,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
