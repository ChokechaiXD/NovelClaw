# NovelClaw Architecture v2.0

> Design System + Component Tree + Data Flow
> Stack: Express.js + Vanilla JS + SQLite FTS5 + Dark Theme

---

## Part 1: Design System

### 1.1 Color Palette

Theme: Dark Mode (Blue-Black)

| Token | Hex | Usage |
|-------|-----|-------|
| --bg-deep | #06060c | Page background |
| --bg-primary | #0c0c14 | Main surface |
| --bg-secondary | #111118 | Sidebar, cards |
| --bg-tertiary | #16161f | Hover, inputs |
| --bg-elevated | #1a1a26 | Elevated cards |
| --border | #222230 | Default borders |
| --border-hover | #2e2e3e | Border hover |
| --accent | #38bdf8 | Primary accent |
| --text-primary | #e8ecf1 | Primary text |
| --text-secondary | #8b93a7 | Secondary text |
| --text-muted | #545d72 | Muted text |
| --success | #34d399 | Success state |
| --warning | #fbbf24 | Warning state |
| --error | #f87171 | Error state |
| --info | #60a5fa | Info state |
| --purple | #a78bfa | Accent secondary |

### 1.2 Typography

--font-sans: Inter, system-ui, sans-serif
--font-mono: JetBrains Mono, SF Mono, monospace
Scale: 9px(badges) 10px(meta) 11px(nav) 12px(body) 13px(titles) 14px(headings) 20px(metrics) 24px(page)

---

## Part 2: Component Tree

Layout Shell: App > Topbar(Logo+ViewToggle+NotifBell+Profile) + Sidebar(left 280px: Nav,QuickActions,SessionList) + Main(flex-1: Header+ContentArea) + RightSidebar(300px: Metrics+Activity)

Pages by Route:
- Home: HeroBanner(stats) + ContinueReading(cards+progress) + LatestUpdates + Recommended + GenreFilter
- Novel Detail: Cover + Meta(Title CN/TH, Author, Tags, Stats) + Actions(Read,Save,Share) + Synopsis + ChapterList(virtual scroll)
- Reader: Toolbar + Content(ParagraphBlock) + Footer(Prev,Progress,Next) + SettingsPanel(Font,Size,Spacing,BG,Brightness)
- Library: Grid(cards+progress) + Filters(Status,Genre,Sort) + Collections
- Search: Bar(autocomplete) + HotKeywords + Results + AdvancedPanel(Tag,Status,ChapterRange,Sort)
- Ranking: Tabs(daily/weekly/monthly/all) + List(rank+cover+title+score+change)
- Profile: Header(Avatar,Username,Level,Premium) + Stats(chart) + Genre(pie) + Achievements + Streak
- Translation Center: Queue(jobs) + Workspace(CN|TH side-by-side,editable,QualityScore) + Compare(diff)
- Admin: StatsCards + TrafficChart(7day) + NovelTable(CRUD)
- Social: Reviews(Rating+Distribution+List+Form) + Comments + Notifications

Shared Components: Btn(primary/secondary/ghost/danger) Card Badge Toggle Slider Modal Toast Tooltip Skeleton Pagination Dropdown Tabs ProgressBar Avatar RatingStars Chip

---

## Part 3: Data Flow Architecture

Endpoints (reader/server.js 889 lines):

Current:
GET /api/novels | GET /api/novel/:slug/chapters | GET /api/novel/:slug/chapter/:num
GET /api/novel/:slug/chapters/search?q= | POST save/delete chapter | POST glossary/save
GET /api/novel/:slug/source/:num | GET /api/novel/:slug/characters
GET /api/lang | GET /api/lang/:lang | POST /api/invalidate-cache

New endpoints needed:
GET/POST reviews + comments + bookmarks | GET user/profile + history + notifications
GET /api/ranking?period= | POST /api/translate/:slug/:num + GET /api/translate/status/:id

Frontend State (app.js IIFE):
Current: { novel, chapters, index, num, searchQuery }
Target: { route, novel, chapters, currentChapter, user, sidebar, theme, readerSettings, searchQuery, translationQueue, notifications }

Routing: Hash-based SPA
#home #novel/:slug #novel/:slug/:num #library #search #ranking
#profile #history #bookmarks #downloads #notifications #settings
#admin #admin/novels #admin/translate #admin/translate/:job

Patterns:
Load: hashchange -> handleRoute -> api(endpoint) -> renderHTML -> attachEvents
Save: click -> gatherFormData -> POST /api/... -> showToast -> updateUI
Translate: trigger -> POST /api/translate -> poll GET status until done -> notify

---

## Part 4: Build Order

Phase A1 - Reader 2.0 (Week 1)
1. CSS Design System variables + base styles
2. Layout shell: Topbar + Sidebar + Main + RightSidebar
3. Hash-based router
4. Home Dashboard (HeroBanner + ContinueReading + LatestUpdates)
5. Novel Detail (cover, meta, synopsis, chapter list)
6. Reader Page with settings panel
7. Library with progress bars + filters

Phase A2 - Discovery (Week 2)
8. Search + hot keywords + advanced filters
9. Ranking system
10. Profile + stats + achievements
11. History + Bookmarks

Phase A3 - Translation Web UI (Week 2-3)
12. Translation Queue
13. Translation Workspace (side-by-side CN/TH)
14. Translation Compare (diff + quality)

Phase A4 - Admin (Week 3)
15. Admin Dashboard + charts
16. Novel Management + CRUD

Phase B - Social (Week 4+)
17. Reviews + Ratings
18. Chapter Comments
19. Notifications system
20. Downloads (offline)
21. Achievements gamification

Phase C - Polish (Ongoing)
22. Mobile responsive
23. Micro-interactions + animations
24. Performance optimization
25. Full i18n (wire req.t() into templates)
