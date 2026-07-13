/**
 * lib/chapter-repo.js — Single source of truth for chapter CRUD
 *
 * All chapter file operations (read, write, delete, list) live here.
 * No route or service should construct chapter file paths directly.
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const { chapterDir, chapterPath, sourceMdPath, chaptersIndexPath,
        allChapterVariants, NOVELS_DIR } = require('./paths');
const { extractMarkdownTitle, parseMarkdownToBlocks } = require('./blocks');
const { writeJsonAtomic } = require('./atomic-write');

// ── Cache ──────────────────────────────────────────────────────────
const cache = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000;
const CHAPTER_FILE_RE = /^(\d{4})\.(?:th|cn)\.json$/;

function invalidateList(slug) {
  if (slug) { cache.delete('list:' + slug); cache.delete('listq:' + slug); }
}
function invalidateAll(slug) {
  if (slug) { cache.delete('list:' + slug); cache.delete('listq:' + slug); cache.delete('meta:' + slug); }
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

function isGenericChapterTitle(title, num) {
  const text = String(title || '').trim();
  if (!text) return true;
  const escapedNum = String(num).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`^(?:ตอนที่\\s*${escapedNum}(?:\\s*\\[ยังไม่แปล\\])?|第\\s*${escapedNum}\\s*[章节章]|Chapter\\s+${escapedNum})$`, 'i').test(text);
}

function isDirtySourceTitle(title) {
  const text = String(title || '').trim().toLowerCase();
  if (!text) return false;
  return ['>>', '黃金屋', '黄金屋', '目錄', '目录', '手機網頁版', '手机网页版', '游戲·競技', '游戏·竞技']
    .some(marker => text.includes(marker.toLowerCase()));
}

function sourceTitleForList(title, num) {
  const text = String(title || '').trim();
  if (isDirtySourceTitle(text)) return '';
  const chinese = text.match(/^第\s*\d+\s*[章节章]\s*(.+)$/);
  if (chinese?.[1]?.trim()) return `ตอนที่ ${num} ${chinese[1].trim()}`;
  return text;
}

async function readSourceTitle(dir, files, num) {
  if (files.cn) {
    try {
      const data = JSON.parse(await fs.readFile(path.join(dir, files.cn), 'utf8'));
      const title = typeof data.title === 'object' ? data.title?.source : data.title;
      const firstParagraph = Array.isArray(data.paragraphs)
        ? (typeof data.paragraphs[0] === 'string' ? data.paragraphs[0] : data.paragraphs[0]?.text)
        : '';
      for (const candidate of [title, firstParagraph]) {
        const clean = sourceTitleForList(candidate, num);
        if (clean && !isGenericChapterTitle(clean, num)) return clean;
      }
    } catch {}
  }
  if (!files.source) return '';
  try {
    const raw = await fs.readFile(path.join(dir, 'source', files.source), 'utf8');
    const title = extractMarkdownTitle(raw);
    return isGenericChapterTitle(title, num) || isDirtySourceTitle(title) ? '' : sourceTitleForList(title, num);
  } catch {
    return '';
  }
}

function summarizeTranslationMeta(data) {
  if (!data || typeof data !== 'object') return {};
  const meta = data.meta && typeof data.meta === 'object' ? data.meta : {};
  const qualityRecord = data.qualityRecord && typeof data.qualityRecord === 'object'
    ? data.qualityRecord
    : null;
  return {
    provider: meta.provider || data.provider || 'unknown',
    model: meta.model || data.model || 'unknown',
    promptProfile: meta.promptProfile || '',
    score: qualityRecord?.score ?? meta.score ?? data.score ?? null,
    qualityRecord,
    qualityStatus: qualityRecord && qualityRecord.passed === false ? 'needs_review' : 'translated',
  };
}

async function readTranslationMeta(slug, num) {
  try {
    const raw = await fs.readFile(chapterPath(slug, num, 'th'), 'utf8');
    return summarizeTranslationMeta(JSON.parse(raw));
  } catch {
    return {};
  }
}

// ── Private: force-scan directory for real file state ──────────────
// Always reads from disk. No cache, no fast-path index.
// Returns: { chapters: [{ num, title, hasTh, hasCn, isTranslated, status }] }

async function scanChapters(slug, options = {}) {
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) return [];
  const dir = chapterDir(slug);
  let dirStat;
  try { dirStat = await fs.stat(dir); }
  catch (err) { if (err.code === 'ENOENT') return []; throw err; }

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const chapterFiles = {};

  for (const e of entries) {
    if (!e.isFile()) continue;
    const m = e.name.match(CHAPTER_FILE_RE);
    if (!m) continue;
    const num = parseInt(m[1], 10);
    if (!chapterFiles[num]) chapterFiles[num] = {};
    if (e.name.endsWith('.th.json')) chapterFiles[num].th = e.name;
    else if (e.name.endsWith('.cn.json')) chapterFiles[num].cn = e.name;
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
      chapterFiles[num].source = e.name;
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
      let translationMeta = {};
      if (hasTh) status = 'translated';
      else status = 'source_only';

      const titleFile = files.th || files.cn || files.source;
      if (titleFile) {
        try {
          // Source files live under chapters/source/, not chapters/
          const titleIsSource = titleFile === files.source;
          const readDir = titleIsSource ? path.join(dir, 'source') : dir;
          const raw = await fs.readFile(path.join(readDir, titleFile), 'utf8');
          if (titleFile.endsWith('.json')) {
            const j = JSON.parse(raw);
            if (titleFile === files.th) translationMeta = summarizeTranslationMeta(j);
            if (j.title && typeof j.title === 'object') {
              const translatedTitle = (j.title.translated || '').toString();
              const sourceTitle = (j.title.source || '').toString();
              title = translatedTitle || sourceTitle || '';
              if (isGenericChapterTitle(title, num) && !isGenericChapterTitle(sourceTitle, num)) {
                title = sourceTitleForList(sourceTitle, num);
              }
            } else {
              title = (j.title || '').toString();
            }
          } else if (titleFile.endsWith('.md')) {
            title = sourceTitleForList(extractMarkdownTitle(raw), num);
          }
        } catch {}
      }
      if (isGenericChapterTitle(title, num)) {
        const sourceTitle = await readSourceTitle(dir, files, num);
        if (sourceTitle) title = sourceTitle;
      }
      if (!title) {
        title = isTranslated ? `ตอนที่ ${num}` : `ตอนที่ ${num} [ยังไม่แปล]`;
      }
      if (options.includeQuality && hasTh && !translationMeta.qualityRecord && translationMeta.score == null) {
        translationMeta = await readTranslationMeta(slug, num);
      }
      return { num, title, hasTh, hasCn, isTranslated, status, ...(options.includeQuality ? translationMeta : {}) };
    }),
  );

  titleEntries.sort((a, b) => a.num - b.num);
  return titleEntries;
}

async function chapterFileNums(dir) {
  const nums = new Set();
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const match = entry.name.match(CHAPTER_FILE_RE);
    if (match) nums.add(parseInt(match[1], 10));
  }
  try {
    const sourceEntries = await fs.readdir(path.join(dir, 'source'), { withFileTypes: true });
    for (const entry of sourceEntries) {
      if (!entry.isFile()) continue;
      const match = entry.name.match(/^(\d{4})\.md$/);
      if (match) nums.add(parseInt(match[1], 10));
    }
  } catch {}
  return nums;
}

async function indexMatchesChapterFiles(dir, chapters) {
  const fileNums = await chapterFileNums(dir);
  return fileNums.size === chapters.length
    && chapters.every(chapter => fileNums.has(chapter.num));
}

async function writeChaptersIndexes(slug, chapters) {
  const index = {
    slug,
    totalChapters: chapters.length,
    chapters: chapters.map(chapter => ({
      num: chapter.num,
      title: chapter.title,
      hasCn: chapter.hasCn,
      hasTh: chapter.hasTh,
      status: chapter.status,
    })),
  };
  await writeJsonAtomic(chaptersIndexPath(slug), index);
  return index;
}

// ── Read a single chapter ──────────────────────────────────────────

async function getChapter(slug, num, lang) {
  lang = lang || 'th';

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

  // Fallback: try source language (.cn.json) when target not found
  if (lang !== 'cn') {
    try {
      const srcFile = chapterPath(slug, num, 'cn');
      const raw = await fs.readFile(srcFile, 'utf8');
      const ch = JSON.parse(raw);
      const cleanTitle = (t) => {
        if (!t) return `ตอนที่ ${num}`;
        if (t.includes('黃金') || t.includes('>>')) return `ตอนที่ ${num}`;
        // Strip Chinese chapter number prefix like "第78章" or "第78장"
        if (/^第\d+[章장]/.test(t.trim())) {
          const rest = t.replace(/^第\d+[章장]\s*/, '').trim();
          return rest ? `ตอนที่ ${num} ${rest}` : `ตอนที่ ${num}`;
        }
        return t;
      };
      return {
        title: cleanTitle(ch.title?.source || `ตอนที่ ${num}`),
        isJson: true,
        paragraphs: ch.paragraphs || [],
        blocks: ch.blocks || [],
        lang: 'cn',
        isTranslated: false,
      };
    } catch {}
  }

  const srcFile = sourceMdPath(slug, num);
  try {
    const raw = await fs.readFile(srcFile, 'utf8');
    const parsed = parseMarkdownToBlocks(raw, num);
    const sourceLang = parsed.frontmatter?.source_lang || parsed.frontmatter?.sourceLang || 'cn';
    const _mdTitle = parsed.title || '';
    const _mdClean = sourceLang === 'cn'
      ? _mdTitle.replace(/^第\d+[章장]\s*/, '').trim()
      : _mdTitle.trim();
    return {
      title: _mdClean ? `ตอนที่ ${num} ${_mdClean}` : (_mdTitle || `ตอนที่ ${num} [ยังไม่แปล]`),
      isJson: true,
      blocks: parsed.blocks,
      source: `ch ${num} (Original Source)`,
      lang: sourceLang,
      notes: parsed.notes,
      isTranslated: false,
    };
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
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

async function deleteTranslatedChapters(slug, nums = null) {
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) return { deleted: 0, nums: [] };
  const dir = chapterDir(slug);
  let targets = [];

  if (Array.isArray(nums) && nums.length) {
    targets = [...new Set(nums.map(n => Number(n)).filter(n => Number.isInteger(n) && n > 0))]
      .map(num => ({ num, filepath: chapterPath(slug, num, 'th') }));
  } else {
    let entries;
    try { entries = await fs.readdir(dir, { withFileTypes: true }); }
    catch (err) { if (err.code === 'ENOENT') return { deleted: 0, nums: [] }; throw err; }
    targets = entries
      .filter(entry => entry.isFile())
      .map(entry => entry.name.match(/^(\d{4})\.th\.json$/))
      .filter(Boolean)
      .map(match => {
        const num = parseInt(match[1], 10);
        return { num, filepath: chapterPath(slug, num, 'th') };
      });
  }

  const deletedNums = [];
  for (const target of targets) {
    try {
      await fs.unlink(target.filepath);
      deletedNums.push(target.num);
    } catch (err) {
      if (err.code !== 'ENOENT') throw err;
    }
  }

  deletedNums.sort((a, b) => a - b);
  return { deleted: deletedNums.length, nums: deletedNums };
}
exports.deleteTranslatedChapters = deleteTranslatedChapters;

