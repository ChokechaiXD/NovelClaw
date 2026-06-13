# NovelClaw 🦀

> Translation workspace for web novels (CN / EN / JP / KR → TH).
> Mika does the translation directly in chat; this project is the persistent
> context (glossary, characters, summary, chapters) that keeps it consistent
> across sessions.

## Why this exists

The previous approach (Electron + Gemini API + scraper + queue manager)
turned out to be over-engineered: hit API rate limits, hard to maintain,
fancy but messy. This project is the opposite: **just files, just chat**.

## Project layout

```
NovelClaw/
├── novelclaw.py             # ← main CLI entry point
├── run.bat                  # ← Windows launcher for the reader
├── README.md                # ← you are here
├── PROMPT.md                # ← translation rules Mika follows
├── STRUCTURE.md             # ← folder design + scale notes
├── tools/                   # ← helper scripts
│   ├── pre_chapter.py       #   bundles context for next chapter
│   ├── validate_chapter.py  #   quality check (with --fix for mechanical)
│   ├── validate_no_cjk.py   #   zero-CJK leakage scan
│   ├── find_candidates.py   #   chapters that may need re-translation
│   └── scrape_chapters.py    #   initial source scraper (aiohttp)
├── tests/                   # ← pytest suite (parse + auto_fix regression)
│   ├── conftest.py
│   ├── test_constants.py
│   ├── test_find_candidates.py
│   └── test_validate_chapter.py
├── reader/                  # ← web reader (Node.js)
│   ├── server.js
│   ├── package.json
│   └── public/              #   index.html, app.js, style.css
└── novels/
    └── <title-slug>/
        ├── meta.md
        ├── style.md
        ├── glossary.md      # ← old redirect note
        ├── glossary/        # ← split glossary (locked / reference / auto)
        │   ├── locked.md    #   must-use (style.md mandated + main cast)
        │   ├── reference.md #   recurring NPCs/items/skills
        │   ├── auto.md      #   one-off terms
        │   └── index.md     #   master view + how-to
        ├── characters.md
        ├── summary.md
        ├── progress.md
        └── chapters/
            ├── NNNN.md      # ← translated chapter
            └── source/
                └── NNNN.md  # ← original (for reference)
```

## CLI

`python novelclaw.py` is the main entry. Subcommands:

| Command | What it does |
|---------|--------------|
| `status` | Show translation progress + glossary stats |
| `prep [N]` | Bundle context (source + glossary hits + last summaries) for chapter N (or next) |
| `validate [N]` | Check chapter N for length/numbers/names; `validate N --fix` auto-fixes mechanical issues |
| `validate --cjk [N...]` | CJK leakage check (all or specific chapters) |
| `candidates` | Find chapters that may need re-translation |
| `scrape` | Re-scrape source chapters (one-time) |
| `health` | Quick health check: candidates + CJK + stale glossary |
| `test [-v]` | Run pytest suite (validates parse + auto_fix logic, 39 tests) |

## Reader

`run.bat` starts the web reader at `http://localhost:4173/`. The reader
binds to `0.0.0.0` so phones on the same Wi-Fi can reach it at
`http://<pc-lan-ip>:4173/`.

Features:
- Left-aligned reading column with character-based max-width (70ch)
- 3 themes (light / sepia / dark)
- Sidebar with Thai chapter titles + search filter
- Mobile-optimized (44×44 touch targets, iOS safe area, slide-out sidebar)
- Keyboard shortcuts: `←`/`→` prev/next, `T` theme, `S` sidebar, `Home`/`End` scroll

## How a translation session works

1. **User says:** "next" or "แปล ch N" or "ต่อ"
2. **Mika runs** `python novelclaw.py prep N` to get source + context
3. **Mika outputs Pre-Translation Fact Sheet** (§4b Phase 1) — list every number, name, stat, dialogue as a fenced code block in chat
4. **Mika translates** per `PROMPT.md` rules using the 5-Phase workflow
5. **Mika runs** `python tools/slop_detector.py --chapter N` to check anti-AI patterns
6. **Mika runs** `python novelclaw.py validate N` to verify Ground Truth coverage + length + glossary
7. **If slop detector flags red** (Tier 1/2 hits, >5 crutches/ch, 【】 split, 3+ em dashes) → **fix and re-validate before claiming done**
8. **Mika writes** to `chapters/NNNN.md` only after all checks pass
9. **Reader** auto-discovers new chapter; sidebar updates

## Why the name

"Claw" — grasps foreign text, holds context tightly, doesn't let go across
chapters. Lightweight, no infrastructure. Just a tool that works.

## Active novel

`global-descent` — 全球降臨：帶著嫂嫂末世種田 by 一条小白蛇
1,239 chapters, 31 translated (ch 1, 71-100), 1,240 source files scraped.
Next: ch 101.
