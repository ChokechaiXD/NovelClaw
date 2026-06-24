#!/usr/bin/env python3
"""contracts.py — Canonical contract definitions for NovelClaw.

SSOT for data shapes: on-disk JSON ↔ Pydantic model ↔ JSON Schema.

Usage:
    from contracts import ChapterV2, chapter_to_disk, chapter_from_disk

    # Load from disk
    ch = chapter_from_disk(data)  # data from .th.json

    # Convert to disk format
    disk = chapter_to_disk(ch, slug="global-descent")
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ── Provider/Model tracking ───────────────────────────────────────────

class Provider(str, Enum):
    OPENROUTER = "openrouter"
    OPENMODEL = "openmodel"
    DEDICATED = "dedicated"
    UNKNOWN = "unknown"


# ── Chapter V2 — canonical on-disk model ──────────────────────────────

class ChapterTitle(BaseModel):
    """Title in both source and translated languages."""
    source: str = ""
    translated: str = ""


class ChapterV2(BaseModel):
    """Canonical chapter format — what goes on disk.

    Matches chapter.schema.json exactly.
    """
    novelId: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$",
                         description="Novel slug — must match novel directory name")
    chapterNo: int = Field(..., ge=1, le=99999)
    sourceLang: str = Field(default="cn", pattern=r"^(cn|jp|kr|en)$")
    targetLang: str = Field(default="th", pattern=r"^(th|cn|jp|kr|en)$")
    title: ChapterTitle = Field(default_factory=ChapterTitle)
    status: str = Field(default="translated",
                        pattern=r"^(translated|source_only|source|legacy)$")
    paragraphs: list[str] = Field(..., min_length=1)
    model: str = Field(default="unknown",
                       description="Model name used for translation")
    provider: str = Field(default="unknown",
                          description="Provider used for translation")
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(),
                           description="ISO 8601 timestamp")
    qualityRecord: dict | None = Field(default=None,
                                       description="Quality metrics at translation time")

    def to_json_schema_dict(self) -> dict:
        """Generate a Draft7 JSON Schema from this Pydantic model."""
        return self.model_json_schema()


# ── Internal pipeline model (used by translate.py) ─────────────────────

class Language(str, Enum):
    CN = 'cn'
    JP = 'jp'
    KR = 'kr'
    EN = 'en'
    TH = 'th'


class ChapterPipeline(BaseModel):
    """Internal model used during translation pipeline.

    NOT the on-disk format — use chapter_to_disk() for save.
    """
    schema_version: int = Field(default=3)
    num: int = Field(..., ge=1, le=9999)
    title: str = Field(..., min_length=1)
    paragraphs: list[str] = Field(..., min_length=1)
    source: str = Field(..., pattern=r"^ch \d+$")
    notes: list[str] = Field(default_factory=list)
    lang: Language = Field(default=Language.CN)
    output_lang: Language | None = Field(default=None)
    profile_lang: Language | None = Field(default=None)
    model: str = Field(default="unknown")
    provider: str = Field(default="unknown")


# ── Conversion functions ──────────────────────────────────────────────

def chapter_to_disk(ch: ChapterPipeline, slug: str) -> dict[str, Any]:
    """Convert internal pipeline Chapter to canonical on-disk format."""
    title_str = ch.title if isinstance(ch.title, str) else ""
    return {
        "novelId": slug,
        "chapterNo": ch.num,
        "sourceLang": ch.lang.value if isinstance(ch.lang, Language) else str(ch.lang),
        "targetLang": (ch.output_lang.value if isinstance(ch.output_lang, Language)
                       else str(ch.output_lang or ch.lang)),
        "title": {
            "translated": title_str,
            "source": ch.source if ch.source and ch.source != f"ch {ch.num}" else "",
        },
        "status": "translated",
        "paragraphs": ch.paragraphs,
        "model": ch.model,
        "provider": ch.provider,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def chapter_from_disk(data: dict) -> ChapterPipeline:
    """Reconstruct internal pipeline Chapter from canonical disk format.

    Used when loading previously-saved chapters for re-validation or repair.
    """
    title_data = data.get("title", {})
    if isinstance(title_data, dict):
        title_str = title_data.get("translated", title_data.get("source", ""))
    elif isinstance(title_data, str):
        title_str = title_data
    else:
        title_str = ""

    return ChapterPipeline(
        num=data["chapterNo"],
        title=title_str or f"ตอนที่ {data['chapterNo']}",
        paragraphs=data["paragraphs"],
        source=f"ch {data['chapterNo']}",
        lang=data.get("sourceLang", "cn"),
        output_lang=data.get("targetLang", "th"),
        model=data.get("model", "unknown"),
        provider=data.get("provider", "unknown"),
    )


# ── Generate JSON Schema file ─────────────────────────────────────────

def write_json_schema(output_path: str | Path) -> None:
    """Generate chapter.schema.json from ChapterV2 Pydantic model."""
    schema = ChapterV2.model_json_schema()
    # Add $schema field
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    Path(output_path).write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
