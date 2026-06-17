# NovelClaw — Complete System Architecture Document

> **Purpose:** Full system overview for AI analysis (Gemini)
> **Date:** 2026-06-17
> **Version:** 2.0

---

## 1. Project Overview

**NovelClaw** is a Chinese-to-Thai novel translation pipeline. It translates web novels from Chinese (CN) to Thai (TH) using AI-assisted workflow with human oversight.

**Repo:** `C:\Users\BlankScreen\Workspace\Projects\NovelClaw`
**Novel:** Global Descent (全球降臨：帶著嫂嫂末世種田) — 1,239 chapters
**Progress:** 65 chapters translated (ch 1, 71-134), ch 2-70 not yet translated

---

## 2. File Structure

```
NovelClaw/
├── PROMPT.md                 # AI system prompt (S0-S9) — translation rules
├── TRANSLATION_MANUAL.md     # Human reference — workflow, tools, maintenance
├── style.md                  # Per-novel style hub (generic defaults)
├── format_spec.md            # File format spec (v2 JSON schema)
├── README.md                 # Project overview
├── run.bat                   # Double-click launcher (opens browser + starts server)
├── progress.md               # Translation progress tracker
├── docs/
│   └── THAI_NATURALNESS.md   # Thai naturalness guide (203 lines)
├── glossary/
│   ├── locked.md             # P1 terms (59 terms) — MUST use, never override
│   ├── reference.md          # P2 terms (50 terms) — use consistently
│   ├── auto.md               # P3 terms (389 terms) — suggestion only
│   ├── glossary.yml          # Canonical glossary (auto-generated from .md)
│   ├── glossary.db           # SQLite FTS5 index (derived from YML)
│   └── index.md              # Glossary documentation
├── tools/                    # CLI tools
│   ├── validate_no_cjk.py    # CJK leakage checker + EN whitelist
│   ├── constants.py          # Paths, LENGTH_RATIO_OK, NAME_CHECKS
│   ├── schema.py             # Pydantic chapter schemas
│   ├── chapter_io.py         # Chapter I/O helpers
│   ├── chapter_search.py     # FTS5 search
│   ├── scrape_chapters.py    # Source scraper (hjwzw.com)
│   └── slop/                 # Anti-AI slop detection modules
│       ├── anti_ai.py
│       ├── scan.py
│       ├── text_stats.py
│       └── paragraph_metrics.py
├── novels/
│   └── global-descent/
│       ├── progress.md       # Next chapter, last translated, total
│       ├── summary.md        # Chapter-by-chapter summaries
│       ├── characters.md     # Character list with speech patterns
│       ├── style.md          # Novel-specific style overrides
│       ├── dynamic_bans.md   # Dynamic ban list
│       ├── format_spec.json  # Declarative format spec
│       ├── glossary/         # Novel-specific glossary overrides
│       ├── npc_bank/         # NPC dossier files (.md per NPC)
│       └── chapters/
│           ├── 0001.json     # Translated chapters (schema v2)
│           ├── 0071.json
│           ├── ...
│           └── 0134.json
│           └── source/       # Raw CN source files
│               ├── 0001.md
│               └── ...
└── reader/                   # Web reader (Express.js SPA)
    ├── server.js             # Express server (port 4173)
    ├── package.json
    └── public/
        ├── index.html        # Dashboard + reader SPA
        ├── app.js            # Frontend logic
        ├── style.css         # Themes: light/sepia/dark
        ├── page-renderers.js # Page renderers (reader, dashboard, etc.)
        ├── router.js         # Hash-based SPA Router
        └── virtual-scroll.js # Sidebar chapter list
```

---

## 3. Translation Workflow

### 3.1 Per-Chapter Flow

```
1. Prepare context
   → Read source CN text from chapters/source/NNNN.md
   → Load glossary (locked > reference > auto)
   → Load style.md for novel-specific rules
   → Load previous chapters for continuity

2. AI Translation (Mika)
   → Follow PROMPT.md (S0-S9 rules)
   → Follow Transmittor Principle (preserve author voice)
   → Zero CN/JP/KO leakage in output
   → Translate ALL text (no skipping, no paraphrasing)
   → Length ratio: 60%-350% of source

3. Validation
   → validate_no_cjk.py: CJK leakage check + EN whitelist
   → validate_chapter.py: Structure, format, glossary compliance
   → glossary_doctor.py: Term consistency

4. Save
   → Save as chapters/NNNN.json (schema v2)
   → Update progress.md
   → git commit
```

