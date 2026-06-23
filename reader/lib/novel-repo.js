/**
 * lib/novel-repo.js — Novel metadata operations
 *
 * novel.json is the canonical source of truth. meta.md is legacy only.
 */

const fs = require('node:fs/promises');
const { novelDir, novelJsonPath, metaMdPath, NOVELS_DIR, assertValidSlug } = require('./paths');
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

  // Try novel.json first (canonical), fallback to meta.md
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
  } catch {}

  try {
    const raw = await fs.readFile(metaMdPath(slug), 'utf8');
    const m = raw.match(/^---\s*\n([\s\S]*?)\n---/);
    meta = { slug, title: slug, source_lang: 'cn', target_lang: 'th', description: '' };
    if (m) {
      for (const line of m[1].split('\n')) {
        const kv = line.match(/^(\w[\w_]*):\s*(.+?)\s*$/);
        if (kv) {
          let val = kv[2].replace(/^['"]|['"]$/g, '');
          meta[kv[1]] = val;
        }
      }
    }
    // Extract description from body
    const lines = raw.split('\n');
    let inDesc = false;
    for (const line of lines) {
      if (inDesc) {
        if (line.startsWith('## ')) break;
        meta.description += line.trim() + '\n';
      } else if (line.startsWith('## Description')) {
        inDesc = true;
      }
    }
    meta.description = meta.description.trim();
  } catch {
    meta = { slug, title: slug, source_lang: 'cn', target_lang: 'th', description: '' };
  }

  _cache.set(mk, meta);
  return meta;
}
exports.getNovelMeta = getNovelMeta;

// ── Save novel metadata ────────────────────────────────────────────

async function saveNovelMeta(slug, data) {
  assertValidSlug(slug);
  const novelDirPath = novelDir(slug);

  // Write canonical novel.json
  const novelData = {
    slug,
    title: data.title || slug,
    translatedTitle: data.translatedTitle || '',
    author: data.author || '',
    sourceLang: data.source_lang || 'cn',
    targetLang: data.target_lang || 'th',
    status: data.status || 'ongoing',
    totalChapters: data.total_chapters ? parseInt(data.total_chapters, 10) : 0,
    description: data.description || '',
    updatedAt: new Date().toISOString(),
  };
  await fs.mkdir(novelDirPath, { recursive: true });
  await fs.writeFile(novelJsonPath(slug), JSON.stringify(novelData, null, 2), 'utf8');

  // Write meta.md as legacy export
  const metaYaml = [
    '---',
    `slug: ${slug}`,
    `title: ${data.title || slug}`,
    `author: ${data.author || ''}`,
    `source_lang: ${data.source_lang || 'cn'}`,
    `target_lang: ${data.target_lang || 'th'}`,
    `status: ${data.status || 'ongoing'}`,
    `total_chapters: ${String(data.total_chapters || '0')}`,
    '---',
    `# ${data.title || slug}`,
  ].join('\n');
  await fs.writeFile(metaMdPath(slug), metaYaml, 'utf8');

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
