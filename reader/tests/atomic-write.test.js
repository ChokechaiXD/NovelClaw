const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { withFileLock, writeJsonAtomic, writeTextAtomic } = require('../lib/atomic-write');

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

test('withFileLock serializes updates and removes its lock file', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-file-lock-'));
  const target = path.join(dir, 'glossary.json');
  let active = 0;
  let maxActive = 0;

  await Promise.all(Array.from({ length: 5 }, () => withFileLock(target, async () => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise(resolve => setTimeout(resolve, 5));
    active -= 1;
  })));

  assert.equal(maxActive, 1);
  assert.equal(await fs.stat(path.join(dir, '.glossary.json.lock')).catch(() => null), null);
});

test('a stale lock owner cannot remove the replacement owner lock', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'novelclaw-stale-lock-'));
  const target = path.join(dir, 'glossary.json');
  const lockPath = path.join(dir, '.glossary.json.lock');
  let releaseFirst;
  let releaseSecond;
  let markFirstEntered;
  let markSecondEntered;
  const firstEntered = new Promise(resolve => { markFirstEntered = resolve; });
  const secondEntered = new Promise(resolve => { markSecondEntered = resolve; });
  const holdFirst = new Promise(resolve => { releaseFirst = resolve; });
  const holdSecond = new Promise(resolve => { releaseSecond = resolve; });

  const first = withFileLock(target, async () => {
    markFirstEntered();
    await holdFirst;
  });
  await firstEntered;
  const old = new Date(Date.now() - 120000);
  await fs.utimes(lockPath, old, old);

  const second = withFileLock(target, async () => {
    markSecondEntered();
    await holdSecond;
  }, { timeoutMs: 1000, staleMs: 1000, pollMs: 5 });
  await secondEntered;
  releaseFirst();
  await first;

  assert.notEqual(await fs.stat(lockPath).catch(() => null), null);
  let thirdEntered = false;
  await assert.rejects(
    withFileLock(target, async () => { thirdEntered = true; }, {
      timeoutMs: 100,
      staleMs: 1000,
      pollMs: 5,
    }),
    /Timed out waiting for file lock/,
  );
  assert.equal(thirdEntered, false);

  releaseSecond();
  await second;
  assert.equal(await fs.stat(lockPath).catch(() => null), null);
});
