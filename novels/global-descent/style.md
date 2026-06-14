# Style Notes — 全球降臨：帶著嫂嫂末世種田 (NovelClaw: global-descent)

> Per-novel translation choices for Mika. Universal craft principles live
> in `PROMPT.md` §4b. This file is the **CN→TH specific layer** that
> references those principles with concrete examples Mika encounters
> repeatedly in this novel.

## Genre & tone

- **Genre:** System / survival / strategy / light romance. Modern Chinese
  web novel, web serial pacing.
- **Tone:** Modern, often comedic. System messages + game mechanics mixed
  with character dialogue. Survives the apocalypse with snark.
- **Characters:** Sarcastic, witty male lead (3rd person POV — เฉาซิง).
  Strong female lead (หลิวมู่เสวี่ย, sister-in-law). Many named NPCs.
- **Action scenes:** Short, punchy, lots of system notifications.
- **Dialogue:** Casual, modern, slang is OK. Particles encouraged.
- **Thai style target:** "ภาษาพูดที่เป็นธรรมชาติ กระชับ อ่านง่าย ท่วงท่าเร็ว
  บทสนทนาดูเหมือนคนจริง"

## Specific term choices (locked)

- **Hong Kong = เซียนเจียง** (preserve CN flavor via transliteration; เซียนเจียง hits emotional register better than ฮ่องกง, which reads as a transliteration of an English name)
- **曹星 = เฉาซิง** (preserve CN name, no romanization change)
- **柳慕雪 = หลิวมู่เสวี่ย** (preserve CN, sister-in-law)
- **伊勒娜 = อิเลน่า** (elf character)
- **大白 = ต้าป่าย** (mammoth pet, name 达白 = big white = ต้าป่าย)
- **《冰封纪元》 = 《มหายุคน้ำแข็ง》** (impactful Thai, not literal "ยุคเยือกแข็ง")
- **极地人 = คนเมืองหนาว** (literal + Thai-friendly)
- **天赋 = สกิลติดตัว** (game term, with original context)
- **领主 = ลอร์ด** (loanword, common in Thai games)
- **外挂 = โปรแกรมช่วยเล่น** (Thai term, NOT literal CN retention)
- **资料片 = เนื้อหาเสริม** (Thai term)
- **HP / 生命值 = HP** (game convention, not "พลังชีวิต" — keep game-feel)
- **System messages:** keep 【】 markers, translate content
- **Game titles:** keep 《》 markers, translate with impact
- **Numbers in 【】 like 【1级 0/100】:** translate to Thai format (เลเวล 1 (0/100))

## CN→TH pitfalls (apply 4b craft layer)

### Word order (P1)

**Appositive compounds** — CN frequently does `[modifier][noun]`
(e.g., `领民曹一` = `vassal Cao-Yi`). Naive TH calque: "ชาวอาณานิคมเฉาอี"
which reads as a compound noun. **Fix:** flip to TH order with comma
or relative clause: "เฉาอี ชาวอาณานิคม" or "เฉาอีซึ่งเป็นชาวอาณานิคม".

**Time/location** — CN puts both at start. TH: time and location
typically come AFTER the verb. Don't preserve CN order.

**Subject-verb chains** — CN often does "X nodded. X smiled. X spoke."
Naive: "เฉาซิงพยักหน้า เฉาซิงยิ้ม เฉาซิงพูด" (subject echo, see P5).
**Note:** subject echo is the AUTHOR's style. We preserve it as-is
(translator = transmittor, not editor).

### Show don't tell (P2)

**Note for translator:** we report "ฉายแวว", "เต็มไปด้วยความ", "สีหน้าเปี่ยม"
in style.md for AI reference, but **the translator does NOT change them**
when they appear in source. We preserve author's flat-emotion style.
These are the AUTHOR's voice — we transmit, not edit.

**Only exception:** when the AI translator (Mika) GENERATES new flat
emotion not in the source — that IS an error to flag. But when source
has "ดวงตาเต็มไปด้วยความ..." we translate as-is.

### Particles & register (P2 + P4) — gap to fill

**Note:** the article you see in ch 1-100 about "missing particles" is
an analysis of historical ch, not a rule for new ch. New ch should
have natural particles from the start (the locked cast dossier has
particle guidance per character).

## Punctuation & formatting

- **【】 system messages** — keep markers, translate content
- **《》 game titles + donor names** — keep markers, translate with impact
- **"—" (em-dash) for missing numbers** — when source has no number, use "—" placeholder (not "0" or "N/A")
- **Stat blocks** like `【等级：10级1533/10000】` — translate inline as
  `【เลเวล 10 (1533/10000)】`
- **Source footer:** `*Source: ch N*` (CN title optional, in CN)

## Banned patterns (Mika MUST avoid)

