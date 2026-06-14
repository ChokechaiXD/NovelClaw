# NovelClaw Translation Reference

**Mika (P'Chok's translator) reads this BEFORE translating any chapter.**

---

## 1. Workflow (5 steps)

```bash
# Step 1: Get context for ch (glossary, style, format, unknown terms)
python tools/translate_ch.py 113 --context --search

# Step 2: Read source, translate to Thai (Mika does this manually)

# Step 3: Build JSON manually OR via Python script
# Save as chapters/0113.json with structure:
#   {"schema_version": 1, "num": 113, "title": "ตอนที่ N ...", "blocks": [...], "source": "ch 113"}

# Step 4: Validate (auto on git commit via pre-commit hook)
python tools/save_json.py 113

# Step 5: Commit
git add novels/global-descent/chapters/0113.json
git commit -m "translate ch 113"
```

---

## 2. Format v2 (STRICT — schema enforces)

| Block type | Required text pattern | Example |
|---|---|---|
| `narration` | any text, no CN leakage (except in 【】/《》) | `เฉาซิงเดินไปข้างหน้า` |
| `dialogue` | CN: `「...」` JP/KR: same. EN/TH: curly `"..."` U+201C/U+201D | `เฉาซิงพูด 「ไปกัน」` (CN) / `"Hello"` (EN) |
| `system` | CN/JP/KR/TH: `【...】`. EN: `[...]` | `【เลเวล 10 (1533/10000)】` |
| `game_title` | CN/TH: `《...》`. JP: `『...』`. EN/TH: curly `"..."` | `《มหายุคน้ำแข็ง》` |
| `end` | CN/TH: `(จบบท)`. JP: `（終）`. KR: `(끝)`. EN: `(End)` | per language |

**Title format:** `ตอนที่ N <translated_title>` (space between N and title)

**Required fields per chapter:**
- `schema_version: 1`
- `num: <ch number>`
- `title: "ตอนที่ N <thai>"`
- `blocks: [...]` (at least 1 content block + 1 end block)
- `source: "ch N"` (short form, no novel title)
- `notes: [...]` (optional)
- `lang: "cn"` (default; can be `cn`, `jp`, `kr`, `en`, `th`)

**Multi-language brackets (Phase 2 — 2026-06-14):**

Each source language has its own bracket convention. The schema
enforces the right brackets per `lang`. Renderer also switches styling.

| Language | Dialogue | System | Game title | End marker |
|---|---|---|---|---|
| `cn` (default) | `「...」` | `【...】` | `《...》` | `(จบบท)` |
| `jp` | `「...」` | `【...】` | `『...』` | `（終）` |
| `kr` | `「...」` | `【...】` | `《...》` | `(끝)` |
| `en` | `"..."` (curly) | `[...]` | `"..."` (curly) | `(End)` |
| `th` | `"..."` (curly) | `【...】` | `《...》` | `(จบบท)` |

Renderer converts kagikakko to curly quotes for `cn/jp/kr` at render time
(so `「สวัสดี」` displays as `"สวัสดี"`). For `en/th`, source already uses
curly quotes — no conversion needed.

**Adding a new language:** edit `BRACKETS` in `tools/schema.py` (single
source of truth) and mirror it in `reader/server.js` (renderer). Add test
to `tests/test_multilang_schema.py`.

---

## 3. Locked Terms (NEVER change Thai for these)

### Main cast
- `曹星` = `เฉาซิง` (also `阿星` = `อาซิง`)
- `柳慕雪` = `หลิวมู่เสวี่ย` (sister-in-law)
- `伊勒娜` = `อิเลน่า` (elf)
- `大白` = `ต้าป่าย` (mammoth)
- `阿薩姆` = `อาซัม` (companion)
- `安德鲁` = `แอนดรูว์` (druid)
- `蕾妮丝·鹰眼` = `เลนนิส ฮอว์อาย` (archer)
- `茱莉叶特` = `จูลี่เอท` (sister of 妮芙)
- `布洛特·硫磺石` = `บรูนท์·ซัลเฟอร์สโตน` (Charr shaman)

### World
- `香江` = `เซียนเจียง` (NOT ฮ่องกง)
- `《冰封纪元》` = `《มหายุคน้ำแข็ง》` (game title)
- `极地人` = `คนเมืองหนาว`
- `永盛集团` = `กลุ่มหย่งเซิ่ง`
- `三英会` = `สมาคมซานอิง`

### Classes
- `寒霜法師` = `จอมเวทน้ำแข็ง`
- `寒铁机械师` = `ช่างกลเหล็กน้ำแข็ง`
- `雪地猎人` = `นายพรานหิมะ`
- `极地战士` = `นักรบขั้วโลก`
- `极光骑士` = `อัศวินแสงออโรร่า`

### Filler / adj
- `果然` = `อย่างที่คาดไว้`
- `原来如此` = `เข้าใจแล้ว`
- `嚣張` = `ทะนงตัว`
- `致命` = `ถึงตาย`
- `叠加` = `ซ้อนทับ`
- `外挂` = `โปรแกรมช่วยเล่น` (Thai, not literal CN)
- `资料片` = `เนื้อหาเสริม`

**Full glossary:** `novels/global-descent/glossary/glossary.yml` (559 terms)

---

