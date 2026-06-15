# NovelClaw Translation Reference

**Mika (P'Choke's translator) reads this BEFORE translating any chapter.**

---

## 1. Workflow (5 steps)

```bash
# Step 1: Get context for ch (glossary, style, format, unknown terms)
python tools/translate_ch.py 113 --context --search

# Step 2: Read source, translate to Thai (Mika does this)

# Step 3: Save chapter JSON
# Save as chapters/NNNN.json (e.g., chapters/0113.json)
python tools/save_chapter.py 113

# Step 4: Validate (auto on git commit via pre-commit hook)
python tools/validate_chapter.py 113

# Step 5: Commit
git add novels/global-descent/chapters/0113.json
git commit -m "translate ch 113"
```

---

## 2. Format v2 (STRICT — schema enforces)

| Block type | Required text pattern | Example |
|---|---|---|
| `narration` | any text, no CN leakage (except in 【】/《》) | `เฉาซิงเดินไปข้างหน้า` |
| `dialogue` | `「...」` (CJK corner brackets) | `เฉาซิงพูด 「ไปกัน」` |
| `system` | `【...】` | `【เลเวล 10 (1533/10000)】` |
| `game_title` | `《...》` | `《มหายุคน้ำแข็ง》` |
| `end` | `(จบบท)` | end marker |

**Title format:** `ตอนที่ N <translated_title>` (space between N and title)

**Required fields per chapter:**
- `schema_version: 1`
- `num: <ch number>`
- `title: "ตอนที่ N <thai>"`
- `blocks: [...]` (at least 1 content block + 1 end block)
- `source: "ch N"` (short form, no novel title)
- `notes: [...]` (optional)
- `lang: "cn"` (default; can be `cn`, `jp`, `kr`, `en`, `th`)

---

## 3. Glossary

**Read in order:** `locked.md` → `reference.md` → `auto.md`

| Tier | File | Priority | Rule |
|------|------|----------|------|
| Locked | `glossary/locked.md` | P1 | **Never deviate.** Use exact Thai. |
| Reference | `glossary/reference.md` | P2 | Use consistently for recurring terms. |
| Auto | `glossary/auto.md` | P3 | Suggestion only. Translate freely if not found. |

**Full glossary:** `glossary/glossary.yml` (auto-generated from the 3 .md files.
Run `python tools/build_yaml.py` to regenerate.)

---

## 4. Style Rules

See `style.md` in the novel folder. Key rules:

**DO:**
- ✅ TRANSMIT source faithfully — keep author's voice
- ✅ Subject echo (3+ MC mentions in row) — author's style, preserve it
- ✅ Em dash `—` for missing numbers (e.g., `พลัง: —`)
- ✅ Stat blocks inline: `【เลเวล 10 (1533/10000)】`
- ✅ 【】 for system messages, 《》 for game/donor names

**DO NOT:**
- ❌ Don't add/remove plot content (transmittor not editor)
- ❌ Don't use straight `"` in dialogue — use `「」`
- ❌ Don't "improve" the source's flat emotion — keep it
- ❌ Don't auto-fix "anti-patterns" (they're author voice, report not fix)
- ❌ Don't paraphrase dialogue (translate, don't rewrite)

---

## 5. Quick Thai-Cheatsheet for Common Patterns

| Source CN | Thai |
|-----------|------|
| 曹星大佬 | พี่เฉาซิง |
| 天選領主 | ลอร์ดผู้ถูกเลือกโดยสวรรค์ |
| 天選之人 | ผู้ถูกเลือก |
| 新手保護期 | โหมดคุ้มครองมือใหม่ |
| 冰晶王國 | อาณาจักรคริสตัลน้ำแข็ง |
| 狂風雪原 | ทุ่งพายุหิมะ |
| 寒冰護盾 | โล่น้ำแข็ง |
| 極地人小屋 | กระท่อมคนเมืองหนาว |
| 招募 | รับสมัคร |
| 好感度 | ค่าความชอบ |
| 忠誠度 | ค่าความจงรักภักดี |
| 領地 | ฐานที่มั่น |
| 祭司 | นักบวช / เจ้าอาวาส |
| 遊獵者 | นักล่า |
| 倖存者 | ผู้รอดชีวิต |
| 兩名倖存者 | ผู้รอดชีวิตสองคน |
| 村民 | ชาวบ้าน |
| 民兵 | ทหารรักษาการณ์ |
| 系統提示 | ข้อความระบบปรากฏ |
| 本章完 | (จบบท) |

---

## 6. Common Sentence Patterns (copy-paste ready)

**System messages:**
```
ข้อความระบบปรากฏ
【...】
```

**Action/transition:**
```
ทันใดนั้น / ขณะนั้น / ในขณะเดียวกัน
ไม่กี่นาทีต่อมา / หลังจากนั้น
เฉาซิงครุ่นคิดครู่หนึ่ง
```

**Dialogue tags:**
```
เฉาซิงพูด 「...」
เฉาซิงส่ายหน้า 「...」
เฉาซิงพยักหน้า 「...」
```

**Narration (single thought):**
```
เฉาซิงรู้สึก...
บนใบหน้าเฉาซิงปรากฏ...
```

---

## 7. Schema Pitfalls (auto-rejected)

- ❌ Title without "ตอนที่ N " prefix
- ❌ Dialogue using straight `"..."`
- ❌ System message missing 【】
- ❌ Missing end marker `(จบบท)`
- ❌ End marker not as last block
- ❌ Narration with CN chars (except in whitelisted zones)
- ❌ Empty blocks array

**Use `python tools/save_chapter.py N` to validate before commit.**

---

## 8. Per-Chapter Workflow

```bash
# 1. Get context
python tools/translate_ch.py N --context --search

# 2. Read source + translate (Mika writes JSON)

# 3. Save + validate
python tools/save_chapter.py N
python tools/validate_chapter.py N

# 4. Commit
git add novels/global-descent/chapters/NNNN.json
git commit -m "translate ch N"
```

---

## 9. Tools Quick Reference

| Tool | Purpose |
|------|---------|
| `python tools/translate_ch.py N --context` | Full context + unknown term search |
| `python tools/save_chapter.py N` | Validate + save ch N |
| `python tools/validate_chapter.py N` | Validate ch N |
| `python tools/glossary_doctor.py --ch N` | Check ch N for issues |
| `python tools/build_yaml.py` | Rebuild glossary.yml from .md |

---

## 10. Common Errors and Fixes

| Error | Fix |
|-------|-----|
| `Title must be "ตอนที่ N ..."` | Add space + Thai title |
| `Dialogue must contain 「」` | Use `「」` not straight `"` |
| `System message must contain 【】` | Use `【】` |
| `Narration contains N raw CN chars` | Translate CN to Thai (except in whitelisted zones) |
| `Chapter has no content blocks` | Add at least 1 narration/dialogue/system before end |
| `End marker must be exactly "(จบบท)"` | Use exact text including parens |
| `JSON invalid` | Check for unescaped quotes in text values |

---

**Last updated:** 2026-06-15
