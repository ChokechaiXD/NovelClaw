"""read_source — Station 1: Read source file from disk."""
from __future__ import annotations
import json
from pathlib import Path

from pipeline._shared import (
    get_logger, resolve_source_lang, source_md_path, chapter_path, _PROJECT_ROOT,
)


def read_source(ch_num: int, slug: str = "global-descent") -> str | None:
    """Station 1: Read source file. Supports .md and source-language .json.

    Source lang detected from novel.json's sourceLang field, falling back to 'cn'.
    """
    log = get_logger("read_source")
    _novel_path = Path(_PROJECT_ROOT) / "novels" / slug / "novel.json"
    _source_lang = "cn"
    try:
        with open(_novel_path, encoding="utf-8") as _f:
            _meta = json.load(_f)
        _source_lang = (_meta.get("sourceLang") or "").lower() or "cn"
    except Exception as exc:
        log.warning("Can't read novel.json for %s: %s — trying fallback langs", slug, exc)
        for _candidate in ("cn", "en", "jp", "zh", "ja"):
            _candidate_json = chapter_path(slug, ch_num, _candidate)
            if _candidate_json.exists():
                _source_lang = _candidate
                break

    src_md = source_md_path(slug, ch_num)
    if src_md.exists():
        return src_md.read_text(encoding="utf-8")

    src_json = chapter_path(slug, ch_num, _source_lang)
    if src_json.exists():
        data = json.loads(src_json.read_text(encoding="utf-8"))
        return "\n".join(data.get("paragraphs", []))

    return None


def _source_chunk_char_limit(source_lang: str, max_tokens: int) -> int:
    """Estimate a safe source size for a target-language output token budget."""
    language_ratio = {
        "cn": 0.4,
        "zh": 0.4,
        "jp": 0.4,
        "ja": 0.4,
        "kr": 0.65,
        "ko": 0.65,
        "en": 1.4,
    }.get(source_lang.lower(), 0.6)
    return max(64, min(6000, int(max_tokens * language_ratio)))


def _split_source_chunks(source_text: str, max_chars: int) -> list[str]:
    """Split source without losing characters, preferring paragraph boundaries."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if len(source_text) <= max_chars:
        return [source_text]

    chunks: list[str] = []
    cursor = 0
    while len(source_text) - cursor > max_chars:
        window = source_text[cursor:cursor + max_chars]
        minimum_break = max_chars // 2
        paragraph_break = window.rfind("\n\n", minimum_break)
        if paragraph_break >= 0:
            cut = paragraph_break + 2
        else:
            sentence_break = max(
                (window.rfind(mark, minimum_break) for mark in ".!?。！？…"),
                default=-1,
            )
            cut = sentence_break + 1 if sentence_break >= 0 else max_chars
        chunks.append(source_text[cursor:cursor + cut])
        cursor += cut
    if cursor < len(source_text):
        chunks.append(source_text[cursor:])
    return chunks
