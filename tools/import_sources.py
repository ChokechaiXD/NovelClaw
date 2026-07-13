"""NovelClaw source import engine.

Core flow:
    Source Adapter -> Extract -> Clean -> Validate -> Save

OCR/image/PDF imports are intentionally not part of this core path. They can be
added later as adapters that return the same extracted chapter shape.
"""

from __future__ import annotations

import argparse
import codecs
import io
import json
import os
import posixpath
import re
import secrets
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote

try:
    from atomic_io import atomic_write_json, atomic_write_text
except ModuleNotFoundError:
    from tools.atomic_io import atomic_write_json, atomic_write_text

try:
    from import_adapters import get_adapter, list_adapters
    from import_adapters.base import ExtractedChapter
    from import_adapters.cleaning import clean_text_lines, validate_paragraphs
    from import_adapters.registry import list_site_catalog
except ModuleNotFoundError:
    from tools.import_adapters import get_adapter, list_adapters
    from tools.import_adapters.base import ExtractedChapter
    from tools.import_adapters.cleaning import clean_text_lines, validate_paragraphs
    from tools.import_adapters.registry import list_site_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOVELS_DIR = PROJECT_ROOT / "novels"
SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_DOCUMENT_BYTES = 6 * 1024 * 1024
MAX_DOCUMENT_CHAPTERS = 10_000
MAX_EPUB_ENTRIES = 5_000
MAX_EPUB_TEXT_BYTES = 20 * 1024 * 1024
IMPORT_LOCK_TIMEOUT_SECONDS = 10 * 60
IMPORT_LOCK_STALE_SECONDS = 6 * 60 * 60
IMPORT_LOCK_POLL_SECONDS = 0.05
DOCUMENT_FORMATS = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".epub": "epub",
}
CHINESE_NUMERAL_CHARS = "零〇○一二三四五六七八九十百千万萬两兩"
DEFAULT_CHAPTER_HEADING_RE = re.compile(
    r"^\s*((?:(?:ตอน(?:ที่)?|Chapter|Episode|Part)\s*\d+|"
    rf"第\s*(?:\d+|[{CHINESE_NUMERAL_CHARS}]+)\s*[章話话回節节]|제\s*\d+\s*화)[^\r\n]*)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
CHINESE_CHAPTER_NUMBER_RE = re.compile(
    rf"第\s*([{CHINESE_NUMERAL_CHARS}]+)\s*[章話话回節节]",
    re.IGNORECASE,
)


class _NovelHTMLParser(HTMLParser):
    """Extract readable block text without browser/site chrome."""

    _ALWAYS_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "nav", "footer", "aside", "form"}
    _CONTEXTUAL_SKIP_TAGS = {"header"}
    _SKIP_TAGS = _ALWAYS_SKIP_TAGS | _CONTEXTUAL_SKIP_TAGS
    _CONTENT_TAGS = {"main", "article"}
    _BLOCK_TAGS = {
        "address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "h1", "h2", "h3",
        "h4", "h5", "h6", "hr", "li", "main", "p", "pre", "section", "table", "td", "th", "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_stack: list[str] = []
        self.content_depth = 0
        self.in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_stack:
            if tag in self._SKIP_TAGS:
                self.skip_stack.append(tag)
            return
        if tag in self._ALWAYS_SKIP_TAGS or (tag in self._CONTEXTUAL_SKIP_TAGS and self.content_depth == 0):
            self.skip_stack.append(tag)
            return
        if tag == "title":
            self.in_title = True
            return
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")
        if tag in self._CONTENT_TAGS:
            self.content_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return
        if tag == "title":
            self.in_title = False
            return
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")
        if tag in self._CONTENT_TAGS and self.content_depth:
            self.content_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_stack:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        self.parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self.parts)

    @property
    def document_title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip())


def parse_range(range_text: str | None) -> set[int] | None:
    if not range_text:
        return None
    selected: set[int] = set()
    for part in range_text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = [int(x.strip()) for x in part.split("-", 1)]
            if b < a:
                raise ValueError("range end must be greater than or equal to start")
            selected.update(range(a, b + 1))
        else:
            selected.add(int(part))
    return selected


def assert_slug(slug: str) -> None:
    if not slug or not SLUG_RE.match(slug):
        raise ValueError("Invalid slug format")


