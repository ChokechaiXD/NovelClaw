# 🐾 NovelClaw — Single Binary Novel Importer, Translator & Reader

NovelClaw คือระบบ **Local-first** สำหรับนำเข้านิยาย แปลด้วย AI คุณภาพสูง และอ่านผ่านเว็บเบราว์เซอร์ในเครื่องหรือมือถือผ่านวง LAN เดียวกัน
เขียนด้วยภาษา **Go (Golang)** รวมทุกอย่างไว้ในไฟล์เดียว (`novelclaw.exe`) โดยไม่ต้องพึ่งพา Node.js, Python venv, หรือ Database ภายนอก

---

## ⚡ จุดเด่น
- **Single Binary (7.8 MB):** ไฟล์ `.exe` เดียวมีทั้ง Web Server, Web Scraper, AI Translation Engine, และ Reader UI ฝังตัวในไฟล์
- **Ultra-Fast & Feather-light:** ใช้ RAM น้อยกว่า 20MB สตาร์ทติดทันทีใน 5ms
- **Universal Import:** ดึงนิยายจากเว็บ (เช่น 69shu และเว็บทั่วไป) พร้อมระบบตัดโฆษณา/ตัวอักษรขยะ หรือวางข้อความดิบ
- **High-Quality AI Translation:** เชื่อมต่อกับ 9Router / OpenRouter พร้อมระบบ **Glossary** (ชื่อตัวละคร/วิชา/สถานที่) และ **Context Memory** จากตอนก่อนหน้าเพื่อสำนวนไทยที่สละสลวย
- **Distraction-Free Web Reader:** รองรับธีม Dark (OLED), Sepia, Light, ปรับฟอนต์/ขนาด, บันทึกตอนที่อ่านค้างไว้อัตโนมัติ

---

## 🚀 การเริ่มใช้งาน (Quick Start)

### วิธีที่ 1: ดับเบิ้ลคลิก `run.bat` หรือรัน `novelclaw.exe`
```powershell
.\run.bat
```
หรือรัน binary ตรงๆ:
```powershell
.\novelclaw.exe -port 4173
```

เปิดเบราว์เซอร์ที่:
- **บนคอมพิวเตอร์:** `http://localhost:4173`
- **บนมือถือ (ในวง LAN เดียวกัน):** `http://[IP-เครื่อง-PC]:4173`

---

## 🛠️ คำสั่งปรับแต่ง (CLI Flags)
```powershell
.\novelclaw.exe -port 4173 -router "http://localhost:20128/v1" -model "google/gemini-2.5-flash"
```

| Flag | คำอธิบาย | ค่าเริ่มต้น |
| :--- | :--- | :--- |
| `-port` | Port สำหรับเปิด Web Server | `4173` |
| `-data` | โฟลเดอร์เก็บข้อมูลนิยาย | `./novels` |
| `-router` | Base URL ของ 9Router หรือ OpenAI endpoint | `http://localhost:20128/v1` |
| `-model` | ชื่อ AI Model ที่ต้องการใช้แปล | `google/gemini-2.5-flash` |
| `-key` | API Key (ถ้ามี) | `""` |

---

## 📁 โครงสร้างโปรเจกต์
```
NovelClaw/
├── novelclaw.exe               # Single Binary สำเร็จรูป
├── run.bat                     # สคริปต์เปิดรัน 1-click
├── novels/                     # โฟลเดอร์เก็บข้อมูลนิยาย (JSON/Markdown)
├── cmd/novelclaw/main.go       # Entry point
├── internal/
│   ├── config/                 # การตั้งค่าระบบ
│   ├── model/                  # Data structures
│   ├── storage/                # JSON & Filesystem Store
│   ├── scraper/                # ตัวดึงเนื้อหานิยายจากเว็บ
│   ├── translator/             # 9Router LLM Client, Prompt & Glossary
│   ├── api/                    # REST API & Server-Sent Events (SSE)
│   └── web/                    # Embedded HTML / CSS / JS Reader
```
