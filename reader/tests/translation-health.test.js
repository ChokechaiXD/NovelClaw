const test = require('node:test');
const assert = require('node:assert/strict');

const { parseBatchLog } = require('../lib/translation-health');

test('parseBatchLog summarizes progress and failures from Thai batch logs', () => {
  const log = [
    '📖 ต้องแปล: 1039 ตอน (ข้าม 10 ตอนที่ API มีปัญหา)',
    '[1/1039] ตอน 201...',
    '  ✅ 86.0/100',
    '[2/1039] ตอน 202...',
    '  ⌛ TIMEOUT (300s)',
    '[3/1039] ตอน 203...',
    '  ❌ cannot access local variable classified',
    '[4/1039] ตอน 204...',
  ].join('\n');

  const parsed = parseBatchLog('batch_all_log.txt', log, '2026-06-29T00:00:00.000Z');

  assert.equal(parsed.name, 'batch_all_log.txt');
  assert.equal(parsed.total, 1039);
  assert.equal(parsed.current, 4);
  assert.equal(parsed.activeChapter, 204);
  assert.equal(parsed.passed, 1);
  assert.equal(parsed.failed, 2);
  assert.equal(parsed.timeout, 1);
  assert.equal(parsed.percent, 0);
  assert.deepEqual(parsed.failures.map(item => item.chapter), [203, 202]);
  assert.match(parsed.latestLine, /204/);
});