@contextmanager
def _import_transaction_lock(slug: str):
    """Serialize one novel's import transaction across threads and processes."""

    assert_slug(slug)
    novel_dir = NOVELS_DIR / slug
    novel_dir.mkdir(parents=True, exist_ok=True)
    lock_path = novel_dir / ".import.lock"
    deadline = time.monotonic() + IMPORT_LOCK_TIMEOUT_SECONDS
    owner_token = f"{os.getpid()}:{secrets.token_hex(16)}"
    fd: int | None = None
    owner_stat: os.stat_result | None = None

    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            owner_stat = os.fstat(fd)
        except FileExistsError:
            try:
                stale_stat = lock_path.stat()
                if time.time() - stale_stat.st_mtime > IMPORT_LOCK_STALE_SECONDS:
                    current_stat = lock_path.stat()
                    if (
                        current_stat.st_dev == stale_stat.st_dev
                        and current_stat.st_ino == stale_stat.st_ino
                        and current_stat.st_mtime_ns == stale_stat.st_mtime_ns
                    ):
                        lock_path.unlink()
                        continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for import lock: {lock_path}")
            time.sleep(IMPORT_LOCK_POLL_SECONDS)

    try:
        os.write(fd, f"{owner_token}\npid={os.getpid()} time={time.time():.3f}\n".encode("ascii"))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            current_stat = lock_path.stat()
            current_token = lock_path.read_text(encoding="ascii").splitlines()[0]
            same_file = (
                owner_stat is not None
                and current_stat.st_dev == owner_stat.st_dev
                and current_stat.st_ino == owner_stat.st_ino
            )
            if same_file and current_token == owner_token:
                lock_path.unlink()
        except FileNotFoundError:
            pass


def source_dir(slug: str) -> Path:
    assert_slug(slug)
    path = NOVELS_DIR / slug / "chapters" / "source"
    path.mkdir(parents=True, exist_ok=True)
    return path


def source_path(slug: str, num: int) -> Path:
    return source_dir(slug) / f"{num:04d}.md"


def source_toc_path(slug: str) -> Path:
    return source_dir(slug) / "toc.json"


def source_toc_path_no_create(slug: str) -> Path:
    assert_slug(slug)
    return NOVELS_DIR / slug / "chapters" / "source" / "toc.json"


