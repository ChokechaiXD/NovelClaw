const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const adminSource = fs.readFileSync(
  path.join(__dirname, '..', 'public', 'js', 'pages', 'admin.js'),
  'utf8'
);

function createHarness() {
  const loaded = [];
  const rendered = [];
  const window = {};
  let adminRoute = null;

  const pageByAsset = {
    '/js/pages/admin-dashboard.js': 'AdminDashboardPage',
    '/js/pages/admin-import.js': 'AdminImportPage',
    '/js/pages/admin-translate.js': 'AdminTranslatePage',
  };

  const document = {
    createElement() {
      return {};
    },
    head: {
      appendChild(script) {
        loaded.push(script.src);
        const pageName = pageByAsset[script.src];
        if (pageName) {
          window[pageName] = {
            render(params) {
              rendered.push({ pageName, params });
            },
          };
        }
        queueMicrotask(() => script.onload());
      },
    },
  };

  const Router = {
    register(name, handler) {
      if (name === 'admin') adminRoute = handler;
    },
  };

  vm.runInNewContext(adminSource, { document, Router, window });
  return {
    loaded,
    rendered,
    run(params) {
      return adminRoute(params);
    },
  };
}

test('admin dashboard loads no route-specific shared models', async () => {
  const harness = createHarness();

  await harness.run({ page: 'dash' });

  assert.deepEqual(harness.loaded, ['/js/pages/admin-dashboard.js']);
  assert.equal(harness.rendered[0].pageName, 'AdminDashboardPage');
});

test('admin import loads only its shared dependencies before the page', async () => {
  const harness = createHarness();

  await harness.run({ page: 'import', slug: 'demo' });

  assert.deepEqual(harness.loaded, [
    '/js/pages/admin-ui.js',
    '/js/pages/admin-format.js',
    '/js/pages/admin-import-model.js',
    '/js/pages/admin-import.js',
  ]);
  assert.equal(harness.rendered[0].pageName, 'AdminImportPage');
});

test('admin translate loads dependencies in three bounded waves', async () => {
  const harness = createHarness();

  await harness.run({ page: 'translate', slug: 'demo' });

  assert.deepEqual(harness.loaded, [
    '/js/pages/admin-ui.js',
    '/js/pages/admin-format.js',
    '/js/pages/admin-translate-model.js',
    '/js/pages/admin-translate-view.js',
    '/js/pages/admin-translate-job.js',
    '/js/pages/admin-translate-catalog.js',
    '/js/pages/admin-translate-selection.js',
    '/js/pages/admin-translate-command.js',
    '/js/pages/admin-translate.js',
  ]);
  assert.equal(harness.rendered[0].pageName, 'AdminTranslatePage');
});
