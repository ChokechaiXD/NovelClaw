/**
 * lib/paths.js — Single source of truth for all file paths
 *
 * Every route must use these helpers. Never construct chapter file paths
 * manually. This is the ONLY module that knows file naming conventions
 * (.th.json / .cn.json / legacy .json / .md).
 */

const path = require('node:path');

// Root novels directory (resolved at module load time)
const NOVELS_DIR = process.env.NOVELCLAW_ROOT
  ? path.resolve(process.env.NOVELCLAW_ROOT)
  : path.resolve(__dirname, '../../novels');

exports.NOVELS_DIR = NOVELS_DIR;

/** Pad chapter number to 4 digits */
function pad(num) {
  return String(num).padStart(4, '0');
}
exports.pad = pad;

/** Return the novel directory for a slug */
function novelDir(slug) {
  return path.join(NOVELS_DIR, slug);
}
exports.novelDir = novelDir;

/** Return the chapters subdirectory for a slug */
function chapterDir(slug) {
  return path.join(NOVELS_DIR, slug, 'chapters');
}
exports.chapterDir = chapterDir;

/** Return path to a per-language chapter JSON file: {pad}.{lang}.json */
function chapterPath(slug, num, lang) {
  return path.join(NOVELS_DIR, slug, 'chapters', `${pad(num)}.${lang}.json`);
}
exports.chapterPath = chapterPath;

/** Return path to legacy combined {num}.json (deprecated, write never) */
function legacyChapterPath(slug, num) {
  return path.join(NOVELS_DIR, slug, 'chapters', `${pad(num)}.json`);
}
exports.legacyChapterPath = legacyChapterPath;

/** Return path to legacy {num}.md (deprecated) */
function legacyMdPath(slug, num) {
  return path.join(NOVELS_DIR, slug, 'chapters', `${pad(num)}.md`);
}
exports.legacyMdPath = legacyMdPath;

/** Return path to source/{num}.md (original scraped source) */
function sourceMdPath(slug, num) {
  return path.join(NOVELS_DIR, slug, 'chapters', 'source', `${pad(num)}.md`);
}
exports.sourceMdPath = sourceMdPath;

/** Return path to novel.json (canonical metadata) */
function novelJsonPath(slug) {
  return path.join(NOVELS_DIR, slug, 'novel.json');
}
exports.novelJsonPath = novelJsonPath;

/** Return path to meta.md (legacy, for backward compat) */
function metaMdPath(slug) {
  return path.join(NOVELS_DIR, slug, 'meta.md');
}
exports.metaMdPath = metaMdPath;

/** Return path to chapters.json (fast chapter index) */
function chaptersIndexPath(slug) {
  return path.join(NOVELS_DIR, slug, 'chapters.json');
}
exports.chaptersIndexPath = chaptersIndexPath;

/** Return path to chapters/index.json (legacy compat index) */
function legacyIndexPath(slug) {
  return path.join(NOVELS_DIR, slug, 'chapters', 'index.json');
}
exports.legacyIndexPath = legacyIndexPath;

/** Return path to glossary/{glossary,yml,json} files */
function glossaryJsonPath(slug) {
  return path.join(NOVELS_DIR, slug, 'glossary', 'glossary.json');
}
exports.glossaryJsonPath = glossaryJsonPath;

function glossaryMdPath(slug) {
  return path.join(NOVELS_DIR, slug, 'glossary.md');
}
exports.glossaryMdPath = glossaryMdPath;

function charactersMdPath(slug) {
  return path.join(NOVELS_DIR, slug, 'characters.md');
}
exports.charactersMdPath = charactersMdPath;

/** Return search index path for a language */
function searchIndexPath(slug, lang) {
  return path.join(NOVELS_DIR, slug, 'search-index.' + lang + '.json');
}
exports.searchIndexPath = searchIndexPath;

/** Return all variant paths for a chapter (used in delete) */
function allChapterVariants(slug, num) {
  const p = pad(num);
  return [
    path.join(NOVELS_DIR, slug, 'chapters', `${p}.th.json`),
    path.join(NOVELS_DIR, slug, 'chapters', `${p}.cn.json`),
    path.join(NOVELS_DIR, slug, 'chapters', `${p}.json`),
    path.join(NOVELS_DIR, slug, 'chapters', `${p}.md`),
  ];
}
exports.allChapterVariants = allChapterVariants;

/** Valid slug regex — reject path traversal */
const SLUG_RE = /^[a-zA-Z0-9_-]+$/;
exports.SLUG_RE = SLUG_RE;

function assertValidSlug(slug) {
  if (!SLUG_RE.test(slug)) throw Object.assign(new Error('Invalid slug format'), { status: 400 });
}
exports.assertValidSlug = assertValidSlug;
