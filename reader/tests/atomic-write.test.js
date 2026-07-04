const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { writeJsonAtomic, writeTextAtomic } = require('../lib/atomic-write');

async function listTempFiles(dir) {
  const names = await fs.readdir(dir);
  return names.filter(name => name.includes('.tmp'));
}

test('writeTextAtomic replaces an existing file without leaving temp files', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-atomic-text-'));
  const target = path.join(dir, 'sample.txt');
  await fs.writeFile(target, 'old', 'utf8');

  await writeTextAtomic(target, 'new');

  assert.equal(await fs.readFile(target, 'utf8'), 'new');
  assert.deepEqual(await listTempFiles(dir), []);
});

test('writeJsonAtomic writes formatted JSON with trailing newline', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-atomic-json-'));
  const target = path.join(dir, 'run.json');

  await writeJsonAtomic(target, { runId: 'abc', status: 'done' });

  const raw = await fs.readFile(target, 'utf8');
  assert.equal(raw.endsWith('\n'), true);
  assert.deepEqual(JSON.parse(raw), { runId: 'abc', status: 'done' });
});
