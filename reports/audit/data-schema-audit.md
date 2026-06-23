# Data Schema Audit — Phase A

## Current State

NovelClaw uses multiple JSON/MD files for data. No formal JSON schema validation exists.

## File Formats

### novel.json (Canonical metadata)
```json
{
  "slug": "global-descent",
  "title": "全球降临",
  "translatedTitle": "Global Descent: ฉันเกิดใหม่มีระบบเซียน",
  "author": "作者",
  "sourceLang": "cn",
  "targetLang": "th",
  "status": "ongoing",
  "totalChapters": 1239,
  "description": "...",
  "updatedAt": "2026-06-23T00:00:00.000Z"
}
```
**Risk**: No schema validation. extra fields silently pass.

### chapters.json (Chapter index)
```json
{
  "slug": "global-descent",
  "totalChapters": 1239,
  "chapters": [
    { "num": 1, "title": "...", "hasCn": true, "hasTh": true, "status": "translated" },
    ...
  ]
}
```
**Risk**: `status` field values not constrained.

### Chapter JSON (Canonical: `{num}.th.json`)
```json
{
  "novelId": "global-descent",
  "chapterNo": 139,
  "sourceLang": "cn",
  "targetLang": "th",
  "title": {
    "source": "第139章",
    "translated": "ตอนที่ 139"
  },
  "status": "translated",
  "paragraphs": ["...", "1239"],
  "updatedAt": "2026-06-24T00:00:00.000Z"
}
```
**Risk**: No validation that `chapterNo` matches filename. No `paragraphs` max length.

### search-index.th.json (Content search cache)
```json
{
  "slug": "global-descent",
  "lang": "th",
  "updatedAt": "...",
  "entries": [
    { "num": 139, "title": "...", "text": "..." }
  ]
}
```
**Risk**: Can grow large. `text` is capped at 10,000 chars per entry in code but schema doesn't enforce.

### Glossary (glossary.json)
```json
{
  "terms": [
    { "source": "曹星", "thai": "เฉาซิง", "lock": "locked", "category": "name" }
  ]
}
```
**Risk**: `lock` field values not constrained (should be locked/reference/unlocked).

## Current Validation

### JS-side: services/validation.js
- Validates Thai/CJK ratio
- Checks specific name translations
- Checks bracket balance
- Returns `{ valid, errors, warnings, info, score }`

### Python-side: tools/validation.py
- Python-based schema/validation (separate from JS)

### What's missing
1. **No JSON Schema files** — `/tools/schema/` doesn't exist yet
2. **No CI schema validation** — CI doesn't check data files
3. **No automatic repair for known drift**
4. **No `novel.json` field type constraints**
5. **No `chapters.json` status enum validation** (`translated` / `source_only` / `legacy` are the valid values)

## Schema Files Needed (from Roadmap Phase H)

- `tools/schema/chapter.schema.json`
- `tools/schema/novel.schema.json`
- `tools/schema/job.schema.json`
- `tools/schema/needs-review.schema.json`
- `tools/schema/glossary.schema.json`
