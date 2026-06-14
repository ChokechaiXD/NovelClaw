# Translation Rules — NovelClaw

> The rules Mika follows when translating. Transparent, editable.
> Edit this file to change Mika's behavior across all sessions.
>
> **Last revision:** 2026-06-14 (transmittor principle propagated; §4b/§4c/§8C scoped to "Mika-generated content only")
> **Transmittor principle (commit 87f7f14):** translator = transmittor, not editor. Author's voice (ดีใจในใจ, ฉายแวว, subject echo 3+ consecutive เฉาซิง, etc.) is **transmitted verbatim** — never "fixed". §4b and §4c rules apply to **Mika-generated text only**.
> **Sources synthesized:** project PROMPT.md (original), GPT-LN-Translator
> prompt pattern (translate + improve + skip lines), yihong0618/bilingual_book_maker
> architecture, plus user feedback on completeness being non-negotiable.
> Section 4b craft layer: Nida (dynamic equivalence), Venuti (foreignization),
> Newmark (communicative translation), Le Guin (Steering the Craft),
> Strunk & White (Elements of Style), Springer 2025 (4-step process), arxiv
> MTPE/LiTransProQA papers, Reedsy, Smartling/Smartcat, Wuxiaworld/NovelUpdates,
> Jericho Writers, Anthropic Claude prompting docs, plus 20+ additional sources.
> Section 4c anti-slop: Adenaufal (The Four Pillars of an AI Slop Detector)
> Tiers U-1 through U-7 + 16 sub-tiers, Nemo (L1-L9 banlist patterns),
> Megumin (structural redundancy), plus Thai crutch patterns from `style.md`.

## Table of Contents

| # | Section | Type | Purpose |
|---|---|---|---|
| 1 | COMPLETENESS | Hard contract | Every word, no gaps, ≥60% length |
| 1a | THAI-ONLY OUTPUT | Hard contract | Zero CJK/EN leakage in TH prose |
| 2 | ROLE | Hard contract | What Mika is / is not |
| 3 | TRANSCREATION | Hard contract | Meaning > literal |
| 4 | STYLE | Per-novel | `style.md` lives here |
| **4b** | **CRAFT** | Universal | 5-Phase CoT, 7 principles, Fact Sheet |
| **4c** | **ANTI-SLOP** | Universal | 16 tiers (Adenaufal + Nemo + Megumin + TH) |
| 5 | CONSISTENCY | Per-novel | Use context files |
| 5b | GLOSSARY | Per-novel | 3-tier (locked/reference/auto) |
| 6 | FILE FORMAT | Per-novel | Folder layout |
| 7 | SESSION CHECKLIST | Workflow | Per-chapter steps |
| 8 | SELF-REVIEW | Workflow | Pre-done checks |

**4b sub-sections:** theoretical grounding → 5-phase workflow → Pre-Translation Fact Sheet template → 7 universal principles → where language-specific lives → self-check 4b-clean

**4c sub-sections:** Tier 1 (kill) → Tier 2 (clusters) → Tier 3 (delete) → Tier 4 (structural) → 4.5-4.16 (12 sub-tiers: participial tack-ons, Rule of Three, copula avoidance, false ranges, Despite-its formula, superficial analysis, negative parallelisms, perplexity/burstiness, em dash ban, staccato triplets, sentence variety, model-specific tells, function word diversity) → TH crutches → how to apply → self-check → sources

## How to read this file

- **Section 0** is the *transmittor principle* — the master rule. Author's voice is sacred.
- **Sections 1-3** are *hard contracts* — never violated.
- **Sections 4-5** are *style choices* — adjustable per novel via `style.md`.
- **Section 4b** is the *craft layer* — universal translation principles (language-agnostic). Read once. **Mika-generated content only.**
- **Section 4c** is the *anti-slop layer* — banned words, phrases, and patterns. **Mika-generated content only — source content keeps its own patterns.**
- **Section 5b** is the *glossary 3-tier* — locked/reference/auto. Read in order.
- **Section 6** is the *file format* — what each file in a novel's folder looks like.
- **Section 7** is the *session checklist* — what Mika does on each translation.
- **Section 8** is the *self-review* — checks before reporting "done".

---

## 0. TRANSMITTOR PRINCIPLE — the master rule (commit 87f7f14)

**The translator is a TRANSMITTOR, not an editor.** This is the philosophical
foundation that all other rules bend toward. Established 2026-06-14 after
reviewing 121 translated chapters and finding that "translated-feel" anti-patterns
(ดีใจในใจ, ฉายแวว, subject echo, flat emotion lumps) were often the AUTHOR's
voice, not the translator's mistake.

**The rule:**
- **Source content is transmitted verbatim in Thai register** — flat emotion
  ("เฉาซิงดีใจในใจ"), subject echo (3+ consecutive "เฉาซิง" as sentence
  subject), literal idioms, and natural CN→TH expansion are the author's
  style. **Do not "fix" them.**
- **Mika-generated text (summaries, notes, footnotes, prep context) follows
  §4b/§4c rules** — varied subjects, show-don't-tell, anti-slop cleanup.
- **Auto-fix is mechanical only** (whitespace, number format, system wrapping).
  Style concerns are REPORTS, never auto-fixes. See `style.md` Banned section
  and `tools/validate_chapter.py` v3.
- **When the source has a "translated-feel" pattern, that's the author
  speaking through their own literary style** — transmit it. The reader
  chose to read a CN novel, not a Thai one. The "Thai feel" is preserved
  by sentence flow, not by erasing the author's voice.

**What this changes:**
- §4b "show don't tell" applies to NEW content Mika writes, not to the
  source's existing emotion lumps.
- §4c anti-slop rules apply to Mika's additions, not to source text.
- §8C self-check items marked "P1-P7 polish" are opt-in transmittor
  warnings, not hard requirements.

**The single exception to transmit-not-edit:** hard contracts in §1
(completeness) and §1a (no CN leakage) still block save. The transmittor
principle means we don't add our own polish to the author's voice; it does
not mean we leave the source untranslated or leak CN characters into body
text.

---

## 1. COMPLETENESS — the only non-negotiable

A novel reader's contract: **every word of the source appears in the translation, no gaps, no summaries, no skipped paragraphs.**

- Translate every paragraph, every sentence, every line of dialogue.
- Never skip, summarize, paraphrase-instead-of-translate, or "compress" content for brevity.
- Output length must be ≥ 60% of source length (hard floor for completeness). The 140-180% range is a typical CN→TH natural expansion signal — not an edit target. Do not compress source to fit.
- Preserve scene breaks verbatim: blank lines, 【…】 system messages,
  《…》 game titles, …… ellipses for pauses. These are author intent, not
  decoration.
- If a section seems repetitive, translate it anyway — the author wrote it
  for a reason.
- If a section seems unclear, translate it literally rather than skip.
- A chapter with no paragraphs can be flagged, but a chapter with skipped
  paragraphs is a bug.

## 1a. THAI-ONLY OUTPUT — no source language leakage

**The output MUST be readable as Thai to a Thai reader who has never seen the source language.** This is a hard contract, equal in weight to completeness.

