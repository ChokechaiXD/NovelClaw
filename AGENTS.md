# NovelClaw — Workspace Rules (สำหรับ Agent อ่านทุกครั้ง)

> **⛳ Workspace MOC**: ก่อนทำงาน NovelClaw ให้อ่าน `C:/Users/BlankScreen/Workspace/00 Home.md` ทุกครั้ง
> นี่คือ Second Brain ของพี่โชค — ใช้เป็นศูนย์กลางอ้างอิงข้าม session

## Project Overview

NovelClaw = Chinese-to-Thai web novel translation toolkit.  
ประกอบด้วย 2 ส่วนหลัก:

| Component | Description |
|:-----------|:------------|
| **Python tools** (`tools/`) | translate, validate, score, glossary, schema |
| **Reader** (`reader/`) | Express.js-based web reader (ITCSS + ESM frontend) |

---

## Core Architecture Decisions (ห้ามเปลี่ยน)

| Decision | Detail |
|:----------|:-------|
| **LLM outputs plain text, Python assembles** | LLM never writes JSON — outputs paragraphs with inline markers |
| **No block types** | All content is paragraphs with inline `"...」`, `【】`, `『』` markers |
| **ITCSS 5-layer** | tokens → generic → elements → BEM components → utilities |
| **ES Modules** | Vanilla JS modules (`js/pages/*.js`), Observer-pattern state |
| **Single source of truth** | `reader/config/brackets.json` for brackets/end-markers |
| **Zero API keys in repo** | All credentials → Hermes Agent config.yaml |
| **Provider** | `tools/providers/api.py` → direct HTTP (NOT Hermes CLI subprocess) |
| **Free model only** | `deepseek-v4-flash` via openmodel.ai (ฟรีตลอด) |
| **JSON canonical format** | Chapter data stored as structured JSON (paragraphs), NOT raw HTML |
| **meta.json & index.json** | Novel metadata + chapter index as JSON files — zero per-file I/O |
| **Per-chapter fetch** | Reader fetches only the requested chapter JSON, never loads whole novel |
| **User state separate** | Reading progress, history, bookmarks in localStorage (not in novel data) |

## Data Storage Layout

```
novels/{slug}/
├── novel.json                    ← Novel metadata (title, author, status, description, translatedTitle)
├── chapters.json                 ← Chapter index (num, title, status: translated|source_only) — fast-path
└── chapters/
    ├── index.json                ← Backward-compat index { num, title, isTranslated }
    ├── 0001.th.json              ← Chapter 1 — Thai translation (structured paragraphs)
    ├── 0001.cn.json              ← Chapter 1 — Chinese source (kept separate from reader)
    ├── 0002.th.json              ← Chapter 2 — Thai translation
    ├── 0002.cn.json              ← Chapter 2 — Chinese source
    └── ...
```

**Reader data flow (per-chapter fetch):**
1. `GET /api/novels` — reads `novel.json` per novel, returns list with `title` + `translatedTitle`
2. `GET /api/novel/:slug/meta` — serves `novel.json` directly
3. `GET /api/novel/:slug/chapters` — serves `chapters.json` directly (fast path, zero per-file I/O)
4. `GET /api/novel/:slug/chapter/:num?lang=th` — serves single chapter JSON (`{num}.{lang}.json`)
5. Frontend Store (localStorage) — reading progress, history, bookmarks (never mixed with novel data)

**Per-chapter JSON format:**
```json
{
  "novelId": "global-descent",
  "chapterNo": 127,
  "sourceLang": "cn",
  "targetLang": "th",
  "title": { "source": "...", "translated": "..." },
  "status": "translated",
  "paragraphs": ["...", "..."],
  "updatedAt": "2026-06-23T00:00:00.000Z"
}
```

**Migration:** `python tools/migrate_json.py` — creates novel.json + chapters.json from existing data

---

## Translation Pipeline (v3)

1. **Source scraping** — Python requests to qidian.com (no Cloudflare)
2. **Translate** — `python tools/translate.py <range> --score --json`
3. **Post-process (1 step)** — CN strip only
4. **Quality check** — `python tools/scorer.py chapters/ --source source/`

### Default translate command
```bash
python tools/translate.py 130 --score --json
```
Post-process: no longer does type fix, end marker append (auto), dialogue reclassify, speaker extract, EN guard, bracket wrap, empty block removal — all obsolete in v3.

**ข้อจำกัด**: `translate.py` รับเฉพาะ range (`131-135`) ไม่รับ space-separated list (`131 132 135`)

