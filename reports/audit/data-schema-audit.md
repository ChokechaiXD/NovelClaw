# Data Schema Audit

## Chapter JSON (Canonical)
Sample: `novels/global-descent/chapters/0001.th.json`
Keys: ['novelId', 'chapterNo', 'sourceLang', 'targetLang', 'title', 'status', 'paragraphs', 'updatedAt']
  - `novelId`: str
  - `chapterNo`: int
  - `sourceLang`: str
  - `targetLang`: str
  - `title`: object(['translated'])
    - `translated`: str
  - `status`: str
  - `paragraphs`: array[134]
  - `updatedAt`: str

## chapters.json
Type: dict
Keys: ['slug', 'totalChapters', 'chapters']
Chapters: 1239
Chapter keys: ['num', 'title', 'hasCn', 'hasTh', 'status']

## novel.json
Keys: ['slug', 'title', 'author', 'sourceLang', 'targetLang', 'status', 'totalChapters', 'translatedChapters', 'description', 'updatedAt', 'translatedTitle']

## Job JSON Schema
Sample `done/translate-20260623-151736.json`:
  - `id`: str
  - `slug`: str
  - `mode`: str
  - `force`: bool
  - `state`: str
  - `chapters`: array[1]
  - `current`: int
  - `done`: array[1]
  - `failed`: array[0]
  - `needs_review`: array[0]
  - `createdAt`: str
  - `updatedAt`: str

## Glossary Schema

## Files Without Formal JSON Schema
No `tools/schema/` directory — no formal JSON schemas yet