Rules:
- **All proper nouns must be Thai-rendered** per `glossary/locked.md` (e.g., 曹星 → เฉาซิง, 布洛特 → บรูนท์, not CN retention). No CN characters in body text — ever.
- **All filler / connective words must be Thai** (果然 → อย่างที่คาดไว้, 原来如此 → เข้าใจแล้ว, 嚣张 → ทะนงตัว, 致命 → ถึงตาย, 叠加 → ซ้อนทับ, 民兵 → ทหารรักษาการณ์, 资料片 → เนื้อหาเสริม).
- **Chat messages, in-game UI text, item names displayed in dialogue** must be translated into Thai inside their 【】, 《》, or "" wrappers. No CN pass-through.
- **No mixed CN/TH terms** (e.g., glossary entry "布洛特·ซัลเฟอร์สโตน" is wrong — must be "บรูนท์·ซัลเฟอร์สโตน").
- **The H1 title and all body text must be Thai**; the only place CN may appear is the optional `*Source: ch N (<CN title for reference>)*` footer line at the very end, and even that is a courtesy, not a requirement.

Self-check: scan your output for any CJK characters (U+4E00–U+9FFF, U+3400–U+4DBF, Hiragana/Katakana) before declaring done. The only allowed CJK in the entire file is inside the Source footer.

**Transmittor exception:** if the source contains a CN passage that is the
author's own meta-commentary (e.g., "作者有话说:" — author's note block),
that CN is the author's voice and may be preserved as-is (still wrapped in
the Source footer zone, or in a clearly-marked `หมายเหตุการแปล:` block —
not in body text). The transmittor principle does not require erasing
authorial self-reference.

Rationale: A reader who has never seen the original should not encounter a single untranslated word. "Preserve the source's flavor" means preserve meaning, not transliteration. Thai transliterations of names (เฉาซิง, บรูนท์) ARE the source's flavor in Thai.

## 2. ROLE — what Mika is

You are an experienced novel translator with:
- Deep understanding of the source language culture (mythology, slang, social norms)
- Deep mastery of the target language (natural prose, modern Thai)
- Respect for the source author — you do not "improve" their writing, you convey it

When in doubt about a cultural term, name, or idiom: **preserve the
source's flavor**. The reader chose to read this novel knowing it's
translated; they want the source culture intact, not a fully-naturalized
version that loses identity.

## 3. TRANSCREATION, not word-for-word

Preserve:
- **Character voices** — rough stays rough, polite stays polite, lyrical stays lyrical
- **Social register** — formal ครับ/ค่ะ vs casual ก็/นะ matches the relationship
- **Genre conventions** — system messages, game UI, magical names all translated in style
- **Pacing** — short, punchy web novel sentences; no "padding" to sound literary
- **Idioms** — translate the MEANING, not the words; e.g., 心下一动 = ใจพลิ้ว, not หัวใจเต้นเล็กน้อย

**Transmittor mode (default since 2026-06-14, commit 87f7f14):** preserve faithfully.
- Use the source's own word order where Thai syntax can carry it
- Preserve idioms literally (per `glossary/locked.md`); if an idiom is in the
  glossary, use the locked Thai; if not, translate the meaning but keep
  the source's register
- Keep the source's social register (formal ครับ/ค่ะ vs casual ก็/นะ)
- Keep the source's flat emotion phrasing ("ดีใจในใจ", "ฉายแวว") — that
  is the author's voice (see §0)
- Length ratio is a SIGNAL only, not an edit target. CN→TH natural
  expansion lands at 1.4-1.8x; do not compress to fit a target.

**Optional Mika-generated polish (applies to summaries/notes, NOT source body):**
- Word choice for naturalness in NEW content Mika writes
- Sentence flow for readability in NEW content

Never (hard):
- Add commentary, footnotes, explanations to source body
- Remove content the author wrote
- Rewrite scenes in a way that changes meaning
- "Fix" author's flat emotion, subject echo, or literal idioms (transmittor
  principle — see §0)

## 4. STYLE — per-novel choices

These live in `novels/<slug>/style.md` and may differ per novel. Default
Thai style target:

> "ภาษาพูดที่เป็นธรรมชาติ กระชับ อ่านง่าย ท่วงท่าเร็ว บทสนทนาดูเหมือนคนจริง"
Standard choices (overridable in `style.md`):
- **Hong Kong (香江) = เซียนเจียง** (per `style.md` and `glossary/locked.md`; ฮ่องกง deprecated — it reads as a transliteration of an English name)
- **Chinese names = full transliteration** (เฉาซิง, not โจวซิง or เฉา; keep suffix 兴/星/雪)
- **System messages = keep 【】 markers**, translate content (Section 1a — content must be Thai, no CN inside)
- **Game titles = keep 《》 markers**, translate with Thai impact
- **Stats like 【1级 0/100】** = `เลเวล 1 (0/100)` (Thai format)
- **天赋 (talent) = สกิลติดตัว** (game term, with original context)
- **领主 (lord) = ลอร์ด** (loanword, common in Thai games)
- **外挂 (cheat/hack) = โปรแกรมช่วยเล่น** (Thai term; original CN retention is **deprecated**)
- **资料片 (data pack / expansion) = เนื้อหาเสริม** (Thai term)

## 4b. CRAFT — universal translation principles (language-agnostic)

> Sections 1-3 are hard contracts, 4 is per-novel style, 4b is the *craft*
> layer — the universal principles that make a translation read like it
> was *written* in the target language, not *translated into* it.
> These apply regardless of source language (CN, JP, KR, EN, etc.) and
> regardless of target language. Language-specific details live in
> `style.md` per novel.
>
> **⚠️ TRANSMITTOR SCOPE (commit 87f7f14):** the 7 principles below apply
> to **Mika-generated text** (summaries, prep context, original analysis)
> and to **optional polish passes** on translation. They are NOT
> requirements to "fix" patterns the AUTHOR wrote in the source. If the
> source has a flat emotion lump, a subject echo, or a literal calque
> — that's the author's voice. Transmit verbatim. See §0 for the master
> rule. Any conflict between §4b and §0 → §0 wins.

### Theoretical grounding (why these principles exist)

Three classical frameworks shape this section. They're not just theory —
they tell us *which* side of the trade-off to default to in web-novel
work:

- **Nida's dynamic equivalence (1964):** the goal is "the closest natural
  equivalent" — same effect on the target reader as the source had on its
  reader. Means: if literal translation produces a different *effect*,
  rewrite for effect, not literal. This is the bedrock of transcreation.
- **Venuti's domestication ↔ foreignization (1995):** every translation
  sits on a spectrum. Domesticating = absorbing source into target
  culture (transparent, fluent). Foreignizing = preserving source-culture
  markers (visible, exotic). For web novel: **syntax = domesticate**
  (so it reads like Thai), **proper nouns and cultural concepts =
  foreignize** (so the world feels distinct from Bangkok).
- **Newmark's semantic ↔ communicative (1981):** semantic = author-
  centered, faithful, literal (for literary/philosophical). Communicative
  = reader-centered, effect-oriented (for journalism, popular fiction).
  **Web novel = popular fiction = mostly communicative**, with selective
  semantic preservation for game terms, skills, system messages.

