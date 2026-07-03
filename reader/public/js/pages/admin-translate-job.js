/* Job tracker helpers for the admin translate workflow. */

(function () {
  const ACTIVE_STATUSES = ['running', 'queued', 'cancelling'];

  function isActiveStatus(status) {
    return ACTIVE_STATUSES.includes(status);
  }

  function syncResultsFromRun(run = {}, resultByNum = {}) {
    for (const item of run.chapters || []) {
      const num = parseInt(item.num || item.ch, 10);
      if (!Number.isFinite(num)) continue;
      resultByNum[num] = {
        ...item,
        status: item.status === 'translated' ? 'ok' : item.status,
      };
    }
    return resultByNum;
  }

  function renderPanel({ run = null, resultByNum = {}, currentModel = '-', renderChapterTable = null } = {}) {
    const badge = document.getElementById('translate-job-badge');
    const fill = document.getElementById('translate-job-progress-fill');
    const progressText = document.getElementById('translate-job-progress-text');
    const doneEl = document.getElementById('translate-job-done');
    const reviewEl = document.getElementById('translate-job-review');
    const failedEl = document.getElementById('translate-job-failed');
    const currentEl = document.getElementById('translate-job-current');
    const eventsEl = document.getElementById('translate-job-events');
    const cancelBtn = document.getElementById('translate-job-cancel');
    if (!badge || !fill || !progressText || !doneEl || !reviewEl || !failedEl || !currentEl || !eventsEl || !cancelBtn) {
      return { rendered: false, active: false };
    }

    if (!run) {
      badge.textContent = 'Idle';
      badge.className = 'c-badge c-badge--gray';
      fill.style.width = '0%';
      progressText.textContent = '0%';
      doneEl.textContent = '0';
      reviewEl.textContent = '0';
      failedEl.textContent = '0';
      currentEl.textContent = 'ยังไม่มีงานที่กำลังรัน';
      eventsEl.textContent = 'Waiting for a run.';
      cancelBtn.hidden = true;
      return { rendered: true, active: false };
    }

    syncResultsFromRun(run, resultByNum);
    const pct = run.total ? Math.round(((run.done || 0) / run.total) * 100) : 0;
    const badgeClass = isActiveStatus(run.status)
      ? 'c-badge c-badge--amber'
      : run.status === 'failed' || run.status === 'cancelled'
        ? 'c-badge c-badge--red'
        : 'c-badge c-badge--teal';
    const statusLabels = {
      queued: 'Queued',
      running: 'Translating',
      cancelling: 'Cancelling',
      done: 'Done',
      failed: 'Failed',
      cancelled: 'Cancelled',
    };
    badge.textContent = statusLabels[run.status] || run.status || 'Unknown';
    badge.className = badgeClass;
    fill.style.width = Math.min(100, Math.max(0, pct)) + '%';
    progressText.textContent = pct + '%';
    doneEl.textContent = String(run.done || 0) + ' / ' + String(run.total || 0);
    reviewEl.textContent = String(run.needsReview || 0);
    failedEl.textContent = String(run.failed || 0);
    currentEl.textContent = run.currentChapter
      ? `กำลังแปล/ล่าสุด: ตอน ${run.currentChapter} · model ${run.model || currentModel || '-'}`
      : `รอผลลัพธ์จาก pipeline · model ${run.model || currentModel || '-'}`;
    eventsEl.textContent = (run.events || [])
      .slice(-8)
      .map(event => `${event.at || ''}  ${event.message || event.type || ''}`)
      .join('\n') || 'ยังไม่มี event จาก pipeline';
    cancelBtn.hidden = !isActiveStatus(run.status);
    if (typeof renderChapterTable === 'function') renderChapterTable();
    return { rendered: true, active: isActiveStatus(run.status), runId: run.runId || '' };
  }

  window.AdminTranslateJob = {
    isActiveStatus,
    syncResultsFromRun,
    renderPanel,
  };
})();
