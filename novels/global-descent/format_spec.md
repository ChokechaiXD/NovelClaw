# Format Spec — NovelClaw global-descent

> Canonical format that ALL translated chapters must follow. This is the
> single source of truth for "what does a ch file look like" — established
> 2026-06-14 in response to ch 1-99 using old format ("dialogue") and
> ch 112 using new format (「dialogue」). P'Chok mandate: เป็นไปเหมือนกันทุกตอน.

## File structure (top to bottom)

```
# ตอนที่ {N} {THAI_TITLE}
                                                ← blank line
{BODY_PARAGRAPHS_SEPARATED_BY_BLANK_LINE}
...
(จบบท)                                          ← end marker
                                                ← blank line
---
                                                ← blank line
*Source: ch {N}*                                 ← exactly this format
                                                ← blank line
---
                                                ← blank line
หมายเหตุการแปล:                                 ← meta section
- {note_1}
- {note_2}
...
```

## Required elements

| Element | Format | Example |
|---------|--------|---------|
| **Title** | `# ตอนที่ {N} {thai_title}` | `# ตอนที่ 112 การทรยศหมู่ครีม กลยุทธ์เนื้อกระต่าย` |
| **End marker** | `(จบบท)` on its own line | `(จบบท)` |
| **Separator 1** | `---` on its own line | `---` |
| **Source footer** | `*Source: ch {N}*` (NO novel title, NO author) | `*Source: ch 112*` |
| **Separator 2** | `---` on its own line | `---` |
| **Meta section** | `หมายเหตยการแปล:` followed by `- {note}` lines | (see ch 112) |

## Bracket conventions (CRITICAL)

| Use | Bracket | Example | Forbidden |
|-----|---------|---------|-----------|
| Dialogue | `「...」` (full-width CJK) | `「อยากกินมั้ย?」` | `"..."` (straight) or `'...'` |
| System message | `【...】` (full-width CJK) | `【เลเวล 8】` | `[...]` (straight) |
| Game title | `《...》` (full-width CJK) | `《มหายุคน้ำแข็ง》` | `<...>` (straight) |
| Emphasis | `**...**` (markdown) | `**สำคัญ**` | `__...__` |
| Source footer | `*...*` (italic) | `*Source: ch 112*` | (only this use) |

## Whitespace rules

- **Between paragraphs:** single blank line (`\n\n`)
- **No trailing whitespace** on any line
- **No 3+ consecutive blank lines** anywhere
- **No tabs** (use spaces)
- **Final newline** at end of file

## Spacing around numbers / units

- `1,000` (comma for 5+ digit), `1000` (no comma for 4 digit)
- `10 กิโล` (space between number and Thai unit)
- `65~67` (tilde, no spaces) for ranges

## Em-dash usage

- `—` (em-dash U+2014) for missing numbers: `HP: 780/—`
- NOT `--` (double hyphen)
- NOT `-` (single hyphen, except in compound words like `สาม-ร้อย-ห้า`)

## Quoting inside dialogue

When a character says a name/title, use `「」` outside and `"` (straight) inside:
```
เฉาซิงพูดว่า "ราชินีแมงมุมเลือด ซีเออร์ดา·จูบเลือด" มาถึงแล้ว
```
This is the ONE exception where straight `"` is allowed (inside dialogue, quoting a name).

## Forbidden (auto-detected, will BLOCK save)

- Straight `"` outside of in-dialogue quoting
- Straight `'` anywhere
- Straight `[` or `]` outside of CN source quote (in meta note)
- Straight `<` or `>` outside of legitimate comparison
- Trailing whitespace on any line
- 3+ consecutive blank lines
- Missing `(จบบท)` end marker
- Missing `*Source: ch N*` footer
- *Source:* footer with novel title or author (use just `*Source: ch N*`)
- Tabs

## Style decision summary

The format spec is enforced by `glossary_doctor.py --format-check` (new)
and reported in `--report`. To reformat existing ch to spec, run:
`python tools/reformat_chapters.py [--dry-run]`

## Versioning

- v1 (pre-2026-06-14): used straight `"` for dialogue, no (จบบท), no spec
- v2 (2026-06-14): use 「」, require (จบบท), require *Source: ch N*, single blank lines

All new ch MUST use v2. Old ch will be reformatted in batch.