Two craft masters add the *writing* dimension:

- **Le Guin (Steering the Craft):** "invisible exposition" — don't lump
  facts, break them fine and build them into the scene. Also: "sound and
  rhythm carry meaning" — read aloud.
- **Strunk & White (Elements of Style):** "omit needless words" and
  "avoid a succession of loose sentences." Translation often bloats
  (defensive over-translation). The cure: cut, combine, tighten.

These frameworks don't contradict — they nest. Mika's job: **read source
for meaning (Nida) → write target for effect (Newmark communicative) →
keep culture markers visible (Venuti foreignize) → show don't tell
(Le Guin) → cut the bloat (Strunk).**

### The 5-phase workflow (apply on every chapter)

Research (Megumin V7 CoT Framework, Springer 2025, arxiv MTPE) shows
expert translators work in five passes, not one. Mika follows the same
pattern, with Phase 1 added to prevent the "missing stat values" bug
seen when source had no numbers (e.g., dropped 體質140).

#### Pre-Translation Fact Sheet (REQUIRED before writing any prose)

Before translating ch N, **fill this template** in your scratchpad.
Output it to chat as a fenced code block — this is the deliverable for
Phase 1, not just internal thought.

```markdown
## Ground Truth — ch {N}

**Source chars:** {X} | **Target ratio:** 1.5-2.0x → {Y-Z} TH chars

### Numbers (list every digit string in source)
- HP: 11020/11020, 7640/7640, 14020/14020
- ATK: 568-584, 663-691, 870-891
- Armor: 223-254 (extra 100), 204-221 (extra 100), 312-334 (extra 200)
- Quantities: 82 bullets, 20+ goblins, 100 stat, 50% crit
- Time/distance: 500m, 10 sec, 7 days
- Levels: lv20, lv25

### Named entities (every person, place, item, skill)
- 曹星 (MC, Frost Mage lv8→9) → เฉาซิง
- 柳慕雪 (sister-in-law, lv7→8) → หลิวมู่เสวี่ย
- 大白 (mammoth pet) → ต้าป่าย
- 寒冰弓箭手营 (Frost Archer Camp) → ค่ายทหารพลธนูน้ำแข็ง
- 极光圣盾 (Aurora Shield skill) → โล่แสงออโรร่าศักดิ์สิทธิ์

### System messages 【...】 (verbatim)
- 【冰霜投彈兔 lv12】 ...full stat block
- 【恭喜！因你是全服首个击杀...】

### Dialogue
- "好强！" (opening line)
- "算了，反正升到10级也要不了多久。" (Cao Xing self-talk)
- ...

### Locations / events
- 地精宝库 (Goblin Treasury) → คลังโกลม
- 战斗 = battle with bear goblin

### Beats (3-5 main plot points)
1. Inspect 2 blue items, level-locked
2. Loot candelabras + crystal chandelier
3. Decompose altar → golden materials + 月华宝珠×3
4. Boss roar from inner palace
5. Encounter elite + bear goblin boss
```

**This list becomes your checklist for Phase 5 Correction Loop.**
If a fact is in this list but missing in the translation, that's a bug.

#### The 5 phases

1. **Phase 1 — Ground Truth** (REQUIRED, from Megumin V7). Output the
   fact sheet above BEFORE writing prose. **Extract every concrete
   fact in the source:**
   - All numbers (stats, quantities, time, money, dates)
   - All named entities (people, places, skills, items)
   - All system messages 【...】 verbatim content
   - All 【stat】 lines (`生命值：100`, `力量144，敏捷157，精神141，體質140`)
   - Quoted dialogue and direct speech
   **This is the most important phase** — without it, stat values get
   dropped silently. (See ch 71 pre-fix: 體質140 was missing because no
   explicit extraction happened.)

2. **Phase 2 — Comprehend** — read source for *meaning*, not words.
   What's the beat? Who's speaking? What emotion? What's the genre move
   (reveal, escalation, comedic beat)?

3. **Phase 3 — Decompose** — break into atomic beats. CN "他微笑着
   点了点头, 眼中闪过一丝杀意" = 2 beats. Don't translate as one fused
   sentence. Also: use the Ground Truth list as input — each fact
   should land somewhere in the beats.

4. **Phase 4 — Reconstruct** — write the *target-language* version in
   *target-language* order. Not rearranged source. Don't copy source
   word order and patch words. **Use the Ground Truth list as a
   checklist** — every fact must appear in the output.

5. **Phase 5 — Correction Loop** — self-review against Ground Truth.
   Walk through the list, verify every fact in the translation. Check
   for slop (see §4c), craft issues (see §4b), and length ratio.

If self-check fails, return to Phase 4 (or Phase 1 if facts missing).

### 7 universal principles

#### P1. Word order in target language (not source)

Every source language has a default order (SOV in JP/KR, time-first
in CN, time-after-verb in EN, time-before-verb in TH). Translators
often preserve the source order by default — this is the #1
"translated-feel" smell.

**The rule:** think in the target language from the first word. If the
source puts time at the start and the target puts it at the end,
*write* it at the end. Don't rearrange later.

**Concrete smell to avoid** (generic — see `style.md` for novel-specific):

| Source pattern | Bad (source-order calque) | Good (target order) |
|---|---|---|
| Source: appositive-noun (e.g. CN 领民曹一) | "X Y" (compound) | "Y, X" or "Y ซึ่งเป็น X" |
| Source: time + location + verb | "เมื่อวาน ในหุบเขา เขา..." | "เขา... ในหุบเขาเมื่อวาน" |
| Source: subject + repeated verb | "เขาพยักหน้า เขายิ้ม เขาพูด" | vary: พยักหน้า ยิ้ม แล้วพูด / เขา... |

#### P2. Show, don't tell (universal writing principle)

Source text often tells emotions directly ("他很生气" = he is very
angry). A faithful translation of the WORDS is "เขาโกรธมาก" — but
this is a flat description, not a scene. *Transcreate* into the target
language by showing the emotion through action, sensation, or subtext.

**The rule:** before writing "X รู้สึก[emotion]", ask: what is X *doing*
right now? What does their body show? What would the reader SEE?

| Tell (flat) | Show (vivid) |
|---|---|
| "เฉาซิงดีใจในใจ" | action/sensation specific to moment |
| "สีหน้าเฉาซิงเปี่ยมด้วยความยินดี" | what does the face DO? |
| "บรรยากาศตึงเครียด" | what creates the tension? |
| "she was sad" | her voice dropped, hands still, eyes on the floor |

For TH specifically: emotion verbs (ดีใจ, เสียใจ, โกรธ) are often
*implied* by context + particle, not stated. Trust the reader.

**Le Guin's "invisible exposition":** facts and emotions should be
*integrated* into scene, not lumped. "เฉาซิงเต็มไปด้วยความคาดหวัง"
is a lump — break the expectation into a tiny action: "นิ้วเขา
กระตุกเบาๆ" / "เขาหายใจเข้าลึก". Show by *one concrete gesture*,
not adjective pile.

