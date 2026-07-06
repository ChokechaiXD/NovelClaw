# NovelClaw — System Architecture

## Overview

NovelClaw = Chinese-to-Thai web novel translation toolkit.
ประกอบด้วย 2 ส่วนหลัก:

- **Python tools** (`tools/`) — translation pipeline, validation, glossary, orchestrator
- **Reader** (`reader/`) — Express.js web reader (ITCSS + ESM frontend, no framework)

## Data Flow

```
Source chapters (scraped from qidian.com)
    ↓
Python tools / novelctl
    ↓   (translate.py → LLM → parse → validate)
    ↓
novels/{slug}/chapters/{num}.th.json
    ↓
Reader API (server.js)
    ↓
Frontend (vanilla JS, hash routing)
    ↓
Display (inline markers → styled HTML)
```

## Core Decisions (stable, do not change)

| Decision | Rationale |
|----------|-----------|
| LLM outputs plain text, Python assembles JSON | No JSON mode needed — simpler prompts, fewer failures |
| Per-chapter JSON fetch | Zero per-file I/O for listing, instant chapter loads |
| User state in localStorage | No backend auth needed, fast, portable |
| ITCSS 5-layer + BEM | Organized CSS, no framework lock-in |
| Vanilla JS ES Modules | Zero build step, no bundler, instant load |
| Observer-pattern Store | Predictable state, zero jQuery, no React |

## File Layout

```
tools/
  novelctl.py          — CLI entry point
  orchestrator/        — Command dispatch, jobs, locks, runner
  translate.py         — LLM translation (never call directly)
  validate_data.py     — JSON schema validation
  schema/              — JSON Schema files (*.schema.json)

reader/
  server.js            — Express API (523 lines)
  lib/                 — paths, chapter-repo, novel-repo, search-service, blocks, brackets
  public/
    index.html         — SPA shell with SVG sprite
    design-system.css  — Single CSS file (ITCSS)
    js/
      app.js           — Router, theme, sidebar, init
      api.js           — Network layer with cache
      components.js    — UI helpers (Ui.*)
      state.js         — Store (Observer pattern)
      pages/           — One file per page feature

novels/{slug}/
  novel.json           — Metadata
  chapters.json        — Chapter index (fast path)
  chapters/{num}.{lang}.json  — Per-chapter content
```

## Key Contracts

- `novelctl.py` is the **single command center** — never call `translate.py` directly
- Chapter file format = `{pad(4)}.{lang}.json` (e.g. `0139.th.json`)
- All API errors return `{ ok: false, error: { code, message } }`
- All admin routes require `Authorization: Bearer <ADMIN_TOKEN>` when HOST=0.0.0.0
