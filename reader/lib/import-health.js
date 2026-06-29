/**
 * lib/import-health.js — Source import diagnostics and repair helpers.
 *
 * This checks canonical source markdown only. It never rewrites chapter
 * content; repair actions rebuild derived indexes around existing files.
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const { chapterDir, sourceMdPath, SLUG_RE } = require('./paths');
const { parseMarkdownToBlocks } = require('./blocks');
const chapterRepo = require('./chapter-repo');
const novelRepo = require('./novel-repo');

const DIRTY_MARKERS = [
  'advertisement',
  'sponsored',
  'this text was taken from royal road',
  'please enable javascript',
  'read next',
  'next chapter',
  'table of contents',
  '最新网址',
  '加入书签',
  'ブックマーク',
];

const DIRTY_TITLE_MARKERS = [
  '>>',
  '黃金屋',
  '黄金屋',
  '目錄',
  '目录',
  '手機網頁版',
  '手机网页版',
];

function parseFrontmatterValue(value) {
  const text = String(value ?? '').trim();
  if (!text) return '';
  if (text === 'true') return true;
  if (text === 'false') return false;
  if ((text.startsWith('[') && text.endsWith(']')) || (text.startsWith('{') && text.endsWith('}'))) {
    try { return JSON.parse(text); } catch {}
  }
  return text;
}

function normalizeFrontmatter(frontmatter = {}) {
  const out = {};
  for (const [key, value] of Object.entries(frontmatter)) {
    out[key] = parseFrontmatterValue(value);
  }
  return out;
}

function looksLinkOnly(text) {
  const compact = text.replace(/\s+/g, ' ').trim();
  if (!compact) return false;
  const urls = compact.match(/https?:\/\/\S+/gi) || [];
  if (urls.length >= 2 && urls.join(' ').length / compact.length > 0.45) return true;
  return /^https?:\/\/\S+$/i.test(compact);
}

function normalizeTextLine(line) {
  return String(line || '')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function extractChapterTitleSegment(text) {
  const line = normalizeTextLine(text).replace(/^#+\s*/, '').trim();
  if (!line || /^https?:\/\//i.test(line)) return '';

  const parts = line.split(/\s*(?:>>|»|›)\s*/).map(normalizeTextLine).filter(Boolean);
  if (parts.length > 1) {
    for (let i = parts.length - 1; i >= 0; i--) {
      const title = extractChapterTitleSegment(parts[i]);
      if (title) return title;
    }
  }

  const cn = line.match(/(第\s*\d+\s*(?:章|节|節|話|话|回)\s*[^<>|]*)$/);
  if (cn) return normalizeTextLine(cn[1]);
  const western = line.match(/\b(Chapter\s+\d+[^<>|]*)$/i);
  if (western) return normalizeTextLine(western[1]);
  const thai = line.match(/(ตอนที่\s*\d+[^<>|]*)$/i);
  if (thai) return normalizeTextLine(thai[1]);
  return '';
}

function isDirtySourceTitle(title) {
  const text = normalizeTextLine(title).toLowerCase();
  if (!text) return false;
  return DIRTY_TITLE_MARKERS.some((marker) => text.includes(marker.toLowerCase()));
}

function titleNeedsRepair(title) {
  return !normalizeTextLine(title) || isDirtySourceTitle(title);
}

function analyzeSourceMarkdown(raw, num, filename = '') {
  const parsed = parseMarkdownToBlocks(raw, num);
  const frontmatter = normalizeFrontmatter(parsed.frontmatter);
  const contentBlocks = (parsed.blocks || []).filter((block) => block.type !== 'end');
  const contentText = contentBlocks.map((block) => block.text || '').join('\n\n').trim();
  const lower = contentText.toLowerCase();
  const warnings = Array.isArray(frontmatter.import_warnings) ? frontmatter.import_warnings : [];
  const issues = [];

  if (!parsed.title) issues.push({ code: 'missing_title', severity: 'warn', message: 'Missing chapter title' });
  else if (isDirtySourceTitle(parsed.title)) {
    issues.push({ code: 'dirty_title', severity: 'warn', message: 'Chapter title contains site breadcrumb text' });
  }
  if (!contentBlocks.length || contentText.length < 30) {
    issues.push({ code: 'empty_content', severity: 'error', message: 'No usable chapter content' });
  } else if (contentText.length < 300) {
    issues.push({ code: 'short_content', severity: 'warn', message: 'Content is unusually short' });
  }
  if (contentBlocks.length < 2 && contentText.length < 800) {
    issues.push({ code: 'few_paragraphs', severity: 'warn', message: 'Very few paragraphs' });
  }
  if (looksLinkOnly(contentText)) {
    issues.push({ code: 'link_only', severity: 'error', message: 'Content looks like links instead of prose' });
  }
  const dirtyHits = DIRTY_MARKERS.filter((marker) => lower.includes(marker));
  if (dirtyHits.length) {
    issues.push({ code: 'dirty_markers', severity: 'warn', message: dirtyHits.slice(0, 3).join(', ') });
  }
  if (frontmatter.needs_review === true || warnings.length > 0) {
    issues.push({ code: 'needs_review', severity: 'warn', message: warnings.slice(0, 3).join(', ') || 'Adapter marked chapter for review' });
  }

  return {
    num,
    filename,
    title: parsed.title || '',
    sourceLang: frontmatter.source_lang || frontmatter.sourceLang || '',
    sourceSite: frontmatter.source_site || frontmatter.sourceSite || '',
    sourceUrl: frontmatter.source_url || frontmatter.sourceUrl || '',
    charCount: contentText.length,
    paragraphCount: contentBlocks.length,
    warnings,
    issues,
    needsReview: issues.length > 0,
  };
}

