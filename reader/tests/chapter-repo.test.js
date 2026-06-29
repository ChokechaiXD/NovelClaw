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
