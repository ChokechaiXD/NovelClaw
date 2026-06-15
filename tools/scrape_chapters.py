"""
scrape_chapters.py — Scrape all missing chapter sources from hjwzw.com

Fetches chapter HTML, extracts content, and saves to chapters/source/NNNN.md.
Uses hjwzw.com (primary) which has all 1239 chapters.

Usage:
  python scrape_chapters.py                      # scrape all missing
  python scrape_chapters.py --start 123          # scrape from ch 123
  python scrape_chapters.py --start 123 --end 130
  python scrape_chapters.py --all                # re-scrape all (overwrite)
"""
import json, re, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root

import urllib.request

NOVEL = "global-descent"
ROOT = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"
SOURCE_DIR = CHAP_DIR / "source"
SOURCE_DIR.mkdir(exist_ok=True)

TOC_URL = "https://tw.hjwzw.com/Book/Chapter/50356"
READ_TEMPLATE = "https://tw.hjwzw.com/Book/Read/50356,{chid}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,*/*",
    "Referer": TOC_URL,
    "Accept-Encoding": "identity",
}

SKIP_KEYWORDS = [
    "黃金屋", "首頁", "排行", "繁體", "收藏", "設為", "手機版", "最新章節",
    "玄幻", "武俠", "都市", "歷史", "科幻", "全本", "移動版", "書架",
    "文章查詢", "熱門", "字母索引", "請記住", "上一章", "下一章", "回車鍵",
]


def fetch(url):
    """Fetch URL with retries."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                raise


def get_chapter_map():
    """Parse TOC to get {ch_num: chid} mapping for all 1239 chapters."""
    html = fetch(TOC_URL)
    pattern = r'Book/Read/50356,(\d+)[^>]*>\s*第\s*(\d+)\s*章'
    matches = re.findall(pattern, html)
    return {int(ch_num): int(chid) for chid, ch_num in matches}


def extract_content(html):
    """Extract chapter text from hjwzw HTML using regex."""
    # Remove script/style
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text)
    # Strip tags
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", "\n", text).strip()

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    content_lines = []
    in_content = False

    for line in lines:
        # Detect chapter title line
        if re.search(r"第\s*\d+\s*章", line) and any(ord(c) > 0x4E00 for c in line[:30]):
            in_content = True
            # Keep the title line
            content_lines.append(line)
            continue

        if in_content:
            if any(kw in line for kw in SKIP_KEYWORDS):
                continue
            if re.match(r"^[A-Z]\s*\|", line):
                continue
            if len(line) < 2:
                continue
            content_lines.append(line)

        if len(content_lines) > 500:
            break

    return "\n".join(content_lines)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Scrape all missing chapter sources")
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--all", action="store_true", help="Re-scrape all (overwrite)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be scraped")
    args = ap.parse_args()

    print("📖 Scrape chapters — NovelClaw")
    print(f"   Source: hjwzw.com (Book/Chapter/50356)")
    print(f"   Output: {SOURCE_DIR}")

    print("\n⏳ Fetching TOC...")
    ch_map = get_chapter_map()
    print(f"   Found {len(ch_map)} chapters in TOC (ch 1–{max(ch_map.keys())})")

    # Determine which chapters to scrape
    if args.all:
        to_scrape = sorted(ch_map.keys())
    elif args.start and args.end:
        to_scrape = [n for n in range(args.start, args.end + 1) if n in ch_map]
    elif args.start:
        to_scrape = sorted(n for n in ch_map if n >= args.start)
    else:
        # Only missing
        existing = set()
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".md") and f[0].isdigit():
                existing.add(int(f[:4]))
        to_scrape = sorted(set(ch_map.keys()) - existing)

    print(f"   To scrape: {len(to_scrape)} chapters")
    if not to_scrape:
        print("✅ All chapters already scraped!")
        return

    if args.dry_run:
        for n in to_scrape[:20]:
            print(f"   ch {n} → chid {ch_map[n]}")
        if len(to_scrape) > 20:
            print(f"   ... and {len(to_scrape) - 20} more")
        return

    # Scrape
    ok = fail = skip = 0
    for i, ch_num in enumerate(to_scrape):
        chid = ch_map[ch_num]
        out = SOURCE_DIR / f"{ch_num:04d}.md"

        if out.exists() and not args.all:
            skip += 1
            continue

        try:
            html = fetch(READ_TEMPLATE.format(chid=chid))
            content = extract_content(html)
            if content and len(content) > 50:
                out.write_text(content, encoding="utf-8")
                ok += 1
                if ok % 10 == 0:
                    print(f"   ✓ {ok} scraped (ch {ch_num})")
            else:
                print(f"   ⚠️  ch {ch_num} content too short ({len(content)} chars)")
                fail += 1
        except Exception as e:
            print(f"   ❌ ch {ch_num} failed: {e}")
            fail += 1

        time.sleep(0.3)

    total = len(to_scrape) - skip
    print(f"\n✅ Done: {ok} OK, {fail} failed, {skip} skipped (already existed)")
    print(f"   Source dir: {SOURCE_DIR} ({len(list(SOURCE_DIR.glob('*.md')))} files)")


if __name__ == "__main__":
    main()
