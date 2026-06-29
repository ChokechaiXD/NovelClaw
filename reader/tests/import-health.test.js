const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

test('import health flags link-only and dirty source chapters', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-health-'));
  process.env.NOVELCLAW_ROOT = root;

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
