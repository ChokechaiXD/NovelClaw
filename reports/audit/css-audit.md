# CSS Audit
File: `design-system.css` — 1575 lines, 60,587 bytes

## Section Breakdown
- `═` — 526 lines
- `Fonts` — 131 lines
- `Sidebar Brand (compact — MIKA spec)` — 62 lines
- `Header (Top Bar)` — 52 lines
- `Toggle Switch` — 43 lines
- `Reader Page` — 41 lines
- `Sidebar (deprecated — use .c-app__sidebar)` — 40 lines
- `Card Grid` — 38 lines
- `Nav Item` — 38 lines
- `App Shell (CSS Grid 3-column)` — 34 lines
- `Admin` — 34 lines
- `Hero` — 32 lines
- `Detail (Novel Page)` — 32 lines
- `App shell children` — 31 lines
- `Floating exit button (book mode)` — 30 lines
- `Reader nav` — 23 lines
- `Main Content` — 22 lines
- `C-Toolbar (reader nav bar)` — 22 lines
- `Buttons` — 21 lines
- `Search` — 21 lines
- `Reader content (backward compat, kept for content)` — 20 lines
- `RC = Right Column` — 20 lines
- `New Updates` — 19 lines
- `Popular` — 19 lines
- `Nav HR (styled divider)` — 19 lines
- `Reader markers` — 18 lines
- `Reader progress bar (thin line at top)` — 17 lines
- `Settings` — 17 lines
- `Empty / Error States` — 17 lines
- `Stat block (system messages, game stats)` — 14 lines
- `Avatar` — 14 lines
- `List` — 12 lines
- `Profile` — 12 lines
- `Toast` — 12 lines
- `Section` — 11 lines
- `Section Label` — 11 lines
- `Reader meta (font controls)` — 9 lines
- `Page Visibility (SPA — CRITICAL: hides all pages, shows one)` — 8 lines
- `C-Content (main scrollable area)` — 7 lines
- `Skeleton` — 7 lines
- `Toggle` — 6 lines
- `Progress Bar` — 6 lines
- `Toggle wrapper` — 4 lines
- `Pagination` — 3 lines

## Inline Styles in JS (to migrate to classes)
Total inline styles: 108
- `app.js`: `font-size:11px;color:var(--c-text-muted);padding:8px 0;...`
- `components.js`: `width:100%;height:100%;border-radius:var(--radius);display:b...`
- `admin.js`: `margin-top:var(--space-md);...`
- `home.js`: `width:14px;height:14px;margin-right:4px;vertical-align:-2px;...`
- `novel.js`: `background:linear-gradient(135deg,hsl(${enriched.hue},70%,40...`
- `pages.js`: `width:16px;height:16px;margin-right:6px;vertical-align:-2px;...`
- `reader.js`: `width:18px;height:18px;...`

## Hardcoded Colors Outside Token Variables
Total unique color values: 83
Colors outside :root tokens: 59

CSS variables defined: 256