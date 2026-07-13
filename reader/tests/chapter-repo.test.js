const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

function resetNovelRootModules() {
  for (const mod of ['../lib/paths', '../lib/chapter-repo']) {
    delete require.cache[require.resolve(mod)];
  }
}

async function pathExists(filepath) {
  try {
    await fs.access(filepath);
    return true;
  } catch {
    return false;
  }
}

test('listChapters uses source markdown title when language json title is generic', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-source-title-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'source-title-fallback';
  const chaptersDir = path.join(root, slug, 'chapters');
  const sourceDir = path.join(chaptersDir, 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(chaptersDir, '0007.cn.json'), JSON.stringify({
    novelId: slug,
    chapterNo: 7,
    targetLang: 'cn',
    title: { source: '第7章' },
    status: 'source',
    blocks: [{ type: 'narration', text: 'Source body.' }],
  }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0007.md'), [
    '# 第7章 Trading House',
    '',
    'Source body.',
  ].join('\n'), 'utf8');

  const { listChapters, rebuildChaptersIndex } = require('../lib/chapter-repo');
  const chapters = await listChapters(slug, { forceScan: true });
  const index = await rebuildChaptersIndex(slug);

  assert.equal(chapters[0].title, 'ตอนที่ 7 Trading House');
  assert.equal(chapters[0].status, 'source_only');
  assert.equal(index.chapters[0].title, 'ตอนที่ 7 Trading House');
  assert.equal(await pathExists(path.join(chaptersDir, 'index.json')), false);
});

test('chapter repository ignores retired root chapter formats', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-canonical-only-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'canonical-only';
  const chaptersDir = path.join(root, slug, 'chapters');
  await fs.mkdir(chaptersDir, { recursive: true });
  await fs.writeFile(path.join(chaptersDir, '0001.json'), JSON.stringify({ num: 1, title: 'Retired JSON' }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0002.md'), '# Retired Markdown\n\nBody.', 'utf8');

  const { getChapter, listChapters, rebuildChaptersIndex } = require('../lib/chapter-repo');
  const chapters = await listChapters(slug, { forceScan: true });
  const chapter = await getChapter(slug, 1, 'th');
  const index = await rebuildChaptersIndex(slug);

  assert.deepEqual(chapters, []);
  assert.equal(chapter, null);
  assert.equal(index.totalChapters, 0);
  assert.equal(await pathExists(path.join(chaptersDir, 'index.json')), false);
});

test('listChapters bypasses stale generic index titles and scans source titles', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-stale-index-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'stale-index-title';
  const chaptersDir = path.join(root, slug, 'chapters');
  const sourceDir = path.join(chaptersDir, 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'chapters.json'), JSON.stringify({
    slug,
    totalChapters: 1,
    chapters: [
      { num: 12, title: 'ตอนที่ 12', hasCn: true, hasTh: false, status: 'source_only' },
    ],
  }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0012.md'), [
    '# 第12章 Clean Source Title',
    '',
    'Source body.',
  ].join('\n'), 'utf8');

  const { listChapters } = require('../lib/chapter-repo');
  const chapters = await listChapters(slug);

  assert.equal(chapters[0].title, 'ตอนที่ 12 Clean Source Title');
  assert.equal(chapters[0].status, 'source_only');
});

test('listChapters repairs a generic translated title from the CN chapter heading', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-cn-title-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'generic-cn-title';
  const chaptersDir = path.join(root, slug, 'chapters');
  await fs.mkdir(chaptersDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'chapters.json'), JSON.stringify({
    slug,
    totalChapters: 1,
    chapters: [
      { num: 12, title: 'ตอนที่ 12', hasCn: true, hasTh: true, status: 'translated' },
    ],
  }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0012.th.json'), JSON.stringify({
    chapterNo: 12,
    title: { source: '', translated: 'ตอนที่ 12' },
    status: 'translated',
    paragraphs: ['ข้อความแปล'],
  }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0012.cn.json'), JSON.stringify({
    chapterNo: 12,
    title: { source: 'ตอนที่ 12' },
    status: 'source',
    paragraphs: ['第12章 Clean CN Heading', 'Source body.'],
  }), 'utf8');

  const { listChapters } = require('../lib/chapter-repo');
  const chapters = await listChapters(slug);
  const repairedIndex = JSON.parse(await fs.readFile(path.join(root, slug, 'chapters.json'), 'utf8'));

  assert.equal(chapters[0].title, 'ตอนที่ 12 Clean CN Heading');
  assert.equal(repairedIndex.chapters[0].title, 'ตอนที่ 12 Clean CN Heading');
});

test('listChapters repairs an index missing chapter files', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-missing-index-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'missing-index-entry';
  const chaptersDir = path.join(root, slug, 'chapters');
  await fs.mkdir(chaptersDir, { recursive: true });
  await fs.writeFile(path.join(root, slug, 'chapters.json'), JSON.stringify({
    slug,
    totalChapters: 1,
    chapters: [
      { num: 1, title: 'ตอนที่ 1 Existing', hasCn: true, hasTh: false, status: 'source_only' },
    ],
  }), 'utf8');
  for (const num of [1, 2]) {
    await fs.writeFile(path.join(chaptersDir, String(num).padStart(4, '0') + '.cn.json'), JSON.stringify({
      chapterNo: num,
      title: { source: `第${num}章 Chapter ${num}` },
      status: 'source',
      paragraphs: ['Source body.'],
    }), 'utf8');
  }

  const { listChapters } = require('../lib/chapter-repo');
  const chapters = await listChapters(slug);
  const repairedIndex = JSON.parse(await fs.readFile(path.join(root, slug, 'chapters.json'), 'utf8'));

  assert.deepEqual(chapters.map(chapter => chapter.num), [1, 2]);
  assert.equal(repairedIndex.totalChapters, 2);
});

