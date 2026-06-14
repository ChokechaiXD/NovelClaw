# NovelClaw Progress — global-descent

**Last translated:** ch 121
**Total progress:** 121/1,239 (9.77%)
**Next chapter:** ch 122
**Quality gate:** transmittor principle (translator transmits, not edits)
**Pipeline:** 2-agent (Translator 5-Phase CoT + Proofreader MQM 8-dim, read-only)
**Max rework rounds per chapter:** 3 (escalate to P'Chok on round 3 FAIL)

## Recent activity (2026-06-13 → 2026-06-14)

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

### Session 9: Tier 1 — tool reliability (3f75efc)
- `.json-aware` patches in save_chapter, validate_chapter, translate_commit (no more treating .json as text by accident)
- LRU chapter cache (default 64 entries) in server.js — chapter list endpoint 8x faster on cold start
- `dedupe_blocks()` helper in translate_chelpers — drops identical consecutive paragraphs that were slipping through
- Stopped relying on familiarity ("oh it usually works") — added pre-flight checks before any state-mutating op

### Session 10: Tier 2 — quality + tests
- **#5 Multi-language schema (eeb850d)**: chapters now store `source_lang` (cn/jp/kr/en) and `target_lang` (th default). Pipeline no longer hard-codes CN→TH.
- **#6 Glossary gate (3c1fd60)**: `glossary_gate.py` runs pre-translate to block obvious violations (missing locked term, CJK leak in title, wrong source binding). STOPWORDS list filters noise from FTS candidate scores.
- **#8 Backend tests (746f487)**: pytest suite covers `cn_checker`, `translate_commit`, `schema`, `server` endpoints. 47 tests pass.

### Session 11: Tier 3 — multi-novel + UX
- **#9 Multi-novel registry (1080fe7)**: `registry.py` + `novels/*.yaml` metadata. 10-20 นิยาย can coexist; CLI routes by `novel_id`. Pre-requisite for expanding beyond global-descent.
- **#11 Frontend virtual scroll (46c0414)**: sidebar renders 1,239 ch smoothly. Old list was jank above 200.
- **#12 FTS5 search (fbd8ed1)**: `/api/search?q=&mode=title|content|all` over FTS5-indexed body. Sub-100ms across all chapters.

### Session 12: Transmittor principle (87f7f14)
Philosophy change. The translator is a **transmittor**, not an editor.
- `style.md`: dropped all "RECURRING ISSUE" + "fix patterns" sections. Subject echo, flat emotion (ดีใจในใจ, ฉายแวว), formal verbs — these are the AUTHOR's voice. We transmit.
- `STYLE_RULES` in `build_glossary.py`: all anti-patterns downgraded `warning` → `info`. Doctor only flags when TRANSLATION has MORE instances than SOURCE.
- `save_chapter.py`: removed `print_fix_hints`. Issues are now REPORTS, not auto-fix instructions printed back to translator.
- `validate_chapter.py` v3: split into `--mechanical-fix` (whitespace, number format, system wrapping, wrong-name variants) and **report-only** for everything else.
- New `format_spec.json`: declarative spec for chapter format (quotes, brackets, separators, forbidden chars). Future: UI edits this without touching code.
- All ch 113-121 translations already conformed to transmittor (translated naturally, no over-edit).

### Session 13: Translate ch 117-121 (5 chapters)
- ch 117: 237 blocks, 0 CN leak (0b8b1ec)
- ch 118: 87 blocks, 0 CN leak (dca3d94) — short chapter
- ch 119: 260 blocks, 0 CN leak (78a6abd)
- ch 120: 248 blocks, 0 CN leak (d0c8c1c)
- ch 121: 277 blocks, 0 CN leak (3b267dd)
- All 5 produced under transmittor principle — flat emotion preserved where source has it.

## Glossary totals (current)
- locked.md: 58 terms
- reference.md: 100 terms
- auto.md: 414 terms
- **Total: 572 terms**

## Tools & scripts (in tools/)
**Translator workflow:**
- `pre_chapter.py` — context bundle for next chapter
- `translate_ch.py` / `translate_chelpers.py` — translation runner
- `translate_commit.py` — pre-commit gate (CN check + glossary gate + format)
- `validate_chapter.py` — quality check (v3, transmittor)
- `validate_no_cjk.py` — strict CJK leak detector

**Glossary / consistency:**
- `build_glossary.py` — parses 3-tier glossary, runs STYLE_RULES
- `glossary_doctor.py` — issue detector
- `glossary_gate.py` — pre-translate guard (Tier 2 #6)
- `glossary_stats.py` — coverage metrics
- `load_glossary.py` — loader
- `learn_slop.py` — auto-detects + bans slop words from auto.md
- `npc_bank.py` — character voice bank

**Multi-novel / registry (Tier 3):**
- `registry.py` — novel metadata router
- `schema.py` — multi-language chapter schema
- `migrate_to_json.py` — converts legacy format

**Source / scraping:**
- `scrape_chapters.py`, `rescrape_chapters.py`, `hybrid_scrape.py`
- `clean_source.py`, `reformat_chapter.py`, `reformat_malformed.py`
- `convert_quotes.py` — straight → curly quotes

**Search / audit (Tier 3):**
- `chapter_search.py` — FTS5 search CLI
- `audit.py`, `review_chapter.py` — quality audit
- `backup.py` — snapshot helper

**Other:**
- `save_chapter.py`, `save_json.py`
- `cn_checker.py` — CN leak detector
- `find_candidates.py` — chapters needing re-translation
- `build_yaml.py` — YAML serialization helper
- `build_tm.py` — translation memory (unused — source has no 【】)
- `translate.py` — legacy translation entry
- `constants.py` — paths/globals

## CLI (root)
- `novelclaw.py status` — show progress
- `novelclaw.py prep [N]` — get ch N context bundle
- `novelclaw.py validate [N] [--mechanical-fix]` — quality check (v3)
- `novelclaw.py translate [N]` — run translation
- `novelclaw.py candidates` — chapters needing re-translation
- `novelclaw.py scrape` — initial source scraper
- `novelclaw.py search <query> [--mode title|content|all]` — FTS5 search

## Reader
- URL: http://192.168.1.41:4173/ (LAN)
- Local: http://localhost:4173/
- Sidebar: search by number prefix or title text, virtual scroll (1,239 ch smooth)
- Mobile: iOS safe area, 44x44 touch targets, slide-out sidebar
- Themes: light / sepia / dark
- Browser tab: shows current chapter
- FTS5 search endpoint: `/api/search?q=...&mode=title|content|all`

## Resume command
- Mika: `python novelclaw.py prep 122` to get ch 122 context, then translate.
- Pre-flight: ensure transmittor principle is observed (preserve author's flat emotion, don't over-edit).

## Architecture (current state)

**Translation pipeline:** 2-agent
- **Translator (Mika)**: 5-Phase CoT (read source → build fact sheet → translate → self-review → polish). Outputs to `chapters/NNNN.json`.
- **Proofreader (Mika review pass)**: MQM 8-dim audit (accuracy, fluency, terminology, style, format, completeness, consistency, locale). Read-only. Up to 3 rounds per chapter; round 3 FAIL escalates to P'Chok.

**Multi-novel foundation:** `registry.py` + `novels/<id>/` (current: global-descent). Each novel has its own glossary, style, source, chapters.

**Quality gate (transmittor principle):**
- Hard errors (block commit): CJK leak, missing locked term, malformed format
- Soft reports (inform only): anti-patterns, subject echo, length ratio, flat emotion
- Mechanical auto-fix: whitespace, number format, system wrapping, wrong-name variants

**State of play:** pipeline stable, infra solid, transmittor principle in effect, 9.77% complete. Next: continue ch 122-130 batch under new philosophy.
