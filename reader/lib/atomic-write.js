const fs = require('node:fs/promises');
const path = require('node:path');

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

module.exports = {
  writeJsonAtomic,
  writeTextAtomic,
};
