/**
 * lib/import-health.js — Source import diagnostics and repair helpers.
 *
 * This checks canonical source markdown only. It never rewrites chapter
 * content; repair actions rebuild derived indexes around existing files.
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const { chapterDir, SLUG_RE } = require('./paths');
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

function analyzeSourceMarkdown(raw, num, filename = '') {
  const parsed = parseMarkdownToBlocks(raw, num);
  const frontmatter = normalizeFrontmatter(parsed.frontmatter);
  const contentBlocks = (parsed.blocks || []).filter((block) => block.type !== 'end');
  const contentText = contentBlocks.map((block) => block.text || '').join('\n\n').trim();
  const lower = contentText.toLowerCase();
  const warnings = Array.isArray(frontmatter.import_warnings) ? frontmatter.import_warnings : [];
  const issues = [];

  if (!parsed.title) issues.push({ code: 'missing_title', severity: 'warn', message: 'Missing chapter title' });
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
  if (!['rebuild-index', 'all'].includes(action)) {
    throw Object.assign(new Error('Unknown repair action'), { status: 400 });
  }
  await chapterRepo.rebuildChaptersIndex(slug);
  chapterRepo.invalidateAll(slug);
  return getNovelImportHealth(slug);
}

module.exports = {
  analyzeSourceMarkdown,
  getAllImportHealth,
  getNovelImportHealth,
  repairNovelImport,
};