### 3.2 AI Translation Rules (PROMPT.md S0-S9)

| Section | Rule |
|---------|------|
| S0 | Universal Identity — Transmittor First |
| S1 | Transmittor Principle — preserve author voice |
| S1b | Completeness — every character translated, ≥80% length |
| S1c | Zero Foreign Script — NO CN/JP/KO in output |
| S2 | Anti-Slop — no academic padding, no repetitive crutches |
| S3 | Glossary Compliance — P1 > P2 > P3 priority |
| S4 | Format Compliance — brackets, punctuation, whitespace |
| S5 | Continuity — cross-chapter term consistency |
| S6 | Output Format — JSON schema v2 |
| S7 | Self-Review Gate — run before finalizing |

### 3.3 EN Game Term Whitelist

Terms that are **acceptable** in Thai translation output:

| Term | Thai Equivalent | Notes |
|------|----------------|-------|
| S, SS, SSR, SSS, UR, LR | — | Tier ratings — do NOT translate |
| HP | พลังชีวิต | Universally understood |
| MP | มนตร์/พลังมนตร์ | |
| CD | คูลดาวน์ | |
| NPC | ตัวละครรอง | OK in game context |
| BUFF | บัฟ/เสริมพลัง | |
| DEBUFF | ลดพลัง | |
| EXP | ประสบการณ์ | |
| LV, LVL | เลเวล | |
| ATK | โจมตี | |
| DEF | ป้องกัน | |
| DMG | ความเสียหาย | |
| AOE | โจมตีวงกว้าง | |
| DPS | ความเสียหายต่อวินาที | |
| PVP, PVE | — | Gaming terms |
| ID | รหัส | Only in system messages |

**Blacklist (NEVER acceptable):** GZ (source artifact)

---

## 4. Chapter JSON Schema (v2)

```json
{
  "schema_version": 2,
  "num": 123,
  "title": "ตอนที่ 123: ชื่อตอน",
  "lang": "cn",
  "blocks": [
    {"type": "narration", "text": "Thai narration..."},
    {"type": "dialogue", "text": "「Thai dialogue」", "speaker": "เฉาซิง"},
    {"type": "system", "text": "【System message in Thai】"},
    {"type": "game_title", "text": "《Game Title》"},
    {"type": "end", "text": "(จบบท)"}
  ],
  "source": "ch 123",
  "notes": ["Translation notes"]
}
```

**Block types:** `narration`, `dialogue`, `system`, `game_title`, `end`

**Bracket conventions:**
- Dialogue: `「...」` (CJK corner brackets)
- System: `【...】`
- Game title: `《...》`
- Emphasis: `**...**`
- End marker: `(จบบท)`

---

## 5. Reader Web App Architecture

### 5.1 Tech Stack
- **Backend:** Express.js (Node.js), port 4173
- **Frontend:** Vanilla JS (no framework), hash-based SPA Router
- **Styling:** CSS variables, 3 themes (light/sepia/dark)
- **No build step** — plain HTML/CSS/JS

### 5.2 Routing
- Hash-based SPA: `router.js` + `page-renderers.js`
- Routes: `#home`, `#reader/slug/chapter`, `#library`, `#search`, etc.
- `Router.handleRoute()` toggles `body.reader-mode` / `body.dashboard-mode`

### 5.3 Key UI Components
- **Dashboard:** Novel grid with progress bars, hero banner, continue reading
- **Reader:** Sidebar (chapter list + search) + content area
- **Reader Toolbar:** 2-row layout (nav + settings)
- **Mobile:** Slide-out sidebar with overlay

### 5.4 API Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /api/novels` | List all novels |
| `GET /api/novel/:slug/chapters` | Chapter list with titles |
| `GET /api/novel/:slug/chapter/:num` | Chapter content (JSON) |
| `GET /api/novel/:slug/chapters/search?q=&mode=` | Search (title/content/all) |
| `POST /api/invalidate-cache` | Cache invalidation |

---

## 6. Validation System

### 6.1 validate_no_cjk.py

