"""Static HTML novel source adapters.

These adapters intentionally use only the Python standard library. Sites that
need browser automation, login, paywall access, captcha solving, or OCR should
be implemented as separate optional adapters rather than pulled into this core.
"""

from __future__ import annotations

import re
import urllib.request
from urllib.parse import urlparse

from .base import ChapterRef, ExtractedChapter, TocResult
from .cleaning import extract_links, extract_paragraphs, extract_title, validate_paragraphs


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NovelClaw/1.0",
}


def fetch_url(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=headers or DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


class StaticHtmlAdapter:
    id = "static"
    display_name = "Static HTML"
    source_lang = "cn"
    adapter_type = "static_html"
    status = "supported"
    quality = "beta"
    domains: tuple[str, ...] = ()
    toc_link_patterns: tuple[str, ...] = ()
    content_attrs: tuple[str, ...] = ()
    headers: dict[str, str] = DEFAULT_HEADERS
    requires_js = False
    requires_login = False
    has_paywall = False
    notes = "Plain HTML adapter. Does not bypass login, paywall, captcha, or DRM."

    def detect(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(domain in host for domain in self.domains)

    def fetch_toc(self, url: str) -> TocResult:
        raw = fetch_url(url, self.headers)
        title = extract_title(raw, fallback=urlparse(url).path.strip("/") or url)
        chapters = self._extract_toc_links(raw, url)
        return TocResult(
            site=self.id,
            url=url,
            title=title,
            source_lang=self.source_lang,
            chapters=chapters,
        )

    def fetch_chapter(self, ref: ChapterRef) -> str:
        return fetch_url(ref.url, self.headers)

    def extract(self, raw: str, ref: ChapterRef) -> ExtractedChapter:
        title = extract_title(raw, fallback=ref.title)
        paragraphs = extract_paragraphs(raw, list(self.content_attrs))
        warnings, needs_review = validate_paragraphs(title, paragraphs)
        return ExtractedChapter(
            title=title or ref.title,
            paragraphs=paragraphs,
            source_url=ref.url,
            source_lang=self.source_lang,
            warnings=warnings,
            needs_review=needs_review,
        )

    def _extract_toc_links(self, raw: str, base_url: str) -> list[ChapterRef]:
        compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.toc_link_patterns]
        seen: set[str] = set()
        chapters: list[ChapterRef] = []
        for href, label in extract_links(raw, base_url):
            if href in seen:
                continue
            if compiled and not any(pattern.search(href) or pattern.search(label) for pattern in compiled):
                continue
            seen.add(href)
            chapters.append(ChapterRef(num=len(chapters) + 1, title=label, url=href))
        return chapters


class Shu69Adapter(StaticHtmlAdapter):
    id = "69shu"
    display_name = "69shu"
    source_lang = "cn"
    quality = "fixture"
    domains = ("69shu.com",)
    toc_link_patterns = (r"/\d+/\d+\.html$",)
    content_attrs = ("content",)
    headers = {
        **DEFAULT_HEADERS,
        "Referer": "https://www.69shu.com/",
    }


class UukanshuAdapter(StaticHtmlAdapter):
    id = "uukanshu"
    display_name = "uukanshu"
    source_lang = "cn"
    quality = "beta"
    domains = ("uukanshu.com",)
    toc_link_patterns = (r"/b/\d+/\d+\.html$",)
    content_attrs = ("contentbox", "content")


class SyosetuAdapter(StaticHtmlAdapter):
    id = "syosetu"
    display_name = "Syosetu"
    source_lang = "jp"
    quality = "beta"
    domains = ("syosetu.com",)
    toc_link_patterns = (r"/n[0-9a-z]+/\d+/?$",)
    content_attrs = ("novel_honbun", "js-novel-text")


class KakuyomuAdapter(StaticHtmlAdapter):
    id = "kakuyomu"
    display_name = "Kakuyomu"
    source_lang = "jp"
    quality = "experimental"
    domains = ("kakuyomu.jp",)
    toc_link_patterns = (r"/works/\d+/episodes/\d+",)
    content_attrs = ("widget-episodeBody", "widget-episode")


class RoyalRoadAdapter(StaticHtmlAdapter):
    id = "royalroad"
    display_name = "Royal Road"
    source_lang = "en"
    quality = "experimental"
    domains = ("royalroad.com",)
    toc_link_patterns = (r"/fiction/\d+/.+/chapter/\d+",)
    content_attrs = ("chapter-inner", "chapter-content")


ADAPTERS = [
    Shu69Adapter(),
    UukanshuAdapter(),
    SyosetuAdapter(),
    KakuyomuAdapter(),
    RoyalRoadAdapter(),
]
