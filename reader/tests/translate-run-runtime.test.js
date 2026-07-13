const test = require('node:test');
const assert = require('node:assert/strict');

const {
  appendBoundedTail,
  createPersistScheduler,
} = require('../lib/translate-run-runtime');

test('appendBoundedTail keeps only the newest output within the limit', () => {
  let output = appendBoundedTail('', '12345', 8);
  output = appendBoundedTail(output, '6789', 8);

  assert.equal(output, '23456789');
  assert.equal(output.length, 8);
  assert.equal(appendBoundedTail(output, 'abcdef', 0), '');
});

test('persist scheduler batches repeated events into one write', async () => {
  let scheduled = null;
  let writes = 0;
  const scheduler = createPersistScheduler(async () => { writes += 1; }, {
    delayMs: 250,
    setTimer(callback, delay) {
      assert.equal(delay, 250);
      assert.equal(scheduled, null);
      scheduled = callback;
      return callback;
    },
    clearTimer() {
      scheduled = null;
    },
  });

  scheduler.schedule();
  scheduler.schedule();
  scheduler.schedule();

  assert.equal(writes, 0);
  const runScheduledWrite = scheduled;
  scheduled = null;
  runScheduledWrite();
  await scheduler.flush();
  assert.equal(writes, 1);
});

test('persist scheduler flush queues terminal state after an in-flight write', async () => {
  let scheduled = null;
  let releaseFirstWrite;
  let writes = 0;
  const firstWriteBlocked = new Promise(resolve => { releaseFirstWrite = resolve; });
  const scheduler = createPersistScheduler(async () => {
    writes += 1;
    if (writes === 1) await firstWriteBlocked;
  }, {
    setTimer(callback) {
      scheduled = callback;
      return callback;
    },
    clearTimer() {
      scheduled = null;
    },
  });

  scheduler.schedule();
  const runScheduledWrite = scheduled;
  scheduled = null;
  runScheduledWrite();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(writes, 1);

  scheduler.schedule();
  const terminalFlush = scheduler.flush();
  assert.equal(writes, 1);
  releaseFirstWrite();
  await terminalFlush;

  assert.equal(writes, 2);
  assert.equal(scheduled, null);
});
