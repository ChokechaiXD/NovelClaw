"""
scrape_chapters.py — Scrape chapter sources from hjwzw.com using Playwright.

Uses headless Chromium to execute JavaScript-rendered content,
then extracts innerText and auto-detects dialogue ("") and system【】 markers.

Usage:
  python scrape_chapters.py                      # scrape all missing
  python scrape_chapters.py --start 123          # scrape from ch 123
  python scrape_chapters.py --start 123 --end 130
  python scrape_chapters.py --all                # re-scrape all (overwrite)
  python scrape_chapters.py --dry-run            # show what would be scraped
"""
import asyncio, json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import get_novel_root

NOVEL = "global-descent"
ROOT = get_novel_root(NOVEL)
CHAP_DIR = ROOT / "chapters"
SOURCE_DIR = CHAP_DIR / "source"
SOURCE_DIR.mkdir(exist_ok=True)

TOC_URL = "https://tw.hjwzw.com/Book/Chapter/50356"
READ_TEMPLATE = "https://tw.hjwzw.com/Book/Read/50356,{chid}"

SKIP_KEYWORDS = [
    "黃金屋", "首頁", "排行", "繁體", "收藏", "設為", "手機版", "最新章節",
    "玄幻", "武俠", "都市", "歷史", "科幻", "全本", "移動版", "書架",
    "文章查詢", "熱門", "字母索引", "請記住", "上一章", "下一章", "回車鍵",
    "頁面執行時間", "隨機推薦", "瀏覽記錄", "聯系我們", "快捷鍵",
]

# System message patterns (game UI text that should be wrapped in 【】)
SYSTEM_PATTERNS = [
    r'交易成功',
    r'你獲得了',
    r'伱失去了',
    r'等級：',
    r'生命值：',
    r'攻擊力：',
    r'護甲：',
    r'技能：',
    r'天賦：',
    r'所屬領主：',
    r'危險：',
    r'地圖介紹：',
    r'你已進入',
    r'注意：',
    r'為高等級區域',
    r'建議至少',
    r'組隊探索',
    r'lv\d+',
    r'LV\d+',
    r'\d+級',
    r'等階：',
    r'種族：',
]


