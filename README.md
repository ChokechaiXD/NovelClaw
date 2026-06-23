<div align="center">

# NovelClaw
### *ภาษาไทย · 中文 · Cross-language web novel translation toolkit*

[![Tests](https://img.shields.io/badge/tests-293%20passed-14b8a6?style=flat-square)](https://github.com/ChokechaiXD/NovelClaw)
[![Python](https://img.shields.io/badge/python-3.12%2B-14b8a6?style=flat-square)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-20%2B-14b8a6?style=flat-square)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-14b8a6?style=flat-square)](LICENSE)
[![Module Coverage](https://img.shields.io/badge/module%20coverage-100%25-14b8a6?style=flat-square)](#test-suite)

|**Production-grade CN→TH translation pipeline** — LLM translation, quality scoring, glossary management, translation memory, and a premium dark-theme reader — all running on vanilla JS and Python with zero framework lock-in.

</div>
---

## Overview

NovelClaw is a complete system for translating Chinese web novels into Thai at scale —
combining a **translation pipeline** (LLM translation, glossary management, quality scoring, translation memory) with a **web reader** (dark theme SPA, responsive, mobile-first).

Built on the *Transmittor Principle*: preserve the author's voice, enforce mechanical purity.

### What it does

- **Translate** individual chapters or batch (1,000+) with resume support
- **Maintain** a tiered glossary (locked → reference → auto) across thousands of terms
- **Score** output quality via 8-dimension objective scorer
- **Cache** translations at block level (exact + fuzzy matching)
- **Read** in a premium dark theme reader on desktop or mobile

---

## Architecture

```
novelclaw/
│
├── novels/{slug}/              Novel data (chapters, glossary, sources)
├── tools/                      Python translation toolkit
│   ├── translate.py            Translation pipeline (CLI entry point)
│   ├── schema.py               Pydantic JSON schema (Chapter model)
│   ├── validation.py           CJK/EN/completeness validation gates
│   ├── glossary.py             Glossary YAML loader (cached LRU)
│   ├── translation_memory.py   Block-level cache (exact + fuzzy)
│   ├── progress.py             Resume progress tracking
│   ├── providers/              LLM provider abstraction (direct HTTP via Hermes config)
│   ├── scorer.py               8-dimension objective quality scorer
│
├── reader/                     Web reader (Node.js / Express)
│   ├── server.js               Backend API + chapter rendering
│   ├── public/                 Frontend (ITCSS + BEM + Vanilla JS)
│   │   ├── styles/             ITCSS 5-layer architecture
│   │   │   ├── 01-tokens.css   Design tokens (colors, type, spacing)
│   │   │   ├── 02-generic.css  Reset & normalize
│   │   │   ├── 03-elements.css HTML element defaults
│   │   │   ├── 04-components.css  BEM component classes
│   │   │   └── 05-utilities.css   Utility classes
│   │   ├── js/                 ES module pages
│   │   │   ├── app.js          Router + theme sync
│   │   │   ├── state.js        Observer-pattern store
│   │   │   ├── api.js          Fetch + cache layer
│   │   │   ├── components.js   Shared UI components
│   │   │   └── pages/          Page modules (home, novel, reader, admin, ...)
│   │   ├── design-system.css   Generated concatenation
│   │   └── index.html          Clean SPA shell
│   ├── config/brackets.json    Single-source bracket config
│   ├── lib/                    Reader utilities
│   └── services/validation.js  JS-side chapter validation
│
├── tests/                      293 tests (pytest)
├── docs/                       Documentation
├── pyproject.toml              Python package config
├── README.md                   This file
└── LICENSE                     MIT
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) (for LLM calls)

### Installation

**Python toolkit**

```bash
pip install -e .[test]
```

**Reader UI**

```bash
cd reader
npm install
```

### Translate a Chapter

```bash
# Single chapter with all features
python tools/translate.py 139 --score --json

# Batch translate (50 chapters, concurrent, resume-safe)
python tools/translate.py 140-190 --resume --concurrent 3 --json
```

### Start the Reader

```bash
cd reader && node server.js
# → http://localhost:4173
```

### Run Tests

```bash
python -m pytest tests/
cd reader && npm test
```

---

## Features

|| Feature | Flag | Description |
||---------|------|-------------|
|| **Translation** | `--tm` | LLM translates with glossary context + translation memory |
|| **Quality scoring** | `--score` | Score translation 0-100 across 8 dimensions |
|| **Translation Memory** | `--tm` | Block-level cache (L1 exact + L2 fuzzy) + skip-LLM for cached chapters |
|| **Resume** | `--resume` | Resume interrupted batch from progress file |
|| **Concurrent** | `--concurrent N` | Translate N chapters in parallel (max 5) |

### Glossary Tier System

```
locked.md     →  Priority 1 — Authoritative translations (manually curated)
reference.md  →  Priority 2 — Verified references (project canonical)
auto.md       →  Priority 3 — Auto-discovered terms (candidates, may be generic)
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `python tools/translate.py <ch>` | Translate chapter(s) with all features |
| `python tools/scorer.py chapters/ --source source/` | Quality scoring across 8 dimensions |
| `python tools/glossary.py --novel <slug> --load` | Export glossary as JSON |
| `python tools/translation_memory.py build\|stats\|lookup` | Translation memory management |

---

## Translation Pipeline

```
Source Text (CN Markdown)
    │
    ▼
┌──────────────────────────────────┐
│  Source Cleaner                   │
│  ├── Strip CJK artifacts          │
│  └── Normalize line endings       │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  TM Cache Check (--tm)          │
│  ├── Source hash match → skip LLM│
│  └── Cache miss → call LLM      │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  LLM Translation                 │
│  (prompt + glossary + style)    │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Python Parse & Assemble         │
│  ├── parse_translation_output()  │
│  └── CN strip                    │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Quality Validation              │
│  ├── Pydantic Schema check       │
│  ├── CJK/EN/completeness gates   │
│  └── 8-dim scorer (--score)     │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Save & Cache                    │
│  ├── TM cache update             │
│  └── Save NNNN.json              │
└──────────────────────────────────┘
```

---

## Reader UI

The web reader is a **pure-vanilla SPA** — no React, no framework, no build step.

### Architecture

| Layer | File(s) | Role |
|-------|---------|------|
| **Design Tokens** | `01-tokens.css` | CSS custom properties (4 themes: dark, light, sepia, ocean) |
| **Reset** | `02-generic.css` | Box-sizing, font smoothing |
| **Elements** | `03-elements.css` | HTML element defaults |
| **Components** | `04-components.css` | BEM classes for every UI component |
| **Utilities** | `05-utilities.css` | Skeleton, hidden, truncate helpers |
| **State** | `state.js` | Observer-pattern store (3 keys: state, settings, profile) |
| **Network** | `api.js` | Fetch + in-memory cache |
| **Components** | `components.js` | `el()`, Skeleton, Empty, Error, Toast |
| **Pages** | `pages/*.js` | Home, Novel Detail, Reader, Library, Search, Settings, Admin |

### Reader Features

- **Dark theme** by default with light, sepia, and ocean variants
- **Responsive** — sidebar collapses on mobile, reading mode on all screens
- **Chapter pagination** — range buttons (1-100, 101-200…)
- **Search** — find chapters by number or title
- **Admin** — dashboard, novel management, chapter table, glossary table
- **SVG icons** — no emoji in UI, brand-consistent masthead

---

## Test Suite

```
Module Coverage: 10/10 (100%)

Python (pytest):  121 tests  ─ ─ ─  2s total
Node (jest):  20+ tests (reader)

All pure-function tests — no LLM calls, no network, no Playwright.

Test suites:
  test_schema.py                  16 tests  Chapter schema validation
  test_validation.py              11 tests  CJK/EN/artifact leakage
  test_translate.py               10 tests  LLM parser, source cleaner
  test_glossary.py                 9 tests  Save/load roundtrip
  test_progress.py                 9 tests  Progress tracking
  test_translation_memory.py      26 tests  Exact + fuzzy cache
  test_frontend.py                 4 tests  HTTP smoke (no Playwright)
  test_edge_cases.py              23 tests  Real chapter validation
  ... and more
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **ITCSS + BEM** | Proven CSS architecture (Harry Roberts / NHS / Google). Low specificity, no cascade surprises, 0 regressions on rebuild. |
| **Vanilla JS SPA** | No framework lock-in. One ES module per page. Render speed scales with browser, not framework overhead. |
| **Observer State** | Single `settings.theme` source of truth — subscribe anywhere. No Redux, no reactivity library. |
| **JSON Chapter Schema** | Pydantic-validated. Replaces regex-parsed Markdown. Type-safe, drift-proof. |
| **Lazy Imports** | Heavy modules (quality scorer, agent coordinator) imported on first use, not at startup. |
| **Glossary as YAML** | Git-trackable, human-mergeable. One `glossary.yml` per novel, built from tiered Markdown. |

---

## Contributing

This is a personal project. If you find a bug or have a suggestion:

1. Open an issue on [GitHub](https://github.com/ChokechaiXD/NovelClaw/issues)
2. Or send a PR from a branch prefixed with your username

Keep translations mechanically pure and the reader free of framework rot. 🦀

---

## License

MIT © 2026 P Choke
