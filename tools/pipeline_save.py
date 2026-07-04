"""Chapter writer station for translated NovelClaw chapters."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json
from novel_paths import chapter_dir, chapter_path
from prompt_builder import get_lang_config


def get_title(source_text: str, ch_num: int, source_lang: str = "cn") -> str:
    """Extract translated chapter title from source text metadata."""
    cfg = get_lang_config(source_lang)
    title_regex = cfg.get("title_regex") or r"第\s*(\d+)\s*章\s*(.+)"
    match = re.search(title_regex, source_text[:300])
    title = match.group(2).strip() if match and match.lastindex and match.lastindex >= 2 else ""
    return f"ตอนที่ {ch_num} {title}".strip()


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
    """Save classified paragraphs to the canonical .th.json path."""
    out_dir = chapter_dir(slug)
    out_dir.mkdir(parents=True, exist_ok=True)

    title = get_title(source_text, ch_num, source_lang)

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

    out_path = chapter_path(slug, ch_num, "th")
    atomic_write_json(out_path, data, ensure_ascii=False, indent=2)
    return out_path