def get_chapter_map():
    """Parse TOC to get {ch_num: chid} mapping using urllib (TOC is static HTML)."""
    import urllib.request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,*/*",
        "Referer": "https://tw.hjwzw.com/",
    }
    req = urllib.request.Request(TOC_URL, headers=headers)
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8", errors="replace")
    pattern = r'Book/Read/50356,(\d+)[^>]*>[^<]*第\s*(\d+)\s*章'
    matches = re.findall(pattern, html)
    return {int(ch_num): int(chid) for chid, ch_num in matches}


def is_system_message(line):
    """Detect if a line is a game system message."""
    for pat in SYSTEM_PATTERNS:
        if re.search(pat, line):
            return True
    return False


def is_dialogue(line):
    """Detect if a line contains dialogue (has quotes or quote-like patterns)."""
    # Has explicit quotes
    if '"' in line or '"' in line or '"' in line or '"' in line:
        return True
    if '「' in line or '」' in line:
        return True
    # Starts with quote-like character
    if line.startswith('"') or line.startswith('"') or line.startswith('「'):
        return True
    return False


def format_content_line(line):
    """Format a content line with appropriate markers."""
    # Skip empty
    if not line.strip():
        return line
    
    # System messages → wrap in 【】
    if is_system_message(line) and '【' not in line:
        return f"【{line}】"
    
    # Dialogue → ensure it has "" markers
    if is_dialogue(line):
        # Already has some form of quotes
        if '「' in line and '」' in line:
            return line  # Keep CN quotes
        if '"' in line or '"' in line:
            return line  # Has curly quotes
        # Has straight quotes — keep as is
        if '"' in line:
            return line
        # Starts with quote but missing close — add closing quote
        if line.startswith('"') and not line.endswith('"'):
            return line + '"'
        if line.startswith('"') and not line.endswith('"'):
            return line + '"'
    
    return line


async def scrape_chapter_playwright(chid, ch_num):
    """Scrape a single chapter using Playwright (JS-rendered content)."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_extra_http_headers({
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        })

        url = READ_TEMPLATE.format(chid=chid)
        await page.goto(url, timeout=30000, wait_until="networkidle")
        await page.wait_for_timeout(5000)

        # Extract content via innerText
        result = await page.evaluate("""
            () => {
                const body = document.body.innerText;
                const lines = body.split('\\n').map(l => l.trim()).filter(l => l);

                // Find chapter title
                let title = '';
                let titleIdx = -1;
                for (let i = 0; i < lines.length; i++) {
                    if (/第\\d+章/.test(lines[i])) {
                        title = lines[i];
                        titleIdx = i;
                        break;
                    }
                }

                // Collect content lines after title
                const contentLines = [];
                const skipKw = [
                    '黃金屋', '首頁', '排行', '繁體', '收藏', '設為', '手機版', '最新章節',
                    '玄幻', '武俠', '都市', '歷史', '科幻', '全本', '移動版', '書架',
                    '文章查詢', '熱門', '字母索引', '請記住', '上一章', '下一章', '回車鍵',
                    '頁面執行時間', '隨機推薦', '瀏覽記錄', '聯系我們', '快捷鍵',
                ];

                for (let i = titleIdx + 1; i < lines.length; i++) {
                    const line = lines[i];
                    if (skipKw.some(kw => line.includes(kw))) continue;
                    if (line.length < 2) continue;
                    if (line.includes('字母索引') || line.includes('頁面執行時間')) break;
                    contentLines.push(line);
                }

                return {
                    title: title,
                    contentLines: contentLines,
                    totalChars: contentLines.join('').length,
                };
            }
        """)

        await browser.close()
        return result


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

    # Scrape using Playwright
    ok = fail = skip = 0
    start_time = time.time()
    
    for i, ch_num in enumerate(to_scrape):
        chid = ch_map[ch_num]
        out = SOURCE_DIR / f"{ch_num:04d}.md"

        if out.exists() and not args.all:
            skip += 1
            continue

        try:
            result = asyncio.run(scrape_chapter_playwright(chid, ch_num))
            content_lines = result["contentLines"]

            if content_lines and len(content_lines) > 3:
                # Format lines: add 【】 to system messages, "" to dialogue
                formatted_lines = [format_content_line(line) for line in content_lines]
                content = "\n".join(formatted_lines)
                
                # Write with title header
                title = result.get("title", f"第{ch_num}章")
                # Clean up title (remove breadcrumb prefix)
                title = re.sub(r'.*>>\s*', '', title)
                out.write_text(f"# {title}\n\n{content}", encoding="utf-8")
                ok += 1
                
                # Progress report every 50 chapters
                if ok % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = ok / elapsed if elapsed > 0 else 0
                    remaining = (len(to_scrape) - i - 1) / rate if rate > 0 else 0
                    print(f"   ✓ {ok} scraped ({rate:.1f} ch/s, ~{remaining:.0f}s remaining)")
            else:
                print(f"   ⚠️  ch {ch_num} content too short ({len(content_lines)} lines)")
                fail += 1
        except Exception as e:
            print(f"   ❌ ch {ch_num} failed: {e}")
            fail += 1

        # Small delay to be polite
        time.sleep(0.2)

    elapsed = time.time() - start_time
    total = len(to_scrape) - skip
    print(f"\n✅ Done: {ok} OK, {fail} failed, {skip} skipped")
    print(f"   Time: {elapsed:.1f}s ({elapsed/max(ok,1):.1f}s per chapter)")
    print(f"   Source dir: {SOURCE_DIR} ({len(list(SOURCE_DIR.glob('*.md')))} files)")


if __name__ == "__main__":
    main()
