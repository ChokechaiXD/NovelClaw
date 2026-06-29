const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

function resetNovelRootModules() {
  for (const mod of ['../lib/paths', '../lib/chapter-repo', '../lib/novel-repo', '../lib/import-health']) {
    delete require.cache[require.resolve(mod)];
  }
}

test('import health flags link-only and dirty source chapters', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-health-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { getNovelImportHealth } = require('../lib/import-health');
  const slug = 'sample-health';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'novel.json'), JSON.stringify({
    slug,
    title: 'Sample Health',
    sourceLang: 'en',
    targetLang: 'th',
  }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0001.md'), `---
source_lang: "en"
source_site: "fixture"
needs_review: false
import_warnings: []
---
# Link Only

https://example.test/chapter/1

https://example.test/chapter/2
`, 'utf8');
  await fs.writeFile(path.join(sourceDir, '0002.md'), `---
source_lang: "en"
source_site: "fixture"
needs_review: true
import_warnings: ["short_content"]
---
# Dirty

This text was taken from Royal Road. Help the author by reading the original version there.
`, 'utf8');

  const health = await getNovelImportHealth(slug);

  assert.equal(health.slug, slug);
  assert.equal(health.sourceFileCount, 2);
  assert.equal(health.status, 'error');
  assert.equal(health.translationReady, false);
  assert.ok(health.issueSummary.byCode.link_only >= 1);
  assert.ok(health.issueSummary.byCode.dirty_markers >= 1);
});

test('source inspector returns raw and parsed source chapter views', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-inspect-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { inspectSourceChapter } = require('../lib/import-health');
  const slug = 'sample-inspect';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(sourceDir, '0003.md'), `---
source_lang: "en"
source_site: "fixture"
---
# Inspect Me

First paragraph.

Second paragraph.
`, 'utf8');

  const inspected = await inspectSourceChapter(slug, 3);

  assert.equal(inspected.title, 'Inspect Me');
  assert.equal(inspected.frontmatter.source_lang, 'en');
  assert.match(inspected.raw, /source_site/);
  assert.equal(inspected.cleanedText, 'First paragraph.\n\nSecond paragraph.');
  assert.equal(inspected.diagnostic.charCount, inspected.cleanedText.length);
});

test('repairMissingSourceTitles adds a markdown title from the first chapter line', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-repair-title-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { inspectSourceChapter, repairNovelImport } = require('../lib/import-health');
  const slug = 'sample-repair-title';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'novel.json'), JSON.stringify({ slug, title: 'Repair Title' }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0007.md'), '第7章 Repairable\n\nReal content paragraph.\nSecond paragraph.', 'utf8');

  const result = await repairNovelImport(slug, 'all');
  const inspected = await inspectSourceChapter(slug, 7);

  assert.equal(result.repair.titlesRepaired, 1);
  assert.equal(inspected.title, '第7章 Repairable');
  assert.match(inspected.raw, /^# 第7章 Repairable/);
  assert.match(inspected.cleanedText, /Real content paragraph\./);
  assert.match(inspected.cleanedText, /Second paragraph\./);
});

test('repairMissingSourceTitles infers embedded Chinese chapter titles from the next line', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-repair-embedded-title-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { inspectSourceChapter, repairNovelImport } = require('../lib/import-health');
  const slug = 'sample-repair-embedded-title';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'novel.json'), JSON.stringify({ slug, title: 'Embedded Title' }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0563.md'), [
    '全球降臨：帶著嫂嫂末世種田第563章',
    '占星法杖,古精靈部落(5600),一條小白蛇',
    '',
    '第一段正文，這裡才是小說內容。',
    '',
    '第二段正文。',
  ].join('\n'), 'utf8');

  const result = await repairNovelImport(slug, 'all');
  const inspected = await inspectSourceChapter(slug, 563);

  assert.equal(result.repair.titlesRepaired, 1);
  assert.equal(inspected.title, '第563章 占星法杖,古精靈部落(5600),一條小白蛇');
  assert.match(inspected.raw, /^# 第563章 占星法杖,古精靈部落\(5600\),一條小白蛇/);
  assert.match(inspected.cleanedText, /第一段正文/);
});

test('repairNovelImport replaces dirty site breadcrumb headings with chapter titles', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-repair-dirty-title-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { inspectSourceChapter, repairNovelImport } = require('../lib/import-health');
  const slug = 'sample-repair-dirty-title';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'novel.json'), JSON.stringify({ slug, title: 'Dirty Title' }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0001.md'), [
    '# 黃金屋中文 >> 全球降臨：帶著嫂嫂末世種田 >> 目錄 >> 第1章冰封紀元公測開啟',
    '',
    '第1章冰封紀元公測開啟',
    '作者:一條小白蛇  分類: 遊戲',
    '',
    '第一段正文。',
    '',
    '第二段正文。',
  ].join('\n'), 'utf8');

  const result = await repairNovelImport(slug, 'all');
  const inspected = await inspectSourceChapter(slug, 1);

  assert.equal(result.repair.titlesRepaired, 1);
  assert.equal(inspected.title, '第1章冰封紀元公測開啟');
  assert.match(inspected.raw, /^# 第1章冰封紀元公測開啟/);
  assert.doesNotMatch(inspected.raw, /黃金屋中文 >>/);
  assert.doesNotMatch(inspected.raw, /作者:一條小白蛇/);
});

test('repairNovelImport dry-run reports changes without touching source files', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-repair-dry-run-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { inspectSourceChapter, repairNovelImport } = require('../lib/import-health');
  const slug = 'sample-repair-dry-run';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'novel.json'), JSON.stringify({ slug, title: 'Dry Run' }), 'utf8');
  const original = [
    '# 黃金屋中文 >> Sample >> 目錄 >> 第2章乾跑',
    '',
    '第2章乾跑',
    '作者:測試  分類: 奇幻',
    '',
    '第一段正文。',
    '',
    'Sample 第2章乾跑 手機網頁版',
  ].join('\n');
  await fs.writeFile(path.join(sourceDir, '0002.md'), original, 'utf8');

  const result = await repairNovelImport(slug, 'all', { dryRun: true });
  const inspected = await inspectSourceChapter(slug, 2);

  assert.equal(result.repair.dryRun, true);
  assert.equal(result.repair.titlesRepaired, 1);
  assert.equal(result.repair.filesChanged, 1);
  assert.equal(result.repair.noiseLinesRemoved, 2);
  assert.equal(result.repair.changes[0].titleAfter, '第2章乾跑');
  assert.equal(inspected.raw, original);
});