def frontmatter_value(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def render_source_markdown(chapter: ExtractedChapter, site: str, import_warnings: list[str]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    header = [
        "---",
        f"source_url: {frontmatter_value(chapter.source_url)}",
        f"source_site: {frontmatter_value(site)}",
        f"source_lang: {frontmatter_value(chapter.source_lang)}",
        f"imported_at: {frontmatter_value(now)}",
        f"needs_review: {'true' if chapter.needs_review else 'false'}",
        f"import_warnings: {json.dumps(import_warnings, ensure_ascii=False)}",
        "---",
    ]
    body = [f"# {chapter.title.strip() or 'Untitled'}"]
    body.extend(p.strip() for p in chapter.paragraphs if p.strip())
    return "\n".join(header) + "\n\n" + "\n\n".join(body).rstrip() + "\n"


def update_novel_json(
    slug: str,
    *,
    title: str,
    author: str = "",
    source_lang: str = "cn",
    source_site: str = "",
    source_url: str = "",
    total_chapters: int = 0,
) -> dict:
    assert_slug(slug)
    novel_dir = NOVELS_DIR / slug
    novel_dir.mkdir(parents=True, exist_ok=True)
    path = novel_dir / "novel.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        data = {}

    refs = data.get("sourceRefs")
    if not isinstance(refs, list):
        refs = []
    if source_url and not any(ref.get("url") == source_url for ref in refs if isinstance(ref, dict)):
        refs.append({"site": source_site, "url": source_url, "importedAt": datetime.now(timezone.utc).isoformat()})

    data.update(
        {
            "slug": slug,
            "title": data.get("title") or title or slug,
            "translatedTitle": data.get("translatedTitle", ""),
            "author": data.get("author") or author or "",
            "sourceLang": source_lang or data.get("sourceLang") or data.get("source_lang") or "cn",
            "targetLang": data.get("targetLang") or data.get("target_lang") or "th",
            "status": data.get("status") or "ongoing",
            "totalChapters": max(int(data.get("totalChapters") or 0), int(total_chapters or 0)),
            "description": data.get("description", ""),
            "originalUrl": data.get("originalUrl") or source_url,
            "sourceSite": data.get("sourceSite") or source_site,
            "sourceRefs": refs,
            "lastImportedAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    atomic_write_json(path, data, ensure_ascii=False, indent=2)
    return data


def write_toc_manifest(slug: str, toc, adapter_id: str) -> Path:
    payload = {
        "site": adapter_id,
        "url": toc.url,
        "title": toc.title,
        "author": toc.author,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "chapters": [asdict(ch) for ch in toc.chapters],
    }
    path = source_toc_path(slug)
    atomic_write_json(path, payload, ensure_ascii=False, indent=2)
    return path


def read_novel_json(slug: str) -> dict:
    assert_slug(slug)
    path = NOVELS_DIR / slug / "novel.json"
    if not path.exists():
        raise ValueError(f"novel.json not found for slug: {slug}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid novel.json for {slug}: {exc}") from exc


def infer_toc_source(slug: str, url: str | None = None, site: str = "auto") -> tuple[str, str]:
    if url:
        return url, site or "auto"

    meta = read_novel_json(slug)
    source_urls = meta.get("sourceUrls")
    if isinstance(source_urls, dict):
        for key, value in source_urls.items():
            if value and str(value).startswith(("http://", "https://")):
                return str(value), key if site == "auto" else site

    refs = meta.get("sourceRefs")
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            ref_url = str(ref.get("url") or "")
            if ref_url.startswith(("http://", "https://")):
                ref_site = str(ref.get("site") or "auto")
                return ref_url, ref_site if site == "auto" else site

    original_url = str(meta.get("originalUrl") or "")
    if original_url.startswith(("http://", "https://")):
        source_site = str(meta.get("sourceSite") or "auto")
        return original_url, source_site if site == "auto" else site

    raise ValueError("No recoverable TOC URL found in novel.json")


def recover_toc(slug: str, site: str = "auto", url: str | None = None, dry_run: bool = True) -> dict:
    assert_slug(slug)
    toc_url, toc_site = infer_toc_source(slug, url, site)
    adapter = get_adapter(toc_url, toc_site)
    toc = adapter.fetch_toc(toc_url)
    toc_path = source_toc_path_no_create(slug)
    if not dry_run:
        toc_path = write_toc_manifest(slug, toc, adapter.id)
    return {
        "slug": slug,
        "dryRun": dry_run,
        "site": adapter.id,
        "url": toc_url,
        "title": toc.title,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "tocPath": str(toc_path),
        "sampleChapters": [asdict(ch) for ch in toc.chapters[:20]],
    }


def preview_url(url: str, site: str = "auto") -> dict:
    adapter = get_adapter(url, site)
    toc = adapter.fetch_toc(url)
    sample: dict | None = None
    diagnostics: dict = {
        "hasToc": len(toc.chapters) > 0,
        "hasSampleContent": False,
        "recommendImport": len(toc.chapters) > 0,
        "warnings": [],
    }
    if toc.chapters:
        ref = toc.chapters[0]
        try:
            raw = adapter.fetch_chapter(ref)
            chapter = adapter.extract(raw, ref)
            total_chars = sum(len(p) for p in chapter.paragraphs)
            sample = {
                "num": ref.num,
                "title": chapter.title or ref.title,
                "sourceUrl": chapter.source_url,
                "paragraphCount": len(chapter.paragraphs),
                "charCount": total_chars,
                "paragraphs": chapter.paragraphs[:3],
                "warnings": list(chapter.warnings),
                "needsReview": chapter.needs_review,
            }
            diagnostics["hasSampleContent"] = total_chars > 0 and len(chapter.paragraphs) > 0
            diagnostics["warnings"] = list(chapter.warnings)
            diagnostics["recommendImport"] = diagnostics["hasSampleContent"] and "empty_content" not in chapter.warnings
        except Exception as exc:
            diagnostics["sampleError"] = str(exc)[:200]
            diagnostics["recommendImport"] = False
    return {
        "site": toc.site,
        "displayName": getattr(adapter, "display_name", toc.site),
        "url": toc.url,
        "title": toc.title,
        "author": toc.author,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "chapters": [asdict(ch) for ch in toc.chapters[:200]],
        "sampleChapter": sample,
        "diagnostics": diagnostics,
        "supportedAdapters": [adapter.id for adapter in list_adapters()],
    }


def import_sites() -> dict:
    return list_site_catalog()


def import_url(url: str, slug: str, site: str = "auto", range_text: str | None = None, force: bool = False) -> dict:
    assert_slug(slug)
    with _import_transaction_lock(slug):
        return _import_url_locked(url, slug, site, range_text, force)


def _import_url_locked(url: str, slug: str, site: str, range_text: str | None, force: bool) -> dict:
    adapter = get_adapter(url, site)
    toc = adapter.fetch_toc(url)
    selected = parse_range(range_text)
    chapters = [ch for ch in toc.chapters if selected is None or ch.num in selected]
    if not chapters:
        raise ValueError("No chapters matched the requested import range")

    results: list[dict] = []
    imported = skipped = failed = 0
    for ref in chapters:
        out_path = source_path(slug, ref.num)
        if out_path.exists() and not force:
            skipped += 1
            results.append({"status": "skipped", "num": ref.num, "title": ref.title, "path": str(out_path)})
            continue
        try:
            raw = adapter.fetch_chapter(ref)
            chapter = adapter.extract(raw, ref)
            warnings = list(chapter.warnings)
            atomic_write_text(out_path, render_source_markdown(chapter, adapter.id, warnings))
            imported += 1
            results.append(
                {
                    "status": "imported",
                    "num": ref.num,
                    "title": chapter.title,
                    "path": str(out_path),
                    "warnings": warnings,
                    "needsReview": chapter.needs_review,
                }
            )
        except Exception as exc:
            failed += 1
            results.append({"status": "failed", "num": ref.num, "title": ref.title, "reason": str(exc)[:200]})

    update_novel_json(
        slug,
        title=toc.title,
        author=toc.author,
        source_lang=toc.source_lang,
        source_site=adapter.id,
        source_url=url,
        total_chapters=len(toc.chapters),
    )
    toc_path = write_toc_manifest(slug, toc, adapter.id)
    return {
        "slug": slug,
        "site": adapter.id,
        "title": toc.title,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "tocPath": str(toc_path),
        "results": results,
    }


def _chinese_numeral_to_int(value: str) -> int | None:
    digits = {
        "零": 0, "〇": 0, "○": 0,
        "一": 1, "二": 2, "两": 2, "兩": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1_000, "万": 10_000, "萬": 10_000}
    if not value or any(char not in digits and char not in units for char in value):
        return None
    if not any(char in units for char in value):
        return int("".join(str(digits[char]) for char in value))

    total = section = number = 0
    for char in value:
        if char in digits:
            number = digits[char]
            continue
        unit = units[char]
        if unit < 10_000:
            section += (number or 1) * unit
        else:
            section += number
            total += (section or 1) * unit
            section = 0
        number = 0
    result = total + section + number
    return result if result > 0 else None


def _heading_chapter_number(title: str, fallback: int) -> int:
    digit_match = re.search(r"\d+", title)
    if digit_match:
        return int(digit_match.group(0))
    chinese_match = CHINESE_CHAPTER_NUMBER_RE.search(title)
    if chinese_match:
        return _chinese_numeral_to_int(chinese_match.group(1)) or fallback
    return fallback


def split_paste_content(content: str, split_rule: str | None = None) -> list[tuple[int, str, list[str]]]:
    regex = (
        re.compile(rf"^\s*({split_rule}.*?)\s*$", re.MULTILINE | re.IGNORECASE)
        if split_rule
        else DEFAULT_CHAPTER_HEADING_RE
    )
    matches = list(regex.finditer(content))
    if not matches:
        paragraphs = clean_text_lines(content)
        return [(1, "Chapter 1", paragraphs)]

    chapters: list[tuple[int, str, list[str]]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        title = match.group(1).strip()
        num = _heading_chapter_number(title, idx + 1)
        paragraphs = clean_text_lines(content[start:end])
        if not paragraphs:
            paragraphs = [title]
        chapters.append((num, title, paragraphs))
    return chapters


def _normalise_source_lang(source_lang: str) -> str:
    value = str(source_lang or "auto").strip().lower()
    aliases = {"zh": "cn", "zh-cn": "cn", "ja": "jp", "ko": "kr"}
    return aliases.get(value, value)


def _validate_decoded_text(text: str) -> bool:
    if not text.strip() or "\ufffd" in text:
        return False
    if "\x00" in text:
        return False
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return controls <= max(1, len(text) // 1000)


def _is_han(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def _legacy_decode_plausibility(text: str, encoding: str) -> float:
    """Rank strict legacy decodes by language signals instead of fallback order."""

    significant = [char for char in text if not char.isspace() and (char.isalnum() or ord(char) >= 128)]
    total = max(1, len(significant))
    kana = sum("\u3040" <= char <= "\u30ff" for char in significant)
    hangul = sum("\uac00" <= char <= "\ud7af" for char in significant)
    han = sum(_is_han(char) for char in significant)
    latin = sum(("A" <= char <= "Z") or ("a" <= char <= "z") for char in significant)
    common_han = sum(char in "的一是在不了有和人这中大来上个国我以要他时生会子年说文正文开始章节話话回" for char in significant)
    printable = sum(char.isprintable() or char in "\n\r\t" for char in text) / max(1, len(text))
    score = printable * 20

    if encoding == "shift_jis":
        kana_ratio = kana / total
        score += (100 + kana_ratio * 80) if kana_ratio >= 0.05 else (han / total) * 15
    elif encoding == "euc_kr":
        hangul_ratio = hangul / total
        score += (100 + hangul_ratio * 80) if hangul_ratio >= 0.35 else hangul_ratio * 20 + (han / total) * 10
    elif encoding in {"gb18030", "big5"}:
        score += (han / total) * 60 + (common_han / total) * 80
        if CHINESE_CHAPTER_NUMBER_RE.search(text) or re.search(r"第\s*\d+\s*[章話话回節节]", text):
            score += 20
    elif encoding == "cp1252":
        extended = sum(0x80 <= ord(char) <= 0xFF for char in significant)
        score += (latin / total) * 70 - (extended / total) * 15
    return score


def decode_document_bytes(raw: bytes, source_lang: str = "auto") -> tuple[str, str]:
    """Decode local novel files deterministically, including common legacy CJK encodings."""

    if not raw:
        raise ValueError("Document is empty")
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"Document is too large (maximum {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB)")

    bom_encodings = (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    )
    for bom, encoding in bom_encodings:
        if raw.startswith(bom):
            text = raw.decode(encoding, errors="strict")
            if _validate_decoded_text(text):
                return text.replace("\r\n", "\n").replace("\r", "\n"), encoding

    lang = _normalise_source_lang(source_lang)
    fallbacks = {
        "cn": ("gb18030", "big5"),
        "jp": ("shift_jis", "euc_jp"),
        "kr": ("euc_kr", "cp949"),
        "en": ("cp1252",),
        "auto": ("gb18030", "shift_jis", "euc_kr", "big5", "cp1252"),
    }
    candidates = ("utf-8",) + fallbacks.get(lang, fallbacks["auto"])
    plausible: list[tuple[float, int, str, str]] = []
    for encoding in candidates:
        try:
            text = raw.decode(encoding, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
        if not _validate_decoded_text(text):
            continue
        normalised = text.replace("\r\n", "\n").replace("\r", "\n")
        if lang != "auto" or encoding == "utf-8":
            return normalised, encoding
        plausible.append((_legacy_decode_plausibility(text, encoding), -len(plausible), normalised, encoding))
    if plausible:
        _score, _order, text, encoding = max(plausible)
        return text, encoding
    raise ValueError("Unable to decode document; save it as UTF-8 or select the correct source language")


def _strip_markdown_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:201], start=1):
        if line.strip() in {"---", "..."}:
            return "\n".join(lines[index + 1 :])
    return text


def _markdown_to_text(text: str) -> str:
    text = _strip_markdown_frontmatter(text)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"```[^\n]*\n[\s\S]*?```", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return text


def _as_paragraph_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "\n\n".join(part for item in value if (part := _as_paragraph_text(item)).strip())
    if isinstance(value, dict):
        for key in ("text", "content", "body", "value", "paragraph"):
            if key in value:
                return _as_paragraph_text(value[key])
    return ""


def _chapter_number(value: Any, fallback: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    match = re.search(r"\d+", str(value or ""))
    if match and int(match.group(0)) > 0:
        return int(match.group(0))
    return fallback


def _unique_chapter_numbers(chapters: list[tuple[int, str, list[str]]]) -> list[tuple[int, str, list[str]]]:
    used: set[int] = set()
    next_num = 1
    normalised: list[tuple[int, str, list[str]]] = []
    for num, title, paragraphs in chapters:
        if num < 1 or num in used:
            while next_num in used:
                next_num += 1
            num = next_num
        used.add(num)
        next_num = max(next_num, num + 1)
        normalised.append((num, title.strip() or f"Chapter {num}", paragraphs))
    return normalised


def _parse_json_document(text: str) -> tuple[list[tuple[int, str, list[str]]], str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON document: {exc.msg} at line {exc.lineno}") from exc

    suggested_title = ""
    items: Any = payload
    if isinstance(payload, dict):
        suggested_title = str(payload.get("title") or payload.get("name") or "").strip()
        for key in ("chapters", "episodes", "items"):
            if key in payload:
                items = payload[key]
                break
        else:
            data = payload.get("data")
            if isinstance(data, dict) and "chapters" in data:
                items = data["chapters"]
            else:
                items = [payload]

    if isinstance(items, dict):
        items = [dict(value, _map_key=key) if isinstance(value, dict) else {"title": key, "content": value}
                 for key, value in items.items()]
    if not isinstance(items, list):
        raise ValueError("JSON document must contain a chapter list or chapter object")
    if len(items) > MAX_DOCUMENT_CHAPTERS:
        raise ValueError(f"Document contains too many chapters (maximum {MAX_DOCUMENT_CHAPTERS})")

    chapters: list[tuple[int, str, list[str]]] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            num = index
            title = f"Chapter {num}"
            body = item
        elif isinstance(item, dict):
            number_value = next((item[key] for key in ("num", "number", "chapter", "index", "id", "_map_key") if key in item), index)
            num = _chapter_number(number_value, index)
            title = str(next((item[key] for key in ("title", "name", "chapterTitle", "chapter_title") if item.get(key)), f"Chapter {num}"))
            body = ""
            for key in ("paragraphs", "content", "body", "text", "blocks"):
                candidate = _as_paragraph_text(item.get(key))
                if candidate.strip():
                    body = candidate
                    break
        else:
            continue
        paragraphs = clean_text_lines(_as_paragraph_text(body))
        if paragraphs:
            chapters.append((num, title, paragraphs))

    if not chapters:
        raise ValueError("JSON document contains no readable chapter text")
    return _unique_chapter_numbers(chapters), suggested_title


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _epub_member_path(base_path: str, href: str) -> str:
    decoded = unquote(str(href or "").split("#", 1)[0]).replace("\\", "/")
    member = posixpath.normpath(posixpath.join(posixpath.dirname(base_path), decoded))
    if not decoded or member.startswith("../") or member.startswith("/") or member == "..":
        raise ValueError("EPUB contains an unsafe content path")
    return member


def _read_epub_member(archive: zipfile.ZipFile, member: str, *, limit: int) -> bytes:
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise ValueError(f"EPUB is missing required file: {member}") from exc
    if info.flag_bits & 0x1:
        raise ValueError("Encrypted EPUB files are not supported")
    if info.file_size > limit:
        raise ValueError(f"EPUB content file is too large: {member}")
    if info.compress_size and info.file_size / info.compress_size > 200:
        raise ValueError("EPUB contains an unsafe compression ratio")
    return archive.read(info)


def _decode_epub_html(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        if _validate_decoded_text(text):
            return text
    raise ValueError("Unable to decode EPUB chapter text")


def _parse_epub_document(raw: bytes) -> tuple[list[tuple[int, str, list[str]]], str]:
    """Extract EPUB spine documents in reading order using only the standard library."""

    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid EPUB archive") from exc

    with archive:
        if len(archive.infolist()) > MAX_EPUB_ENTRIES:
            raise ValueError(f"EPUB contains too many files (maximum {MAX_EPUB_ENTRIES})")
        container_raw = _read_epub_member(archive, "META-INF/container.xml", limit=1024 * 1024)
        try:
            container = ET.fromstring(container_raw)
        except ET.ParseError as exc:
            raise ValueError("Invalid EPUB container metadata") from exc
        rootfile = next(
            (element.attrib.get("full-path", "") for element in container.iter()
             if _xml_local_name(element.tag) == "rootfile" and element.attrib.get("full-path")),
            "",
        )
        if not rootfile:
            raise ValueError("EPUB package document was not found")
        rootfile = _epub_member_path("", rootfile)
        package_raw = _read_epub_member(archive, rootfile, limit=2 * 1024 * 1024)
        try:
            package = ET.fromstring(package_raw)
        except ET.ParseError as exc:
            raise ValueError("Invalid EPUB package metadata") from exc

        suggested_title = next(
            (" ".join((element.text or "").split()) for element in package.iter()
             if _xml_local_name(element.tag) == "title" and (element.text or "").strip()),
            "",
        )
        manifest: dict[str, dict[str, str]] = {}
        for element in package.iter():
            if _xml_local_name(element.tag) != "item":
                continue
            item_id = element.attrib.get("id", "").strip()
            href = element.attrib.get("href", "").strip()
            if item_id and href:
                manifest[item_id] = {
                    "href": href,
                    "mediaType": element.attrib.get("media-type", ""),
                    "properties": element.attrib.get("properties", ""),
                }
        spine_items = [
            element for element in package.iter()
            if _xml_local_name(element.tag) == "itemref" and element.attrib.get("idref")
        ]
        spine_ids = [
            element.attrib.get("idref", "").strip()
            for element in spine_items
            if element.attrib.get("linear", "yes").strip().lower() != "no"
        ]
        if not spine_items:
            spine_ids = [
                item_id for item_id, item in manifest.items()
                if item["mediaType"] in {"application/xhtml+xml", "text/html"}
            ]

        chapters: list[tuple[int, str, list[str]]] = []
        total_text_bytes = 0
        for item_id in spine_ids:
            item = manifest.get(item_id)
            if not item or "nav" in item["properties"].split():
                continue
            if item["mediaType"] not in {"application/xhtml+xml", "text/html", ""}:
                continue
            member = _epub_member_path(rootfile, item["href"])
            chapter_raw = _read_epub_member(archive, member, limit=4 * 1024 * 1024)
            total_text_bytes += len(chapter_raw)
            if total_text_bytes > MAX_EPUB_TEXT_BYTES:
                raise ValueError("EPUB contains too much uncompressed chapter text")
            parser = _NovelHTMLParser()
            parser.feed(_decode_epub_html(chapter_raw))
            parser.close()
            text = parser.text
            if DEFAULT_CHAPTER_HEADING_RE.search(text):
                chapters.extend(split_paste_content(text))
                continue
            paragraphs = clean_text_lines(text)
            if not paragraphs:
                continue
            chapter_num = len(chapters) + 1
            document_title = parser.document_title.strip()
            if not document_title or document_title == suggested_title:
                document_title = f"Chapter {chapter_num}"
            chapters.append((chapter_num, document_title, paragraphs))

    if not chapters:
        raise ValueError("EPUB contains no readable chapter text")
    return _unique_chapter_numbers(chapters), suggested_title


def parse_document_bytes(
    raw: bytes,
    filename: str,
    source_lang: str = "auto",
    split_rule: str | None = None,
) -> dict:
    safe_name = Path(str(filename or "")).name
    document_format = DOCUMENT_FORMATS.get(Path(safe_name).suffix.lower())
    if not document_format:
        supported = ", ".join(sorted(DOCUMENT_FORMATS))
        raise ValueError(f"Unsupported document format; use one of: {supported}")

    suggested_title = ""
    if document_format == "epub":
        if not raw or len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"Document is too large or empty (maximum {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB)")
        chapters, suggested_title = _parse_epub_document(raw)
        encoding = "epub-xml"
    else:
        text, encoding = decode_document_bytes(raw, source_lang)
    if document_format == "json":
        chapters, suggested_title = _parse_json_document(text)
    elif document_format != "epub":
        if document_format == "markdown":
            text = _markdown_to_text(text)
        elif document_format == "html":
            parser = _NovelHTMLParser()
            parser.feed(text)
            parser.close()
            text = parser.text
            suggested_title = parser.document_title
        chapters = _unique_chapter_numbers(split_paste_content(text, split_rule))

    chapters = [(num, title, paragraphs) for num, title, paragraphs in chapters if paragraphs]
    if not chapters:
        raise ValueError("Document contains no readable chapter text")
    if len(chapters) > MAX_DOCUMENT_CHAPTERS:
        raise ValueError(f"Document contains too many chapters (maximum {MAX_DOCUMENT_CHAPTERS})")
    return {
        "filename": safe_name,
        "format": document_format,
        "encoding": encoding,
        "suggestedTitle": suggested_title,
        "chapters": chapters,
    }


def _import_chapter_chunks(
    *,
    slug: str,
    title: str,
    chunks: list[tuple[int, str, list[str]]],
    source_lang: str,
    author: str,
    source_site: str,
    source_url: str,
    force: bool,
) -> dict:
    assert_slug(slug)
    results: list[dict] = []
    imported = skipped = 0
    for num, chapter_title, paragraphs in chunks:
        out_path = source_path(slug, num)
        if out_path.exists() and not force:
            skipped += 1
            results.append({"status": "skipped", "num": num, "title": chapter_title, "path": str(out_path)})
            continue
        warnings, needs_review = validate_paragraphs(chapter_title, paragraphs)
        chapter = ExtractedChapter(
            title=chapter_title,
            paragraphs=paragraphs,
            source_url=source_url,
            source_lang=source_lang,
            warnings=warnings,
            needs_review=needs_review,
        )
        atomic_write_text(out_path, render_source_markdown(chapter, source_site, warnings))
        imported += 1
        results.append(
            {
                "status": "imported",
                "num": num,
                "title": chapter_title,
                "path": str(out_path),
                "warnings": warnings,
                "needsReview": needs_review,
            }
        )

    update_novel_json(
        slug,
        title=title or slug,
        author=author,
        source_lang=source_lang,
        source_site=source_site,
        source_url=source_url,
        total_chapters=len(chunks),
    )
    return {
        "slug": slug,
        "site": source_site,
        "title": title or slug,
        "sourceLang": source_lang,
        "chapterCount": len(chunks),
        "imported": imported,
        "skipped": skipped,
        "failed": 0,
        "results": results,
    }


def import_document_bytes(
    *,
    slug: str,
    title: str,
    filename: str,
    raw: bytes,
    source_lang: str = "auto",
    author: str = "",
    split_rule: str | None = None,
    force: bool = False,
) -> dict:
    assert_slug(slug)
    with _import_transaction_lock(slug):
        return _import_document_bytes_locked(
            slug=slug,
            title=title,
            filename=filename,
            raw=raw,
            source_lang=source_lang,
            author=author,
            split_rule=split_rule,
            force=force,
        )


def _import_document_bytes_locked(
    *,
    slug: str,
    title: str,
    filename: str,
    raw: bytes,
    source_lang: str,
    author: str,
    split_rule: str | None,
    force: bool,
) -> dict:
    parsed = parse_document_bytes(raw, filename, source_lang, split_rule)
    resolved_title = title.strip() or parsed["suggestedTitle"] or Path(parsed["filename"]).stem or slug
    source_site = f"file-{parsed['format']}"
    source_url = f"local-file:{parsed['filename']}"
    result = _import_chapter_chunks(
        slug=slug,
        title=resolved_title,
        chunks=parsed["chapters"],
        source_lang=_normalise_source_lang(source_lang),
        author=author,
        source_site=source_site,
        source_url=source_url,
        force=force,
    )
    return {
        **result,
        "format": parsed["format"],
        "encoding": parsed["encoding"],
        "sourceFilename": parsed["filename"],
    }


def import_paste(
    *,
    slug: str,
    title: str,
    content: str,
    source_lang: str = "cn",
    author: str = "",
    split_rule: str | None = None,
    force: bool = False,
) -> dict:
    assert_slug(slug)
    with _import_transaction_lock(slug):
        chunks = split_paste_content(content, split_rule)
        return _import_chapter_chunks(
            slug=slug,
            title=title or slug,
            chunks=_unique_chapter_numbers(chunks),
            source_lang=_normalise_source_lang(source_lang),
            author=author,
            source_site="manual-paste",
            source_url="manual-paste",
            force=force,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="import_sources")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sites")

    preview = sub.add_parser("preview")
    preview.add_argument("url")
    preview.add_argument("--site", default="auto")

    run = sub.add_parser("run")
    run.add_argument("url")
    run.add_argument("--slug", required=True)
    run.add_argument("--site", default="auto")
    run.add_argument("--range", dest="range_text", default=None)
    run.add_argument("--force", action="store_true")

    recover = sub.add_parser("recover-toc")
    recover.add_argument("--slug", required=True)
    recover.add_argument("--site", default="auto")
    recover.add_argument("--url", default=None)
    recover.add_argument("--dry-run", action="store_true")

    paste = sub.add_parser("paste")
    paste.add_argument("--slug", required=True)
    paste.add_argument("--title", required=True)
    paste.add_argument("--source-lang", default="cn")
    paste.add_argument("--author", default="")
    paste.add_argument("--split-rule", default=None)
    paste.add_argument("--force", action="store_true")
    paste.add_argument("--content", default=None)

    file_import = sub.add_parser("file")
    file_import.add_argument("path", nargs="?")
    file_import.add_argument("--stdin-name", default=None)
    file_import.add_argument("--slug", required=True)
    file_import.add_argument("--title", default="")
    file_import.add_argument("--source-lang", default="auto")
    file_import.add_argument("--author", default="")
    file_import.add_argument("--split-rule", default=None)
    file_import.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "sites":
            payload = import_sites()
        elif args.command == "preview":
            payload = preview_url(args.url, args.site)
        elif args.command == "run":
            payload = import_url(args.url, args.slug, args.site, args.range_text, args.force)
        elif args.command == "recover-toc":
            payload = recover_toc(args.slug, args.site, args.url, args.dry_run)
        elif args.command == "paste":
            content = args.content if args.content is not None else sys.stdin.read()
            payload = import_paste(
                slug=args.slug,
                title=args.title,
                content=content,
                source_lang=args.source_lang,
                author=args.author,
                split_rule=args.split_rule,
                force=args.force,
            )
        else:
            if args.path:
                filepath = Path(args.path)
                if not filepath.is_file():
                    raise ValueError(f"Document not found: {filepath}")
                if filepath.stat().st_size > MAX_DOCUMENT_BYTES:
                    raise ValueError(f"Document is too large (maximum {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB)")
                raw = filepath.read_bytes()
                filename = filepath.name
            elif args.stdin_name:
                raw = sys.stdin.buffer.read(MAX_DOCUMENT_BYTES + 1)
                filename = Path(args.stdin_name).name
            else:
                raise ValueError("Provide a document path or --stdin-name")
            payload = import_document_bytes(
                slug=args.slug,
                title=args.title,
                filename=filename,
                raw=raw,
                source_lang=args.source_lang,
                author=args.author,
                split_rule=args.split_rule,
                force=args.force,
            )
        print(json.dumps({"ok": True, "data": payload}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
