const STATUS_META = Object.freeze({
  translated: {
    label: 'แปลแล้ว',
    tone: 'teal',
    ready: true,
  },
  untranslated: {
    label: 'ยังไม่แปล',
    tone: 'gray',
    ready: true,
  },
  needs_review: {
    label: 'ควรดู',
    tone: 'amber',
    ready: true,
  },
  failed: {
    label: 'ล้มเหลว',
    tone: 'red',
    ready: true,
  },
  source_not_ready: {
    label: 'source error',
    tone: 'red',
    ready: false,
  },
  queued: {
    label: 'รอแปล',
    tone: 'gray',
    ready: true,
  },
  running: {
    label: 'กำลังแปล',
    tone: 'amber',
    ready: true,
  },
});

function statusPayload(status, reasons = []) {
  const meta = STATUS_META[status] || STATUS_META.untranslated;
  return {
    workflowStatus: status,
    workflowLabel: meta.label,
    workflowTone: meta.tone,
    workflowReady: meta.ready,
    workflowBlocked: meta.ready === false,
    workflowReasons: reasons.filter(Boolean),
  };
}

function normalizeRunStatus(status) {
  if (!status) return '';
  if (status === 'ok') return 'translated';
  if (status === 'translated') return 'translated';
  if (status === 'queued') return 'queued';
  if (status === 'running' || status === 'cancelling') return 'running';
  if (status === 'failed') return 'failed';
  if (status === 'needs_review') return 'needs_review';
  return 'needs_review';
}

function sourceIssueCodes(sourceIssue = {}) {
  return (sourceIssue?.issues || [])
    .map(issue => issue && issue.code)
    .filter(Boolean);
}

function hasBlockingSourceIssue(sourceIssue = {}) {
  return (sourceIssue?.issues || []).some(issue => issue && issue.severity === 'error');
}

function classifyChapterState({ chapter = {}, sourceIssue = null, runResult = null } = {}) {
  const runStatus = normalizeRunStatus(runResult?.status);
  if (runStatus) {
    return statusPayload(runStatus, [
      runResult.reason || '',
      runResult.runId ? `run:${runResult.runId}` : '',
    ]);
  }

  if (hasBlockingSourceIssue(sourceIssue)) {
    const codes = sourceIssueCodes(sourceIssue).slice(0, 3).join(', ');
    return statusPayload('source_not_ready', [codes || 'source issue']);
  }

  const quality = chapter.qualityRecord || chapter.quality;
  if (quality && quality.passed === false) {
    const hardFailures = (quality.hardFailures || []).slice(0, 2).join(', ');
    return statusPayload('needs_review', [hardFailures || 'quality gate failed']);
  }

  if (chapter.isTranslated || chapter.status === 'translated' || chapter.hasTh === true) {
    return statusPayload('translated');
  }

  return statusPayload('untranslated');
}

function decorateChapter(chapter = {}, context = {}) {
  const state = classifyChapterState({
    chapter,
    sourceIssue: context.sourceIssue || null,
    runResult: context.runResult || null,
  });
  const sourceIssues = context.sourceIssue?.issues || [];
  return {
    ...chapter,
    ...state,
    workflowSourceIssues: sourceIssues,
  };
}

function summarizeChapterStates(chapters = []) {
  const counts = {};
  for (const status of Object.keys(STATUS_META)) counts[status] = 0;
  for (const chapter of chapters) {
    const status = chapter.workflowStatus || classifyChapterState({ chapter }).workflowStatus;
    counts[status] = (counts[status] || 0) + 1;
  }
  return counts;
}

module.exports = {
  STATUS_META,
  classifyChapterState,
  decorateChapter,
  hasBlockingSourceIssue,
  normalizeRunStatus,
  summarizeChapterStates,
};
