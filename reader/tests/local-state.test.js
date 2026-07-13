const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { readLocalState, saveLocalState } = require('../lib/local-state');

test('readLocalState returns an empty object when state is missing or malformed', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-local-state-read-'));
  const target = path.join(dir, 'local_state.json');

  assert.deepEqual(await readLocalState(target), {});
  await fs.writeFile(target, '{invalid', 'utf8');
  assert.deepEqual(await readLocalState(target), {});
  await fs.writeFile(target, '[]', 'utf8');
  assert.deepEqual(await readLocalState(target), {});
});

test('saveLocalState writes a JSON object atomically', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-local-state-write-'));
  const target = path.join(dir, 'local_state.json');
  const state = { 'example-last': 12, example: { 12: 123456 } };

  await saveLocalState(state, target);

  const raw = await fs.readFile(target, 'utf8');
  const entries = await fs.readdir(dir);
  assert.equal(raw.endsWith('\n'), true);
  assert.deepEqual(JSON.parse(raw), state);
  assert.equal(entries.some(name => name.endsWith('.tmp')), false);
});

test('saveLocalState rejects non-object state', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-local-state-invalid-'));
  const target = path.join(dir, 'local_state.json');

  await assert.rejects(
    saveLocalState([], target),
    err => err instanceof TypeError && err.status === 400 && err.code === 'INVALID_LOCAL_STATE',
  );
});
