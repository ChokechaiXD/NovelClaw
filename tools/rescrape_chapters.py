"""Re-scrape chapters from tw.hjwzw.com Book 50356.

URL pattern: /Book/Read/50356,XXXXXXXX
Source page: /Book/Chapter/50356 (TOC, lists all ch IDs)
Body extraction: find the div containing the chapter text, strip HTML.

Usage:
  python tools/rescrape_chapters.py --list
  python tools/rescrape_chapters.py --ch 101
  python tools/rescrape_chapters.py --missing   # re-scrape ch with <1500 chars
  python tools/rescrape_chapters.py --all       # re-scrape all
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT  # noqa: E402

ROOT = NOVEL_ROOT
SRC_DIR = ROOT / 'chapters' / 'source'
TOC_URL = 'https://tw.hjwzw.com/Book/Chapter/50356'
READ_URL_TPL = 'https://tw.hjwzw.com/Book/Read/50356,{chid}'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

CHID_CACHE = SRC_DIR / '.chid_cache.json'


def fetch_toc_sync() -> dict[int, int]:
    """Return {ch_num: chid} from TOC page. Synchronous (one-shot)."""
    import urllib.request
    req = urllib.request.Request(TOC_URL, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode('utf-8', errors='ignore')
    # Find all /Book/Read/50356,XXXXXXXX links
    # and parse the chapter number from adjacent text "第N章"
    pairs = []
    # Pattern: <a href="/Book/Read/50356,24722071">第1章 xxx</a>
    for m in re.finditer(r'href="/Book/Read/50356,(\d+)"[^>]*>\s*第(\d+)章', html):
        chid = int(m.group(1))
        chnum = int(m.group(2))
        pairs.append((chnum, chid))
    if not pairs:
        # Alt pattern (TOC may use different link format)
        for m in re.finditer(r'href="/Book/Read/50356,(\d+)"', html):
            chid = int(m.group(1))
            pairs.append((chid, chid))  # fallback: chid is the index
    return dict(pairs)


def extract_body(html: str) -> str:
    """Extract clean chapter body from HTML page."""
    # Find all divs, pick the one with most Chinese text
    divs = re.findall(r'<div[^>]*>(.*?)</div>', html, re.DOTALL)
    if not divs:
        return ''
    best = max(divs, key=lambda d: len(re.sub(r'<[^>]+>', '', d)))
    # Strip HTML
    body = re.sub(r'<br\s*/?>', '\n', best, flags=re.IGNORECASE)
    body = re.sub(r'<[^>]+>', '\n', body)
    body = re.sub(r'&nbsp;', ' ', body)
    body = re.sub(r'&amp;', '&', body)
    body = re.sub(r'&lt;', '<', body)
    body = re.sub(r'&gt;', '>', body)
    body = re.sub(r'&[a-z]+;|&#\d+;', '', body)
    body = re.sub(r'\n\s*\n+', '\n', body)
    body = re.sub(r' +', ' ', body)
    return body.strip()


def extract_title(html: str) -> str:
    """Extract chapter title (e.g. 第101章 xxx)."""
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        # Title is "全球降臨：帶著嫂嫂末世種田/一條小白蛇/txt下載-黃金屋中文"
        # Chapter title is in body, look for "第N章" first
        pass
    m = re.search(r'第(\d+)章\s*([^\s<]+)', html)
    if m:
        return f'第{m.group(1)}章 {m.group(2)}'
    return ''


def clean_body(body: str, chnum: int) -> str:
    """Strip page furniture (scripts, nav, comments) and trailing numbers."""
    # Remove embedded scripts
    body = re.sub(r'window\.[^;]+;', '', body)
    body = re.sub(r'\$\([^)]+\)[^;]*;', '', body)
    # Strip page header (請記住本站域名: 黃金屋 全球降臨...) — 3 lines at top
    body = re.sub(
        r'^.*?請記住本站域名.*?(?:黃金屋|手机版|笔趣阁).*?第\s*\d+章[^\n]*\n?',
        '', body, count=1, flags=re.DOTALL
    )
    # Strip trailing 1-2 digit numbers at end of each line (page-app artifact)
    body = re.sub(r'(\S)\d{1,2}\s*$', r'\1', body, flags=re.MULTILINE)
    # Trim
    return body.strip()


def parse_chapter(html: str, chnum: int) -> tuple[str, str]:
    """Return (title, body) for a chapter page."""
    body = extract_body(html)
    body = clean_body(body, chnum)
    title = extract_title(html)
    return title, body


async def fetch_one(session: aiohttp.ClientSession, chid: int, sem: asyncio.Semaphore):
    async with sem:
        url = READ_URL_TPL.format(chid=chid)
        try:
            async with session.get(url, headers={'User-Agent': USER_AGENT},
                                   timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    return chid, None, f'HTTP {r.status}'
                html = await r.text()
                return chid, html, None
        except Exception as e:
            return chid, None, str(e)


async def scrape_chapters(chid_map: dict[int, int], chs: list[int],
                          concurrency: int = 4, delay: float = 0.3):
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        results = []
        for ch in chs:
            if ch not in chid_map:
                print(f'  ch {ch}: no chid in TOC, skipping')
                continue
            chid = chid_map[ch]
            chid_v, html, err = await fetch_one(session, chid, sem)
            if err:
                print(f'  ch {ch} (id={chid}): ERROR {err}')
                continue
            title, body = parse_chapter(html, ch)
            if not body or len(body) < 200:
                print(f'  ch {ch} (id={chid}): body too short ({len(body)} chars), saving empty')
            out = SRC_DIR / f'{ch:04d}.md'
            out.write_text(f'# {title}\n\n{body}\n', encoding='utf-8')
            print(f'  ch {ch} (id={chid}): {len(body)} chars -> {out.name}')
            results.append(ch)
            await asyncio.sleep(delay)
    return results


def find_missing_chapters() -> list[int]:
    """Find all ch with body < 1500 chars (suspect).

    Counts whitespace-stripped length to ignore CN convention of
    no spaces between characters. Threshold 1500 = below typical
    web novel chapter length (usually 2,500-4,000 stripped chars).
    """
    out = []
    for f in sorted(SRC_DIR.glob('0*.md'), key=lambda p: int(p.stem)):
        n = int(f.stem)
        if n < 1 or n > 1500:
            continue
        body = f.read_text(encoding='utf-8')
        body = re.sub(r'\s+', '', body)
        if len(body) < 500:  # CN text without spaces — anything < 500 = real broken
            out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='List missing chapters only')
    ap.add_argument('--ch', type=int, help='Scrape single chapter')
    ap.add_argument('--missing', action='store_true', help='Scrape all < 1500 char chapters')
    ap.add_argument('--all', action='store_true', help='Scrape all chapters')
    ap.add_argument('--from', type=int, dest='from_', help='Start ch number')
    ap.add_argument('--to', type=int, help='End ch number')
    ap.add_argument('--concurrency', type=int, default=4)
    args = ap.parse_args()

    if args.list or args.missing:
        missing = find_missing_chapters()
        print(f'Found {len(missing)} chapters with < 1500 chars:')
        print(missing[:50], '...' if len(missing) > 50 else '')
        if not args.missing:
            return
        chs = missing
    elif args.ch:
        chs = [args.ch]
    elif args.all:
        chs = list(range(1, 1240))
    elif args.from_ or args.to:
        f = args.from_ or 1
        t = args.to or 1239
        chs = list(range(f, t + 1))
    else:
        ap.print_help()
        return

    # Get TOC
    print(f'Fetching TOC from {TOC_URL}...')
    chid_map = fetch_toc_sync()
    print(f'Got {len(chid_map)} ch IDs from TOC')

    if not chid_map:
        print('ERROR: no ch IDs from TOC. Aborting.')
        return

    # Save cache
    CHID_CACHE.write_text(json.dumps({str(k): v for k, v in chid_map.items()}, indent=2), encoding='utf-8')

    # Run async scrape
    print(f'Scraping {len(chs)} chapters (concurrency={args.concurrency})...')
    asyncio.run(scrape_chapters(chid_map, chs, concurrency=args.concurrency))


if __name__ == '__main__':
    main()
