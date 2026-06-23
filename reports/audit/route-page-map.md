# Route / Page Map — Phase A Audit

## Server API Routes

| Method | Route | Auth | Handler | File |
|--------|-------|------|---------|------|
| GET | `/api/novels` | No | novelRepo.listNovels() | server.js:84 |
| GET | `/api/novel/:slug/meta` | No | novelRepo.getNovelMeta() | server.js:109 |
| GET | `/api/novel/:slug/chapters` | No | chapterRepo.listChapters() | server.js:125 |
| GET | `/api/novel/:slug/chapters/search` | No | searchService.searchTitle/Content | server.js:133 |
| GET | `/api/novel/:slug/chapter/:num` | No | chapterRepo.getChapter() | server.js:165 |
| GET | `/api/novel/:slug/source/:num` | No | readTextOrNull() | server.js:194 |
| GET | `/api/novel/:slug/glossary` | No | readTextOrNull() | server.js:205 |
| GET | `/api/novel/:slug/glossary/data` | No | readTextOrNull() | server.js:212 |
| POST | `/api/novel/:slug/glossary/save` | requireAdmin | spawn(glossary.py) | server.js:224 |
| GET | `/api/novel/:slug/characters` | No | readTextOrNull() | server.js:248 |
| POST | `/api/novel/update` | requireAdmin | novelRepo.saveNovelMeta() | server.js:257 |
| POST | `/api/novel/:slug/delete` | requireAdmin | novelRepo.deleteNovel() | server.js:268 |
| POST | `/api/novel/:slug/chapter/:num/save` | requireAdmin | validate → saveChapter → rebuildIndex | server.js:275 |
| POST | `/api/novel/:slug/chapter/:num/delete` | requireAdmin | deleteChapter → rebuildIndex | server.js:330 |
| POST | `/api/invalidate-cache` | requireAdmin | chapterRepo.invalidateAll() | server.js:342 |
| GET | `/api/admin/jobs` | requireAdmin | readJsonDir() | server.js:369 |
| GET | `/api/admin/logs/:slug/:num` | requireAdmin | readDir + readFile | server.js:383 |
| GET | `*` | No | SPA fallback (index.html) | server.js:503 |

## Frontend Routes (Hash Router in app.js)

| Hash Route | Handler | Page Container | Condition |
|------------|---------|----------------|-----------|
| `#home` | HomePage.render | `page-home` | Active by default |
| `#library` | LibraryPage.render | `page-library` | |
| `#search` | SearchPage.render | `page-search` | |
| `#novel/:slug` | NovelPage.render | `page-novel-detail` | No num param |
| `#novel/:slug/:num` | ReaderPage.render | `page-reader` | Has num param |
| `#ranking` | RankingPage.render | `page-ranking` | |
| `#profile` | ProfilePage.render | `page-profile` | |
| `#history` | HistoryPage.render | `page-history` | |
| `#bookmarks` | BookmarksPage.render | `page-bookmarks` | Bookmarked in admin.js |
| `#settings` | SettingsPage.render | `page-settings` | |
| `#admin` | AdminDashboardPage.render | `page-admin` | Defaults to dashboard |
| `#admin/jobs` | AdminJobsPage.render | `page-admin-jobs` | |
| `#admin/novels` | AdminNovelsPage.render | `page-admin-novels` | |
| `#admin/chapters` | AdminChaptersPage.render | `page-admin-chapters` | |
| `#admin/glossary` | AdminGlossaryPage.render | `page-admin-glossary` | |
| `#admin/novel-edit` | AdminNovelEditPage.render | `page-admin-novel-edit` | |
| `#admin/logs/:slug/:num` | AdminLogsPage.render | `page-admin-logs` | |

## Page Containers in index.html

All 17 page containers exist → **100% route/container match** ✓

```
page-home          page-novel-detail   page-reader
page-library       page-search         page-ranking
page-profile       page-history        page-bookmarks
page-settings      page-admin          page-admin-novels
page-admin-chapters page-admin-novel-edit page-admin-jobs
page-admin-logs    page-admin-glossary
```

## Issues Found

### Minor: Admin Nav tabs missing "logs"
`renderAdminNav()` in admin.js only defines 5 tabs: dashboard, jobs, novels, chapters, glossary.
The logs page (`#admin/logs/:slug/:num`) has no nav tab → clicking to logs page shows no active tab highlight, and no way to navigate back via tabs.

### Minor: AdminGlossaryPage hardcoded to first novel
```js
const slug = novels[0]?.slug;  // line 209
```
Always loads glossary for the first novel only. Should allow novel selection.

### AdminNovelEditPage incomplete
Only shows title + author fields. Missing source_lang, target_lang, status, total_chapters, description — despite the API endpoint supporting all of them.
