# Style Notes — 全球降臨：帶著嫂嫂末世種田 (global-descent)

> Per-novel translation choices for Mika. Universal craft principles live in
> `PROMPT.md` §4b. This file is the **novel-specific layer**.

## Genre & tone

- **Genre:** System / survival / strategy / light romance. Modern CN web novel.
- **Tone:** Modern, often comedic. System messages + game mechanics mixed with
  character dialogue. Survives the apocalypse with snark.
- **POV:** 3rd person, MC-focused.
- **Dialogue:** Casual, modern, slang is OK. Particles encouraged.
- **Thai style target:** ภาษาพูดที่เป็นธรรมชาติ กระชับ อ่านง่าย ท่วงท่าเร็ว
  บทสนทนาดูเหมือนคนจริง

## Locked term choices

All locked terms live in `glossary/locked.md`. Key highlights:

| Source | Target | Notes |
|--------|--------|-------|
| 曹星 | เฉาซิง | MC (also called 阿星 / อาซิง) |
| 柳慕雪 | หลิวมู่เสวี่ย | sister-in-law |
| 香江 | เซียนเจียง | NOT ฮ่องกง |
| 《冰封纪元》 | 《มหายุคน้ำแข็ง》 | game title |
| 极地人 | คนเมืองหนาว | |
| 天赋 | สกิลติดตัว | game term |
| 领主 | ลอร์ด | loanword, common in Thai games |
| 外挂 | โปรแกรมช่วยเล่น | Thai term, NOT CN retention |
| 资料片 | เนื้อหาเสริม | expansion / data pack |
| 民兵 | ทหารรักษาการณ์ | militia |
| 果然 | อย่างที่คาดไว้ | filler (see TH crutches below) |
| 原来如此 | เข้าใจแล้ว | filler |
| 嚣張 | ทะนงตัว | adj. |
| 致命 | ถึงตาย | adj. |
| 叠加 | ซ้อนทับ | tech term (stack) |

Full list: `glossary/locked.md`. **Never deviate from locked.md.**

## Bracket conventions

| Use | Bracket | Forbidden |
|-----|---------|-----------|
| Dialogue | `「…」` (CJK corner brackets) | `"…"` straight quotes |
| System message | `【…】` | `[…]` |
| Game title | `《…》` | `<…>` |
| Emphasis | `**…**` | `__…__` |

**One exception:** inside dialogue, a character quoting a name may use straight
`"…"` inside the outer `「」`.

## Punctuation & formatting

- Em-dash `—` (U+2014) for missing numbers in stat blocks: `力量: —`
- Single blank line between paragraphs (`\n\n`)
- No trailing whitespace, no tabs, final newline at end of file
- `(จบบท)` as end marker, last block of every chapter
- Source footer: `*Source: ch N*` (no novel title, no author)

## CN→TH pitfalls

(Universal craft principles in PROMPT.md §4b. These are the CN→TH specifics.)

### Word order (P1)

**Appositive compounds** — CN does `[modifier][noun]` (e.g., `领民曹一`).
TH calque "ชาวอาณานิคมเฉาอี" reads as a compound noun. **Fix:** flip to
TH order: "เฉาอี ชาวอาณานิคม" or "เฉาอีซึ่งเป็นชาวอาณานิคม".

**Time/location** — CN puts both at start. TH: time and location typically come
AFTER the verb.

**Subject-verb chains** — Source often does "X nodded. X smiled. X spoke."
→ TH subject echo. **The transmittor principle preserves this.** (See §0.)
However, when Mika generates NEW text, vary the subject per §4b P5.

### Show don't tell (P2)

Source often tells emotions directly ("他很生气"). Flat translation =
"เขาโกรธมาก" — this is an emotion lump. **Transmit per §0.** For Mika-generated
text, show through action per §4b P2.

### TH crutches (CN→TH specific)

These are banned **in Mika-generated text only**. When they appear in source,
transmit verbatim (author's voice).

| Source CN | Mika slop | Better TH |
|-----------|-----------|-----------|
| 果然 | "อย่างที่คาดไว้" (mechanical) | "ดั่งที่หวัง" / omit entirely |
| 值得注意的是 | "ที่น่าสังเกตคือ…" | state the thing directly |
| 此外 / 而且 | "นอกจากนี้…" | "และ" / "อีกทั้ง" / omit |
| 因此 | "ดังนั้น…" | "เลย…" / restructure |
| 然而 / 不过 | "อย่างไรก็ตาม…" | "แต่" / restructure |
| 为了 | "เพื่อที่จะ…" (mechanical) | "เพื่อ…" (drop "ที่จะ") |
| 与此同时 | "ในขณะเดียวกัน" | "ตอนนั้นเอง" / restructure |

### Mika-specific crutches (observed in translations)

- Subject echo: MC name x 3 in a row (source = transmit; Mika text = vary)
- "ดีใจในใจ" / "เสียใจในใจ" (source = transmit)
- "เต็มไปด้วยความ[X]" emotion lumps (source = transmit)
- "ทั้งนี้…" / "อย่างไรก็ตาม…" as sentence starters (formal tic — rest in peace)

## Thai naturalness reference

Deep guide: `docs/THAI_NATURALNESS.md` — read once, apply consistently.

Key points:
- Cut filter words: `รู้สึกว่า`, `คิดว่า`, `เชื่อว่า` (in Mika text; transmit in source)
- Cut adverb `-ๆ` doubling: `เดินช้าๆ` → `เดินช้าลง`
- Drop unnecessary `ของ`, `เป็น`, `คือ`, `แล้ว`
- Body betrays voice: anchor dialogue in small involuntary physical actions
- Rotate paragraph entry points (dialogue-first, mid-action, sound/sensation)

## Transmittor scope — what we do NOT flag

> The old title "Banned patterns" was misleading. This section is a scope
> statement: what the doctor does NOT auto-fix in body text.

**Translator = transmittor.** We preserve:
- Author's flat emotion phrasing ("เต็มไปด้วยความ…", "ฉายแวว")
- Author's subject echo (3+ consecutive MC name as subject)
- Author's connector choices ("ดังนั้น", "อย่างไรก็ตาม")
- Author's sentence-level "translated-feel"

**The doctor only flags:**
- **ERROR (blocks save):** CN chars in body / locked term violation / missing paragraphs
- **WARNING (logged):** length ratio extremes, structural issues
- **INFO (logged):** new CN terms not yet in glossary

## Adult / explicit content

**Rule: Translate explicitly, soften vocabulary, never skip.**

- KEEP all scene beats: opening, motivations, transitions, rewards, cliffhangers
- Translate intimate scenes with euphemistic Thai: แนบ/สัมผัส/จูบ
- **Never skip or summarize** a scene because it's explicit — that's a
  completeness violation (§1), not a style choice
- When in doubt: แปลแบบเบา + ellipsis to imply rather than skip entirely

## File format spec

Reference: `format_spec.md` in this folder. The format spec is **single source
of truth** for chapter file structure. All chapters must use v2 format.

## Version

- v1 (pre-2026-06-14): straight `"` dialogue, no end marker, inconsistent
- v2 (2026-06-14+): `「」`, `(จบบท)`, `*Source: ch N*`, blank line rules

All new chapters MUST use v2.