**Translator transmittor principle:** we preserve the author's voice.
We do NOT remove the author's "ฉายแวว", "ดังนั้น", "เต็มไปด้วย",
"3+ consecutive เฉาซิง" — these are the author's style, transmitted
verbatim in Thai register.

The doctor only flags:
- **Forbidden** (ERROR — blocks save): hard rule violations like
  "ฮ่องกง" (locked term) or CN chars in body (excluding whitelisted
  zones 【】, 《》, *Source:* footer, หมายเหตุ meta)
- **Completeness** (ERROR — blocks save): missing source beats, missing
  paragraphs, missing characters
- **Structural** (WARNING): title/body mismatch, length ratio extreme
  (only as signal, not auto-fix)
- **Info** (logged): new CN terms not yet in glossary

We do NOT flag "translated-feel" anti-patterns in body text — those are
the author's style, transmitted as-is.

## Thai Naturalness (CN→TH-specific)

Universal writing principles + TH-specific application live in
[`docs/THAI_NATURALNESS.md`](../../../docs/THAI_NATURALNESS.md).
Read once, apply consistently.

**Top 5 things that make TH read as "CN-translation" (avoid these):**

1. **Filter words** — `รู้สึกว่า` / `คิดว่า` / `เชื่อว่า` (drop if removable)
2. **Adverb -ๆ** — `ช้าๆ` / `เบาๆ` / `เงียบๆ` (use verb choice instead)
3. **的 → ของ** — drop "ของ" when possessive is clear
4. **是 → เป็น/คือ** — drop when sentence works without it
5. **了 → แล้ว** — drop when context already marks completion

See `THAI_NATURALNESS.md` §5 for banned phrases, §6 for CN→TH anti-patterns,
§3 for sentence rhythm. Goal: respect the source's voice, deliver TH that
reads Thai to a Thai reader.

## Adult / explicit content policy

**Rule: Translate explicitly, soften vocabulary, preserve plot beats.**

- ✅ KEEP: scene opening, character motivations, plot transitions, system rewards, cliffhanger outcomes
- ✅ KEEP: 抱/撫/親暱/脫衣 wording — translate to TH แนบ/สัมผัส/จูบ (euphemistic but present)
- ❌ DO NOT: 跳過/สรุปย่อ scene เพราะ explicit — title ก็อ้าง scene นั้น
- ❌ DO NOT: invent "Mika skipped due to policy" notes if no policy exists
- Reference case: ch 97 source has 夏燕妮半夜 encounter (~400 chars) but translation was 32% of source — that's a §1 completeness violation, not a style choice
- When in doubt: แปลแบบเบา + ใส่ ellipsis เพื่อ imply rather than 跳過ทั้งหมด


## Auto-detected slop candidates (from slop_detector.py)

- "อย่างไรก็ตาม" (Tier 3 — 92x)
- "ดังนั้น" (Tier 3 — 44x)
- "เต็มไปด้วยความ" (Tier 3 — 28x)
- "รวมถึง" (Tier 3 — 22x)
- "แม้ว่า" (Tier 3 — 21x)
- "นอกจากนี้" (Tier 3 — 13x)
- "ถึงแม้ว่า" (Tier 3 — 11x)
- "ชาวอาณานิคม" (Tier 3 — 11x)
- "ดีใจในใจ" (Tier 3 — 8x)
- "โดยเฉพาะ" (Tier 3 — 7x)

## Auto-detected slop candidates (slop_detector v2)

- "อย่างไรก็ตาม" (Tier 3 — 90x)
- "ดังนั้น" (Tier 3 — 42x)
- "เต็มไปด้วยความ" (Tier 3 — 27x)
- "รวมถึง" (Tier 3 — 23x)
- "รู้สึกว่า" (Tier 3 — 23x)
- "แม้ว่า" (Tier 3 — 19x)
- "นอกจากนี้" (Tier 3 — 13x)
- "รู้สึกถึง" (Tier 3 — 12x)
- "ชาวอาณานิคม" (Tier 3 — 11x)
- "ถึงแม้ว่า" (Tier 3 — 10x)
- Function word: `ที่` (6x — check overuse)
- Function word: `อัน` (3x — check overuse)
- Function word: `อย่าง` (2x — check overuse)
- Function word: `ครับ` (1x — check overuse)
- Function word: `เห็นได้ว่า` (1x — check overuse)
- Descriptor echo: 'งดงาม' → 'สง่า' within 200 chars (0001.md)
- 3-stage falling rhythm at sentence 0: 40>21>1 (0001.md)
- Descriptor echo: 'ชัด' → 'เปล่งประกาย' within 200 chars (0071.md)
- 3-stage falling rhythm at sentence 14: 150>79>1 (0071.md)
- Descriptor echo: 'เย็น' → 'สว่าง' within 200 chars (0072.md)