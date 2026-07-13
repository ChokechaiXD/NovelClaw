const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

function resetNovelRootModules() {
  for (const mod of ['../lib/paths', '../lib/chapter-repo', '../lib/novel-repo']) {
    delete require.cache[require.resolve(mod)];
  }
}

test('saveNovelMeta writes only canonical novel.json', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-novel-repo-canonical-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const { getNovelMeta, saveNovelMeta } = require('../lib/novel-repo');
  await saveNovelMeta('canonical-novel', {
    title: 'Canonical Novel',
    source_lang: 'cn',
    target_lang: 'th',
    total_chapters: 12,
  });

  const saved = JSON.parse(await fs.readFile(path.join(root, 'canonical-novel', 'novel.json'), 'utf8'));
  const meta = await getNovelMeta('canonical-novel');

  assert.equal(saved.totalChapters, 12);
  assert.equal(meta.title, 'Canonical Novel');
  await assert.rejects(fs.access(path.join(root, 'canonical-novel', 'meta.md')));
});

test('getNovelMeta surfaces malformed canonical metadata', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-novel-repo-invalid-'));
  process.env.NOVELCLAW_ROOT = root;
  resetNovelRootModules();

  const novelDir = path.join(root, 'invalid-novel');
  await fs.mkdir(novelDir, { recursive: true });
  await fs.writeFile(path.join(novelDir, 'novel.json'), '{invalid', 'utf8');

  const { getNovelMeta } = require('../lib/novel-repo');
  await assert.rejects(getNovelMeta('invalid-novel'), SyntaxError);
});