---

## Source Scraping

| Tier | Tool | Use when |
|:-----|:-----|:---------|
| 1 | Python requests | **qidian.com** (no CF, fastest) |
| 2 | agent-browser CLI | JS-rendered sites without CF |
| 3 | undetected-chromedriver | Last resort against CF |
| 4 | Smart Proxy API (paid) | Production-scale CF bypass |

**Key finding**: No free tool reliably bypasses Cloudflare in 2026.  
**Best free source**: qidian.com (no CF, Python requests works directly)

---

## Bang Command Rules

> ⚠️ **CRITICAL**: ห้ามเรียก `translate.py` โดยตรงเด็ดขาด — ใช้ `novelctl.py translate` เท่านั้น
> เรียก `translate.py` ตรง = เสี่ยงสร้าง legacy format, index stale, cache corrupt

| User says | MIKA does |
|:-----------|:-----------|
| `"แปลตอน 130"` | `terminal("python tools/novelctl.py translate 130 --slug global-descent")` |
| `"แปล 131-135 อีก 5 ตอน"` | `terminal("python tools/novelctl.py translate 131-135 --mode autopilot --slug global-descent")` |
| `"แปล 139 strict"` | `terminal("python tools/novelctl.py translate 139 --mode strict --slug global-descent")` |
| `"แปลใหม่ 139"` | `terminal("python tools/novelctl.py translate 139 --force --slug global-descent")` |
| `"ลองแปล 139"` | `terminal("python tools/novelctl.py translate 139 --mode draft --slug global-descent")` |
| `"ตรวจ 139"` | `terminal("python tools/novelctl.py validate 139 --slug global-descent")` |
| `"ตรวจ 131-135"` | `terminal("python tools/novelctl.py validate 131-135 --slug global-descent")` |
| `"ตรวจคุณภาพ"` | `terminal("python tools/novelctl.py validate 1-200 --slug global-descent")` |
| `"เช็ค 140-150"` | `terminal("python tools/novelctl.py preflight 140-150 --slug global-descent")` |
| `"ซ่อม 139"` | `terminal("python tools/novelctl.py repair 139 --slug global-descent")` |
| `"สถานะ"` | `terminal("python tools/novelctl.py status")` |
| `"หยุด"` | `terminal("python tools/novelctl.py stop")` |
| `"ต่อ"` | `terminal("python tools/novelctl.py resume --slug global-descent")` |
| `"รายงาน"` | `terminal("python tools/novelctl.py report --slug global-descent")` |
| `"rebuild"` | `terminal("python tools/novelctl.py rebuild --slug global-descent")` |
| `"scrape ตอน 128"` | `terminal("python tools/scrape_chapters.py 128")` |

## Anti-Patterns (ห้ามทำเด็ดขาด)

- ❌ อย่าเรียก `translate.py` โดยตรง — ใช้ `novelctl.py translate` เท่านั้น
- ❌ อย่าใช้ `hermes chat -q` หรือ `hermes prompt` ใน translate pipeline — ใช้ HTTP ตรง
- ❌ อย่าเปลี่ยน model จาก deepseek-v4-flash โดยไม่ถามพี่โชค — ฟรีเท่านั้น
- ❌ อย่าใส่ API keys ใน code หรือ .env ของ project
- ❌ อย่าใช้ cloudscraper — project ตายแล้ว
- ❌ อย่าใช้ `git add -A` — git root = C:\ จะ time out
- ❌ อย่าใช้ `--entities`, `--two-pass`, `--passes` — ถูกถอนออกจาก translate.py แล้ว
- ❌ อย่าให้ LLM output JSON — ใช้ `parse_translation_output()` แทน

---

## Known Gotchas

| Issue | Fix |
|:-------|:-----|
| CSS variables empty (white bg) | Unclosed `@media` block in design-system.css → balance braces |
| translate.py fails on `unrecognized arguments: 94` | ใช้ range (`89 94`) แยกไม่ได้ |
| Pydantic `model_serializer` warnings | `chapter.model_dump()` warnings — cosmetic, ignore |
| TM source cache stale from old schema | ลบ `.tmemory/global-descent.json` source_cache |
| `git add -A` time out | ใช้ `git add <absolute-path>` เฉพาะไฟล์ที่เปลี่ยน |
| agent-browser stuck on CF | เปลี่ยนไปใช้ Tier 1 (requests → qidian) หรือ Tier 4 (paid API) |
