# NovelClaw Progress — global-descent

Last translated:** ch 110**
Total progress: 110/1,239 (8.88%)
Next chapter: **ch 111**

## Recent activity (2026-06-13)

### Session 1: Foundation
- Translated ch 1 (sample)
- Re-imported ch 71 from ice-apocalypse (later re-translated for v2 quality)
- Created global-descent folder structure
- Created progress.md, characters.md, summary.md, style.md

### Session 2: Glossary refactor (3-tier split)
- Categorized 192 glossary terms: locked (31) / reference (64) / auto (97)
- Updated PROMPT.md Section 5b (Contextual Loading)
- Updated STRUCTURE.md

### Session 3: Translate ch 72-80 (9 chapters, v2 quality)
- Real-time feedback (8 checkpoint self-review)
- Glossary updated (+366 terms from these chapters)
- New chars: 阿薩姆, 布洛特, 坎達爾, 坎特爾, 茱莉葉特
- All translated with character consistency, scene breaks, dialogue markers
- Length ratio 1.5-3.0x (target met)

### Session 4: Quality boosters (3 quality-of-work tools)
- pre_chapter.py (auto context bundle) — 166 lines
- validate_chapter.py (quality check, --fix mode) — 173 lines
- Thai title in reader sidebar (server.js + app.js)

### Session 5: Reader v2
- Sidebar with Thai titles, search input
- Mobile-optimized (44x44 touch targets, iOS safe area)
- 3 themes (light/sepia/dark), keyboard shortcuts
- LAN access (server binds 0.0.0.0)

### Session 6: Project organization
- Created tools/ subfolder for .py scripts
- Updated novelclaw.py CLI dispatcher
- Removed junk files (tmp_*, __pycache__, scrape.log, tm.json)
- Updated README.md

### Session 7: Translate ch 81-100 (20 chapters)
- Real-time translation with quality maintenance
- All translated following v2 PROMPT rules
- ch 81: แยกแรงเวทย์หินบูชายัญ (decompose magic stone altar)
- ch 82-83: หุบเขาแห่งความน่ากลัว + ค่าภักดีของทุกคนพุ่งสูง (terrible valley, loyalty surge)
- ch 84-85: เปิดความลับสุดท้าย + ต่อสู้อย่างดุเดือด (unveil final secret, intense battle — goblin king)
- ch 86: ไอเทมระดับตำนาน บัลลังก์ระยิบระยับ (legendary item: Shining Throne)
- ch 87-88: แบบแปลนสีทอง + การเปลี่ยนแปลงของซาร่า (golden blueprints + Sara's transformation)
- ch 89-90: อันดับหนึ่ง + ชำแหละซากกระต่าย (rank 1 + rabbit dismantling)
- ch 91-93: ค้นพบหมู่บ้านพื้นเมือง + ซื้ออาหาร + ซื้อคนเลี้ยงสัตว์ (village, food, livestock + purchasing Mel)
- ch 94-95: ท่าเด็ดๆ + การค้าเก็บเกี่ยวมาก (various tactics + trading)
- ch 96-97: ก้าวหน้าจอมเวท + ดินแดนแห่งความหวัง (advance frost mage + Land of Hope)
- ch 98: ปีศาจในหิมะ (snow demon)
- ch 99-100: translated fresh in Session 8 (see below)

### Session 8: Audit + 5 bug fixes (post-batch)
- **ch 99 missing**: file was never created during ch 81-100 batch. Translated fresh.
- **ch 100 wrong content**: file was overwritten with ch 99 content (mistake during batch). Re-translated from source 0100.md (Blood Spider Queen 希兒妲·血吻).
- **ch 99 ---\n separator bug**: `*Source: ch 99*` placed BEFORE separator, body landed in meta. Reconstructed so H1 + Source come first, then ---, then body, then ---, then meta note.
- **ch 100 endpoint cache leak**: 42 chars returned (file was 12K). Server cached old version. Fixed via POST /api/invalidate-cache.
- **Scroll to top on chapter switch**: added `window.scrollTo({top:0, behavior:'auto'})` to loadChapter() so user sees title on next page.
- **Back-to-top button alignment**: changed `.chapter-nav-bottom` to grid `1fr auto 1fr` (was flex space-between, looked misaligned). Prev/next at edges, back-to-top centered.
- **Mobile backdrop click**: changed `e.target.matches('body.sidebar-open::before')` (pseudo-element not matchable) → `e.target === document.body`.
- **Validator whitelists**: 【】 system messages, 《》 donor names, *Source: ch N* footers are now scanned-through (legitimate uses).
- **Removed stale Source CN title from ch 99/100 footers**: now `*Source: ch N*` only (not `(第N章 CN_TITLE)`).
- **validate --cjk**: 31/31 chapters CJK-free ✅

## Glossary totals
- locked.md: 48 terms
- reference.md: 98 terms
- auto.md: 412 terms
- **Total: 558 terms**

## Tools & scripts (in tools/)
- pre_chapter.py — context bundle for next chapter
- validate_chapter.py — quality check + auto-fix (mechanical)
- find_candidates.py — chapters needing re-translation
- build_tm.py — translation memory (unused — source has no 【】)
- scrape_chapters.py — initial source scraper

## CLI (root)
- novelclaw.py status / prep [N] / validate [N] [--fix] / candidates / scrape

## Reader
- URL: http://192.168.1.41:4173/ (LAN)
- Local: http://localhost:4173/
- Sidebar: search by number prefix or title text
- Mobile: iOS safe area, 44x44 touch targets, slide-out sidebar
- Themes: light / sepia / dark
- Browser tab: shows current chapter

## Resume command
- Mika: `python novelclaw.py prep 101` to get ch 101 context, then translate.
