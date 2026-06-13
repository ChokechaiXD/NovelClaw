# Folder Structure — NovelClaw

> How translated chapters, source files, and context files are organized
> across the NovelClaw project. Designed to scale to 1,000+ chapters per
> novel and multiple novels in parallel.

## Top-level layout

```
NovelClaw/
├── README.md
├── PROMPT.md                       (Mika's translation rules)
├── STRUCTURE.md                    (this file)
├── run.bat                         (Windows launcher for the reader)
├── scrape_chapters.py              (one-time source scraper)
├── reader/                         (the web reader, ~150 LOC)
│   ├── server.js
│   └── public/
└── novels/                         (per-novel workspaces)
    └── <slug>/                     (one folder per novel)
        ├── meta.md                 (title, author, status)
        ├── style.md                (per-novel style choices)
        ├── summary.md              (cumulative plot summary)
        ├── progress.md             (cross-session tracking)
        ├── characters.md           (character profiles)
        ├── glossary/               (split by priority for prompt size)
        │   ├── locked.md           (must-use, style.md mandated)
        │   ├── reference.md        (recurring NPCs/items/skills)
        │   ├── auto.md             (one-off terms)
        │   └── index.md            (master view)
        ├── chapters/               (translated chapters, Thai)
        │   ├── 0001.md
        │   ├── 0002.md
        │   └── NNNN.md
        └── source/                 (original CN/EN source, for reference)
            ├── 0001.md
            └── NNNN.md
```

## Why this structure

### Multi-novel support
- Each novel lives in its own `<slug>/` folder
- No cross-contamination of glossary, characters, or styles
- Adding a new novel: `mkdir novels/<new-slug>/` and start
- The reader auto-discovers all novels in `novels/`

### 1,000+ chapter support
- Flat file structure under `chapters/` — modern file systems handle 10,000+ files per folder without issue
- 4-digit zero-padded prefix (`0001.md`, `1239.md`) keeps files sorted naturally and supports up to 9,999 chapters per novel
- The reader uses `fs.readdir` to list chapters — O(n) but n ≤ ~10,000 is fine
- For novels >5,000 chapters (rare), we can migrate to a hierarchical scheme (see "Future scaling" below)

### Reading UX
- Sidebar chapter list (in the reader) shows all chapters as `0001 ตอนที่ 1`
- Click any chapter to load
- Keyboard: `←` / `→` to navigate

## Future scaling (>5,000 chapters per novel)

If a novel ever exceeds ~5,000 chapters (rare for web novels, but possible for very long serials), we have two options:

**Option A: Volume sub-folders** (recommended)
```
chapters/
├── vol-01/0001-0500.md
├── vol-02/0501-1000.md
└── vol-03/1001-NNNN.md
```
- Reader needs a small update to recurse into `vol-XX/`
- Easy to back up by volume
- Human-friendly organization

**Option B: Thousand-grouped sub-folders**
```
chapters/
├── 0001-0999/
├── 1000-1999/
└── 2000-NNNN/
```
- Cleaner numeric hierarchy
- Reader needs recursion logic
- Backups are by ~1000 chapters

**Decision: not needed yet.** Current novel (全球降臨) has 1,239 chapters — flat is fine. Migrate to Option A if we ever hit 5,000+.

## Backup / git strategy

- `NovelClaw/novels/<slug>/chapters/` is the **primary translation work** — commit to git regularly
- `NovelClaw/novels/<slug>/source/` is reference material — can be `.gitignore`d (regenerate via `scrape_chapters.py` from URL)
- `glossary.md`, `characters.md`, `summary.md`, `progress.md` — commit (these are the long-term memory)
- `meta.md`, `style.md` — commit (project config)
- `run.bat`, `reader/`, `scrape_chapters.py`, `PROMPT.md`, `README.md` — commit (project infrastructure)

## Migration history

- 2026-06-13: Initial structure, flat `chapters/` per novel. Designed to scale to 1,239 chapters for 全球降臨. Reader auto-discovers.
