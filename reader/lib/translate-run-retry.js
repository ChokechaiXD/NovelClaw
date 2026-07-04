const RETRY_STATUSES = new Set(['failed', 'needs_review']);

function normalizeStatus(status) {
  return String(status || '').trim().toLowerCase();
}

function chapterNum(item) {
  const num = parseInt(item?.num ?? item?.ch, 10);
  return Number.isFinite(num) && num > 0 ? num : null;
}

function rangeFromNums(nums) {
  const sorted = [...new Set(nums)]
    .map(num => parseInt(num, 10))
    .filter(num => Number.isFinite(num) && num > 0)
    .sort((a, b) => a - b);
  const ranges = [];
  let start = null;
  let prev = null;
  for (const num of sorted) {
    if (start === null) {
      start = num;
      prev = num;
      continue;
    }
    if (num === prev + 1) {
      prev = num;
      continue;
    }
    ranges.push(start === prev ? String(start) : `${start}-${prev}`);
    start = num;
    prev = num;
  }
  if (start !== null) ranges.push(start === prev ? String(start) : `${start}-${prev}`);
  return ranges.join(',');
}

function retryableChapters(run = {}, statuses = RETRY_STATUSES) {
  const wanted = new Set([...statuses].map(normalizeStatus));
  const nums = [];
  for (const item of run.chapters || []) {
    const num = chapterNum(item);
    if (!num) continue;
    if (wanted.has(normalizeStatus(item.status))) nums.push(num);
  }
  return [...new Set(nums)].sort((a, b) => a - b);
}

function buildRetryPlan(run = {}, options = {}) {
  const nums = retryableChapters(run, options.statuses || RETRY_STATUSES);
  return {
    sourceRunId: run.runId || '',
    slug: run.slug || '',
    nums,
    range: rangeFromNums(nums),
    total: nums.length,
    hasRetryable: nums.length > 0,
  };
}

module.exports = {
  buildRetryPlan,
  rangeFromNums,
  retryableChapters,
};
