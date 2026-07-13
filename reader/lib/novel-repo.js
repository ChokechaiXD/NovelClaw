/**
 * lib/novel-repo.js — Novel metadata operations
 *
 * novel.json is the canonical source of truth.
 */

const fs = require('node:fs/promises');
const { novelDir, novelJsonPath, NOVELS_DIR, assertValidSlug } = require('./paths');
const { _cache, invalidateAll } = require('./chapter-repo');

// ── List all novels ────────────────────────────────────────────────

async function listNovels() {
  try {
    const entries = await fs.readdir(NOVELS_DIR, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory())
      .map((d) => d.name)
      .sort();
  } catch (err) {
    if (err.code === 'ENOENT') return [];
    throw err;
  }
}
exports.listNovels = listNovels;

// ── Read novel metadata ────────────────────────────────────────────

async function getNovelMeta(slug) {
  assertValidSlug(slug);
  const mk = 'meta:' + slug;
  if (_cache.has(mk)) return _cache.get(mk);

  let meta;
  try {
    const raw = await fs.readFile(novelJsonPath(slug), 'utf8');
    meta = JSON.parse(raw);
    meta.slug = meta.slug || slug;
    meta.title = meta.title || meta.sourceTitle || slug;
    meta.translated_title = meta.translatedTitle || '';
    meta.source_lang = meta.sourceLang || 'cn';
    meta.target_lang = meta.targetLang || 'th';
    meta.total_chapters = String(meta.totalChapters || 0);
    meta.description = meta.description || '';
    _cache.set(mk, meta);
    return meta;
  } catch (err) {
    if (err.code !== 'ENOENT') throw err;
  }

  meta = { slug, title: slug, source_lang: 'cn', target_lang: 'th', description: '' };
  _cache.set(mk, meta);
  return meta;
}
exports.getNovelMeta = getNovelMeta;

// ── Save novel metadata ────────────────────────────────────────────

async function saveNovelMeta(slug, data) {
  assertValidSlug(slug);
  const novelDirPath = novelDir(slug);
  let existing = {};
  try {
    existing = JSON.parse(await fs.readFile(novelJsonPath(slug), 'utf8'));
  } catch {}

  const novelData = {
    ...existing,
    ...data,
    slug,
    title: data.title || existing.title || slug,
    translatedTitle: data.translatedTitle ?? existing.translatedTitle ?? '',
    author: data.author ?? existing.author ?? '',
    sourceLang: data.source_lang || data.sourceLang || existing.sourceLang || existing.source_lang || 'cn',
    targetLang: data.target_lang || data.targetLang || existing.targetLang || existing.target_lang || 'th',
    status: data.status || existing.status || 'ongoing',
    totalChapters: data.total_chapters !== undefined
      ? parseInt(data.total_chapters, 10) || 0
      : (data.totalChapters !== undefined ? parseInt(data.totalChapters, 10) || 0 : (existing.totalChapters || 0)),
    description: data.description ?? existing.description ?? '',
    updatedAt: new Date().toISOString(),
  };
  await fs.mkdir(novelDirPath, { recursive: true });
  await fs.writeFile(novelJsonPath(slug), JSON.stringify(novelData, null, 2), 'utf8');

  invalidateAll(slug);
}
exports.saveNovelMeta = saveNovelMeta;

// ── Delete entire novel ────────────────────────────────────────────

async function deleteNovel(slug) {
  assertValidSlug(slug);
  await fs.rm(novelDir(slug), { recursive: true, force: true });
  invalidateAll(slug);
}
exports.deleteNovel = deleteNovel;
