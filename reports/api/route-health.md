# API Route Health

**Date**: 2026-06-24
**Base URL**: `http://localhost:4173`
**Test tool**: `reader/tests/test-api.js`

## Routes tested (10/10 ✅)

| # | Route | Status | Notes |
|---|-------|--------|-------|
| 1 | `GET /api/novels` | ✅ | Returns novel list with translatedTitle |
| 2 | `GET /api/novel/:slug/chapters` | ✅ | Chapter list with hasTh flags |
| 3 | `GET /api/novel/:slug/chapter/:num?lang=th` | ✅ | Thai paragraph content |
| 4 | `GET /api/novel/:slug/chapter/:num?lang=cn` | ✅ | Chinese source content |
| 5 | `GET /api/novel/:slug/glossary/data` | ✅ | Returns term list |
| 6 | `GET /api/novel/:slug/chapters/search?mode=content` | ✅ | Full-text search |
| 7 | `POST .../chapter/:num/save` | ✅ | Admin save (temp) |
| 8 | Chapters includes temp after save | ✅ | Index rebuilt |
| 9 | `POST .../chapter/:num/delete` | ✅ | Admin delete (temp) |
| 10 | Chapters excludes temp after delete | ✅ | Cleanup verified |

## Response shape (standardized)

Success:
```json
{ "ok": true, "data": { ... } }
```

Error:
```json
{ "ok": false, "error": { "code": "INVALID_SLUG", "message": "..." } }
```

## Cache behaviour

- `/api/novels`: 30s server cache (`X-Cache: HIT|MISS`)
- `/api/novel/:slug/chapters`: 60s server cache
- Chapter content: `Cache-Control: public, max-age=20, stale-while-revalidate=60`
- Chapter content (client): 10 min in-memory cache (`Api._chapterContentCache`)
