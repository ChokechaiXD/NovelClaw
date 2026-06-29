const fs = require('node:fs/promises');
const path = require('node:path');

function parseBatchLog(name, text, updatedAt = '') {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n').filter(Boolean);
  const recentLines = lines.slice(-12);
  const failures = [];
  let total = 0;
  let current = 0;
  let activeChapter = null;
  let passed = 0;
  let failed = 0;
  let timeout = 0;
  let completed = false;
  let currentChapter = null;

  for (const line of lines) {
    const totalMatch = line.match(/(?:ต้องแปล|ยังไม่แปล):\s*(\d+)\s*ตอน/);
    if (totalMatch) total = parseInt(totalMatch[1], 10) || total;

    const progressMatch = line.match(/\[(\d+)\/(\d+)\]\s*ตอน\s*(\d+)/);
    if (progressMatch) {
      current = parseInt(progressMatch[1], 10) || current;
      total = parseInt(progressMatch[2], 10) || total;
      currentChapter = parseInt(progressMatch[3], 10) || null;
      activeChapter = currentChapter;
      continue;
    }

    if (/✅/.test(line)) {
      passed += 1;
      continue;
    }

    if (/⌛|TIMEOUT/i.test(line)) {
      timeout += 1;
      failed += 1;
      failures.push({
        chapter: currentChapter,
        reason: line.replace(/^\s*[⌛❌]\s*/, '').trim(),
      });
      continue;
    }

    if (/❌|FAILED:/i.test(line)) {
      failed += 1;
      failures.push({
        chapter: currentChapter,
        reason: line.replace(/^\s*[⌛❌]\s*/, '').trim(),
      });
    }

    if (/เสร็จ|complete|finished/i.test(line)) completed = true;
  }

  const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  return {
    name,
    updatedAt,
    total,
    current,
    percent,
    activeChapter,
    passed,
    failed,
    timeout,
    completed,
    latestLine: lines[lines.length - 1] || '',
    recentLines,
    failures: failures.slice(-10).reverse(),
  };
}

async function readBatchLogs(rootDir) {
  const names = ['batch_all_log.txt', 'batch_2478_log.txt'];
  const logs = [];
  for (const name of names) {
    const filepath = path.join(rootDir, name);
    try {
      const [text, stat] = await Promise.all([
        fs.readFile(filepath, 'utf8'),
        fs.stat(filepath),
      ]);
      logs.push(parseBatchLog(name, text, stat.mtime.toISOString()));
    } catch (err) {
      if (err.code !== 'ENOENT') throw err;
    }
  }
  logs.sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
  return logs;
}

module.exports = {
  parseBatchLog,
  readBatchLogs,
};
