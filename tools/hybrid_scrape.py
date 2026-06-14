"""hybrid_scrape.py — Multi-tier scraper for web novel chapters.

Tier-based design for future-proof content extraction:

  Tier 1: HTML fetch (fast, 0.5s/ch) — works for 80%+ of sites/chapters
  Tier 2: Playwright screenshot + OCR (slow, 5-10s/ch) — fallback when
          HTML returns fragment/contamination
  Tier 3: Manual flag (returns None) — log for human review

Each tier has its own verification:
  - Body length >= MIN_BODY_CHARS (default 2000 stripped)
  - No contamination markers (random characters from other novels)
  - Contains at least 1 main character mention (e.g. 曹星)

Site config lives in `tools/sites/<name>.json` for site-agnostic
support. Add a new site = drop a JSON file.

Usage:
  python hybrid_scrape.py --site hjwzw --ch 988        # single ch
  python hybrid_scrape.py --site hjwzw --range 800 999  # ch range
  python hybrid_scrape.py --site hjwzw --missing       # re-scrape bad ch
  python hybrid_scrape.py --site hjwzw --all           # all ch

Output: novels/<name>/chapters/source/NNNN.md (overwrites existing)
Logs:   novels/<name>/chapters/source/.scrape_log.json
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import aiohttp
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT, SOURCE_DIR  # noqa: E402

# Sites directory
SITES_DIR = Path(__file__).parent / 'sites'

# Verification thresholds
MIN_BODY_CHARS = 2000           # stripped (no whitespace) chars
MAIN_CHAR_MARKERS = ['曹星', '星火城', '一條小白蛇', '陳江', '柳慕雪',
                     '梅爾', '埃麗莎', '希兒妲', '蕾妮絲']  # any 1 = real
# Contamination markers — if ANY present, body is mixed with other novels
CONTAMINATION_MARKERS = ['林平之', '左冷禪', '蒼龍山脈', '楚笛', '趙水田',
                          '于波一郎', '雲沐陽', '紀濤云', '司馬懿']

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# Default verify quality function
def verify_body(body: str) -> tuple[bool, str]:
    """Return (passed, reason). Reason is empty if passed."""
    if not body:
        return False, 'empty'
    stripped = re.sub(r'\s+', '', body)
    if len(stripped) < MIN_BODY_CHARS:
        return False, f'too_short({len(stripped)}<{MIN_BODY_CHARS})'
    # Contamination check
    for marker in CONTAMINATION_MARKERS:
        if marker in body:
            return False, f'contaminated({marker})'
    # Main character check (any 1 marker = real)
    if not any(m in body for m in MAIN_CHAR_MARKERS):
        return False, 'no_main_character'
    return True, ''


# ── Tier 1: HTML fetch ───────────────────────────────────────────────

def parse_hjwzw_html(html: str) -> str:
    """hjwzw-specific HTML parser (reused from rescrape_chapters.py)."""
    # Find all divs, pick the one with most Chinese text
    divs = re.findall(r'<div[^>]*>(.*?)</div>', html, re.DOTALL)
    if not divs:
        return ''
    best = max(divs, key=lambda d: len(re.sub(r'<[^>]+>', '', d)))
    body = re.sub(r'<br\s*/?>', '\n', best, flags=re.IGNORECASE)
    body = re.sub(r'<[^>]+>', '\n', body)
    body = re.sub(r'&nbsp;', ' ', body)
    body = re.sub(r'&amp;', '&', body)
    body = re.sub(r'&lt;', '<', body)
    body = re.sub(r'&gt;', '>', body)
    body = re.sub(r'&[a-z]+;|&#\d+;', '', body)
    body = re.sub(r'\n\s*\n+', '\n', body)
    body = re.sub(r' +', ' ', body)
    # Strip page header
    body = re.sub(
        r'^.*?請記住本站域名.*?(?:黃金屋|手机版|笔趣阁).*?第\s*\d+章[^\n]*\n?',
        '', body, count=1, flags=re.DOTALL
    )
    # Strip trailing 1-2 digit line numbers
    body = re.sub(r'(\S)\d{1,2}\s*$', r'\1', body, flags=re.MULTILINE)
    return body.strip()


def parse_hjwzw_trim_at_contamination(html: str) -> str:
    """hjwzw parser that trims content at contamination boundary.

    hjwzw ch 800+ injects 'random recommendations' section after the
    real ch content, mixing in text from other web novels. We detect
    the boundary by looking for contamination markers and cut the body
    at the FIRST marker occurrence, keeping only the real ch content.

    For ch 800+, the real content is typically very short (< 500 chars)
    because the site returns fragments. We use STRICTER detection: any
    contamination marker = boundary (since real ch content is unlikely
    to mention these specific character names from other novels).
    """
    body = parse_hjwzw_html(html)
    if not body:
        return body

    # Strict contamination markers — these NEVER appear in 全球降臨 novel
    # (verified by checking real ch 1-799 from uukanshu)
    contamination_markers = [
        '林平之', '左冷禪', '于波一郎', '陸承楓', '陸雲', '聶英', '宋無敵',
        '宇波智', '古桐', '霍斯燕', '杜明', '張若風', '莫凡', '林凡',
        '陳丹青', '朱木藝', '嚴戰', '徐坤', '古佛族', '佛漣大師', '谷主',
        '魔主', '云沐陽', '紀濤云', '司馬懿', '楚笛', '趙水田', '晴兒',
        '刀疤臉', '楊雪', '蒼龍山脈', '蕭陽',  # '蕭陽' might be in real — included anyway
    ]

    earliest = len(body)
    found_marker = None
    for marker in contamination_markers:
        idx = body.find(marker)
        if idx >= 0 and idx < earliest:
            earliest = idx
            found_marker = marker

    if found_marker is None:
        return body  # no contamination detected

    # Truncate at marker, then back up to last paragraph break
    trimmed = body[:earliest]
    last_break = max(trimmed.rfind('\n\n'), trimmed.rfind('。\n'),
                     trimmed.rfind('！\n'), trimmed.rfind('？\n'))
    if last_break > 0 and len(trimmed) - last_break < 200:
        trimmed = trimmed[:last_break].rstrip()
    return trimmed


def get_hjwzw_parser_for_ch(ch_num: int):
    """Return hjwzw parser function based on ch number."""
    if ch_num >= 800:
        return parse_hjwzw_trim_at_contamination
    return parse_hjwzw_html


def parse_uukanshu_html(html: str) -> str:
    """uukanshu-specific HTML parser.

    Structure: <div class="readcotent bbb font-normal"> contains body
    with <br /> line breaks. Also has script tags (ads) we must skip.
    """
    # Find readcotent div
    m = re.search(
        r'<div[^>]*class="[^"]*readcotent[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if not m:
        # Fallback: largest div with Chinese
        divs = re.findall(r'<div[^>]*>(.*?)</div>', html, re.DOTALL)
        divs = [d for d in divs if len(re.sub(r'<[^>]+>', '', d)) > 500]
        if not divs:
            return ''
        best = max(divs, key=lambda d: len(re.sub(r'<[^>]+>', '', d)))
    else:
        best = m.group(1)
    # Convert <br> to newlines, strip everything else
    body = re.sub(r'<br\s*/?>', '\n', best, flags=re.IGNORECASE)
    body = re.sub(r'<script.*?</script>', '', body, flags=re.DOTALL)
    body = re.sub(r'<[^>]+>', '', body)
    body = re.sub(r'&nbsp;', ' ', body)
    body = re.sub(r'&amp;', '&', body)
    body = re.sub(r'&lt;', '<', body)
    body = re.sub(r'&gt;', '>', body)
    body = re.sub(r'&[a-z]+;|&#\d+;', '', body)
    # Strip leading &emsp; and page header
    body = re.sub(r'^[\s&;emsp;【】（）()]+', '', body)
    # Strip trailing line numbers
    body = re.sub(r'(\S)\d{1,2}\s*$', r'\1', body, flags=re.MULTILINE)
    body = re.sub(r'\n\s*\n+', '\n', body)
    body = re.sub(r' +', ' ', body)
    return body.strip()


async def tier1_html(url: str, session: aiohttp.ClientSession,
                     site_config: dict, ch_num: int = 0) -> tuple[str, str]:
    """Tier 1: HTML fetch + parse. Returns (body, error_msg)."""
    # Retry on 429 (rate limit) — 3 attempts with backoff
    last_err = ''
    for attempt in range(3):
        try:
            async with session.get(url, headers={'User-Agent': USER_AGENT},
                                   timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 429:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
                    last_err = f'HTTP 429 (attempt {attempt+1})'
                    continue
                if r.status != 200:
                    return '', f'HTTP {r.status}'
                html = await r.text()
                break
        except Exception as e:
            return '', f'fetch_error: {e}'
    else:
        return '', last_err or 'HTTP 429'

    # Use site-specific parser (or ch-aware variant for hjwzw ch 800+)
    site = site_config.get('name', '')
    if site == 'hjwzw' and ch_num >= 800:
        body = parse_hjwzw_trim_at_contamination(html)
    else:
        parser_name = site_config.get('html_parser', 'parse_hjwzw_html')
        parser_fn = globals().get(parser_name)
        if parser_fn is None:
            body = ''
        else:
            body = parser_fn(html)

    return body, ''


# ── Tier 2: Playwright + OCR ─────────────────────────────────────────

async def tier2_ocr(url: str, ocr_reader, browser) -> tuple[str, str]:
    """Tier 2: Headless browser + DOM text + OCR fallback. Returns (body, error_msg).

    Strategy:
      1. Load page in headless browser
      2. Try to extract body from rendered DOM (best div heuristic)
      3. If DOM text is too short, screenshot the body div and OCR it
      4. If OCR also fails, return error
    """
    try:
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 800, 'height': 1200},
        )
        page = await context.new_page()
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        # Wait for JS to populate content
        await page.wait_for_timeout(3000)

        # Find body div (largest div with Chinese text)
        best_el = await page.evaluate("""
            () => {
                const divs = Array.from(document.querySelectorAll('div'));
                let best = null, bestLen = 0;
                for (const d of divs) {
                    const text = d.innerText || '';
                    if (text.length > bestLen) {
                        bestLen = text.length;
                        best = d;
                    }
                }
                return best ? {
                    text: best.innerText,
                    rect: best.getBoundingClientRect()
                } : null;
            }
        """)
        if not best_el or not best_el.get('text'):
            await context.close()
            return '', 'no_content_div'

        text = best_el['text']

        # Clean: remove page header
        text = re.sub(
            r'請記住本站域名.*?(?:黃金屋|手机版|笔趣阁).*?第\s*\d+章[^\n]*\n?',
            '', text, count=1, flags=re.DOTALL
        )
        # Strip trailing line numbers
        text = re.sub(r'(\S)\d{1,2}\s*$', r'\1', text, flags=re.MULTILINE)
        text = text.strip()

        # If DOM text is too short, try OCR on screenshot
        stripped = re.sub(r'\s+', '', text)
        if len(stripped) < MIN_BODY_CHARS and ocr_reader is not None:
            try:
                # Screenshot the body element
                rect = best_el.get('rect', {})
                if rect and rect.get('width', 0) > 0:
                    el = await page.query_selector('div:has-text("' + text[:50].replace('"', "'") + '")')
                    if el:
                        png_bytes = await el.screenshot()
                    else:
                        png_bytes = await page.screenshot(full_page=True)
                else:
                    png_bytes = await page.screenshot(full_page=True)
                # Save screenshot for debugging
                debug_path = Path('.scrape_debug') / f'{url.split(",")[-1]}.png'
                debug_path.parent.mkdir(exist_ok=True)
                debug_path.write_bytes(png_bytes)

                # OCR
                import numpy as np
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(png_bytes))
                arr = np.array(img)
                results = ocr_reader.readtext(arr)
                text = '\n'.join([r[1] for r in results])
                # Re-clean
                text = re.sub(
                    r'請記住本站域名.*?(?:黃金屋|手机版|笔趣阁).*?第\s*\d+章[^\n]*\n?',
                    '', text, count=1, flags=re.DOTALL
                )
                text = re.sub(r'(\S)\d{1,2}\s*$', r'\1', text, flags=re.MULTILINE)
                text = text.strip()
            except Exception as ocr_err:
                # OCR failed but we have DOM text — return what we have
                pass

        await context.close()
        return text, ''

    except Exception as e:
        return '', f'ocr_error: {e}'


# ── Main orchestration ───────────────────────────────────────────────

async def fetch_one_chapter(site: str, ch_num: int, chid: int,
                            session: aiohttp.ClientSession,
                            ocr_reader, browser, site_config: dict) -> dict:
    """Fetch 1 ch using tier-based logic. Returns result dict."""
    url = site_config['read_url_template'].format(chid=chid)
    result = {
        'ch': ch_num, 'chid': chid, 'url': url, 'site': site,
        'tier_used': None, 'body_len': 0, 'status': 'fail', 'error': '',
    }

    # Tier 1
    body, err = await tier1_html(url, session, site_config, ch_num)
    if not err and verify_body(body)[0]:
        result['tier_used'] = 'tier1_html'
        result['body_len'] = len(re.sub(r'\s+', '', body))
        result['status'] = 'ok'
        result['body'] = body
        return result

    tier1_err = err or verify_body(body)[1]
    result['tier1_error'] = tier1_err

    # Tier 2 (OCR fallback)
    if ocr_reader is not None and browser is not None:
        body2, err2 = await tier2_ocr(url, ocr_reader, browser)
        if not err2 and verify_body(body2)[0]:
            result['tier_used'] = 'tier2_ocr'
            result['body_len'] = len(re.sub(r'\s+', '', body2))
            result['status'] = 'ok'
            result['body'] = body2
            return result
        tier2_err = err2 or verify_body(body2)[1]
        result['tier2_error'] = tier2_err

    result['error'] = f'tier1: {tier1_err}' + (
        f'; tier2: {tier2_err}' if 'tier2_err' in dir() else '')
    return result


def load_site_config(site: str) -> dict:
    """Load site config from tools/sites/<site>.json"""
    config_path = SITES_DIR / f'{site}.json'
    if not config_path.exists():
        raise FileNotFoundError(f'Site config not found: {config_path}')
    return json.loads(config_path.read_text(encoding='utf-8'))


def fetch_toc(site_config: dict) -> dict[int, int]:
    """Fetch TOC from site, return {ch_num: chid}."""
    import urllib.request
    req = urllib.request.Request(site_config['toc_url'],
                                  headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode('utf-8', errors='ignore')

    # Generic TOC pattern: find /<read_url_path>/50356,XXXXXXXX near 第N章
    toc_pattern = site_config.get('toc_pattern', None)
    if toc_pattern:
        # Pattern format: capture (chid, chnum) in named/group form
        return {int(m.group(2)): int(m.group(1))
                for m in re.finditer(toc_pattern, html)}

    # Default: hjwzw-style
    pairs = []
    for m in re.finditer(r'href="(/Book/Read/\d+,\d+)"[^>]*>\s*第(\d+)章', html):
        chid = int(re.search(r'(\d+)$', m.group(1)).group(1))
        chnum = int(m.group(2))
        pairs.append((chnum, chid))
    return dict(pairs)


async def run_scrape(site: str, chs: list[int], concurrency: int = 4, delay: float = 0.5):
    """Main scrape loop."""
    site_config = load_site_config(site)
    print(f'=== Hybrid scrape: site={site}, chs={len(chs)} ===')

    # Fetch TOC
    print('Fetching TOC...')
    chid_map = fetch_toc(site_config)
    print(f'Got {len(chid_map)} ch IDs from TOC')

    # Try to load OCR lazily (skip by default — slow startup, only used as fallback)
    ocr_reader = None
    browser = None
    enable_ocr = False
    if '--no-ocr' not in sys.argv and '-h' not in sys.argv and '--help' not in sys.argv:
        # Allow opt-in: HUB_OCR=1 or --ocr
        import os
        if os.environ.get('HUB_OCR') == '1' or '--ocr' in sys.argv:
            enable_ocr = True
    if enable_ocr:
        try:
            import easyocr
            print('Loading EasyOCR (one-time model download if not cached)...')
            ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
        except Exception as e:
            print(f'EasyOCR not available: {e}. Tier 2 disabled.')
            ocr_reader = None

    if ocr_reader is not None:
        print('Launching headless browser...')
        pw = await async_playwright().start()
        # Use installed Chrome (not chromium download)
        browser = await pw.chromium.launch(
            headless=True,
            executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            args=['--disable-blink-features=AutomationControlled']
        )

    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        async def bounded_fetch(ch_num):
            chid = chid_map.get(ch_num)
            if chid is None:
                return {'ch': ch_num, 'status': 'no_chid', 'error': 'no chid in TOC'}
            async with sem:
                # Small delay to be polite to servers (avoid 429)
                await asyncio.sleep(delay)
                r = await fetch_one_chapter(site, ch_num, chid, session,
                                            ocr_reader, browser, site_config)
                if r.get('status') == 'ok':
                    # Write to file
                    title = f'第{ch_num}章'
                    out = SOURCE_DIR / f'{ch_num:04d}.md'
                    out.write_text(f'# {title}\n\n{r["body"]}\n', encoding='utf-8')
                return r

        tasks = [bounded_fetch(ch) for ch in chs]
        results = []
        t0 = time.time()
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            r = await coro
            results.append(r)
            tier = r.get('tier_used') or '-'
            err = r.get('error', '')
            body_len = r.get('body_len') or 0
            print(f'  [{i}/{len(chs)}] ch {r["ch"]:>4} {tier:>10} {r["status"]} {body_len:>5} chars {err[:60]}', flush=True)

    if browser is not None:
        await browser.close()
        await pw.stop()

    # Summary
    elapsed = time.time() - t0
    ok = sum(1 for r in results if r.get('status') == 'ok')
    print(f'\nDone in {elapsed:.1f}s. ok={ok}/{len(results)}')
    by_tier = {}
    for r in results:
        if r.get('status') == 'ok':
            by_tier[r['tier_used']] = by_tier.get(r['tier_used'], 0) + 1
    print(f'By tier: {by_tier}')

    # Save log
    log_path = SOURCE_DIR / '.scrape_log.json'
    log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                        encoding='utf-8')
    print(f'Log: {log_path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True, help='Site name (e.g. hjwzw)')
    ap.add_argument('--ch', type=int, help='Single ch number')
    ap.add_argument('--range', nargs=2, type=int, metavar=('FROM', 'TO'),
                    help='Ch range (inclusive)')
    ap.add_argument('--missing', action='store_true',
                    help='Re-scrape ch with < MIN_BODY_CHARS')
    ap.add_argument('--all', action='store_true', help='Scrape all ch')
    ap.add_argument('--concurrency', type=int, default=2)
    ap.add_argument('--delay', type=float, default=0.5,
                    help='Delay between requests (seconds)')
    ap.add_argument('--ocr', action='store_true',
                    help='Enable Tier 2 OCR fallback (slow startup, ~30s)')
    args = ap.parse_args()

    # Determine ch list
    if args.ch:
        chs = [args.ch]
    elif args.range:
        f, t = args.range
        chs = list(range(f, t + 1))
    elif args.missing:
        chs = []
        for f in sorted(SOURCE_DIR.glob('0*.md'), key=lambda p: int(p.stem)):
            n = int(f.stem)
            text = f.read_text(encoding='utf-8')
            stripped = re.sub(r'\s+', '', text)
            if len(stripped) < MIN_BODY_CHARS:
                chs.append(n)
        print(f'Found {len(chs)} missing ch (body < {MIN_BODY_CHARS} chars)')
    elif args.all:
        chs = list(range(1, 1240))
    else:
        ap.print_help()
        return

    asyncio.run(run_scrape(args.site, chs, args.concurrency, args.delay))


if __name__ == '__main__':
    main()
