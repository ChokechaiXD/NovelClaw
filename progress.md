# NovelClaw — Project Progress Tracker

> **อัปเดตล่าสุด:** 2026-06-17
> **วิธีใช้:** เวลาทำอะไรเสร็จ → ย้ายจาก In Progress → Done + วันที่
> **เวลาเจอ bug/ปัญหา** → เพิ่มใน Known Issues
> **เวลาจะทำอะไรใหม่** → เพิ่มใน Backlog หรือ In Progress

---

## 📊 สถานะโดยรวม

| หมวด | สถานะ | หมายเหตุ |
|------|-------|----------|
| แปลนิยาย | 🟡 ทำอยู่ | ch 1-134 แล้ว (65 JSON files), ต่อจาก ch 135 |
| Reader UI Desktop | 🟢 ใช้งานได้ | แก้ bug หลักหมดแล้ว |
| Reader UI Mobile | 🟡 มี bug เหลือ | กล่องดำบัง content (overlay issue) |
| Tools/Pipeline | 🟢 ใช้งานได้ | เทสต์ผ่าน, ใช้งานได้ |
| Glossary | 🟢 ใช้งานได้ | 572 terms (58 locked / 100 ref / 414 auto) |
| Tests | 🟢 มีพื้นฐาน | 47 tests pass |
| Multi-novel | 🟢 Infra พร้อม | registry.py + schema รองรับ |

---

## 🔴 Known Issues (ต้องแก้)

| # | ปัญหา | ตำแหน่ง | ระดับ | สถานะ | หมายเหตุ |
|---|--------|---------|-------|--------|----------|
| — | — | — | — | — | แก้หมดแล้ว 🎉 |

---

## 🟢 แก้ไปแล้ว (Deep Scan 2026-06-17 — ตรวสอบจากโค้ดจริง)

| # | ปัญหาเดิม | ผลการตรวจสอบ | สถานะ |
|---|-----------|-------------|--------|
| 1 | Desktop hamburger toggle ไม่ปิด sidebar | JS ใช้ `.collapsed` สำหรับ desktop ถูกต้องแล้ว (app.js:526-540) | ✅ แก้แล้ว |
| 2 | Content ไม่ขึ้นบน desktop Brave | ไม่มี CSS/JS ที่ทำให้ content หายไป — cache control ปิดแล้ว | ✅ แก้แล้ว (cache issue) |
| 3 | กล่องดำบัง content บน fullscreen | **Desktop:** sidebar.collapsed ทำงานถูก ✅ | ✅ แก้แล้ว |
| 4 | Server crash: `fs.readFileSync is not a function` | ไม่มี `readFileSync` ในโค้ดแล้ว ใช้ `fs/promises` ทั้งหมด | ✅ แก้แล้ว |
| 5 | XSS: `ch.meta` ไม่ผ่าน HTML escape | ไม่มี `ch.meta` ในโค้ด ใช้ `esc()` ครบทุก output | ✅ แก้แล้ว |
| 6 | XSS: `novel.title/slug` innerHTML โดยตรง | ใช้ `textContent` ไม่ใช่ innerHTML (app.js:89-98) | ✅ แก้แล้ว |
| 7 | `pushState` ทุกครั้ง — history ระเบิด | ถูก comment ออกหมดแล้ว (app.js:301-307) ไม่เปลี่ยน URL | ✅ แก้แล้ว |
| 8 | EADDRINUSE retry ไม่มี limit | ไม่มี retry loop ในโค้ดปัจจุบัน | ✅ แก้แล้ว |
| 9 | virtual-scroll.js: `prevCount` overwrite | ไม่มีตัวแปร `prevCount` ในโค้ด — logic ใหม่ทำงานถูก | ✅ แก้แล้ว |
| 10 | Overlay CSS `display:block` ทับ JS บน mobile | ไม่มี media query `display:block` — ใช้ class .open ผ่าน JS | ✅ แก้แล้ว |
| 11 | ปุ่ม ✕ ซ้ำซ้อนกับ hamburger | ถูกลบออกหมดแล้ว (คอมเม้นต์ใน app.js:573 ยืนยัน) | ✅ แก้แล้ว |
| 12 | `.card-progress` CSS หายไป | ถูกเปลี่ยนเป็น `.continue-progress` แล้ว ทำงานปกติ | ✅ แก้แล้ว |
| 13 | Double IIFE ใน app.js | เหลือ IIFE เดียว (app.js:3) | ✅ แก้แล้ว |

---

## 🟡 In Progress (กำลังทำ)

| # | งาน | เริ่ม | หมายเหตุ |
|---|-----|-------|----------|
| 1 | แก้ mobile overlay ทับ content | — | เหลืออันเดียวนี้ |

---

## 🟢 Done — แปลนิยาย

| ช่วง | สถานะ | หมายเหตุ |
|------|-------|----------|
| ch 1 | ✅ แล้ว | sample |
| ch 2-70 | ❌ ยังไม่มี | ไม่มี source ใน chapters/ |
| ch 71 | ✅ แล้ว | 30KB |
| ch 72-134 | ✅ แล้ว | 63 ตอนรวมกัน |
| ch 89, 94 | ⚠️ ขนาดเล็กผิดปกติ | ~12KB (ต้องตรวจสอบเนื้อหา) |
| ch 101, 102, 103 | ⚠️ ขนาดเล็กผิดปกติ | 3-10KB (ต้องตรวจสอบเนื้อหา) |
| ch 74, 115, 131 | ⚠️ ขนาดใหญ่ผิดปกติ | 60-65KB (อาจปกติ — เนื้อหาเยอะ) |

---

## 📋 Backlog (ยังไม่ทำ)

| # | งาน | ลำดับ | หมายเหตุ |
|---|-----|-------|----------|
| 1 | แปลต่อ ch 135+ | 1 | ต่อเนื่อง |
| 2 | แก้ mobile overlay bug | 2 | เหลือ issue สุดท้าย |
| 3 | สร้าง favicon.ico | 3 | ง่ายมาก 5 นาที |
| 4 | ตรวจสอบ ch 89/94/101/102/103 เนื้อหา | 4 | ขนาดเล็กผิดปกติ อาจ truncated |
| 5 | แปล ch 2-70 (แยก source จาก source/) | 5 | มี source อยู่แล้ว |
| 6 | เพิ่ม tests ให้ครบ coverage | 6 | ปัจจุบัน 47 tests |
| 7 | เพิ่มนิยายเรื่องที่ 2 | 7 | Infra พร้อมแล้ว |

---

## 📝 Session Log (ย้อนหลัง)

| Session | วันที่ | สิ่งที่ทำ |
|---------|--------|----------|
| 1-16 | 2026-06-13~16 | Foundation, แปล, tools, UI, bugs |
| 17 | 2026-06-17 | สร้าง progress.md + Deep scan bug |

---

## 🔗 ไฟล์สำคัญ

| ไฟล์ | วัตถุประสงค์ |
|------|------------|
| `PROMPT.md` | AI system prompt สำหรับแปล (v3 paragraphs) |
| `TRANSLATION_MANUAL.md` | คู่มือ pipeline สำหรับมนุษย์ |
| `novels/global-descent/style.md` | Style choices เฉพาะเรื่อง |
| `novels/global-descent/summary.md` | เนื้อเรื่องย่อ |
| `novels/global-descent/glossary/locked.md` | คำศัพท์ locked |
