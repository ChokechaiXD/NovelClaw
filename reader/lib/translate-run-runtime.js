const DEFAULT_OUTPUT_TAIL_CHARS = 256 * 1024;

function appendBoundedTail(current, chunk, limit = DEFAULT_OUTPUT_TAIL_CHARS) {
  const maxChars = Math.max(0, Number(limit) || 0);
  if (maxChars === 0) return '';

  const next = String(current || '') + String(chunk || '');
  return next.length <= maxChars ? next : next.slice(-maxChars);
}

function createPersistScheduler(write, options = {}) {
  if (typeof write !== 'function') throw new TypeError('write must be a function');

  const delayMs = Math.max(0, Number(options.delayMs) || 0);
  const setTimer = options.setTimer || setTimeout;
  const clearTimer = options.clearTimer || clearTimeout;
  const onError = options.onError || (() => {});
  let timer = null;
  let dirty = false;
  let writeQueue = Promise.resolve();

  function queueWrite() {
    if (!dirty) return writeQueue;
    dirty = false;
    writeQueue = writeQueue.catch(() => {}).then(() => write());
    return writeQueue;
  }

  function schedule() {
    dirty = true;
    if (timer !== null) return;
    timer = setTimer(() => {
      timer = null;
      queueWrite().catch(onError);
    }, delayMs);
  }

  function flush() {
    if (timer !== null) {
      clearTimer(timer);
      timer = null;
    }
    return queueWrite();
  }

  return { schedule, flush };
}

module.exports = {
  DEFAULT_OUTPUT_TAIL_CHARS,
  appendBoundedTail,
  createPersistScheduler,
};