function inferTitleFromBody(body) {
  const lines = String(body || '').replace(/\r\n/g, '\n').split('\n')
    .map(line => line.trim())
    .filter(Boolean);
  for (let i = 0; i < Math.min(lines.length, 40); i++) {
    const line = lines[i];
    const title = normalizeTextLine(line);
    const extracted = extractChapterTitleSegment(title);
    if (extracted) {
      const bareChapter = /^第\s*\d+\s*(?:章|节|節|話|话|回)\s*$/.test(extracted);
      const next = normalizeTextLine(lines[i + 1] || '');
      if (bareChapter && next && next.length <= 120 && !/[<>]/.test(next)) {
        return (extracted + ' ' + next).trim();
      }
      return extracted;
    }
    if (title.length > 140) return '';
    const embeddedCn = title.match(/第\s*\d+\s*[章节章]\s*(.*)$/);
    if (embeddedCn) {
      const rest = (embeddedCn[1] || '').trim();
      if (rest) return title.slice(title.indexOf(embeddedCn[0])).trim();
      const next = (lines[i + 1] || '').trim();
      if (next && next.length <= 100 && !/[<>]/.test(next)) {
        return (embeddedCn[0].trim() + ' ' + next).trim();
      }
      return embeddedCn[0].trim();
    }
    if (/^(Chapter\s+\d+|ตอนที่\s*\d+)/i.test(title)) return title;
  }
  return '';
}

function addMarkdownTitle(raw, title) {
  const normalized = String(raw || '').replace(/\r\n/g, '\n').trimStart();
  const frontmatterMatch = normalized.match(/^---\n[\s\S]*?\n---(?:\n|$)/);
  const frontmatter = frontmatterMatch ? frontmatterMatch[0] : '';
  const body = frontmatterMatch ? normalized.slice(frontmatter.length).trimStart() : normalized;
  const lines = body.split('\n');
  if (lines[0]?.trim().startsWith('#')) lines.shift();
  if (lines[0]?.trim() === title) lines.shift();
  return frontmatter + `# ${title}\n\n` + lines.join('\n').replace(/^\n+/, '');
}

function summarizeIssues(chapters) {
  const byCode = {};
  let errorCount = 0;
  let warningCount = 0;
  for (const chapter of chapters) {
    for (const issue of chapter.issues || []) {
      byCode[issue.code] = (byCode[issue.code] || 0) + 1;
      if (issue.severity === 'error') errorCount += 1;
      else warningCount += 1;
    }
  }
  return { byCode, errorCount, warningCount };
}