test('listChapters does not promote dirty category source titles', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-dirty-title-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'dirty-source-title';
  const sourceDir = path.join(root, slug, 'chapters', 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(sourceDir, '1132.md'), [
    '# 第1132章 游戲·競技',
    '',
    '閱讀底色..',
    '曹星緩緩睜開雙眼，輕聲感嘆道：“果然……”',
  ].join('\n'), 'utf8');

  const { listChapters } = require('../lib/chapter-repo');
  const chapters = await listChapters(slug, { forceScan: true });

  assert.equal(chapters[0].title, 'ตอนที่ 1132 [ยังไม่แปล]');
  assert.equal(chapters[0].status, 'source_only');
});

test('listChapters includes translation quality only when requested', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-quality-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'quality-list';
  const chaptersDir = path.join(root, slug, 'chapters');
  await fs.mkdir(chaptersDir, { recursive: true });
  await fs.writeFile(path.join(chaptersDir, '0003.th.json'), JSON.stringify({
    chapterNo: 3,
    title: { translated: 'ตอนที่ 3 Quality Check', source: '' },
    status: 'translated',
    paragraphs: [{ type: 'narration', text: 'ทดสอบคุณภาพ' }],
    meta: { provider: 'openrouter', model: 'test-model', promptProfile: 'faithful_default' },
    qualityRecord: {
      passed: false,
      score: 72,
      hardFailures: ['Completeness: too short'],
      warnings: [],
      lengthRatio: 0.7,
    },
  }), 'utf8');

  const { listChapters } = require('../lib/chapter-repo');
  const basic = await listChapters(slug, { forceScan: true });
  const withQuality = await listChapters(slug, { forceScan: true, includeQuality: true });

  assert.equal(basic[0].qualityRecord, undefined);
  assert.equal(withQuality[0].score, 72);
  assert.equal(withQuality[0].qualityStatus, 'needs_review');
  assert.equal(withQuality[0].model, 'test-model');
});

test('deleteTranslatedChapters removes only selected Thai translations', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-delete-translated-selected-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'delete-translated-selected';
  const chaptersDir = path.join(root, slug, 'chapters');
  const sourceDir = path.join(chaptersDir, 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(chaptersDir, '0001.th.json'), JSON.stringify({ chapterNo: 1 }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0001.cn.json'), JSON.stringify({ chapterNo: 1 }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0002.th.json'), JSON.stringify({ chapterNo: 2 }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0001.md'), '# Chapter 1\n\nSource body.', 'utf8');
  await fs.writeFile(path.join(sourceDir, '0002.md'), '# Chapter 2\n\nSource body.', 'utf8');

  const { deleteTranslatedChapters } = require('../lib/chapter-repo');
  const result = await deleteTranslatedChapters(slug, [1]);

  assert.deepEqual(result, { deleted: 1, nums: [1] });
  assert.equal(await pathExists(path.join(chaptersDir, '0001.th.json')), false);
  assert.equal(await pathExists(path.join(chaptersDir, '0002.th.json')), true);
  assert.equal(await pathExists(path.join(chaptersDir, '0001.cn.json')), true);
  assert.equal(await pathExists(path.join(sourceDir, '0001.md')), true);
});

test('deleteTranslatedChapters can remove every Thai translation without deleting source files', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-chapter-repo-delete-translated-all-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const slug = 'delete-translated-all';
  const chaptersDir = path.join(root, slug, 'chapters');
  const sourceDir = path.join(chaptersDir, 'source');
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.writeFile(path.join(chaptersDir, '0001.th.json'), JSON.stringify({ chapterNo: 1 }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0002.th.json'), JSON.stringify({ chapterNo: 2 }), 'utf8');
  await fs.writeFile(path.join(chaptersDir, '0002.cn.json'), JSON.stringify({ chapterNo: 2 }), 'utf8');
  await fs.writeFile(path.join(sourceDir, '0001.md'), '# Chapter 1\n\nSource body.', 'utf8');
  await fs.writeFile(path.join(sourceDir, '0002.md'), '# Chapter 2\n\nSource body.', 'utf8');

  const { deleteTranslatedChapters } = require('../lib/chapter-repo');
  const result = await deleteTranslatedChapters(slug);

  assert.deepEqual(result, { deleted: 2, nums: [1, 2] });
  assert.equal(await pathExists(path.join(chaptersDir, '0001.th.json')), false);
  assert.equal(await pathExists(path.join(chaptersDir, '0002.th.json')), false);
  assert.equal(await pathExists(path.join(chaptersDir, '0002.cn.json')), true);
  assert.equal(await pathExists(path.join(sourceDir, '0001.md')), true);
  assert.equal(await pathExists(path.join(sourceDir, '0002.md')), true);
});
