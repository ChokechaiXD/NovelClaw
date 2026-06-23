# API Route Audit
File: `reader/server.js` — 498 lines

## All Routes
| Method | Path | Protected | Line |
|--------|------|-----------|------|
| GET | `/api/admin/jobs` | ✅ | 361 |
| GET | `/api/admin/logs/:slug/:num` | ✅ | 375 |
| POST | `/api/invalidate-cache` | ✅ | 334 |
| GET | `/api/novel/:slug/chapter/:num` | ❌ | 157 |
| POST | `/api/novel/:slug/chapter/:num/delete` | ✅ | 322 |
| POST | `/api/novel/:slug/chapter/:num/save` | ✅ | 267 |
| GET | `/api/novel/:slug/chapters` | ❌ | 117 |
| GET | `/api/novel/:slug/chapters/search` | ❌ | 125 |
| GET | `/api/novel/:slug/characters` | ✅ | 240 |
| POST | `/api/novel/:slug/delete` | ✅ | 260 |
| GET | `/api/novel/:slug/glossary` | ❌ | 197 |
| GET | `/api/novel/:slug/glossary/data` | ✅ | 204 |
| POST | `/api/novel/:slug/glossary/save` | ✅ | 216 |
| GET | `/api/novel/:slug/meta` | ❌ | 101 |
| GET | `/api/novel/:slug/source/:num` | ❌ | 186 |
| POST | `/api/novel/update` | ✅ | 249 |
| GET | `/api/novels` | ❌ | 76 |

## Unguarded Admin Routes (Missing requireAdmin)

## Unguarded Write/Delete Routes (No requireAdmin)

## Param Validation Check
Routes with params:
- `/api/admin/logs/:slug/:num` — params: slug, num
- `/api/novel/:slug/chapter/:num` — params: slug, num
- `/api/novel/:slug/chapter/:num/delete` — params: slug, num
- `/api/novel/:slug/chapter/:num/save` — params: slug, num
- `/api/novel/:slug/chapters` — params: slug
- `/api/novel/:slug/chapters/search` — params: slug
- `/api/novel/:slug/characters` — params: slug
- `/api/novel/:slug/delete` — params: slug
- `/api/novel/:slug/glossary` — params: slug
- `/api/novel/:slug/glossary/data` — params: slug
- `/api/novel/:slug/glossary/save` — params: slug
- `/api/novel/:slug/meta` — params: slug
- `/api/novel/:slug/source/:num` — params: slug, num

## Error Response Shape
JSON error responses found: 32