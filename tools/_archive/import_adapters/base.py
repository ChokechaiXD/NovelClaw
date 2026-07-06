"""Adapter contracts for importing novel source text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ChapterRef:
    num: int
    title: str
    url: str


@dataclass(frozen=True)
class TocResult:
    site: str
    url: str
    title: str
    author: str = ""
    source_lang: str = "cn"
    chapters: list[ChapterRef] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedChapter:
    title: str
    paragraphs: list[str]
    source_url: str
    source_lang: str
    warnings: list[str] = field(default_factory=list)
    needs_review: bool = False


class SourceAdapter(Protocol):
    id: str
    display_name: str
    source_lang: str

    def detect(self, url: str) -> bool:
        """Return True if this adapter can handle the URL."""

    def fetch_toc(self, url: str) -> TocResult:
        """Fetch and parse a table of contents URL."""

    def fetch_chapter(self, ref: ChapterRef) -> str:
        """Fetch raw chapter HTML/text for a chapter reference."""

    def extract(self, raw: str, ref: ChapterRef) -> ExtractedChapter:
        """Extract clean chapter text from raw HTML/text."""
