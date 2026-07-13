const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const PAGE_DIR = path.resolve(__dirname, '..', 'public', 'js', 'pages');
const pages = {
  'admin-translate.js': ['id="translate-health-refresh"', 'href="#admin/provider"'],
  'admin-glossary.js': ['id="glossary-novel-select"', 'href="#admin/translate/'],
  'admin-provider.js': ['id="provider-refresh-models"', 'id="provider-save"'],
  'admin-logs.js': ['id="logs-novel-select"', 'id="logs-chapter-num"'],
  'admin-novels.js': ['id="admin-novel-search"', 'id="admin-novels-tbody"'],
  'admin-chapters.js': ['id="ch-filter-search"', 'id="ch-translate-selected"'],
  'admin-novel-edit.js': ['id="edit-save"', 'id="edit-cover-save"'],
};

for (const [filename, behaviorTokens] of Object.entries(pages)) {
  test(`${filename} uses the semantic studio page heading`, () => {
    const source = fs.readFileSync(path.join(PAGE_DIR, filename), 'utf8');

    assert.match(source, /<header class="c-page-heading c-page-heading--studio">/);
    assert.match(source, /<h1>[^<]*[\u0E00-\u0E7F][^<]*<\/h1>/);
    assert.doesNotMatch(source, /c-control-center|c-admin-cockpit|__cockpit|<h2\b/);
    for (const token of behaviorTokens) {
      assert.ok(source.includes(token), `${filename} must keep behavior hook: ${token}`);
    }
  });
}

test('leaving the translation studio clears its polling interval', () => {
  const translateSource = fs.readFileSync(path.join(PAGE_DIR, 'admin-translate.js'), 'utf8');
  const appSource = fs.readFileSync(path.resolve(PAGE_DIR, '..', 'app.js'), 'utf8');

  assert.match(translateSource, /cleanup\(\) \{[\s\S]*clearInterval\(this\._pollTimer\)[\s\S]*this\._pollTimer = null;/);
  assert.match(translateSource, /async render\(params\) \{[\s\S]*this\.cleanup\(\);/);
  assert.match(appSource, /page === 'admin' && params\.page === 'translate'/);
  assert.ok(appSource.includes('window.AdminTranslatePage?.cleanup?.();'));
});