async function scanSourceFiles(slug) {
  if (!SLUG_RE.test(slug)) return [];
  const dir = path.join(chapterDir(slug), 'source');
  let entries;
  try { entries = await fs.readdir(dir, { withFileTypes: true }); }
  catch (err) { if (err.code === 'ENOENT') return []; throw err; }

  const files = entries
    .filter((entry) => entry.isFile() && /^\d{4}\.md$/.test(entry.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  return Promise.all(files.map(async (entry) => {
    const num = parseInt(entry.name, 10);
    const raw = await fs.readFile(path.join(dir, entry.name), 'utf8');
    return analyzeSourceMarkdown(raw, num, entry.name);
  }));
}

async function repairMissingSourceTitles(slug) {
  if (!SLUG_RE.test(slug)) return { repaired: 0, unchanged: 0 };
  const dir = path.join(chapterDir(slug), 'source');
  let entries;
  try { entries = await fs.readdir(dir, { withFileTypes: true }); }
  catch (err) { if (err.code === 'ENOENT') return { repaired: 0, unchanged: 0 }; throw err; }

  let repaired = 0;
  let unchanged = 0;
  for (const entry of entries) {
    if (!entry.isFile() || !/^\d{4}\.md$/.test(entry.name)) continue;
    const filepath = path.join(dir, entry.name);
    const raw = await fs.readFile(filepath, 'utf8');
    const parsed = parseMarkdownToBlocks(raw, parseInt(entry.name, 10));
    if (!titleNeedsRepair(parsed.title)) continue;
    const frontmatterMatch = String(raw).replace(/\r\n/g, '\n').trimStart().match(/^---\n[\s\S]*?\n---(?:\n|$)/);
    const body = frontmatterMatch ? String(raw).replace(/\r\n/g, '\n').trimStart().slice(frontmatterMatch[0].length) : raw;
    const title = inferTitleFromBody(body);
    if (!title) {
      unchanged += 1;
      continue;
    }
    await fs.writeFile(filepath, addMarkdownTitle(raw, title), 'utf8');
    repaired += 1;
  }
  return { repaired, unchanged };
}

async function getNovelImportHealth(slug) {
  const meta = await novelRepo.getNovelMeta(slug);
  const chapters = await chapterRepo.listChapters(slug);
  const sourceDiagnostics = await scanSourceFiles(slug);
  const issueSummary = summarizeIssues(sourceDiagnostics);
  const sourceOnlyCount = chapters.filter((chapter) => chapter.status === 'source_only').length;
  const translatedCount = chapters.filter((chapter) => chapter.isTranslated).length;
  const staleIndexTitleCount = chapters.filter((chapter) =>
    chapter.status === 'source_only'
    && typeof chapter.title === 'string'
    && /^ตอนที่ \d+ \[ยังไม่แปล\]$/.test(chapter.title)
  ).length;
  const status = issueSummary.errorCount > 0
    ? 'error'
    : (issueSummary.warningCount > 0 || staleIndexTitleCount > 0 ? 'warn' : 'ok');

  return {
    slug,
    title: meta.translatedTitle || meta.translated_title || meta.title || slug,
    sourceSite: meta.sourceSite || '',
    sourceLang: meta.sourceLang || meta.source_lang || '',
    totalChapters: chapters.length,
    sourceFileCount: sourceDiagnostics.length,
    sourceOnlyCount,
    translatedCount,
    staleIndexTitleCount,
    status,
    translationReady: issueSummary.errorCount === 0,
    issueSummary,
    sampleIssues: sourceDiagnostics
      .filter((chapter) => chapter.issues.length > 0)
      .slice(0, 5)
      .map((chapter) => ({
        num: chapter.num,
        title: chapter.title,
        charCount: chapter.charCount,
        issues: chapter.issues,
      })),
  };
}

async function getAllImportHealth() {
  const slugs = await novelRepo.listNovels();
  const novels = await Promise.all(slugs.map(getNovelImportHealth));
  const summary = novels.reduce((acc, novel) => {
    acc.novels += 1;
    acc.sourceFiles += novel.sourceFileCount;
    acc.errors += novel.issueSummary.errorCount;
    acc.warnings += novel.issueSummary.warningCount + novel.staleIndexTitleCount;
    acc.ready += novel.translationReady ? 1 : 0;
    return acc;
  }, { novels: 0, sourceFiles: 0, errors: 0, warnings: 0, ready: 0 });
  return { summary, novels };
}

async function repairNovelImport(slug, action = 'rebuild-index') {
  if (!SLUG_RE.test(slug)) {
    throw Object.assign(new Error('Invalid slug format'), { status: 400 });
  }
  if (!['rebuild-index', 'repair-titles', 'all'].includes(action)) {
    throw Object.assign(new Error('Unknown repair action'), { status: 400 });
  }
  const result = { titlesRepaired: 0, titlesUnchanged: 0, indexRebuilt: false };
  if (action === 'repair-titles' || action === 'all') {
    const titleRepair = await repairMissingSourceTitles(slug);
    result.titlesRepaired = titleRepair.repaired;
    result.titlesUnchanged = titleRepair.unchanged;
  }
  await chapterRepo.rebuildChaptersIndex(slug);
  result.indexRebuilt = true;
  chapterRepo.invalidateAll(slug);
  return { repair: result, health: await getNovelImportHealth(slug) };
}

async function inspectSourceChapter(slug, num) {
  if (!SLUG_RE.test(slug)) {
    throw Object.assign(new Error('Invalid slug format'), { status: 400 });
  }
  const chapterNum = parseInt(num, 10);
  if (Number.isNaN(chapterNum)) {
    throw Object.assign(new Error('Invalid chapter number'), { status: 400 });
  }
  let raw;
  try {
    raw = await fs.readFile(sourceMdPath(slug, chapterNum), 'utf8');
  } catch (err) {
    if (err.code === 'ENOENT') {
      throw Object.assign(new Error('Source chapter not found'), { status: 404 });
    }
    throw err;
  }
  const parsed = parseMarkdownToBlocks(raw, chapterNum);
  const diagnostic = analyzeSourceMarkdown(raw, chapterNum, `${String(chapterNum).padStart(4, '0')}.md`);
  const paragraphs = (parsed.blocks || [])
    .filter((block) => block.type !== 'end')
    .map((block) => block.text || '')
    .filter(Boolean);

  return {
    slug,
    num: chapterNum,
    raw,
    title: parsed.title || '',
    frontmatter: normalizeFrontmatter(parsed.frontmatter),
    paragraphs,
    cleanedText: paragraphs.join('\n\n'),
    diagnostic,
  };
}

module.exports = {
  analyzeSourceMarkdown,
  getAllImportHealth,
  getNovelImportHealth,
  inspectSourceChapter,
  repairMissingSourceTitles,
  repairNovelImport,
};
