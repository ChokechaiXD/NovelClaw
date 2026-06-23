/**
 * lib/chapter-repo.js — Single source of truth for chapter CRUD
 *
 * All chapter file operations (read, write, delete, list) live here.
 * No route or service should construct chapter file paths directly.
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const { chapterDir, chapterPath, legacyChapterPath, legacyMdPath,
        sourceMdPath, chaptersIndexPath, legacyIndexPath, allChapterVariants,
        pad, NOVELS_DIR } = require('./paths');

// ── Cache ──────────────────────────────────────────────────────────
const cache = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000;

function invalidateList(slug) {
  if (slug) cache.delete('list:' + slug);
}
function invalidateAll(slug) {
  if (slug) { cache.delete('list:' + slug); cache.delete('meta:' + slug); }
  else cache.clear();
}
exports.invalidateList = invalidateList;
exports.invalidateAll = invalidateAll;
exports._cache = cache;

// ── Helpers ────────────────────────────────────────────────────────

async function readTextOrNull(filepath) {
  try { return await fs.readFile(filepath, 'utf8'); }
  catch (err) { if (err.code === 'ENOENT') return null; throw err; }
}

// ── Private: force-scan directory for real file state ──────────────
// Always reads from disk. No cache, no fast-path index.
// Returns: { chapters: [{ num, title, hasTh, hasCn, isTranslated, status }] }

async function scanChapters(slug) {
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) return [];
  const dir = chapterDir(slug);
  let dirStat;
  try { dirStat = await fs.stat(dir); }
  catch (err) { if (err.code === 'ENOENT') return []; throw err; }

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const fileRe = /^(\d{4})\.(?:th\.json|cn\.json|json|md)$/;
  const chapterFiles = {};

  for (const e of entries) {
    if (!e.isFile()) continue;
    const m = e.name.match(fileRe);
    if (!m) continue;
    const num = parseInt(m[1], 10);
    if (!chapterFiles[num]) chapterFiles[num] = {};
    if (e.name.endsWith('.th.json')) chapterFiles[num].th = e.name;
    else if (e.name.endsWith('.cn.json')) chapterFiles[num].cn = e.name;
    else if (e.name.endsWith('.json')) chapterFiles[num].legacy = e.name;
    else if (e.name.endsWith('.md')) chapterFiles[num].md = e.name;
  }

  // Source files — only when no other file exists for that num
  try {
    const sourceEntries = await fs.readdir(path.join(dir, 'source'), { withFileTypes: true });
    for (const e of sourceEntries) {
      if (!e.isFile()) continue;
      const m = e.name.match(/^(\d{4})\.md$/);
      if (!m) continue;
      const num = parseInt(m[1], 10);
      if (!chapterFiles[num]) chapterFiles[num] = {};
      if (!chapterFiles[num].th && !chapterFiles[num].cn && !chapterFiles[num].legacy && !chapterFiles[num].md) {
        chapterFiles[num].source = e.name;
      }
    }
  } catch {}

  const titleEntries = await Promise.all(
    Object.entries(chapterFiles).map(async ([numStr, files]) => {
      const num = parseInt(numStr, 10);
      let title = '';
      const hasTh = !!files.th;
      const hasCn = !!files.cn;
      const isTranslated = hasTh; // .th.json = translated
      let status;
      if (hasTh) status = 'translated';
      else if (hasCn || files.source) status = 'source_only';
      else status = 'legacy';

      const titleFile = files.th || files.cn || files.legacy || files.md || files.source;
      if (titleFile) {
        try {
          // Source files live under chapters/source/, not chapters/
          const readDir = files.source ? path.join(dir, 'source') : dir;
          const raw = await fs.readFile(path.join(readDir, titleFile), 'utf8');
          if (titleFile.endsWith('.json')) {
            const j = JSON.parse(raw);
            if (j.title && typeof j.title === 'object') {
              title = j.title.translated || j.title.source || '';
            } else {
              title = (j.title || '').toString();
            }
          } else if (titleFile.endsWith('.md')) {
            const m = raw.match(/^#\s+(.+?)\r?\n/);
            if (m) title = m[1].trim();
          }
        } catch {}
      }
      if (!title) {
        title = isTranslated ? `ตอนที่ ${num}` : `ตอนที่ ${num} [ยังไม่แปล]`;
      }
      return { num, title, hasTh, hasCn, isTranslated, status };
    }),
  );

  titleEntries.sort((a, b) => a.num - b.num);
  return titleEntries;
}

// ── Read a single chapter ──────────────────────────────────────────

async function getChapter(slug, num, lang) {
  lang = lang || 'th';
  const padded = pad(num);

  // Per-language JSON: try {num}.{lang}.json first
  const langFile = chapterPath(slug, num, lang);
  try {
    const raw = await fs.readFile(langFile, 'utf8');
    const ch = JSON.parse(raw);
    const title = ch.title
      ? (ch.title.translated || ch.title.source || `ตอนที่ ${ch.chapterNo || num}`)
      : `ตอนที่ ${num}`;
    return {
      title,
      isJson: true,
      paragraphs: ch.paragraphs || [],
      blocks: ch.blocks || [],
      lang: ch.targetLang || lang,
      isTranslated: ch.status === 'translated' || lang === 'th',
      _raw: ch,
    };
  } catch {}

  // Fallback: legacy combined format
  const jsonFile = legacyChapterPath(slug, num);
  const mdFile = legacyMdPath(slug, num);
  const srcFile = sourceMdPath(slug, num);

  let raw;
  let isJson = false;
  let isTranslated = true;

  try {
    raw = await fs.readFile(jsonFile, 'utf8');
    isJson = true;
  } catch {
    try {
      raw = await fs.readFile(mdFile, 'utf8');
    } catch {
      try {
        raw = await fs.readFile(srcFile, 'utf8');
        isTranslated = false;
        isJson = true;
      } catch (sourceErr) {
        if (sourceErr.code === 'ENOENT') return null;
        throw sourceErr;
      }
    }
  }

  if (!isTranslated) {
    const { parseMarkdownToBlocks } = require('./blocks');
    const parsed = parseMarkdownToBlocks(raw, num);
    return {
      title: parsed.title || `ตอนที่ ${num} [ยังไม่แปล]`,
      isJson: true,
      blocks: parsed.blocks,
      source: `ch ${num} (Original Source)`,
      lang: 'cn',
      notes: [],
      isTranslated: false,
    };
  }

  if (isJson) {
    let ch;
    try { ch = JSON.parse(raw); }
    catch (parseErr) {
      throw Object.assign(new Error(`Invalid JSON in ${padded}: ${parseErr.message}`), { status: 500 });
    }
    return {
      title: ch.title || `ตอนที่ ${ch.num}`,
      isJson: true,
      paragraphs: ch.paragraphs || [],
      blocks: ch.blocks || [],
      source: ch.source || '',
      lang: ch.lang || 'cn',
      notes: ch.notes || [],
      isTranslated: true,
    };
  }

  // Legacy .md
  const parts = raw.split(/\n---\n/);
  let body = (parts[0] || '').trim();
  let meta = '';
  if (parts.length >= 3) {
    body = body + '\n\n---\n\n' + (parts[1] || '').trim();
    meta = (parts[2] || '').trim();
  } else if (parts.length === 2) {
    const subparts = parts[1].split(/\n---\n/);
    if (subparts.length >= 2) {
      body = body + '\n\n---\n\n' + subparts[0].trim();
      meta = subparts.slice(1).join('\n\n---\n').trim();
    } else {
      body = body + '\n\n---\n\n' + parts[1].trim();
    }
  }
  let mdTitle = '';
  const m = body.match(/^#\s+(.+?)\r?\n/);
  if (m) { mdTitle = m[1].trim(); body = body.slice(m[0].length).trim(); }

  const { parseMarkdownToBlocks } = require('./blocks');
  const parsed = parseMarkdownToBlocks(raw, num);
  return {
    title: mdTitle,
    body,
    meta,
    isJson: false,
    blocks: parsed.blocks,
    source: parsed.notes.length > 0 ? '' : `ch ${num}`,
    lang: 'cn',
    notes: parsed.notes,
  };
}
exports.getChapter = getChapter;

// ── Save a chapter ─────────────────────────────────────────────────

async function saveChapter(slug, num, lang, data) {
  const targetExt = lang === 'th' ? 'th' : 'cn';
  const jsonPath = chapterPath(slug, num, targetExt);
  const chapterData = {
    novelId: slug,
    chapterNo: num,
    sourceLang: 'cn',
    targetLang: targetExt,
    title: {
      translated: targetExt === 'th' ? (data.title || `ตอนที่ ${num}`) : '',
      source: targetExt === 'cn' ? (data.title || '') : '',
    },
    status: targetExt === 'th' ? 'translated' : 'source',
    paragraphs: (data.paragraphs && data.paragraphs.length) ? data.paragraphs : [],
    blocks: (!data.paragraphs || !data.paragraphs.length) ? (data.blocks || []) : [],
    notes: data.notes || [],
    updatedAt: new Date().toISOString(),
  };
  await fs.mkdir(path.dirname(jsonPath), { recursive: true });
  await fs.writeFile(jsonPath, JSON.stringify(chapterData, null, 2), 'utf8');
  return chapterData;
}
exports.saveChapter = saveChapter;

// ── Delete a chapter (all variants) ────────────────────────────────

async function deleteChapter(slug, num) {
  const variants = allChapterVariants(slug, num);
  for (const v of variants) {
    try { await fs.rm(v, { force: true }); } catch {}
  }
}
exports.deleteChapter = deleteChapter;

// ── List chapters (cached, fast-path via chapters.json) ────────────
// Accepts options.forceScan = true to bypass cache and index.

async function listChapters(slug, options = {}) {
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) return [];

  // Force scan bypasses cache and chapters.json fast path
  if (options.forceScan) {
    return await scanChapters(slug);
  }

  const dir = chapterDir(slug);
  let dirStat;
  try { dirStat = await fs.stat(dir); }
  catch (err) { if (err.code === 'ENOENT') return []; throw err; }

  let sourceDirMtimeMs = 0;
  try {
    const sourceStat = await fs.stat(path.join(dir, 'source'));
    sourceDirMtimeMs = sourceStat.mtimeMs;
  } catch {}
  const cacheKeyMtime = dirStat.mtimeMs + sourceDirMtimeMs;

  const cached = cache.get('list:' + slug);
  if (cached && cached.mtimeMs === cacheKeyMtime && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.list;
  }

  // Fast path: chapters.json (canonical index)
  try {
    const chRaw = await fs.readFile(chaptersIndexPath(slug), 'utf8');
    const chIdx = JSON.parse(chRaw);
    if (chIdx && chIdx.chapters && chIdx.chapters.length > 0) {
      const out = chIdx.chapters.map(c => ({
        num: c.num, title: c.title,
        hasTh: !!c.hasTh, hasCn: !!c.hasCn,
        isTranslated: c.status !== 'source_only',
        status: c.status || 'translated',
      }));
      cache.set('list:' + slug, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: out });
      return out;
    }
  } catch {}

  // Legacy: index.json
  try {
    const idxRaw = await fs.readFile(legacyIndexPath(slug), 'utf8');
    const idx = JSON.parse(idxRaw);
    if (idx && idx.chapters && idx.chapters.length > 0) {
      cache.set('list:' + slug, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: idx.chapters });
      return idx.chapters;
    }
  } catch {}

  // Fallback: actually scan
  const scanned = await scanChapters(slug);
  cache.set('list:' + slug, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: scanned });
  return scanned;
}
exports.listChapters = listChapters;

// ── Rebuild chapters.json index from actual files ──────────────────
// Uses forceScan to guarantee accuracy.

async function rebuildChaptersIndex(slug) {
  const chapters = await scanChapters(slug);
  const idx = {
    slug,
    totalChapters: chapters.length,
    chapters: chapters.map(c => ({
      num: c.num,
      title: c.title,
      hasCn: c.hasCn,
      hasTh: c.hasTh,
      status: c.status,
    })),
  };
  // Write to chapters/ directory
  await fs.writeFile(chaptersIndexPath(slug), JSON.stringify(idx, null, 2), 'utf8');
  // Also write legacy index.json for backward compat
  try {
    await fs.writeFile(
      legacyIndexPath(slug),
      JSON.stringify({ slug, chapters: chapters.map(c => ({ num: c.num, title: c.title, isTranslated: c.isTranslated })) }, null, 2),
      'utf8'
    );
  } catch {}
  return idx;
}
exports.rebuildChaptersIndex = rebuildChaptersIndex;
