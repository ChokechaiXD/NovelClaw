const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

async function writeTextAtomic(filePath, text) {
  const dir = path.dirname(filePath);
  const tmpPath = path.join(dir, `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`);
  let handle = null;
  try {
    await fs.mkdir(dir, { recursive: true });
    handle = await fs.open(tmpPath, 'w');
    await handle.writeFile(text, 'utf8');
    await handle.sync();
    await handle.close();
    handle = null;
    await fs.rename(tmpPath, filePath);
  } catch (err) {
    if (handle) await handle.close().catch(() => {});
    await fs.unlink(tmpPath).catch(() => {});
    throw err;
  }
}

async function writeJsonAtomic(filePath, data) {
  await writeTextAtomic(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

async function withFileLock(filePath, callback, options = {}) {
  const timeoutMs = Math.max(100, Number(options.timeoutMs) || 5000);
  const staleMs = Math.max(timeoutMs, Number(options.staleMs) || 60000);
  const pollMs = Math.max(5, Number(options.pollMs) || 10);
  const lockPath = path.join(path.dirname(filePath), `.${path.basename(filePath)}.lock`);
  const deadline = Date.now() + timeoutMs;
  const ownerToken = `${process.pid}:${randomUUID()}`;
  let handle = null;
  let ownerStat = null;

  await fs.mkdir(path.dirname(filePath), { recursive: true });
  while (!handle) {
    try {
      handle = await fs.open(lockPath, 'wx');
      await handle.writeFile(`${ownerToken}\npid=${process.pid} time=${Date.now()}\n`, 'utf8');
      ownerStat = await handle.stat();
    } catch (err) {
      if (err.code !== 'EEXIST') throw err;
      const stat = await fs.stat(lockPath).catch(() => null);
      if (!stat) continue;
      if (Date.now() - stat.mtimeMs > staleMs) {
        await fs.unlink(lockPath).catch(() => {});
        continue;
      }
      if (Date.now() >= deadline) throw new Error(`Timed out waiting for file lock: ${lockPath}`);
      await new Promise(resolve => setTimeout(resolve, pollMs));
    }
  }

  try {
    return await callback();
  } finally {
    await handle.close().catch(() => {});
    const [currentStat, contents] = await Promise.all([
      fs.stat(lockPath).catch(() => null),
      fs.readFile(lockPath, 'utf8').catch(() => ''),
    ]);
    const sameFile = currentStat && ownerStat
      && currentStat.dev === ownerStat.dev
      && currentStat.ino === ownerStat.ino;
    if (sameFile && contents.split(/\r?\n/, 1)[0] === ownerToken) {
      await fs.unlink(lockPath).catch(() => {});
    }
  }
}

module.exports = {
  withFileLock,
  writeJsonAtomic,
  writeTextAtomic,
};
