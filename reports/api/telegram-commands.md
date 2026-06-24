# Telegram Command Surface — NovelClaw

## หลักการ

ให้ Hermes/LLM ใช้คำสั่งตายตัว (ไม่ต้อง "ประดิษฐ์ format เองทุกครั้ง").  
ทุกคำสั่ง map 1:1 กับ `novelctl.py` command.  
ใช้ deep links + inline keyboards สำหรับ UX ที่ดีขึ้น.

## คำสั่ง Telegram (setMyCommands)

| คำสั่ง | คำอธิบาย | novelctl equivalent |
|:-------|:---------|:-------------------|
| `/translate` | แปลตอนใหม่ | `novelctl.py translate <range>` |
| `/retry` | แปลใหม่ (force) | `novelctl.py translate <range> --force` |
| `/review` | ตรวจ needs_review | `novelctl.py check` |
| `/resume` | ทำต่อจากที่ค้าง | `novelctl.py resume` |
| `/report` | รายงานสถานะ | `novelctl.py report` |
| `/validate` | ตรวจสอบตอน | `novelctl.py validate <range>` |
| `/repair` | ซ่อมตอน | `novelctl.py repair <range>` |
| `/status` | สถานะ job | `novelctl.py status` |
| `/backup` | สำรองข้อมูล | `novelctl.py backup` |

## Payload Schema

```python
# ทุก command มี payload schema ที่ชัดเจน
TRANSLATE_SCHEMA = {
    "slug": str,
    "range": str,           # "77-99" หรือ "140,142,145"
    "mode": "safe|strict|autopilot|draft",
    "force": bool,
    "workers": int,         # default 1
}

REVIEW_SCHEMA = {
    "slug": str | None,     # None = all slugs
}
```

## Hermes Agent Skill Integration

```markdown
# NovelClaw Telegram Commands

เมื่อ user พิมพ์:
- `"/translate 77-99"` → หนูเข้าใจว่าแปลตอน 77-99
  → terminal("python tools/novelctl.py --slug global-descent translate 77-99")
  
- `"/retry 139"` → แปลใหม่ตอน 139
  → terminal("python tools/novelctl.py --slug global-descent --force translate 139")

- `"/report"` → รายงานสถานะ
  → terminal("python tools/novelctl.py --slug global-descent report")
```

## Deep Links

```
https://t.me/novelclaw_bot?start=translate_77-99
https://t.me/novelclaw_bot?start=resume
https://t.me/novelclaw_bot?start=report_global-descent
```

## Inline Keyboard Flow

```
User: /translate 77-99
Bot: ⚡ ใช้ 1 workers แปลตอน 77-99 (22 ตอน)
[✅ ดำเนินการ] [⏸ หยุด] [📋 รายงาน]
```

## สถานะ

**Design phase** — ยังไม่ได้ implement จริง.
ต้องทำ:
- [ ] setMyCommands ใน Telegram Bot API
- [ ] implement callback handlers สำหรับ inline keyboards
- [ ] เชื่อม Hermes slash commands → novelctl commands
