const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public', 'js', 'state.js'), 'utf8');

function loadStore() {
  const values = new Map();
  const requests = [];
  const context = {
    console: { warn() {} },
    document: { body: { dataset: {} } },
    fetch: async (url, options = {}) => {
      requests.push({ url, options });
      return { ok: true, json: async () => ({}) };
    },
    localStorage: {
      getItem(key) { return values.get(key) || null; },
      setItem(key, value) { values.set(key, value); },
    },
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.__store = Store;`, context);
  return { store: context.__store, requests, values };
}

test('recordRead updates history and last position with one server write', async () => {
  const { store, requests, values } = loadStore();
  await Promise.resolve();
  await Promise.resolve();
  requests.length = 0;

  store.recordRead('fixture-novel', 7);
  await Promise.resolve();

  assert.equal(store.isRead('fixture-novel', 7), true);
  assert.equal(store.getLastPosition('fixture-novel'), 7);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, '/api/local/state');
  assert.equal(requests[0].options.method, 'POST');

  const saved = JSON.parse(values.get('novelclaw-state'));
  assert.equal(saved['fixture-novel-last'], 7);
  assert.ok(saved['fixture-novel']['7'] > 0);
});
