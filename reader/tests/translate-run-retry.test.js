const test = require('node:test');
const assert = require('node:assert/strict');

const { buildRetryPlan, rangeFromNums, retryableChapters } = require('../lib/translate-run-retry');

test('rangeFromNums compacts sorted unique chapter ranges', () => {
  assert.equal(rangeFromNums([5, 4, 2, 2, 7, 6, 10]), '2,4-7,10');
});

test('retryableChapters selects failed and needs_review chapters only', () => {
  const run = {
    chapters: [
      { num: 1, status: 'translated' },
      { num: 2, status: 'needs_review' },
      { ch: 3, status: 'failed' },
      { num: 4, status: 'running' },
      { num: 5, status: 'ok' },
    ],
  };

  assert.deepEqual(retryableChapters(run), [2, 3]);
});

test('buildRetryPlan returns a restart-ready range for a run', () => {
  const plan = buildRetryPlan({
    runId: 'run-123',
    slug: 'global-descent',
    chapters: [
      { num: 8, status: 'failed' },
      { num: 9, status: 'failed' },
      { num: 11, status: 'needs_review' },
    ],
  });

  assert.deepEqual(plan, {
    sourceRunId: 'run-123',
    slug: 'global-descent',
    nums: [8, 9, 11],
    range: '8-9,11',
    total: 3,
    hasRetryable: true,
  });
});
