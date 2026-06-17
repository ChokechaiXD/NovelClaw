# NovelClaw — Processes & Responsibilities

> **คำอธิบาย:** กระบวนการทำงานของแต่ละส่วนในระบบ — หน้าที่อะไร ทำงานยังไง เชื่อมกับอะไรบ้าง

---

## 🔄 Process 1: Translation Pipeline (กระบวนการแปล)

### หน้าที่
แปลนิยายจากภาษาจีน (CN) → ภาษาไทย (TH) โดยใช้ AI (Mika) ช่วยและมนุษย์ (P'Choke) กำกับ

### ลำดับการทำงาน

```
[1. เตรีมงาน] → [2. แปล] → [3. ตรวจสอบ] → [4. บันทึก] → [5. Commit]
```

### รายละเอียดแต่ละขั้น

#### ขั้น 1: เตรียมงาน
- **ใครทำ:** Mika
- **ทำอะไร:**
  - อ่าน source CN จาก `novels/global-descent/chapters/source/NNNN.md`
  - โหลด glossary (locked.md → reference.md → auto.md)
  - โหลด style.md สำหรับ novel-specific rules
  - อ่านตอนก่อนๆ เพื่อความสม่ำเสมอ (continuity)
- **เชื่อมกับ:** `tools/translate_next.py` (เตรียม context bundle)

#### ขั้น 2: แปล
- **ใครทำ:** Mika (AI)
- **ทำอะไร:**
  - แปลตาม PROMPT.md (S0-S9)
  - ใช้ Transmittor Principle — รักษาเสียงผู้เขียน
  - แปลทุกตัวอักษร — ไม่ข้าม ไม่ย่อ
  - รักษา format: `「」` dialogue, `【】` system, `《》` game title
  - แปล system messages เป็นไทยทั้งหมด
  - EN game terms ตาม whitelist (HP, BUFF, SSS ฯลฯ)
- **เชื่อมกับ:** PROMPT.md, style.md, glossary/

#### ขั้น 3: ตรวจสอบ
- **ใครทำ:** Mika (Self-Review Gate)
- **ทำอะไร:**
  - เช็ค CN/JP/KO leakage
  - เช็ค EN terms ตาม whitelist
  - เช็ค locked term violations
  - เช็ค format (brackets, punctuation, whitespace)
- **เชื่อมกับ:** `tools/validate_no_cjk.py`

#### ขั้น 4: บันทึก
- **ใครทำ:** Mika
- **ทำอะไร:**
  - บันทึกเป็น `novels/global-descent/chapters/NNNN.json`
  - อัปเดต `progress.md`
- **เชื่อมกับ:** `tools/save_chapter.py`

#### ขั้น 5: Commit
- **ใครทำ:** Mika
- **ทำอะไร:**
  - `git add` + `git commit` ด้วย commit message ที่ชัดเจน
- **เชื่อมกับ:** Git

---

## 🔄 Process 2: Validation (กระบวนการตรวจสอบ)

### หน้าที่
ตรวจสอบคุณภาพการแปล — ไม่มี CN leak, format ถูกต้อง, glossary compliance

### เครื่องมือหลัก

#### validate_no_cjk.py
- **หน้าที่:** ตรวจ CJK leakage + EN terms
- **ทำอะไร:**
  - สแกนทุก block ใน chapter JSON
  - ตรวจ CN characters (FAIL)
  - ตรวจ JP kana (FAIL)
  - ตรวจ KO hangul (FAIL)
  - ตรวจ source artifacts เช่น 求订阅, GZ (FAIL)
  - ตรวจ EN blacklist เช่น GZ (FAIL)
  - ตรวจ EN unknown terms (WARN — แจ้งเตือนให้ review)
- **Whitelist:** S/SS/SSR/SSS/UR/LR, HP, MP, CD, NPC, BUFF, DEBUFF, EXP, LV, ATK, DEF, DMG, AOE, DPS, TPS, PVP, PVE, ID
- **เชื่อมกับ:** ทุก chapter JSON, glossary whitelist

#### validate_chapter.py
- **หน้าที่:** ตรวจสอบโครงสร้าง + format + glossary
- **ทำอะไร:**
  - ตรวจ JSON schema validity
  - ตรวจ paragraph ratio (≥60%)
  - ตรวจ number preservation (2+ digit numbers)
  - ตรวจ locked term violations
  - ตรวจ length ratio (60%-350%)
- **เชื่อมกับ:** `tools/constants.py`, `glossary/glossary.yml`

#### glossary_doctor.py
- **หน้าที:** ตรวจความสม่ำเสมอของคำศัพท์
- **ทำอะไร:**
  - เช็ค term usage consistency across chapters
  - เช็ค name/skill/place consistency
  - เช็ค completeness (system messages)
- **เชื่อมกับ:** `glossary/glossary.yml`, `chapters/source/`

---

## 🔄 Process 3: Source Scraping (กระบวนการดึงต้นฉบับ)

### หน้าที่
ดึงต้นฉบับนิยายจากเว็บไซต์จีนมาเก็บเป็นไฟล์

### เครื่องมือ: scrape_chapters.py
- **หน้าที่:** Scrape ทุกตอนจาก hjwzw.com
- **ทำอะไร:**
  - ดึง HTML จาก hjwzw.com
  - แยกเนื้อหาออกจาก HTML (pure regex, no bs4)
  - บันทึกเป็น `novels/{slug}/chapters/source/NNNN.md`
- **ข้อจำกัดที่รู้:**
  - hjwzw.com strips `「」` และ `【】` ออกจาก HTML
  - บางตอนอาจไม่มี system messages
- **เชื่อมกับ:** `glossary_doctor.py` (detect_completeness skip ถ้า source ไม่มี `【】`)

---

## 🔄 Process 4: Reader Web App (กระบวนการแสดงผล)

### หน้าที่
แสดงผลนิยายที่แปลแล้วบนเว็บไซต์สำหรับอ่าน

### สถาปัตยกรรม

```
[Browser] → [server.js] → [API] → [novels/*.json]
                ↓
         [router.js] → [page-renderers.js] → [index.html]
```

### ส่วนประกษ

#### server.js (Backend)
- **หน้าที่:** Express.js server — ให้ API + serve static files
- **ทำอะไร:**
  - ให้ API endpoints (/api/novels, /api/novel/:slug/chapter/:num)
  - Serve static files จาก `public/`
  - SPA fallback (serve index.html สำหรับ non-API routes)
  - Handle EADDRINUSE (auto-kill old process)
- **เชื่อมกับ:** `public/`, `novels/`

#### router.js (Frontend Router)
- **หน้าที่:** Hash-based SPA routing
- **ทำอะไร:**
  - Parse URL hash → determine page
  - Toggle `body.reader-mode` / `body.dashboard-mode`
  - Call page renderer
  - Update nav active state
- **เชื่อมกับ:** `page-renderers.js`, `index.html`

#### page-renderers.js (Page Renderers)
- **หน้าที่:** Render HTML สำหรับแต่ละ page
- **ทำอะไร:**
  - `renderDashboard()` — แสดง novel grid, hero banner, continue reading
  - `renderReader({slug, chapter})` — แสดง reader toolbar + chapter content
  - `renderLibrary()`, `renderSearch()`, etc.
- **เชื่อมกับ:** `router.js`, `app.js`, API

#### app.js (Frontend Logic)
- **หน้าที่:** Event handlers + UI logic
- **ทำอะไร:**
  - Sidebar toggle (mobile/desktop)
  - Chapter navigation
  - Theme switching
  - Font size adjustment
  - Search
- **เชื่อมกับ:** `index.html`, `style.css`, API

#### style.css (Styling)
- **หน้าที่:** จัดรูปแบบหน้าเว็บ
- **ทำอะไร:**
  - CSS variables (themes: dark/light/sepia)
  - Responsive layout (mobile/desktop)
  - Reader toolbar layout
  - Sidebar overlay
- **เชื่อมกับ:** `index.html`, `app.js`

---

## 🔄 Process 5: Glossary Management (กระบวนการจัดการคำศัพท์)

### หน้าที่
จัดการคำศัพท์เฉพาะที่ใช้ในการแปล

### โครงสร้าง

```
glossary/locked.md (P1) ──→ glossary.yml ──→ glossary.db
glossary/reference.md (P2) ──┘
glossary/auto.md (P3) ──┘
```

### กระบวนการ

#### เพิ่มคำศัพท์ใหม่
1. ตัดสินใจ tier (P1/P2/P3)
2. เพิ่ม row ใน .md file ที่เหมาะสม
3. Rebuild: `python tools/build_yaml.py`

#### ใช้คำศัพท์ตอนแปล
1. Mika โหลด glossary ผ่าน `tools/translate_next.py`
2. ใช้คำตาม priority: locked > reference > auto
3. ถ้าไม่มีใน glossary → แปลตาม context + เพิ่มเข้า auto.md

#### ตรวจสอบคำศัพท์
1. `tools/glossary_doctor.py` — ตรวจ consistency
2. `tools/term_frequency.py` — ดูว่าคำไหนใช้บ่อย
3. `tools/chapter_diff.py` — ตรวจ consistency ระหว่างตอน

---

## 🔄 Process 6: UI Bug Fix (กระบวนการแก้บั๊ก UI)

### หน้าที่
แก้บั๊กในหน้าเว็บ reader โดยไม่เปลี่ยน style

### กระบวนการ

#### 1. ระบุปัญหา
- พี่แจ้งบั๊ก → หนูวิเคราะห์
- อ่าน code ที่เกี่ยวข้อง
- ระบุ root cause

#### 2. แก้ไข
- แก้เฉพาะจุดที่เป็นบั๊ก
- **ไม่เปลี่ยน:** colors, gradients, layout structure (ยกเว้นบั๊กคือ layout), font choices, spacing
- รักษา CSS/HTML structure เดิมให้มากที่สุด

#### 3. ทดสอบ
- ทดสอบใน browser จริง (Brave/Chrome) — **ไม่ใช่ browser tool**
- ทดสอบทั้ง desktop และ mobile
- ทดสอบทุก entry point (เช่น sidebar toggle ทั้ง hamburger, overlay, escape)

#### 4. Commit
- `git add` + `git commit` ด้วย message ที่อธิบายบัช + วิธีแก้

### หลักสำคัญ
- **"แก้ได้อย่างเดียว ก้ามแก้ไขสไตล์เด็ดขาด"** — แก้แค่บั๊ก ไม่เปลี่ยน style
- **ทดสอบใน browser จริง** — browser tool ของ Hermes ไม่ reliable
- **แก้ทุก entry point** — ถ้าแก้ sidebar ต้องแก้ทั้ง hamburger, overlay, escape, chapter click

---

## 🔄 Process 7: Ponytail Audit (กระบวนการตรวจสอบ code bloat)

### หน้าที่
ตรวจสอบว่า code มีส่วนที่ไม่จำเป็นหรือ over-engineered อยู่ไหม

### กระบวนการ

#### 1. Inventory
- นับไฟล์, LOC, dependencies
- ขอบเขต: `reader/`, `tools/`, `tests/`, repo root
- ข้าม: `.venv/`, `node_modules/`, `novels/*/chapters/`

#### 2. Scan
- Dead code (functions ที่ไม่เคยถูกเรียก)
- CSS classes ที่ไม่มีใน HTML/JS
- Tools ที่ทำงานซ้ำกัน
- Duplicate logic

#### 3. Report
- จัดลำดับจากส่วนที่ตัดได้มากที่สุดก่อน
- ใช้ tags: `delete:`, `stdlib:`, `native:`, `yagni:`, `shrink:`

#### 4. Fix (หลัง approval)
- ลบเป็น batch ละ 3-5 ไฟล์
- Syntax check หลังแต่ละ batch
- Verify server ยังทำงาน

### หลักสำคัญ (Ponytail Ladder)
1. ต้องสร้างด้วยไหม? (YAGNI)
2. stdlib ทำได้ไหม?
3. platform feature มีไหม?
4. dependency ที่มีอยู่แล้วใช้ได้ไหม?
5. เป็น 1 บรรทัดได้ไหม?
6. ถ้าไม่ใช่ทั้งหมด → เขียนให้สั้นที่สุด

---

## 📊 Summary: การเชื่อมต่อระหว่างส่วน

```
Translation Pipeline
    ↓ ใช้
Glossary System (locked.md → reference.md → auto.md → glossary.yml → glossary.db)
    ↓ ตรวจโดย
Validation System (validate_no_cjk.py, validate_chapter.py, glossary_doctor.py)
    ↓ บันทึกเป็น
Chapter JSON Files (novels/*/chapters/NNNN.json)
    ↓ อ่านโดย
Reader Web App (server.js → API → router.js → page-renderers.js)
    ↓ แสดงผลใน
Browser (index.html + style.css + app.js)

Source Scraping (scrape_chapters.py)
    ↓ สร้าง
Source Files (novels/*/chapters/source/NNNN.md)
    ↓ ใช้โดย
Translation Pipeline + glossary_doctor.py

Ponytail Audit
    ↓ ตรวจ
ทุกไฟล์ code (tools/, reader/, tests/)
    ↓ แนะนำ
ลบ/ยุบ/แทนที่ code ที่ไม่จำเป็น
```

---

*End of document*
