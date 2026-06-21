# NovelClaw Reader — Rebuild Plan

## ปัญหาที่จะแก้

| ปัญหาเดิม | Root cause | วิธีแก้ |
|-----------|------------|--------|
| CSS 2800+ lines duplicate 2 copies | Patch ซ้ำซ้อน | เขียนใหม่ทั้งหมด — tokens → components |
| page-renderers.js 2200+ lines รวมทุกหน้า | ไฟล์เดียวรวมทุก renderer | แยกเป็น pages/*.js module files |
| Data progress/theme/history state สับสน | localStorage keys เดียวกัน | แยก storage เป็น sections: reader, settings, profile |
| Theme state หลายแหล่ง | reader + sidebar toggle sync ไม่ตรง | ตั้ง theme จาก `settings` key เดียว |
| History แสดง Invalid Date + theme key | filter ไม่ได้ exclude `"theme"` | HISTORY_KEYS + date fallback |
| Profile/Settings UI ยังเป็น raw HTML | ไม่มี component library | shared components module |

## โครงสร้างใหม่

```
reader/public/
├── index.html            ← App Shell ลดรูป (sidebar skeleton + main + rightbar)
├── styles/
│   ├── tokens.css        ← CSS variables, type scale, brand colors
│   ├── layout.css        ← App Shell, sidebar, main, rightbar, responsive
│   └── components.css    ← nav-item, card, badge, button, hero, form, table
├── js/
│   ├── app.js            ← Router, init, theme sync, shared helpers
│   ├── state.js          ← loadState/saveState/loadSettings/saveSettings
│   ├── components.js     ← el(), showSkeleton(), showEmpty(), showError()
│   ├── api.js            ← getNovels(), getChapters(), fetch wrapper
│   └── pages/
│       ├── home.js       ← renderHome
│       ├── novel.js      ← renderNovelDetail
│       ├── reader.js     ← renderReader
│       ├── library.js    ← renderLibrary
│       ├── history.js    ← renderHistory (fixed)
│       ├── settings.js   ← renderSettings (theme, font, etc.)
│       ├── profile.js    ← renderProfile
│       ├── admin.js      ← renderAdmin + AdminNovels + AdminChapters
│       └── glossary.js   ← renderGlossary
└── design-system.css     ← GENERATED: tokens + layout + components concatenated
```

## Component Library (shared)

| Component | CSS class | Description |
|-----------|-----------|-------------|
| `el(tag, attrs, ...children)` | — | DOM builder (มีอยู่แล้ว) |
| `showSkeleton(container, type)` | `.skel-line/card/block` | Loading state (มีอยู่แล้ว) |
| `showEmpty(container, title, desc)` | `.empty-state` | Empty + mascot (มีอยู่แล้ว) |
| `showError(container, title, desc)` | `.error-state` | Error + retry (มีอยู่แล้ว) |
| `Section(title, link, content)` | `.dash-section` | Section wrapper |
| `HeroBanner(novel)` | `.hero-banner` | Teal gradient hero |
| `Card(title, meta, progress)` | `.continue-card` | Novel card |
| `Badge(text, variant)` | `.badge` | Status badge |
| `Button(text, variant)` | `.btn` | Button component |
| `FormField(label, input)` | `.form-field` | Form wrapper |
| `DataTable(headers, rows)` | `.admin-table` | Admin table |
| `NavItem(icon, label, page)` | `.nav-item` | Sidebar item |

## Data Schema

```js
// State (novelclaw-reader-v1) — reading progress only
state = {
  "global-descent": { 1: 1712345678000, 2: 1712345679000 },  // chapter → timestamp
  "global-descent-last": 125  // last read chapter
}

// Settings (novelclaw-settings)
settings = {
  theme: "dark",          // dark | light | sepia | amoled
  fontSize: 17,
  fontStep: 0,
  autoTranslate: true,
  sidebarCollapsed: false,
  rightbarCollapsed: false
}

// Profile (novelclaw-profile)
profile = {
  name: "P'Choke",
  email: "chokechai@gmail.com",
  role: "admin",
  avatarColorIndex: 0,
  tokensUsed: 0
}

// Novel (from API /api/novels)
novel = {
  slug, title, author, source_lang, target_lang,
  chapterCount: 1239,         // total JSON files
  translatedChapters: 138,    // files with output_lang
  totalChapters: 1239,        // from meta.total_chapters
  status: "ongoing",          // ongoing | complete | paused
  meta: "---\ntitle: ...\n---"
}

// Derived
translationProgress = translatedChapters / totalChapters
readingProgress = chaptersRead / totalChapters
```

## Execution Order

1. **Create `styles/` directory** — tokens.css, layout.css, components.css
2. **Create `js/state.js`** — separated storage (state, settings, profile)
3. **Create `js/api.js`** — getNovels, getChapters with caching
4. **Create `js/components.js`** — shared UI components
5. **Create `js/app.js`** — router, init, theme sync, sidebar events
6. **Create page files** — home, novel, reader, library, search, history, settings, profile, admin, glossary
7. **Rebuild `index.html`** — cleaner Shell, fewer inline styles
8. **Update `server.js` Cache-Control** — bust old CSS/JS paths
9. **Verify** — navigate every page, check console errors, check History/Theme