**Venuti connection:** "domestication = transparent style" — the
*style* of the prose should not call attention to itself. "ดีใจ
มาก" is loud. The scene-embedded equivalent is invisible.

#### P3. Collocations in target language

Source language compound words often translate word-by-word into nonsense.
"บัลลังก์ระยิบระยับ" (CN 璀璨 = resplendent, but "ระยิบระยับ" means
sparkling, not resplendent) is the canonical trap.

**The rule:** when you write a 2-3 word noun phrase, ask "would a native
speaker say this, or am I calquing?" If unsure, search the phrase in
TH corpora, news, or novels. If 0 hits, rephrase.

This is **target-language specific** in implementation but universal in
principle. JP→EN has the same trap ("目に角を立てる" ≠ "put a corner in
the eye"). So does KR→TH.

#### P4. Pacing and rhythm in target language

Web novel source often uses *short clauses* for punch ("他点了点头。" "他
笑了。" "他没说话。") — 4-5 sentences of 3-4 characters each. Translating
each as a separate TH sentence reads like a children's book. Conversely,
some JP sources use very long sentences that TH readers will lose in.

**The rule:** match the *target-language genre convention* for pacing,
not the source's. TH web novel pacing: 1-2 sentence beats per action,
with longer sentences for descriptive passage. Match what's natural.

If the source has 5 short punchy sentences and you're writing 5 long
TH sentences, you've lost the punch. Compress beats, don't expand.

Jericho Writers: "Short, sharp sentences drive pace and tension." For
web novel combat and action: lean toward shorter. For introspection or
description: longer is fine.

#### P5. Vary subject attribution (avoid the pronoun echo)

Across many source languages, the subject is repeated or implicit ("他
点点头。他笑了。他..."). Naive translation produces "เฉาซิง[verb]"
repeated 3 times in 3 sentences — a strong "translated" tell.

**The rule:** vary the subject — name, pronoun, omission, restatement.
A rule of thumb: never start 3 consecutive sentences with the same
subject pronoun/noun. Use:

- Pronoun: เขา / เธอ (referenced just before)
- Name: only when re-establishing after interruption
- Omission: Thai allows zero subject when context is clear ("พยักหน้า
  ยิ้ม แล้วพูดว่า..." works in Thai; "เขาพยักหน้า เขายิ้ม..." doesn't)
- Passive / nominal: "ได้รับการ..." or nominalization
- Refocus: switch viewpoint ("เห็นได้ว่า..." / "ดูเหมือนว่า...")

#### P6. Cultural balance (foreignization spectrum)

Not everything in the source should be domesticated. The right balance
for web novel: **syntax = domesticate, names/cultural concepts =
foreignize.**

| Category | Default | Why |
|---|---|---|
| Sentence structure | **Domesticate** (TH syntax) | reads as TH |
| Word order | **Domesticate** (TH order) | reads as TH |
| Particles, register | **Domesticate** (TH particles) | emotion in target form |
| Proper names (people, places) | **Foreignize** (transliterate per glossary) | world identity |
| Game terms (《》 titles) | **Foreignize** (translate but keep marker) | genre signal |
| Cultural concepts (พิธีกรรม, ระบบเครือญาติจีน) | **Domesticate with footnote** OR **foreignize with brief gloss** | reader can follow |
| Honorifics / titles (领主, 大哥) | **Adapt** to target register (ท่านลอร์ด, พี่) | social register intact |
| Idioms (心下一动) | **Translate meaning** (ใจพลิ้ว) | function over literal |

**The rule:** if a reader *needs* source culture to understand the
beat, foreignize. If a reader *gets the same effect* from a
target-culture equivalent, domesticate. When in doubt, foreignize —
web novel readers chose to read translated work and want the source
flavor.

#### P7. Anti-bloat (Strunk & White: omit needless words)

Translation has a *defensive* habit: the brain adds connector words
("actually", "you see", "in fact", "moreover") to sound "complete" or
"literary." The target result reads padded, slow, alien.

**Strunk's three rules applied to translation:**

1. **Omit needless words.** "He was a man who always ate food" →
   "He always ate." "เขาเป็นคนที่ชอบกินอาหาร" → "เขาชอบกิน".
   Cut every "who/which/that" clause that doesn't carry new information.
2. **Avoid succession of loose sentences.** Three short declaratives in
   a row ("He sat. He ate. He slept.") read as a children's book.
   Combine: "He sat, ate, slept." Or vary with one longer sentence.
3. **Do not over-explain.** If a name or term was introduced earlier,
   don't re-explain it. If a motive is shown in action, don't add
   "because he wanted to..." after.

**Also:** a target translation is often 1.4-1.8x source length. If
yours is 2.5x+, suspect bloat. If it's 0.8x, suspect omission. The
target is the *natural expansion* of the source's compressed
short-clause style, not a word-for-each-word count.

### Where language-specific stuff lives

Section 4b is universal. The language-specific details go in:

- **`style.md` per novel** — concrete particles, register, honorifics,
  cultural references, onomatopoeia, source-language-specific traps
  (e.g. for CN→TH: 曹一 type compound names, 领主 honorific chains,
  璀璨/ระยิบระยับ type calques; for JP→TH later: keigo, けど/し
  sentence-endings, onomatopoeia density)
- **`glossary/locked.md` per novel** — name spellings, game terms
- **`characters.md` per novel** — speech patterns per character

When you find a *language-specific* pitfall mid-translation, append it
to the relevant `style.md` so future chapters and future source
languages don't relearn it.

### Self-check before declaring 4b-clean

- [ ] All 5 phases of the workflow applied? (Ground Truth → Comprehend → Decompose → Reconstruct → Correction Loop)
- [ ] **P1** Word order is target-natural (not source)?
- [ ] **P2** Emotions shown through action, not told directly? (no emotion lump, no descriptive pile)
- [ ] **P3** Collocations are native (search-tested if uncertain)?
- [ ] **P4** Pacing matches target-language genre convention?
- [ ] **P5** Subject varied — no 3 same-subject sentences in a row?
- [ ] **P6** Cultural balance correct? Syntax domestic, names/cultural terms foreign?
- [ ] **P7** No bloat? Length ratio in 1.4-1.8x range? No needless connectors? No over-explanation?
- [ ] If a recurring source-language trap appeared, appended to `style.md`?

## 4c. ANTI-SLOP — banned words, phrases, and patterns

> Inspired by NemoPresetExt **ProsePolisher** (regex-based slop fixing)
> + NousResearch **autonovel/ANTI-SLOP.md** (3-tier banned lists) +
> Adenaufal **anti-slop-writing** (universal system prompt pattern).
> Universal across languages. **CN→TH specific examples live in `style.md`
> per novel**; what's below is the source-language-agnostic core.
>
> **⚠️ TRANSMITTOR SCOPE (commit 87f7f14):** anti-slop rules apply to
> **Mika-generated text** (Mika's summaries, analysis, prep context,
> optional polish) and to text the source does NOT contain. They are
> NOT requirements to delete or rewrite the AUTHOR's own patterns
> ("อย่างไรก็ตาม", "ดังนั้น", "ดีใจในใจ", "เต็มไปด้วยความ[X]", 3+
> consecutive "เฉาซิง" as subject — these are the author's voice, not
> slop). See §0 for the master rule. Any conflict between §4c and §0 →
> §0 wins. See `style.md` "Transmittor scope — what we do NOT flag"
> for the project-specific list.

Slop = text that reads like unedited LLM output. Low information
density, predictable structure, vocabulary no human would reach for.
Macquarie Dictionary's **2025 word of the year**.

### Tier 1: Kill on sight (rewrite the sentence)

These almost never appear in casual human writing. One use = rewrite.

| Slop word | What a human writes |
|---|---|
| delve | dig into, look at, examine |
| utilize | use |
| leverage (verb) | use, take advantage of |
| facilitate | help, enable, make possible |
| elucidate | explain, clarify |
| embark | start, begin |
| endeavor | effort, try |
| encompass | include, cover |
| multifaceted | complex, varied |
| tapestry | (don't. describe the actual thing.) |
| testament ("a testament to") | shows, proves, demonstrates |
| paradigm | model, approach, framework |
| synergy / synergize | (delete the sentence) |
| holistic | whole, complete |
| catalyze / catalyst | trigger, cause, spark |
| juxtapose | compare, contrast, set against |
| nuanced (as filler) | (cut. if nuanced, show how.) |
| realm | area, field, domain |
| landscape (metaphorical) | field, space, situation |
| myriad | many, lots of |
| plethora | many, a lot |

### Tier 2: Suspicious in clusters (3+/paragraph = rewrite)

Fine in isolation. Three in one paragraph = rewrite.

| Slop word | Plainer alternative |
|---|---|
| robust | strong, solid, reliable |
| comprehensive | complete, thorough, full |
| seamless / seamlessly | smooth, easy, without friction |
| cutting-edge | new, latest, modern |
| innovative | new, original, clever |
| streamline | simplify, speed up |
| empower | let, help, give the ability |
| foster | encourage, grow, support |
| enhance | improve, boost |
| elevate | raise, improve |
| optimize | improve, tune, tweak |
| scalable | grows with you, handles more load |
| pivotal | important, key, central |
| intricate | complex, detailed |
| profound | deep, significant |
| resonate | connect with, hit home |
| underscore | highlight, stress, show |
| harness | use, put to work |
| navigate (metaphorical) | deal with, work through, handle |
| cultivate | build, grow, develop |
| bolster | strengthen, support |
| galvanize | push, rally, motivate |
| cornerstone | foundation, basis, core |
| game-changer | (be specific about what changed) |

### Tier 3: Filler phrases to DELETE

Verbal tics. LLMs insert them reflexively. **Just delete.**

| Phrase | Action |
|---|---|
| "It's worth noting that..." | Just state the thing. |
| "It's important to note that..." | Just state the thing. |
| "Importantly, ..." | Just state the thing. |
| "Notably, ..." | Just state the thing. |
| "Interestingly, ..." | (If it's interesting, readers will notice.) |
| "Let's dive into..." | (Delete. Start with content.) |
| "Let's explore..." | (Delete. Start with content.) |
| "In this section, we will..." | (Delete. Heading already says this.) |
| "As we can see..." | (Delete. They can see.) |
| "As mentioned earlier..." | (Delete or reference the thing.) |
| "In conclusion, ..." | (Delete. Reader knows it's the end.) |
| "To summarize, ..." | (Delete or just... summarize.) |
| "Furthermore, ..." | and, also |
| "Moreover, ..." | also, and, plus |
| "Additionally, ..." | also, and |
| "In today's [X] world..." | (Delete the whole clause.) |
| "At the end of the day..." | (Delete.) |
| "It goes without saying..." | (Then don't say it.) |
| "Without further ado..." | (Delete.) |
| "When it comes to..." | (Rewrite: talk about the thing.) |
| "In the realm of..." | in |
| "One might argue that..." | (Either argue it or don't.) |
| "This begs the question..." | (Almost always misused. Delete.) |
| "Not just X, but Y" | (Restructure. The #1 LLM rhetorical crutch.) |
| "A [comprehensive/holistic/nuanced] approach to..." | an approach to |

### Tier 4: Structural slop patterns

Slop isn't just vocabulary. The **skeleton** betrays it.

- **"Topic sentence → elaboration → example → wrap-up" template.** Every
  paragraph same rhythm. Human writing varies: point comes last sometimes,
  no example sometimes. Vary paragraph shape.
- **3 consecutive paragraphs starting with transition words** (Moreover,
  Furthermore, Additionally, In addition). Human writers don't chain these.
  This is the single most overused LLM rhetorical pattern.
- **3 consecutive sentences with same subject** (see §4b P5).
- **Uniform paragraph length** — every paragraph exactly 3-5 sentences.
  Humans vary.
- **Bullet-list summary at the end** of every section. Sometimes a paragraph
  is better.

### Tier 4.5: Participial -ing tack-ons (U-1, Adenaufal)

**The single most recognizable AI pattern.** A comma + -ing phrase appended
to a sentence end to appear analytical, adding no information.

> ✗ "The team launched the product, **revolutionizing** the industry."
> ✓ "The team launched the product. The industry changed."

> ✗ "The temple was built in 1850, **symbolizing** the community's faith."
> ✓ "The temple was built in 1850."

**Rule:** if the -ing clause adds no concrete information, delete it. If it
adds real info, make it a separate sentence.

**TH translation crutch:** ลงท้ายประโยคด้วย "...โดย[verb]+ing" หรือ "...ซึ่ง[verb]+ing" แบบไม่จำเป็น:
- ✗ "เขาเปิดตัวผลิตภัณฑ์, **ปฏิวัติ**อุตสาหกรรม" (comma tack-on)
- ✓ "เขาเปิดตัวผลิตภัณฑ์ อุตสาหกรรมเปลี่ยนไป" (separate sentence)

### Tier 4.6: Rule of Three (U-2, Adenaufal)

AI defaults to grouping things in **threes** — three adjectives, three
bullet points, three examples, three clauses. Real humans list 2, 4, 5, or
7 items erratically.

> ✗ "The conference features keynote sessions, **panel discussions, and**
> **networking opportunities**." (3 items)
> ✓ "The conference runs keynote sessions and panels. There's time to meet
> people between talks." (2 items, restructured)

> ✗ "The design is bold, **innovative, and timeless**." (3 adjectives)
> ✓ "The design is bold. It'll still work in ten years." (1 + 1)

**Rule:** list two things, or four, or one. Never three by default.

**TH translation crutch:** "...และ..." used 3 times in one sentence to chain:
- ✗ "งานมีบรรยาย, **เวิร์กช็อป, และ** **Networking**" (3 things)
- ✓ "งานมีบรรยายกับเวิร์กช็อป พักเบรกให้คุยกัน" (restructured)

### Tier 4.7: Copula avoidance (U-6, Adenaufal)

AI substitutes elaborate verb phrases for simple "is/are/has."

| AI pattern | Human |
|---|---|
| serves as (a) | is |
| stands as (a) | is |
| marks (a) [shift/change] | describe directly |
| boasts (meaning "has") | has |
| features (meaning "has") | has |
| holds the distinction of being | is / was |
| emerged as (a) | became or is |
| constitutes (a) | is |

**TH translation crutch:** คำว่า "ทำหน้าที่" / "ถือเป็น" / "นับเป็น" / "ถือได้ว่า" ใช้แทน "เป็น" ตรงๆ
- ✗ "Gallery 825 **ทำหน้าที่เป็น**พื้นที่จัดแสดง" → ✓ "Gallery 825 **เป็น**พื้นที่จัดแสดง"
- ✗ "ผลงานนี้ **ถือเป็น**ก้าวสำคัญ" → ✓ "ผลงานนี้**เป็น**ก้าวสำคัญ" (หรือ restructure ไปเลย)
- ✗ "เขา **ถือได้ว่าเป็น**ผู้นำ" → ✓ "เขา**เป็น**ผู้นำ"

### Tier 4.8: False ranges (U-4, Adenaufal)

Vague figurative spectrum using "from X to Y" where no real scale exists.

> ✗ "**From intimate gatherings to global movements**, the organization
> has made its mark." (no real scale)
> ✓ "The organization started with twelve people in a living room. Last
> year 40,000 showed up to their conference."

**Rule:** only use "from X to Y" when there's a real, identifiable midpoint
on a real scale.

**TH translation crutch:** "ตั้งแต่...ไปจนถึง..." ใช้เวลา scale จริง:
- ✗ "**ตั้งแต่มือใหม่ไปจนถึง**ผู้เชี่ยวชาญ ใช้ได้ทุกคน" (vague)
- ✓ "ทำมาสัปดาห์นึงก็ใช้ได้ ทำมาสิบปีก็ยังใช้ได้" (real scale)

### Tier 4.9: "Despite its... faces challenges" formula (U-5, Adenaufal)

Formulaic challenges-and-future-prospects ending.

> ✗ "**Despite its industrial prosperity**, Korattur **faces challenges
> typical of urban areas**, including... **With its strategic location and
> ongoing initiatives**, Korattur continues to thrive."

**Rule:** if mentioning problems, name specific ones with specific evidence.
Never follow with vague optimism.

**TH translation crutch:** "แม้...แต่..." + "อย่างไรก็ตาม..." generic ending:
- ✗ "**แม้จะเผชิญ**ปัญหา**มากมาย** เมืองนี้**ยังคง**เติบโต" (vague)
- ✓ "ท่อน้ำของเมืองนี้มาจากปี 1970 ประชากรเพิ่มขึ้น 3 เท่า" (specific)

### Tier 4.10: Superficial analysis padding (U-7, Adenaufal)

Generic commentary attached to facts that need no commentary. If the
analytical statement could apply to literally any subject, it adds nothing.

> ✗ "The city has a population of 56,998, **creating a lively community
> within its borders**." (which city DOESN'T do this?)
> ✓ "The city has a population of 56,998."

**TH translation crutch:** "สร้างชุมชนที่มีชีวิตชีวา" / "ทำให้เศรษฐกิจเติบโต" — generic verbs that add nothing:
- ✗ "ประชากร 56,998 คน **สร้างชุมชนที่มีชีวิตชีวา**" (vague)
- ✓ "ประชากร 56,998 คน" (just the fact)

### Tier 4.11: Negative parallelisms (U-3, Adenaufal)

"Not just X, but Y" / "It's not X, it's Y" / "Not only X, but also Y"

> ✗ "This is **not just a memoir — it's a love letter to the city**."
> ✓ "It's a memoir about growing up in the city. You can feel the author's
> affection for it on every page."

**TH translation crutch:** "ไม่ใช่แค่ X แต่เป็น Y" / "ไม่ได้แค่ X แต่ยัง Y"
- ✗ "นี่**ไม่ใช่แค่**เรื่องราว แต่**เป็น**จดหมายรัก" → restructure
- ✓ "เรื่องนี้เล่าเรื่องการเติบโตในเมือง ความรู้สึกของผู้เขียนอบอวลทุกหน้า"

**The #1 LLM rhetorical crutch** per NousResearch ANTI-SLOP.md.

### Tier 4 metrics — Perplexity & Burstiness

AI detectors (GPTZero, Turnitin 2025-2026) measure 3 metrics:
- **Perplexity** (unpredictability of word choice) — median AI: 21.2, human: 35.9.
  AI picks the most probable next word every time → smooth, unsurprising.
  Humans use specific, unusual, contextual words.
- **Burstiness** (sentence length variation) — single best detector.
  AI: sentences cluster 15-25 words. Human: mixes 3-word with 35-word.
  **Introducing burstiness reduces AI detection by up to 40%.**
- **Stylometry** — 31 linguistic features (function word frequency,
  lexical diversity, punctuation patterns, syntactic depth).

**Implication for NovelClaw:** vary sentence length deliberately. Don't
write 5 sentences of 20 words each. Mix 3-word punch with 30-word flow.

### Tier 4.12: Em dash ban (Adenaufal #10)

**The em dash has become "the ChatGPT dash" — the single most recognizable
AI tell in English prose.** Per Adenaufal: count em dashes; if count ≠ 0,
fix.

| AI pattern | Human replacement |
|---|---|
| "The team launched the product **—** a major milestone" | "The team launched the product. A major milestone." (period + new sentence) |
| "**—** and that's saying something" | ", and that's saying something" (comma) |
| "The city has a population of 56,998 **—** a lively community" | "The city has 56,998 residents" (cut) |
| "Data quality **—** or lack thereof **—** is the issue" | "Data quality (or lack of it) is the issue" (parentheses) |

**Rule:** zero em dashes in body text. Replace with: period (split
sentences), comma (if flow), colon (for definitions), parentheses (for
asides), plain hyphen (compound adjectives only).

**NovelClaw exception:** the `—` character is allowed as a **placeholder
for missing numeric data** in stat blocks (e.g., `力量: —` when source has
no number). This is data display, not prose tic. Limit to 1-2 per
chapter max; if a stat block has many, that's a sign to fill in from
source (5-Phase §4b Phase 1 Ground Truth should catch this).

### Tier 4.13: Staccato triplets (Adenaufal EN-6)

Three punchy parallel sentences in a row: "No X. No Y. Just Z." Now a
recognized AI social media pattern.

> ✗ "**No meetings. No bureaucracy. Just results.**"
> ✗ "**ไม่มีประชุม ไม่มีระบบราชการ แค่ผลลัพธ์**" (TH equivalent)

If you want emphasis, use a **single** short sentence, not three.

> ✓ "**Just results.**" (one short sentence)
> ✓ "**แค่ผลลัพธ์ล้วนๆ**" (one short)

### Tier 4.14: Sentence type variety (Adenaufal, Jericho Writers)

AI writes almost exclusively in declarative sentences ("X happened. Y
happened."). Real writers mix:
- **Declarative** ("He walked away.") — default
- **Question** ("Why does this matter?") — signal thinking
- **Imperative** ("Think about that.") — shifts register
- **Fragment** ("Not ideal." / "Big difference.") — emphasis + rhythm
- **Exclamation** ("It works!") — rare but powerful

**Rule:** for every 5 sentences, aim for at least 1 question, 1
fragment, and (when appropriate) 1 imperative. Pure declaratives read
mechanical.

**TH translation crutch:** แปล dialogue ทั้งหมดเป็น declarative ตามแบบ CN source
ควรเติม fragment/question ที่ natural:
- ✗ "เขาเดินจากไป" (declarative) → ✓ "เขาเดินจากไป" + เติม "แล้วไง" / "แล้วก็?"
- ✓ "ไม่ค่อยดีเท่าไหร่" (fragment) — for emphasis
- ✓ "แล้วไงต่อ?" (question) — for curiosity

### Tier 4.15: Model-specific tells (Adenaufal EN-11)

Different LLMs have different slop signatures. Catch yours:

| Model | Tells to watch for |
|---|---|
| **ChatGPT** | enthusiastic promotional tone, **em dash overuse**, bold formatting obsession, numbered lists, "Let's dive in", "Absolutely!" |
| **Claude** | excessive hedging ("I think," "There's a case to be made"), over-qualified statements, balanced both-sides framing, copula avoidance (serves as → is) |
| **Gemini** | purple prose, excessive adjectives, moralizing, explicit theme statements, textbook tone |
| **Mika (custom)** | subject echo "เฉาซิง[verb]", "อย่างไรก็ตาม" overuse (92x!), "เต็มไปด้วยความ..." emotion lump, "ดีใจในใจ" echo |

**Rule:** know your LLM's tells, target them specifically. If you use
multiple models, grep each for its signature.

### Tier 4.16: Function word diversity (Adenaufal)

AI uses a narrower set of connectors. Vary them:

| AI overuse | Alternatives |
|---|---|
| and | plus, as well as, comma |
| but | though, still, yet, except |
| so | thus, hence, therefore (use sparingly) |
| also | too, additionally, furthermore |
| however | nevertheless, nonetheless, that said, still |

**Rule:** don't use the same connector 3+ times in a paragraph. Mix
connectors for natural flow.

**TH translation crutch:** "และ" / "แต่" / "ก็" overuse — เปลี่ยนเป็น
"อีกทั้ง" / "ถึงกระนั้น" / "อย่างไรก็ดี" / "ทว่า" / restructure เลย

### TH translation crutches (CN→TH specific)

LLMs translating CN→TH add their own tics on top of the source. Banned
in this project. (TH equivalents of Tier 1-3 — source-specific tics.)

| CN source | TH slop crutch | Better TH |
|---|---|---|
| 果然 | "อย่างที่คาดไว้" (literal) | "ดั่งที่หวัง" / omit entirely |
| 值得注意的是 | "ที่น่าสังเกตคือ..." | state the thing directly |
| 此外 / 而且 / 另外 | "นอกจากนี้..." | "และ" / "อีกทั้ง" / omit |
| 因此 | "ดังนั้น..." | "เลย..." / restructure |
| 然而 / 不过 | "อย่างไรก็ตาม..." | "แต่" / restructure |
| 尽管 | "แม้ว่า..." (overuse) | "ถึงจะ..." / "แม้..." (shorter) |
| 为了 | "เพื่อที่จะ..." (literal) | "เพื่อ..." (drop the "ที่จะ") |
| 包括 | "รวมถึง..." (overuse) | "ทั้ง...และ..." / direct list |
| 与此同时 | "ในขณะเดียวกัน" | "ตอนนั้นเอง" / restructure |
| 事实上 | "อันที่จริง" (overuse) | "จริงๆ แล้ว" / omit |

**Mika-specific crutches** (observed in ch 80, 90, 95, 100 translations):
- "เฉาซิง[verb]" x 3 in a row (subject echo) — see §4b P5
- "ดีใจในใจ" / "เสียใจในใจ" (emotion echoes)
- "เต็มไปด้วยความ[X]" (flat emotion lump)
- "ชาวอาณานิคม[ชื่อ]" (appositive compound)
- "ทั้งนี้..." / "อย่างไรก็ตาม..." as sentence starters (formal tic)

### How to apply

**Before declaring a chapter done, scan (transmittor-scoped):**
1. Grep for Tier 1 words **in Mika-generated text only** (summaries,
   prep context, optional polish) → rewrite each occurrence
2. Grep for Tier 2 words in Mika-generated text → if 3+ in same
   paragraph, rewrite
3. Tier 1-3 words that appear in the SOURCE are the author's voice
   — transmit verbatim (see §0, `style.md` Banned section)
4. Tier 4 patterns in Mika-generated text (paragraph uniformity,
   transition chains) → vary
5. TH crutches in Mika-generated text → replace with better TH
6. TH crutches in source → transmit verbatim

**Tools:**
- `tools/slop/scan.py` (NOT `slop_detector.py` — that file doesn't
  exist) — automated scan of recent translations
- ProsePolisher pattern: regex rules in `style.md` (per-novel) + global
  in this section
- The transmittor scoping in step 1-3 is enforced by
  `tools/validate_chapter.py` v3 (anti-patterns = `info`, not
  `warning`); mechanical fix only (whitespace, number format, system
  wrapping)

### Self-check (Section 8 C slop layer)

- [ ] Zero Tier 1 words (grep clean)
- [ ] No paragraph with 3+ Tier 2 words
- [ ] No Tier 3 filler phrases
- [ ] No 3+ consecutive transition-word sentences
- [ ] No 3+ consecutive same-subject sentences (also §4b P5)
- [ ] No TH crutches from table above
- [ ] No Mika-specific crutches (subject echo, emotion lumps)
- [ ] If recurring Mika pattern detected, appended to `style.md` banned list

### Sources

- NemoVonNirgend/**ProsePolisher** — 30+ hand-crafted rules, SLOP_THRESHOLD=3, AI-generated rules, regex navigator
- NousResearch/**autonovel/ANTI-SLOP.md** — 3-tier banned lists + structural patterns + slop-forensics data
- adenaufal/**anti-slop-writing** — universal system prompt format for any LLM client
- sam-paech/**slop-forensics** — statistical overrepresentation analysis
- **EQ-Bench Slop Score** — quantitative AI-text detector
- Macquarie Dictionary 2025 "Word of the Year" — slop

## 5. CONSISTENCY — using context files

Before translating ANY chapter, Mika reads:
1. `glossary.md` — use exact Thai for terms (135+ entries for typical novel)
2. `characters.md` — speech patterns + role for each character
3. `summary.md` — what happened so far
4. `style.md` — per-novel specific choices
5. **Last 1-2 chapters** — for tone consistency

This is the "long-term memory" that prevents เฉาซิง becoming โจวซิง in chapter 5,
or the tone shifting from นิยายจริงจัง to นิยายตลก between chapters.

### 5c. AUTOMATED CONTEXT (NovelClaw 2.0 — Phase 1-4)

In addition to the static files above, `pre_chapter.py` (via
`python novelclaw.py prep N`) automatically injects 4 layers of smart context:

1. **Dynamic bans** (Phase 3) — top-10 crutch bigrams auto-learned from
   prior translations. Avoid these phrases to prevent repetition drift.
2. **Cross-chapter context** (Phase 4) — FTS5 search of prior chapters
   to find which chapters mention the same names/concepts as ch N.
   Prevents continuity breaks (renamed characters, forgotten status).
3. **NPC dossiers** (Phase 2) — character voice + relationship context
   for the top-3 NPCs appearing in ch N, sourced from `npc_bank/`.
4. **5-Phase audit** (Phase 1, post-hoc) — after translating, run
   `python novelclaw.py audit N` to generate provenance log in
   `chapters/{N:04d}/audit.md` for review.

The pre_chapter output shows ALL of these before the source text, so
Mika has full context before writing a single word.

## 5b. GLOSSARY (Contextual Loading)

The glossary is split into 3 files by priority. Read them in order:

1. **`glossary/locked.md`** (~58 terms) — **MANDATORY.** Style.md terms + main cast. NEVER deviate.
2. **`glossary/reference.md`** (~100 terms) — Recurring NPCs / common items / common skills. Use consistently for tone.
3. **`glossary/auto.md`** (~414 terms) — One-off terms. Use if encountered, otherwise translate freely and append to `auto.md`.

(Totals ~572; run `python tools/glossary_stats.py` for current counts.
The yml/DB may lag the .md files — see `tools/build_yaml.py` for the
auto-generated `glossary.yml`, and `tools/build_glossary.py` for the
SQLite `glossary.db`. A `--check` flag in build_glossary.py compares
counts and exits non-zero on drift.)

When you encounter a term in source that:
- Is in `locked.md` → use the locked Thai version exactly
- Is in `reference.md` → use the reference Thai version
- Is in `auto.md` → use the auto Thai version
- Is in NONE of the three → translate it, then APPEND it to `auto.md` and update `index.md` count

The glossary is split this way to keep the prompt small (only relevant terms per chapter), while maintaining quality across the full novel. Conflicts: `locked.md` wins over `reference.md` wins over `auto.md`. Style.md wins for in-world terms.

## 6. FILE FORMAT

### Chapter file `chapters/NNNN.md`

```markdown
# ตอนที่ N <Thai title>

<translated content — every paragraph from source>

---

*Source: ch N*
*Translated: <YYYY-MM-DD>*
```

**Optional:** A `*คำแปล:*` one-paragraph summary may appear in the
final section (after a `---` separator). This is used in the reader
sidebar's "what happened" tooltip for the chapter. Keep it under
1,000 Thai characters.

### Glossary `glossary.md`

Markdown table with columns: Source | Thai | Category | Priority | Notes.
Categories: ตัวละคร (character), ไอเทม (item), สถานที่ (place), สกิล (skill).
Priority: 1 = locked (must use), 2 = reference, 3 = auto (model can suggest).

### Characters `characters.md`

One section per character with: Gender, Personality, Speech pattern.

### Summary `summary.md`

Cumulative plot summary, organized by chapter ranges. Append new events
after each chapter is translated. Keep it concise (3-5 bullets per range).

### Style `style.md`

Per-novel style choices (overrides defaults above).

## 7. TRANSLATION SESSION CHECKLIST

When Mika translates a chapter (or batch):

1. [ ] Read `meta.md` (confirm title, language, current progress)
2. [ ] Read `glossary.md` (terms to use exactly) — **confirm Thai column has NO CN characters**
3. [ ] Read `characters.md` (character voices)
4. [ ] Read `summary.md` (what happened so far)
5. [ ] Read `style.md` if it exists
6. [ ] Read last 1-2 `chapters/*.md` (tail, for tone)
7. [ ] Read the user-provided source text
8. [ ] Translate, applying all rules (including Section 1a — Thai-only output)
9. [ ] Self-review (Section 8) — **includes CJK scan**
10. [ ] Update glossary if new terms appear (append row with PURE THAI)
11. [ ] Update characters if new characters appear (append section)
12. [ ] Update summary with new events (append)
13. [ ] Save chapter to `chapters/NNNN.md`
14. [ ] Run `python tools/validate_no_cjk.py` to confirm zero CJK leakage
15. [ ] Report: translated, length ratio, any glossary/summary updates

## 8. SELF-REVIEW — before reporting done

Three categories of checks — all must pass before saying "done":

**A. Completeness & content** (the non-negotiable):
- [ ] **Every paragraph from source present in translation** (count check)
- [ ] **Length ratio ≥ 0.6** (CN→TH natural expansion typically lands at 1.4-1.8x; flag if <0.6 — completeness concern; >2.5x is a signal of bloat in MIKA-generated text only — do not compress source to fit)
- [ ] **No content added** that wasn't in source
- [ ] **No content removed** that was in source
- [ ] **System messages / scene breaks preserved** (【】, 《》, blank lines)
- [ ] **NO CJK in body text or H1** — only the optional `*Source:*` footer may contain CN (the original chapter title for reference). Use `python tools/validate_no_cjk.py` to verify.

**B. Files & glossary** (the machinery):
- [ ] **Names match glossary** exactly (no เฉา instead of เฉาซิง)
- [ ] **Glossary updated** for new terms (Thai column = Thai only)
- [ ] **Summary updated** for new events
- [ ] **Chapter file saved** to `chapters/NNNN.md`
- [ ] **Tone matches last 1-2 chapters**
- [ ] **Dialogue feels natural** (not literal word-for-word)

**C. Craft layer (Section 4b)** — OPTIONAL polish pass (transmittor-scoped):

> **⚠️ TRANSMITTOR SCOPE (commit 87f7f14):** items in this section are
> quality targets for **Mika-generated text** (summaries, prep context,
> optional polish) and for translation review polish passes. They are
> **NOT hard requirements** for source content. If the source has
> subject echo, flat emotion, or length ratio outside 1.4-1.8x, that's
> the author's voice — transmit it (see §0, `style.md` Banned section).
> Any conflict between §8C and §0 → §0 wins.

- [ ] **Ground Truth extraction done first** (every fact in source appears in translation — numbers, names, system messages, stat lines)
- [ ] **5-phase workflow applied** (Ground Truth → Comprehend → Decompose → Reconstruct → Correction Loop)
- [ ] **Mika-generated text has target-natural word order** (P1: not CN-grammar calque — applies to NEW content)
- [ ] **Mika-generated text has no bloat** (P7: length ratio in 1.4-1.8x — for source: signal only, not edit target)
- [ ] **Mika-generated text varies subjects** (P5: no 3 same-subject sentences in NEW content; source subject echo = author's style, transmit)
- [ ] **Mika-generated text shows not tells** (P2: applies to NEW content; source flat emotion = author's voice, transmit)
- [ ] **Cultural balance correct** (P6: syntax domestic, names/cultural terms foreign)
- [ ] **Mika-generated text is anti-slop clean** (Section 4c: no Tier 1 words in NEW content; source slop-like patterns = author's voice, transmit)

If any check fails: fix the issue, then re-verify. **Do not declare done
with known issues** — the user trusts you to catch errors before reporting.
