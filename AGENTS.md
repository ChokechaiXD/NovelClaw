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

| User says | MIKA does |
|:-----------|:-----------|
| `"แปลตอน 130"` | `terminal("python tools/translate.py 130 --score --json")` |
| `"แปล 131-135 อีก 5 ตอน"` | `terminal("python tools/translate.py 131-135 --score --json --concurrent 3")` |
| `"ตรวจคุณภาพ"` | `terminal("python tools/scorer.py chapters/ --source source/")` |
| `"scrape ตอน 128"` | `terminal("python tools/scrape_chapters.py 128")` |

---

## Anti-Patterns (ห้ามทำเด็ดขาด)

- ❌ อย่าใช้ `hermes chat -q` หรือ `hermes prompt` ใน translate pipeline — ใช้ HTTP ตรง
- ❌ อย่าเปลี่ยน model จาก deepseek-v4-flash โดยไม่ถามพี่โชค — ฟรีเท่านั้น
- ❌ อย่าใส่ API keys ใน code หรือ .env ของ project
- ❌ อย่าใช้ cloudscraper — project ตายแล้ว
- ❌ อย่าใช้ `git add -A` — git root = C:\ จะ time out
- ❌ อย่าใช้ `--entities`, `--two-pass`, `--passes` flags — ไม่มีผลแล้ว (entity pipeline ถูกลบ)
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
