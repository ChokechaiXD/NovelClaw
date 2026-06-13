"""Scrape all chapters from hjwzw.com to novels/global-descent/chapters/source/NNNN.md.

DEPRECATED (2026-06-13): The original scraper pipeline was removed
during Session 6 cleanup (see progress.md "Removed junk files"). The
`tmp_chapters.json` input file no longer exists, and source chapters
are now in `chapters/source/0001-1239.md` having been scraped by an
earlier run / external tool.

This script is kept as documentation of the original scraping flow.
Re-enable by:
  1. Restoring tmp_chapters.json (chapter title list from hjwzw.com)
  2. Updating the URL pattern to match the current site structure
  3. Removing this deprecation notice
"""
import asyncio
import aiohttp
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import NOVEL_ROOT  # noqa: E402

ROOT = NOVEL_ROOT
OUTPUT_DIR = ROOT / 'chapters' / 'source'

# Original input file (no longer present after Session 6 cleanup)
# To re-enable: restore tmp_chapters.json and uncomment the line below
CHAPTERS_FILE = Path(__file__).parent / 'tmp_chapters.json'
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CONCURRENCY = 6
DELAY_BETWEEN = 0.3  # seconds between requests within a worker


def extract_chapter(html: str) -> tuple[str, str]:
    """Return (title, body) from hjwzw chapter page HTML.

    Strategy:
      - body is between the first <p/> (after page header/scripts) and the
        LAST '請記住本站域名' marker (the actual page footer)
      - <p/> and <br/> are converted to paragraph breaks
      - Trailing line numbers like '11' after a Chinese sentence are
        stripped (they're a hjwzw reader-app quirk)
    """
    # 1. Find the LAST 請記住本站域名 (page footer)
    positions = [m.start() for m in re.finditer(r'請記住本站域名', html)]
    if not positions:
        return '', ''
    end_pos = positions[-1]

    # 2. Find the first <p/> (body content)
    all_p = [m.start() for m in re.finditer(r'<p\s*/?>', html)]
    # Skip early <p/> tags (in nav, scripts, etc.) — start search from position 10000+
    body_p = [p for p in all_p if p > 10000]
    if not body_p:
        return '', ''
    start_pos = body_p[0]

    # 3. Extract and clean
    raw = html[start_pos:end_pos]
    # Paragraphs and line breaks
    text = re.sub(r'<p\s*/?>', '\n\n', raw)
    text = re.sub(r'<br\s*/?>', '\n', text)
    # Strip all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    # Strip trailing line numbers like "死了！11" or "的！11<p/>"
    # Pattern: digit(s) right after Chinese punctuation, before paragraph break or end
    text = re.sub(r'([\u4e00-\u9fff，。！？…：])\s*(\d{1,3})(?=\s|$)', r'\1', text)
    # Strip a single trailing number on its own line
    text = re.sub(r'\n\d{1,3}\n', '\n\n', text)
    # Collapse excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    # 4. Title: extract from the header line "全球降臨：... 第N章 标题"
    m = re.search(r'(第\s*\d+\s*章[^\n]*)', text)
    title = m.group(1).strip() if m else ''

    return title, text


async def fetch_one(session, ch, sem, idx, total):
    url = ch['url']
    ch_num = ch.get('num') or 0  # some special chapters have no num
    ch_label = f"ch {ch_num:4}" if ch_num else f"id {ch['id']}"

    # Idempotency: skip if file already exists
    padded = f"{ch_num:04d}.md" if ch_num else f"id_{ch['id']}.md"
    out_path = OUTPUT_DIR / padded
    if out_path.exists() and out_path.stat().st_size > 500:
        print(f'  [{idx}/{total}] {ch_label} ⏭ (exists)', flush=True)
        return True, ch

    async with sem:
        for attempt in range(3):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    html = await resp.text()
                    title, body = extract_chapter(html)
                    if not body or len(body) < 100:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    out_path.write_text(f"# {ch['title']}\n\n{body}\n", encoding='utf-8')
                    await asyncio.sleep(DELAY_BETWEEN)
                    print(f'  [{idx}/{total}] {ch_label} ✓  ({len(body):,} chars)', flush=True)
                    return True, ch
            except Exception as e:
                print(f'  [{idx}/{total}] {ch_label} ✗  attempt {attempt+1}: {e}', flush=True)
                await asyncio.sleep(2 ** attempt)
    return False, ch


async def main():
    with open(CHAPTERS_FILE, encoding='utf-8') as f:
        chapters = json.load(f)
    print(f'Total chapters: {len(chapters)}', flush=True)
    print(f'Output: {OUTPUT_DIR}', flush=True)
    print(f'Concurrency: {CONCURRENCY}', flush=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}) as session:
        tasks = [fetch_one(session, ch, sem, i + 1, len(chapters))
                 for i, ch in enumerate(chapters)]
        results = await asyncio.gather(*tasks)
    ok = sum(1 for r, _ in results if r)
    fail = len(results) - ok
    print(f'\nDone. ok={ok}, fail={fail}', flush=True)
    fails = [ch for r, ch in results if not r]
    if fails:
        with open(OUTPUT_DIR / '_failed.json', 'w', encoding='utf-8') as f:
            json.dump(fails, f, ensure_ascii=False, indent=2)
        print(f'Failed saved to _failed.json', flush=True)


if __name__ == '__main__':
    # Force unbuffered output
    sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)
    asyncio.run(main())
