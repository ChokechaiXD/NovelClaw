# NovelClaw — Translation Manual

คู่มือดูแลระบบนำเข้า แปล ตรวจคุณภาพ และจัดเก็บตอนแบบ local-first

**Last updated:** 2026-07-13

## โครงสร้างข้อมูล

```text
novels/<slug>/
├── novel.json                 # metadata หลัก
├── chapters.json              # generated chapter index
├── chapters/
│   ├── NNNN.cn.json           # source chapter แบบ canonical
│   ├── NNNN.th.json           # translated chapter แบบ canonical
│   └── source/NNNN.md         # raw source จาก importer ถ้ามี
└── glossary/
    ├── locked.md              # P1: ต้องใช้ตรงทุกครั้ง
    ├── reference.md           # P2: คำที่ใช้ซ้ำ
    ├── auto.md                # P3: คำที่ระบบค้นพบ
    ├── glossary.yml
    └── glossary.json
```

`novel.json`, chapter files และ glossary เป็น source of truth ส่วน `chapters.json` เป็น index ที่ rebuild ได้ ห้ามสร้าง `meta.md`, `chapters/index.json` หรือ root `NNNN.json` แบบเก่า

## นำเข้าต้นฉบับ

ดู adapters ที่รองรับ:

```powershell
python novelclaw.py import-sites
```

ตรวจ URL โดยไม่เขียนไฟล์:

```powershell
python novelclaw.py import-url <toc-url> --site auto --preview
```

นำเข้าเป็นเรื่องใหม่หรือเพิ่มตอน:

```powershell
python novelclaw.py import-url <toc-url> --slug <slug> --site auto --range 1-20
```

ใช้ `--force` เฉพาะเมื่อต้องการเขียนทับ source ที่มีอยู่แล้ว หน้า Admin มี paste/URL import และ source inspection สำหรับงานเดียวกัน

## แปล

ทดสอบ flow โดยไม่เรียก LLM และไม่บันทึกคำแปล:

```powershell
python novelclaw.py translate 1 --slug <slug> --mock --dry-run --sequential
```

แปลจริงทีละตอนหรือเป็นช่วง:

```powershell
python novelclaw.py translate 1 --slug <slug> --sequential
python novelclaw.py translate 1-20 --slug <slug> --parallel 3 --retry 1
```

pipeline จะอ่านและทำความสะอาด source, สร้าง prompt จาก glossary/profile, เรียก provider, แยก paragraph types, ตรวจ deterministic quality, repair/retry ตาม config และบันทึก `.th.json` แบบ atomic

ดู options ล่าสุดด้วย:

```powershell
python novelclaw.py translate --help
```

## Canonical translated chapter

```json
{
  "novelId": "example-novel",
  "chapterNo": 142,
  "sourceLang": "cn",
  "targetLang": "th",
  "title": {
    "source": "第142章",
    "translated": "ตอนที่ 142"
  },
  "status": "translated",
  "paragraphs": [
    { "type": "narration", "text": "ข้อความบรรยาย" },
    { "type": "dialogue", "text": "\"ข้อความสนทนา\"" },
    { "type": "system", "text": "【ข้อความระบบ】" },
    { "type": "narration", "text": "(จบบท)" }
  ],
  "meta": {
    "provider": "provider-id",
    "model": "model-id",
    "promptProfile": "omni"
  },
  "qualityRecord": {
    "passed": true,
    "score": 90,
    "hardFailures": [],
    "warnings": []
  }
}
```

paragraph types หลักคือ `narration`, `dialogue`, `system`, `thought` และ `action` ตัว reader escape text ก่อน render และใช้ type เป็น semantic class

## ตรวจคุณภาพ

ตรวจคำแปลที่บันทึกแล้วด้วย judge:

```powershell
python novelclaw.py judge 142 --slug <slug>
python novelclaw.py judge 140-150 --slug <slug> --json
```

ตรวจ repository ก่อน commit:

```powershell
python -m ruff check novelclaw.py tools tests
python -m pytest -q
npm --prefix reader run check
```

API integration test ต้องเปิด Reader ก่อน:

```powershell
npm --prefix reader run test:api
```

## ดูแล glossary

1. คำหลัก ตัวละคร สถานที่ และศัพท์ที่ห้ามเปลี่ยน ใส่ `locked.md`
2. คำที่เกิดซ้ำและต้องการความสม่ำเสมอ ใส่ `reference.md`
3. คำชั่วคราวหรือคำที่ระบบค้นพบ ใส่ `auto.md`
4. ใช้รูปแบบตาราง `| source | target | notes |`

ลำดับความสำคัญคือ `locked.md` > `reference.md` > `auto.md` ระบบจะอ่านไฟล์เหล่านี้ใน translation pipeline และสร้าง cache/index ที่จำเป็นเอง

## เพิ่มนิยายใหม่

1. สร้าง `novels/<slug>/novel.json` หรือใช้หน้า Admin
2. นำเข้า source ด้วย `import-url`, paste import หรือวาง `chapters/source/NNNN.md`
3. สร้าง glossary tiers สำหรับเรื่องนั้น
4. ตรวจ source health ก่อนเริ่มแปล
5. รัน mock/dry-run หนึ่งตอน แล้วจึงเริ่ม batch จริง

ระบบ Reader จะค้นพบเรื่องจาก directory และ `novel.json`; ไม่ต้องลงทะเบียนซ้ำในไฟล์อื่น