Checks for:
1. **CN leakage** (Chinese characters) — FAIL
2. **JP leakage** (Japanese kana) — FAIL
3. **KO leakage** (Korean hangul) — FAIL
4. **Source artifacts** (求订阅, GZ, etc.) — FAIL
5. **EN blacklisted terms** (GZ) — FAIL
6. **EN unknown terms** — WARN (review against whitelist)

```bash
python tools/validate_no_cjk.py --all           # check all chapters
python tools/validate_no_cjk.py 72              # check specific chapter
python tools/validate_no_cjk.py --novel global-descent --all
```

### 6.2 Validation Rules

| Check | Severity | Blocks Save |
|-------|----------|-------------|
| CJK chars in body | FAIL | ✅ |
| Source artifacts | FAIL | ✅ |
| EN blacklisted (GZ) | FAIL | ✅ |
| EN unknown terms | WARN | ❌ |
| Missing paragraphs | FAIL | ✅ |
| Length ratio < 60% | FAIL | ✅ |
| Locked term violation | FAIL | ✅ |
| Length ratio > 350% | WARN | ❌ |

---

## 7. Glossary Priority System

| Priority | File | Count | Rule |
|----------|------|-------|------|
| P1 (locked) | `glossary/locked.md` | 59 | MUST use locked Thai — never override |
| P2 (reference) | `glossary/reference.md` | 50 | Use unless context demands otherwise |
| P3 (auto) | `glossary/auto.md` | 389 | Suggestion only — translator's choice |

**Single source of truth:** `glossary/glossary.yml` (auto-generated)
**Derived:** `glossary/glossary.db` (SQLite FTS5)

---

## 8. Key Conventions

### 8.1 Translation Style
- **Transmittor Principle:** Preserve author's voice, don't "improve"
- **Flat emotion:** Keep where source has it (don't add feelings)
- **Subject echo:** Keep where source has it (don't vary)
- **Formal connectors:** Keep ดังนั้น, อย่างไรก็ตาม (don't "fix")
- **System messages:** Translate ALL text inside `【】` to Thai

### 8.2 Formatting
- 4-digit zero-padded filenames: `0072.json`
- Single blank line between paragraphs
- No trailing whitespace, no tabs
- Final newline at end of file
- `(จบบท)` as end marker

### 8.3 Mobile Responsive
- Breakpoint: 768px
- Mobile sidebar: fixed, slides in from left, overlay
- Topbar: flex-wrap, novel-title ellipsis
- Reader toolbar: 2-row layout, compact on mobile

---

## 9. Known Issues & Blind Spots

### 9.1 Translation
- **ch 2-70:** Not translated yet (no JSON files exist)
- **ch 1-70 (when translated):** May have CN leakage from older translation approach
- **EN terms:** Whitelist approach in place but needs periodic review

### 9.2 Reader UI
- **Browser tool caching:** Hermes browser tool has aggressive disk cache — always verify in real browser
- **Router vs showView():** Reader uses Router (router.js), NOT showView() — body class toggle must go in handleRoute()
- **Mobile overlay:** Must sync across ALL sidebar open/close paths

### 9.3 Tools
- **validate_no_cjk.py:** New version created 2026-06-17 with EN whitelist
- **Scraper:** hjwzw.com strips `「」` and `【】` — source may lack dialogue markers

---

## 10. Recent Changes (2026-06-17)

1. **Fixed CN/JP leak** in ch 123, 125, 133, 134
2. **Created validate_no_cjk.py** with EN whitelist (replaces old version)
3. **Redesigned reader toolbar** — single `.reader-toolbar` with 2 rows
4. **Fixed mobile sidebar overlay** — sync across all entry points
5. **Added `body.reader-mode` toggle** in Router.handleRoute()
6. **Fixed `position: sticky`** on reader toolbar → changed to `static`
7. **Added EN whitelist:** S/SS/SSR/SSS/UR/LR, HP, MP, CD, NPC, BUFF, DEBUFF, EXP, LV, ATK, DEF, DMG, AOE, DPS, TPS, PVP, PVE, ID
8. **Blacklist:** GZ (source artifact — always strip)

---

## 11. Commit History (Recent)

```
771f377  fix: CN/JP leak in ch 123, 134 + reader toolbar UI improvements
...
```

---

*End of document — ready for Gemini analysis*