// ── List chapters (cached, fast-path via chapters.json) ────────────
// Accepts options.forceScan = true to bypass cache and index.

async function listChapters(slug, options = {}) {
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) return [];

  // Force scan bypasses cache and chapters.json fast path
  if (options.forceScan) {
    return await scanChapters(slug, options);
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
  const listCacheKey = (options.includeQuality ? 'listq:' : 'list:') + slug;

  const cached = cache.get(listCacheKey);
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
      const needsRepair = out.some(c => isGenericChapterTitle(c.title, c.num))
        || !(await indexMatchesChapterFiles(dir, out));
      if (needsRepair) {
        const scanned = await scanChapters(slug, options);
        await writeChaptersIndexes(slug, scanned);
        cache.set(listCacheKey, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: scanned });
        return scanned;
      }
      if (options.includeQuality) {
        const withQuality = await Promise.all(out.map(async c => (
          c.hasTh ? { ...c, ...(await readTranslationMeta(slug, c.num)) } : c
        )));
        cache.set(listCacheKey, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: withQuality });
        return withQuality;
      }
      cache.set(listCacheKey, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: out });
      return out;
    }
  } catch {}

  // Fallback: actually scan
  const scanned = await scanChapters(slug, options);
  cache.set(listCacheKey, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: scanned });
  return scanned;
}
exports.listChapters = listChapters;

// ── Rebuild chapters.json index from actual files ──────────────────
// Uses forceScan to guarantee accuracy.

async function rebuildChaptersIndex(slug) {
  const chapters = await scanChapters(slug);
  return writeChaptersIndexes(slug, chapters);
}
exports.rebuildChaptersIndex = rebuildChaptersIndex;
