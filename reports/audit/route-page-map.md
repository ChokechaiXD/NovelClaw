# NovelClaw Route/Page Map

## API Routes (server.js)
| Method | Path | Protected |
|--------|------|-----------|
| GET | `/api/admin/jobs` | ✅ |
| GET | `/api/admin/logs/:slug/:num` | ✅ |
| POST | `/api/invalidate-cache` | ✅ |
| GET | `/api/novel/:slug/chapter/:num` | ❌ |
| POST | `/api/novel/:slug/chapter/:num/delete` | ✅ |
| POST | `/api/novel/:slug/chapter/:num/save` | ✅ |
| GET | `/api/novel/:slug/chapters` | ❌ |
| GET | `/api/novel/:slug/chapters/search` | ❌ |
| GET | `/api/novel/:slug/characters` | ❌ |
| POST | `/api/novel/:slug/delete` | ✅ |
| GET | `/api/novel/:slug/glossary` | ❌ |
| GET | `/api/novel/:slug/glossary/data` | ❌ |
| POST | `/api/novel/:slug/glossary/save` | ✅ |
| GET | `/api/novel/:slug/meta` | ❌ |
| GET | `/api/novel/:slug/source/:num` | ❌ |
| POST | `/api/novel/update` | ✅ |
| GET | `/api/novels` | ❌ |

## Page Containers (index.html)
Found: 18 containers
- `page-admin`
- `page-admin-chapters`
- `page-admin-glossary`
- `page-admin-jobs`
- `page-admin-logs`
- `page-admin-novel-edit`
- `page-admin-novels`
- `page-bookmarks`
- `page-history`
- `page-home`
- `page-library`
- `page-novel-detail`
- `page-profile`
- `page-ranking`
- `page-reader`
- `page-search`
- `page-settings`
- `page-title`

## Registered Routes (app.js)
Router.register: 10
Hash page check: 7
- `admin`
- `bookmarks`
- `history`
- `home`
- `library`
- `novel`
- `profile`
- `ranking`
- `search`
- `settings`

## Admin Sub-Routes
- `admin/dash` → `AdminDashboardPage`
- `admin/jobs` → `AdminJobsPage`
- `admin/novels` → `AdminNovelsPage`
- `admin/chapters` → `AdminChaptersPage`
- `admin/glossary` → `AdminGlossaryPage`
- `admin/novel-edit` → `AdminNovelEditPage`
- `admin/logs` → `AdminLogsPage`

## Nav Pages
- `admin`
- `bookmarks`
- `history`
- `home`
- `library`
- `profile`
- `ranking`
- `search`
- `settings`

## Gaps
Containers without routes: {'novel-detail', 'admin-chapters', 'admin-novels', 'admin-novel-edit', 'title', 'reader', 'admin-logs', 'admin-jobs', 'admin-glossary'}
Routes without containers: {'novel'}