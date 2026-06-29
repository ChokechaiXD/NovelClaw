"""HTML/text cleanup helpers shared by source import adapters."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin


BOILERPLATE_PATTERNS = [
    r"^\s*(read\s+next|next\s+chapter|previous\s+chapter|table\s+of\s+contents)\b",
    r"^\s*(chapter\s+list|back\s+to\s+top|bookmark|subscribe|share)\b",
    r"^\s*(advertisement|ads?|sponsored)\s*$",
    r"^\s*(本章未完|请收藏|最新网址|手机用户请浏览|加入书签|推荐本书)",
    r"^\s*(次の話|前の話|目次|ブックマーク|しおり)",
    r"^\s*(作者を応援|応援コメント|レビュー|フォロー)",
    r"^\s*(login|sign\s+in|register)\s+to\b",
]

DIRTY_MARKERS = [
    "advertisement",
    "sponsored",
    "login to",
    "please enable javascript",
    "加入书签",
    "最新网址",
    "ブックマーク",
]

REMOVE_BLOCK_RE = re.compile(
    r"<(script|style|noscript|iframe|svg|nav|header|footer|aside|form|button)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
DOC_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
LINK_RE = re.compile(r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)


def html_to_text(fragment: str) -> str:
    fragment = REMOVE_BLOCK_RE.sub("\n", fragment)
    fragment = COMMENT_RE.sub("\n", fragment)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"</(p|div|li|h1|h2|h3|section|article)>", "\n", fragment, flags=re.IGNORECASE)
    fragment = TAG_RE.sub("", fragment)
    return html.unescape(fragment).replace("\xa0", " ")


def clean_text_lines(text: str) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in BOILERPLATE_PATTERNS):
            continue
        if line in seen and len(line) < 80:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def extract_title(raw: str, fallback: str = "") -> str:
    for pattern in (TITLE_RE, DOC_TITLE_RE):
        match = pattern.search(raw)
        if match:
            title = clean_inline_text(match.group(1))
            if title:
                return title
    return clean_inline_text(fallback)


def clean_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", html_to_text(text)).strip()


def extract_links(raw: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for href, label_html in LINK_RE.findall(raw):
        label = clean_inline_text(label_html)
        if not label:
            continue
        links.append((urljoin(base_url, html.unescape(href)), label))
    return links


def extract_by_attr(raw: str, attr_names: list[str]) -> str:
    for name in attr_names:
        pattern = re.compile(
            rf"<(?P<tag>[a-z0-9]+)[^>]*(?:id|class)=[\"'][^\"']*\b{re.escape(name)}\b[^\"']*[\"'][^>]*>(?P<body>.*?)</(?P=tag)>",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(raw)
        if match:
            return match.group("body")
    return raw


def extract_paragraphs(raw: str, attr_names: list[str] | None = None) -> list[str]:
    fragment = extract_by_attr(raw, attr_names or [])
    return clean_text_lines(html_to_text(fragment))


def validate_paragraphs(title: str, paragraphs: list[str]) -> tuple[list[str], bool]:
    warnings: list[str] = []
    total_chars = sum(len(p) for p in paragraphs)
    if not title:
        warnings.append("missing_title")
    if not paragraphs:
        warnings.append("empty_content")
    if total_chars < 300:
        warnings.append("short_content")
    if len(paragraphs) < 2:
        warnings.append("few_paragraphs")

    lower_joined = "\n".join(paragraphs).lower()
    dirty_hits = [m for m in DIRTY_MARKERS if m in lower_joined]
    if dirty_hits:
        warnings.append("dirty_markers:" + ",".join(dirty_hits[:3]))

    unique_count = len(set(paragraphs))
    if paragraphs and unique_count / len(paragraphs) < 0.75:
        warnings.append("duplicate_lines")

    return warnings, bool(warnings)
