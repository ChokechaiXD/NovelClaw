"""scrape_chapters.py — Scrape chapter source from Chinese novel sites.

Tier 1: qidian.com (no Cloudflare, Python requests)
Tier 2: agent-browser fallback for JS-rendered sites

Usage:
    # Single chapter
    python tools/scrape_chapters.py 128
    
    # Range
    python tools/scrape_chapters.py 128-130
    
    # Specific novel slug
    python tools/scrape_chapters.py 128 --novel global-descent

The source file is saved to novels/<slug>/chapters/source/<num>.md
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional


# ── Book IDs ───────────────────────────────────────────────────────────

# Map novel slug → qidian.com book info
BOOK_MAP: dict[str, dict] = {
    "global-descent": {
        "name": "全球降臨：帶著嫂嫂末世種田",
        "book_id": "1040133596",
        "book_url": "https://m.qidian.com/book/1040133596/",
        "catalog_url": "https://m.qidian.com/book/1040133596/catalog/",
        "cname_prefix": "第",  # chapter name prefix: "第128章"
    },
    "global-descent-qq": {
        "name": "冰封末世：我打造完美領地",
        "book_id": "50133618",
        "book_url": "https://book.qq.com/book-detail/50133618",
        "catalog_url": None,
        "cname_prefix": "第",
    },
}

# Cache for chapter IDs (catalog page)
_CATALOG_CACHE: dict[str, dict[int, str]] = {}


# ── Tier 1: Python requests ──────────────────────────────────────────

def _fetch_with_requests(url: str, session=None) -> Optional[str]:
    """Fetch a URL using Python requests with mobile UA.

    Best for: qidian.com (no Cloudflare protection)
    Returns: HTML text, or None on failure
    """
    if session is None:
        import requests as req
    else:
        req = session
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        resp = req.get(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            cn = len(re.findall(r'[\u4e00-\u9fff]', resp.text))
            if cn > 50:
                return resp.text
        return None
    except Exception:
        return None


def _find_chapter_ids(slug: str, session=None) -> dict[int, str]:
    """Fetch catalog page and extract chapter ID mapping.

    Returns: {chapter_number: cid_string}
    """
    if slug in _CATALOG_CACHE:
        return _CATALOG_CACHE[slug]
    
    info = BOOK_MAP.get(slug)
    if not info or not info.get("catalog_url"):
        return {}
    
    html = _fetch_with_requests(info["catalog_url"], session)
    if not html:
        return {}
    
    # qidian catalog format:
    # data-cid="XXXXX" ... 第128章 布隆进阶
    result: dict[int, str] = {}
    
    # Pattern: data-cid="12345"...>第128章</a>
    # Or newer format: href="/chapter/{bid}/{cid}"
    for m in re.finditer(
        r'data-cid=["\'](\d+)["\'][^>]*>[^<]*第(\d+)章',
        html
    ):
        cid = m.group(1)
        ch_num = int(m.group(2))
        result[ch_num] = cid
    
    # Try alternate pattern: .../chapter/bid/cid/
    if not result:
        bid = info["book_id"]
        alt_pattern = rf'/chapter/{bid}/(\d+)/[^>]*>第(\d+)章'
        for m in re.finditer(alt_pattern, html):
            cid = m.group(1)
            ch_num = int(m.group(2))
            result[ch_num] = cid
    
    _CATALOG_CACHE[slug] = result
    return result


def _extract_qidian_content(html: str) -> Optional[str]:
    """Extract clean chapter content from qidian chapter page HTML.

    Qidian renders content inside <div class="content mt-..."><p>...</p></div>
    """
    # Find content div
    m = re.search(r'<div[^>]*class="content[^"]*"[^>]*>(.*?)</main>', html, re.DOTALL)
    if not m:
        # Try alternative: find all meaningful <p> tags
        paras = []
        for p in re.finditer(r'<p>(.*?)</p>', html, re.DOTALL):
            text = re.sub(r'<[^>]+>', '', p.group(1)).strip()
            text = re.sub(r'&nbsp;|\u3000|\s+', ' ', text).strip()
            cn = len(re.findall(r'[\u4e00-\u9fff]', text))
            if cn > 10 and len(text) > 20:
                paras.append(text)
        
        if paras:
            return "\n\n".join(paras)
        return None
    
    content = m.group(1)
    
    # Clean script/style tags
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
    
    # Extract text from <p> tags
    paras = []
    for p in re.finditer(r'<p>(.*?)</p>', content, re.DOTALL):
        text = re.sub(r'<[^>]+>', '', p.group(1)).strip()
        text = re.sub(r'&nbsp;|\u3000|\s+', ' ', text).strip()
        if text:
            paras.append(text)
    
    if paras:
        return "\n\n".join(paras)
    
    # Fallback: strip all HTML
    text = re.sub(r'<[^>]+>', '\n', content)
    text = re.sub(r'&nbsp;|\u3000', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    
    return text if len(text) > 50 else None


def scrape_qidian(ch_num: int, slug: str = "global-descent") -> Optional[str]:
    """Scrape chapter content from qidian.com.

    Strategy:
    1. Fetch catalog to find chapter CID
    2. Fetch chapter page with CID
    3. Extract content from HTML

    Args:
        ch_num: Chapter number (e.g. 128)
        slug: Novel slug

    Returns:
        Clean chapter text, or None on failure
    """
    import requests as req
    
    session = req.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    
    info = BOOK_MAP.get(slug)
    if not info:
        print(f"  ❌ Unknown novel slug: {slug}")
        return None
    
    # Step 1: Find chapter CID
    cid_map = _find_chapter_ids(slug, session)
    cid = cid_map.get(ch_num)
    
    if not cid:
        print(f"  ⚠ Chapter {ch_num} CID not found in catalog, trying direct URL")
        # Try direct URL format: /chapter/{bid}/{cid}/
        chapter_url = f"https://m.qidian.com/chapter/{info['book_id']}/{ch_num}/"
    else:
        chapter_url = f"https://m.qidian.com/chapter/{info['book_id']}/{cid}/"
    
    print(f"  URL: {chapter_url}")
    
    # Step 2: Fetch chapter page
    html = _fetch_with_requests(chapter_url, session)
    if not html:
        print("  ❌ Failed to fetch chapter page")
        return None
    
    # Step 3: Extract content
    content = _extract_qidian_content(html)
    if not content:
        print("  ❌ Failed to extract content from page")
        return None
    
    cn_count = len(re.findall(r'[\u4e00-\u9fff]', content))
    print(f"  ✅ Extracted {cn_count} CN chars, {len(content)} total chars")
    
    return content


# ── Tier 2: agent-browser fallback ───────────────────────────────────

def _has_agent_browser() -> bool:
    """Check if agent-browser is installed."""
    import shutil
    if shutil.which("agent-browser"):
        return True
    # Check common install paths
    for p in [
        Path.home() / "node_modules" / "agent-browser" / "bin" / "agent-browser-win32-x64.exe",
    ]:
        if p.exists():
            return True
    return False


def scrape_with_agent_browser(ch_num: int, slug: str = "global-descent") -> Optional[str]:
    """Scrape chapter content using agent-browser CLI.

    Fallback for sites that need JS rendering.
    """
    import subprocess
    
    agent_path = None
    for p in [
        "agent-browser",
        str(Path.home() / "node_modules" / "agent-browser" / "bin" / "agent-browser-win32-x64.exe"),
    ]:
        if p == "agent-browser":
            if _has_agent_browser():
                agent_path = p
                break
        elif Path(p).exists():
            agent_path = p
            break
    
    if not agent_path:
        print("  ❌ agent-browser not installed. Run: npm install -g agent-browser")
        return None
    
    info = BOOK_MAP.get(slug)
    if not info:
        return None
    
    url = f"https://m.qidian.com/chapter/{info['book_id']}/{ch_num}/"
    print(f"  URL: {url}")
    
    try:
        result = subprocess.run(
            [agent_path, "open", url, "--timeout", "20s"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
        
        cn = len(re.findall(r'[\u4e00-\u9fff]', output))
        if cn > 200:
            # Extract content from snapshot
            # agent-browser may have it in the output
            paras = []
            for line in output.split('\n'):
                cn_line = len(re.findall(r'[\u4e00-\u9fff]', line))
                if cn_line > 10:
                    paras.append(line.strip())
            if paras:
                return "\n\n".join(paras)
        
        # Try snapshot
        snap_result = subprocess.run(
            [agent_path, "snapshot", "--full"],
            capture_output=True, text=True, timeout=15
        )
        snap = snap_result.stdout
        cn = len(re.findall(r'[\u4e00-\u9fff]', snap))
        if cn > 200:
            # Try to extract content
            content = re.sub(r' - .*?\n', '\n', snap)
            content = re.sub(r'\[ref=e\d+\]', '', content)
            return content
        
        return None
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  ❌ agent-browser failed: {e}")
        return None


# ── Save ──────────────────────────────────────────────────────────────

def _save_source(content: str, ch_num: int, slug: str = "global-descent") -> Path:
    """Save scraped content to source file."""
    novel_root = Path(__file__).resolve().parent.parent / "novels" / slug
    source_dir = novel_root / "chapters" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    
    dest = source_dir / f"{ch_num:04d}.md"
    dest.write_text(content, encoding="utf-8")
    
    print(f"  💾 Saved: {dest} ({len(content)} chars)")
    return dest


# ── Main ──────────────────────────────────────────────────────────────

def scrape(ch_num: int, slug: str = "global-descent", use_agent: bool = False) -> bool:
    """Scrape a single chapter.

    Returns: True if successful
    """
    print(f"\n─── Scraping chapter {ch_num} ({slug}) ───")
    
    # Tier 1: Python requests → qidian
    if not use_agent:
        content = scrape_qidian(ch_num, slug)
        if content:
            _save_source(content, ch_num, slug)
            return True
    
    # Tier 2: agent-browser fallback
    if _has_agent_browser():
        print("  → Trying agent-browser (Tier 2)")
        content = scrape_with_agent_browser(ch_num, slug)
        if content:
            _save_source(content, ch_num, slug)
            return True
    
    print("  ❌ All tiers failed")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape chapter source from Chinese novel sites."
    )
    parser.add_argument("chapters",
                        help="Chapter number or range (128 or 128-130)")
    parser.add_argument("--novel", "-n", default="global-descent",
                        help="Novel slug (default: global-descent)")
    parser.add_argument("--agent", action="store_true",
                        help="Force agent-browser instead of Python requests")
    parser.add_argument("--list", action="store_true",
                        help="List available chapters from catalog")
    
    args = parser.parse_args()
    slug = args.novel.lower().replace(" ", "-")
    
    # Parse chapter range
    if "-" in args.chapters:
        parts = args.chapters.split("-")
        start, end = int(parts[0]), int(parts[1])
        ch_nums = list(range(start, end + 1))
    else:
        ch_nums = [int(args.chapters)]
    
    # List mode
    if args.list:
        print(f"\n─── Available chapters ({slug}) ───")
        cid_map = _find_chapter_ids(slug)
        if cid_map:
            for ch in sorted(cid_map.keys())[:20]:
                print(f"  Ch {ch} → CID {cid_map[ch]}")
            print(f"  ... ({len(cid_map)} total)")
        else:
            print("  No chapters found. Check slug or internet connection.")
        return
    
    # Scrape mode
    success = 0
    for ch in ch_nums:
        ok = scrape(ch, slug, args.agent)
        if ok:
            success += 1
    
    print(f"\n─── Result: {success}/{len(ch_nums)} chapters scraped ───")


if __name__ == "__main__":
    main()