## 4. Style Rules (transmittor principle)

**DO:**
- ✅ TRANSMIT source faithfully — keep author's voice
- ✅ Keep `ดังนั้น`, `ฉายแวว`, `เต็มไปด้วยความ` (author's style)
- ✅ Subject echo (3+ `เฉาซิง` in row) — author does this, preserve it
- ✅ Em dash `—` for missing numbers (e.g., `พลัง: —`)
- ✅ Stat blocks inline: `【เลเวล 10 (1533/10000)】`
- ✅ 【】 keep for system messages, 《》 for game/donor names

**DO NOT:**
- ❌ Don't add/remove plot content (transmittor not editor)
- ❌ Don't use straight `"` in dialogue — use `「」`
- ❌ Don't "improve" the source's flat emotion — keep it
- ❌ Don't auto-fix "anti-patterns" (they're author voice, report not fix)
- ❌ Don't paraphrase dialogue (translate, don't rewrite)

---

## 5. Quick Thai-Cheatsheet for Common Patterns

| Source CN | Thai |
|---|---|
| `曹星大佬` | `พี่เฉาซิง` |
| `天選領主` | `ลอร์ดผู้ถูกเลือกโดยสวรรค์` |
| `天選之人` | `ผู้ถูกเลือก` |
| `新手保護期` | `โหมดคุ้มครองมือใหม่` |
| `冰晶王國` | `อาณาจักรคริสตัลน้ำแข็ง` |
| `狂風雪原` | `ทุ่งพายุหิมะ` |
| `寒冰護盾` | `โล่น้ำแข็ง` |
| `極地人小屋` | `กระท่อมคนเมืองหนาว` |
| `招募` | `รับสมัคร` |
| `好感度` | `ค่าความชอบ` |
| `忠誠度` | `ค่าความจงรักภักดี` |
| `領地` | `ฐานที่มั่น` |
| `祭司` | `นักบวช` / `เจ้าอาวาส` (depends on context) |
| `遊獵者` | `นักล่า` |
| `倖存者` | `ผู้รอดชีวิต` |
| `兩名倖存者` | `ผู้รอดชีวิตสองคน` (no classifier) |
| `村民` | `ชาวบ้าน` |
| `民兵` | `ทหารรักษาการณ์` (local militia) |
| `村長` | `ผู้อำนวยการหมู่บ้าน` |
| `系統提示` | `ข้อความระบบปรากฏ` |
| `本章完` | `(จบบท)` |

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

**Narration (author's style — KEEP):**
```
ในดวงตาเฉาซิงเต็มไปด้วยความ...
บนใบหน้าปรากฏสีหน้าดีใจ
มุมปากเฉาซิงยกขึ้นเป็นเส้นโค้ง
```

---

## 7. Schema Pitfalls (auto-rejected)

- ❌ Title without "ตอนที่ N " prefix
- ❌ Dialogue using straight `"..."`
- ❌ System message missing 【】
- ❌ Missing end marker `(จบบท)`
- ❌ End marker not as last block
- ❌ Narration with CN chars (except in 【】/《》/「」)
- ❌ Empty blocks array

**Use `python tools/save_json.py N` to validate before commit.**

---

## 8. Per-Chapter Workflow

```bash
# 1. Get context
python tools/translate_ch.py 113 --context --search > /tmp/ch113.txt
cat /tmp/ch113.txt

# 2. Read source
python -c "
with open('novels/global-descent/chapters/source/0113.md', encoding='utf-8') as f:
    print(f.read())
"

# 3. Translate (Mika writes JSON)

# 4. Validate
python tools/save_json.py 113

# 5. Commit (pre-commit hook auto-runs)
git add novels/global-descent/chapters/0113.json
git commit -m "translate ch 113"
```

---

## 9. Tools Quick Reference

| Tool | Purpose |
|---|---|
| `python tools/pre_chapter.py N` | Get context (glossary, summary, FTS) for ch N |
| `python tools/translate_ch.py N --context` | Full context + unknown term web search |
| `python tools/migrate_to_json.py N` | Migrate .md to .json (legacy) |
| `python tools/save_json.py N` | Validate + save ch N |
| `python tools/glossary_doctor.py --ch N` | Check ch N for issues |
| `python tools/build_yaml.py` | Rebuild glossary.yml from .md |
| `python tools/load_glossary.py` | Verify glossary loads |
| `python tools/schema.py` | Test schema |
| `python tools/migrate_to_json.py` | Migrate helper |
| `python tools/reformat_malformed.py N` | Fix malformed ch (body in wrong place) |
| `python tools/convert_quotes.py N` | Convert "..." to 「...」 |

---

## 10. Common Errors and Fixes

| Error | Fix |
|---|---|
| `Title must be "ตอนที่ N ..."` | Add space + Thai title |
| `Dialogue must contain 「」` | Use `「」` not straight `"` |
| `System message must contain 【】` | Use `【】` |
| `Narration contains N raw CN chars` | Translate CN to Thai (except in whitelisted zones) |
| `Chapter has no content blocks` | Add at least 1 narration/dialogue/system before end |
| `End marker must be exactly "(จบบท)"` | Use exact text including parens |
| `JSON invalid` | Check for unescaped quotes in text values |

---

**Last updated:** 2026-06-14
