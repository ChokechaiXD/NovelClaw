# NovelClaw

NovelClaw คือระบบ local-first สำหรับนำเข้านิยาย แปลด้วย LLM ตรวจคุณภาพ และอ่านผ่านเว็บในเครื่องหรือวง LAN เดียวกัน ระบบใช้ Python สำหรับ pipeline และ Node.js/Express สำหรับ Reader โดยไม่ต้องมีฐานข้อมูล, frontend framework หรือ build step

## ความสามารถหลัก

- นำเข้าจากข้อความ, URL และ source adapters ที่รองรับ
- เก็บต้นฉบับและคำแปลเป็นไฟล์ JSON/Markdown ที่ตรวจสอบและสำรองได้ง่าย
- แปลทีละตอนหรือเป็นช่วง พร้อม retry, mock และ dry-run
- จัดการ provider, model, glossary, translation health และ source health จากหน้า Admin
- Reader แบบ responsive พร้อมประวัติการอ่าน, bookmark, theme และอ่านต่อจากตอนล่าสุด
- เปิดให้โทรศัพท์หรือเครื่องอื่นใน LAN ใช้งานผ่าน Node process เดียว
- chapter index ตรวจความครบถ้วนและซ่อมตัวเองแบบ atomic เมื่อไฟล์จริงเปลี่ยน

## Quick start บน Windows

ต้องมี Python 3.11+ และ Node.js 20+

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
npm --prefix reader install --no-audit --no-fund
```

เริ่ม Reader ด้วย:

```powershell
.\run.bat
```

`run.bat` จะ:

- เปิด Reader ที่ `http://localhost:4173`
- bind ที่ `0.0.0.0` เพื่อใช้ใน LAN
- แสดง URL ของเครื่องสำหรับเปิดจากโทรศัพท์
- reuse เฉพาะ NovelClaw process ที่มี health check ผ่าน
- ปิดเฉพาะ process ที่ script เป็นผู้เริ่ม ไม่ปิด Node process อื่นในเครื่อง

## ใช้ในวง LAN

เครื่องลูกต้องอยู่ในเครือข่ายส่วนตัวเดียวกัน แล้วเปิด URL ที่ `run.bat` แสดง เช่น:

```text
http://192.168.1.20:4173
```

หากเข้าไม่ได้ ให้ตรวจ Windows Firewall ว่าอนุญาต inbound TCP port 4173 บน Private network แล้ว

ค่าเริ่มต้นของ `run.bat` คือ `TRUSTED_LAN=true` ซึ่งอนุญาตคำสั่งเขียนจากอุปกรณ์ในวงเดียวกัน ใช้เฉพาะ LAN ที่ไว้ใจได้และห้าม forward port นี้ออกอินเทอร์เน็ต

ปรับ port หรือปิดการเปิด browser อัตโนมัติได้ก่อนรัน:

```powershell
$env:PORT = "4180"
$env:NOVELCLAW_RUN_OPEN = "0"
.\run.bat
```

สำหรับ localhost-only:

```powershell
$env:HOST = "127.0.0.1"
$env:TRUSTED_LAN = "false"
npm --prefix reader start
```

## คำสั่งหลัก

ตรวจสถานะและ config:

```powershell
python novelclaw.py status
python novelclaw.py config --validate
python novelclaw.py import-sites
```

ทดสอบ translation path โดยไม่เรียก LLM และไม่เขียนคำแปล:

```powershell
python novelclaw.py translate 1 --slug global-descent --mock --dry-run --sequential
```

แปลจริงทีละตอนหรือเป็นช่วง:

```powershell
python novelclaw.py translate 1 --slug global-descent --sequential
python novelclaw.py translate 1-10 --slug global-descent --parallel 3
```

คำสั่งรองรับ `--provider`, `--model`, `--from`, `--to`, `--retry` และ `--json` ใช้ `python novelclaw.py translate --help` เพื่อดูค่าปัจจุบัน

งานนำเข้าและงานแปลสามารถสั่งจากหน้า Admin ได้เช่นกัน การตั้งค่า runtime หลักอยู่ที่ `novelclaw.config.yaml`

## โครงสร้างข้อมูล

```text
NovelClaw/
├── novelclaw.py                 # CLI หลัก
├── novelclaw.config.yaml        # runtime defaults
├── run.bat                      # Windows local/LAN launcher
├── novels/{slug}/
│   ├── novel.json               # metadata
│   ├── chapters.json            # generated canonical index
│   ├── chapters/
│   │   ├── NNNN.cn.json         # ต้นฉบับ
│   │   ├── NNNN.th.json         # คำแปล
│   │   └── index.json           # compatibility index
│   └── glossary/                # glossary ของเรื่อง
├── tools/
│   ├── import_sources.py        # import orchestrator
│   ├── import_adapters/         # source-specific adapters
│   ├── pipeline.py              # translation pipeline
│   └── llm_router/              # provider/model routing
├── reader/
│   ├── server.js                # HTTP API และ static server
│   ├── lib/                     # file repositories/services
│   ├── public/                  # HTML/CSS/vanilla JS SPA
│   └── tests/                   # Node/API regression tests
└── tests/                       # Python regression tests
```

ข้อมูลนิยายเป็น source of truth ส่วน `chapters.json` และ `chapters/index.json` เป็น generated indexes ระบบจะตรวจเลขตอนจากชื่อไฟล์แบบเบาและ rebuild indexes เมื่อพบข้อมูลขาดหรือ title เก่า

## Data flow

```text
Import/Paste/URL
      ↓
Source inspection and cleaning
      ↓
Translation with provider + glossary
      ↓
Quality gate and translation metadata
      ↓
Atomic chapter/index writes
      ↓
Reader and LAN clients
```

หน้าอ่านใช้ chapter metadata แบบบางและไม่ค้นหา provider/model ระหว่างเปิดบท ข้อมูล workflow และ quality แบบเต็มจะโหลดเฉพาะหน้า Admin ที่ร้องขอ `withQuality=1`

## Quality gates

```powershell
# Python pipeline/import tests
python -m pytest -q

# Reader static checks, syntax และ unit tests
npm --prefix reader run check

# API integration tests — ต้องเปิด Reader อยู่
npm --prefix reader run test:api
```

tests ใช้ mock และ local fixtures ไม่ต้องเรียก LLM จริง การทดสอบ API จะ snapshot/restore generated chapter indexes และลบข้อมูลทดสอบเมื่อจบ

## หลักการของโครงการ

- local-first: ไฟล์ในเครื่องเป็น source of truth
- lightweight: ใช้ standard library และ dependency ที่มีอยู่ก่อนเพิ่มของใหม่
- trusted-LAN: ออกแบบสำหรับเครื่องเดียวหรือเครือข่ายส่วนตัวขนาดเล็ก
- atomic writes: งานที่แก้ไฟล์สำคัญต้องไม่ทิ้งไฟล์ครึ่งสมบูรณ์
- explicit quality: source error, translation state และ quality result แยกจากกัน
- framework-free Reader: HTML, CSS และ vanilla JavaScript ไม่มี build pipeline

## License

MIT — ดู [LICENSE](LICENSE)
