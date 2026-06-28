#!/usr/bin/env python3
"""
scraper.py — Novel source chapter scraper.

Download source chapters from supported websites and save as .md files.
Supports multi-chapter downloads with retry and incremental mode.

Usage (via novelclaw.py CLI):
    novelclaw scrape 1-10           # download chapters 1-10
    novelclaw scrape 1-10 --site 69shu  # use 69shu
    novelclaw scrape 1               # single chapter
    novelclaw scrape 1-10 --incremental  # skip existing

Supported sites:
    - 69shu (69书吧) — default
    - uukanshu (UU看书)

Output: novels/<slug>/chapters/source/<ch:04d>.md
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_NOVELS_DIR = _PROJECT_ROOT / "novels"


# ── URL builders ─────────────────────────────────────────────────────

def _build_url_69shu(novel_id: str, ch: int) -> str:
    """Build chapter URL for 69shu.com"""
    return f"https://www.69shu.com/{novel_id}/{ch}.html"


def _build_url_uukanshu(novel_id: str, ch: int) -> str:
    """Build chapter URL for uukanshu.com"""
    return f"https://www.uukanshu.com/b/{novel_id}/{ch}.html"


# ── Extractors ────────────────────────────────────────────────────────

def _extract_69shu(html: str) -> str | None:
    """Extract chapter content from 69shu HTML."""
    # Try <div class="content" id="content">
    m = re.search(r'<div[^>]*class\s*=\s*["\']content["\'][^>]*id\s*=\s*["\']content["\'][^>]*>(.*?)</div>', html, re.S)
    if not m:
        m = re.search(r'<div[^>]*id\s*=\s*["\']content["\'][^>]*>(.*?)</div>', html, re.S)
    if not m:
        return None

    text = m.group(1)
    # Clean HTML tags
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^\s*\n', '', text, flags=re.MULTILINE)
    return text.strip()


def _extract_uukanshu(html: str) -> str | None:
    """Extract chapter content from uukanshu HTML."""
    m = re.search(r'<div[^>]*id\s*=\s*["\']contentbox["\'][^>]*>(.*?)</div>', html, re.S)
    if not m:
        m = re.search(r'<div[^>]*id\s*=\s*["\']content["\'][^>]*>(.*?)</div>', html, re.S)
    if not m:
        return None

    text = m.group(1)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Site config ──────────────────────────────────────────────────────

SITES = {
    "69shu": {
        "url_fn": _build_url_69shu,
        "extract": _extract_69shu,
        "delay": 1.0,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.69shu.com/",
        },
    },
    "uukanshu": {
        "url_fn": _build_url_uukanshu,
        "extract": _extract_uukanshu,
        "delay": 1.5,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    },
}


# ── Core scraper ─────────────────────────────────────────────────────


def fetch_chapter(url: str, headers: dict, timeout: int = 30) -> str:
    """Download a chapter URL."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _get_slug_source_dir(slug: str) -> Path:
    """Get source directory for a novel."""
    d = _NOVELS_DIR / slug / "chapters" / "source"
    d.mkdir(parents=True, exist_ok=True)
    return d


def scrape_chapter(
    ch: int,
    slug: str = "global-descent",
    novel_id: str | None = None,
    site: str = "69shu",
    force: bool = False,
) -> dict:
    """Scrape a single chapter and save to source/<ch>.md.

    Args:
        ch: Chapter number.
        slug: Novel slug (directory name).
        novel_id: Site-specific novel ID (auto-detect from novel.json if None).
        site: Site name ("69shu" or "uukanshu").
        force: Re-download even if file exists.

    Returns:
        {"status": "ok"|"exists"|"failed", "ch": ch, "path": "..."}
    """
    src_dir = _get_slug_source_dir(slug)
    out_path = src_dir / f"{ch:04d}.md"

    if out_path.exists() and not force:
        return {"status": "exists", "ch": ch, "path": str(out_path)}

    # Auto-detect novel_id
    if not novel_id:
        novel_json = _NOVELS_DIR / slug / "novel.json"
        if novel_json.exists():
            try:
                data = json.loads(novel_json.read_text(encoding="utf-8"))
                novel_id = data.get(f"{site}_id") or data.get("id") or data.get("sourceId")
            except Exception:
                pass
        if not novel_id:
            return {"status": "failed", "ch": ch, "reason": "no novel_id (set in novel.json or pass --novel-id)"}

    site_cfg = SITES.get(site)
    if not site_cfg:
        return {"status": "failed", "ch": ch, "reason": f"unknown site: {site}"}

    url = site_cfg["url_fn"](novel_id, ch)
    extract = site_cfg["extract"]
    headers = site_cfg["headers"]

    try:
        html = fetch_chapter(url, headers)
    except urllib.error.HTTPError as e:
        return {"status": "failed", "ch": ch, "reason": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"status": "failed", "ch": ch, "reason": f"Connection: {e.reason}"}
    except Exception as e:
        return {"status": "failed", "ch": ch, "reason": str(e)[:120]}

    content = extract(html)
    if not content:
        return {"status": "failed", "ch": ch, "reason": "empty content"}

    # Save
    out_path.write_text(content, encoding="utf-8")
    return {"status": "ok", "ch": ch, "path": str(out_path)}


def scrape_range(
    start: int,
    end: int,
    slug: str = "global-descent",
    novel_id: str | None = None,
    site: str = "69shu",
    force: bool = False,
    incremental: bool = True,
    delay: float | None = None,
) -> list[dict]:
    """Scrape a range of chapters.

    Args:
        start: First chapter (inclusive).
        end: Last chapter (inclusive).
        slug: Novel slug.
        novel_id: Site novel ID.
        site: Site name.
        force: Re-download existing.
        incremental: Skip existing (default True).
        delay: Seconds between requests (None = site default).

    Returns:
        List of result dicts.
    """
    results = []
    site_cfg = SITES.get(site, {})
    delay_sec = delay if delay is not None else site_cfg.get("delay", 1)

    for ch in range(start, end + 1):
        # If incremental, skip existing
        if incremental and not force:
            src_dir = _get_slug_source_dir(slug)
            if (src_dir / f"{ch:04d}.md").exists():
                results.append({"status": "exists", "ch": ch, "path": str(src_dir / f"{ch:04d}.md")})
                continue

        result = scrape_chapter(ch, slug, novel_id, site, force)
        results.append(result)

        if result["status"] == "ok":
            print(f"  ✅ ตอน {ch}: {len(open(result['path']).read())} chars")
        elif result["status"] == "exists":
            print(f"  ⏭️  ตอน {ch}: มีแล้ว")
        else:
            print(f"  ❌ ตอน {ch}: {result.get('reason', '?')}")

        # Delay between requests
        if ch < end:
            time.sleep(delay_sec)

    return results
