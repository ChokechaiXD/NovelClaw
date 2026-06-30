const test = require('node:test');
const assert = require('node:assert/strict');

const { parseTranslateJsonOutput, parseBatchTranslateSummary } = require('../lib/translate-result');

test('parseTranslateJsonOutput reads ok and failed JSON lines', () => {
  const parsed = parseTranslateJsonOutput([
    'noise line',
    '{"status":"failed","ch":12,"reason":"source_not_found"}',
    '{"status":"ok","ch":13,"score":91}',
  ].join('\n'));

  assert.equal(parsed.length, 2);
  assert.equal(parsed[0].status, 'failed');
  assert.equal(parsed[0].reason, 'source_not_found');
  assert.equal(parsed[1].status, 'ok');
  assert.equal(parsed[1].score, 91);
});

test('parseBatchTranslateSummary flags failed chapters from CLI summary', () => {
  const parsed = parseBatchTranslateSummary('完毕! 8 ผ่าน, 2 ล้มเหลว จาก 10 ตอน');

  assert.deepEqual(parsed, { passed: 8, failed: 2, total: 10 });
});

test('parseBatchTranslateSummary prefers structured JSON chapter statuses', () => {
  const parsed = parseBatchTranslateSummary([
    '{"status":"ok","ch":1,"quality":{"score":91}}',
    '{"status":"needs_review","ch":2,"reason":"quality gate failed","quality":{"hardFailures":["Completeness: too short"]}}',
    '{"status":"failed","ch":3,"reason":"source_not_found"}',
    '完毕! 1 ผ่าน, 2 ล้มเหลว จาก 3 ตอน',
  ].join('\n'));

  assert.equal(parsed.passed, 1);
  assert.equal(parsed.failed, 2);
  assert.equal(parsed.total, 3);
  assert.equal(parsed.chapters.length, 3);
  assert.equal(parsed.chapters[1].status, 'needs_review');
  assert.equal(parsed.chapters[1].reason, 'quality gate failed');
});
