import { escapeHTML } from './utils.js';

export function createJobController({
  state, el, api, showToast, openModal, closeModal,
  loadChapters, loadChapterContent, loadNovels,
  renderQASummary, triggerQuickTranslate,
}) {
  let tocRefreshTimer = null;
  let progressHideTimer = null;
  let source = null;
  let bound = false;

  function scheduleLoadChapters(slug) {
    clearTimeout(tocRefreshTimer);
    tocRefreshTimer = setTimeout(() => loadChapters(slug), 2000);
  }

  function beginJob(jobID, kind = 'translation') {
    clearTimeout(progressHideTimer);
    progressHideTimer = null;
    state.currentJobId = jobID;
    state.currentJobKind = kind;
    state.activeJobQueue = [];
    if (el.modalQueue && !el.modalQueue.classList.contains('hidden')) renderQueueDrawer();
  }

  function finishJob() {
    state.currentJobId = null;
    state.currentJobKind = null;
  }

  function upsertQueue(chapterNo, patch) {
    if (!chapterNo) return;
    let item = state.activeJobQueue.find(entry => entry.chapterNo === chapterNo);
    if (!item) {
      item = { chapterNo };
      state.activeJobQueue.push(item);
    }
    Object.assign(item, patch);
    if (el.modalQueue && !el.modalQueue.classList.contains('hidden')) renderQueueDrawer();
  }

  function setRunningProgress(data) {
    const pct = Math.max(0, Math.min(100, Number(data.percentage) || 0));
    el.topProgressBar?.classList.remove('hidden');
    if (el.topProgressBar) {
      el.topProgressBar.style.width = `${pct}%`;
      el.topProgressBar.style.background = 'var(--accent)';
    }
    el.floatingJobBar?.classList.remove('hidden');
    if (el.floatJobTitle) el.floatJobTitle.innerText = data.message || 'กำลังแปล...';
    if (el.floatJobPct) el.floatJobPct.innerText = `${pct}%`;
    if (el.floatJobBar) el.floatJobBar.style.width = `${pct}%`;
    el.transProgressBox?.classList.remove('hidden');
    el.transErrorMsg?.classList.add('hidden');
    if (el.transProgressMsg) el.transProgressMsg.innerText = data.message || 'กำลังแปล...';
    if (el.transProgressPct) el.transProgressPct.innerText = `${pct}%`;
    if (el.transProgressBar) {
      el.transProgressBar.style.width = `${pct}%`;
      el.transProgressBar.style.background = 'var(--accent)';
    }
  }

  function hideProgressAfter(ms) {
    clearTimeout(progressHideTimer);
    progressHideTimer = setTimeout(() => {
      el.topProgressBar?.classList.add('hidden');
      el.floatingJobBar?.classList.add('hidden');
      progressHideTimer = null;
    }, ms);
  }

  function handleChapterTranslated(data) {
    showToast(`แปล ${data.title} เสร็จเรียบร้อยแล้ว ✨`, 'success');
    if (Array.isArray(data.warnings) && data.warnings.length) {
      const suffix = data.warnings.length > 1 ? ` (+${data.warnings.length - 1} จุด)` : '';
      showToast(`⚠️ ${data.warnings[0]}${suffix}`, 'warning');
    }
    if (typeof data.qaScore === 'number') {
      const report = {
        chapterNo: data.chapterNo,
        score: data.qaScore,
        issues: Array.isArray(data.qaIssues) ? data.qaIssues : [],
      };
      const index = state.qaReports.findIndex(item => item.chapterNo === data.chapterNo);
      if (index >= 0) state.qaReports[index] = report;
      else state.qaReports.push(report);
      if (el.modalIntelligence && !el.modalIntelligence.classList.contains('hidden')) renderQASummary();
    }
    upsertQueue(data.chapterNo, { status: 'done', title: data.title });
    if (state.currentSlug === data.novelSlug) {
      scheduleLoadChapters(state.currentSlug);
      if (state.currentView === 'reader' && state.currentChapterNo === data.chapterNo) {
        loadChapterContent(state.currentSlug, data.chapterNo);
      }
    }
  }

  function handleFinalStatus(data) {
    finishJob();
    if (data.status === 'partial') {
      showToast(data.message || 'การแปลเสร็จบางส่วน — มีบางตอนที่ต้องตรวจสอบ', 'warning');
      if (el.topProgressBar) {
        el.topProgressBar.classList.remove('hidden');
        el.topProgressBar.style.width = '100%';
        el.topProgressBar.style.background = 'var(--warning)';
      }
      if (el.floatJobPct) el.floatJobPct.innerText = '100%';
      if (el.floatJobBar) el.floatJobBar.style.width = '100%';
      if (el.floatJobTitle) el.floatJobTitle.innerText = 'แปลเสร็จบางส่วน ⚠️';
      hideProgressAfter(5000);
    } else if (data.status === 'completed') {
      showToast(data.message || 'การแปลเสร็จสิ้นเรียบร้อยแล้ว!', 'success');
      if (el.topProgressBar) {
        el.topProgressBar.style.background = 'var(--success)';
        el.topProgressBar.style.width = '100%';
      }
      if (el.floatJobPct) el.floatJobPct.innerText = '100%';
      if (el.floatJobBar) el.floatJobBar.style.width = '100%';
      if (el.floatJobTitle) el.floatJobTitle.innerText = 'แปลเสร็จสมบูรณ์ ✨';
      hideProgressAfter(3000);
    } else if (data.status === 'error') {
      showToast(data.message || 'การแปลล้มเหลว', 'error');
      if (el.topProgressBar) {
        el.topProgressBar.classList.remove('hidden');
        el.topProgressBar.style.background = 'var(--danger)';
        el.topProgressBar.style.width = '100%';
      }
      if (el.floatJobPct) el.floatJobPct.innerText = '100%';
      if (el.floatJobBar) el.floatJobBar.style.width = '100%';
      if (el.floatJobTitle) el.floatJobTitle.innerText = 'การแปลล้มเหลว';
      hideProgressAfter(5000);
    }
    if (state.currentSlug === data.novelSlug) scheduleLoadChapters(state.currentSlug);
  }

  function handleImportProgress(data) {
    const pct = Math.max(0, Math.min(100, Number(data.percentage) || 0));
    state.currentJobId = data.jobId || state.currentJobId;
    state.currentJobKind = 'import';
    el.topProgressBar?.classList.remove('hidden');
    if (el.topProgressBar) el.topProgressBar.style.width = `${pct}%`;
    el.floatingJobBar?.classList.remove('hidden');
    if (el.floatJobPct) el.floatJobPct.textContent = `${pct}%`;
    if (el.floatJobBar) el.floatJobBar.style.width = `${pct}%`;
    if (el.floatJobTitle) {
      el.floatJobTitle.textContent = `กำลังนำเข้า ${data.current || 0}/${data.total || 0} ตอน • สำเร็จ ${data.imported || 0}`;
    }
  }

  function handleImportFinal(data, kind) {
    finishJob();
    if (kind === 'partial') {
      showToast(data.message || 'นำเข้าเสร็จบางส่วน', 'warning');
      if (el.topProgressBar) el.topProgressBar.style.background = 'var(--warning)';
    } else if (kind === 'cancelled') {
      showToast('ยกเลิกการนำเข้าแล้ว', 'info');
    } else if (kind === 'error') {
      showToast(data.message || 'นำเข้านิยายล้มเหลว', 'error');
      if (el.topProgressBar) el.topProgressBar.style.background = 'var(--danger)';
    } else {
      showToast(data.message || 'นำเข้านิยายเสร็จสิ้นเรียบร้อยแล้ว', 'success');
      if (el.topProgressBar) el.topProgressBar.style.background = 'var(--success)';
    }
    if (el.topProgressBar) el.topProgressBar.style.width = '100%';
    if (el.floatJobPct) el.floatJobPct.textContent = '100%';
    if (el.floatJobBar) el.floatJobBar.style.width = '100%';
    hideProgressAfter(kind === 'partial' || kind === 'error' ? 5000 : 2500);
    loadNovels();
    if (state.currentSlug === data.novelSlug) loadChapters(state.currentSlug);
  }

  function handleSSEEvent(data) {
    if (data.type === 'auto_intelligence') {
      showToast(data.message || 'AI อัปเดตข้อมูลอัตโนมัติแล้ว', 'success');
      return;
    }
    if (data.type === 'chapter_translated') {
      handleChapterTranslated(data);
      return;
    }
    if (data.type === 'import_progress') {
      handleImportProgress(data);
      return;
    }
    if (data.type === 'import_done') {
      handleImportFinal(data, 'done');
      return;
    }
    if (data.type === 'import_partial') {
      handleImportFinal(data, 'partial');
      return;
    }
    if (data.type === 'import_cancelled') {
      handleImportFinal(data, 'cancelled');
      return;
    }
    if (data.type === 'import_error') {
      handleImportFinal(data, 'error');
      return;
    }
    if (data.status === 'running') {
      state.currentJobId = data.jobId;
      state.currentJobKind = 'translation';
      upsertQueue(data.currentChapter, { status: 'running', message: data.message });
      setRunningProgress(data);
      return;
    }
    if (data.status === 'error') {
      if ((Number(data.percentage) || 0) >= 100) {
        handleFinalStatus(data);
        return;
      }
      showToast(data.message, 'error');
      upsertQueue(data.currentChapter, {
        status: 'error',
        error: data.errorDetails || data.message,
      });
      el.transProgressBox?.classList.remove('hidden');
      if (el.transProgressMsg) el.transProgressMsg.innerText = data.message;
      if (el.transErrorMsg) {
        el.transErrorMsg.innerText = data.errorDetails || data.message;
        el.transErrorMsg.classList.remove('hidden');
      }
      if (el.transProgressBar) el.transProgressBar.style.background = 'var(--danger)';
      return;
    }
    if (data.status === 'partial' || data.status === 'completed') {
      handleFinalStatus(data);
      return;
    }
    if (data.status === 'cancelled') {
      const kind = state.currentJobKind;
      finishJob();
      showToast(kind === 'import' ? 'ยกเลิกการนำเข้าแล้ว' : 'ยกเลิกคิวการแปลแล้ว', 'info');
      el.topProgressBar?.classList.add('hidden');
      el.floatingJobBar?.classList.add('hidden');
    }
  }

  function initSSE() {
    if (source) return;
    source = new EventSource('/events');
    source.onmessage = event => {
      try {
        handleSSEEvent(JSON.parse(event.data));
      } catch (err) {
        console.error('SSE JSON error', err);
      }
    };
    source.onerror = () => console.warn('SSE connection interrupted; browser will retry');
    window.addEventListener('beforeunload', () => source?.close(), { once: true });
  }

  function openQueueModal() {
    openModal(el.modalQueue);
    renderQueueDrawer();
  }

  function renderQueueDrawer() {
    if (state.currentJobKind === 'import') {
      el.queueSummary.innerText = 'กำลังนำเข้านิยาย — สามารถยกเลิกได้จากปุ่มหยุดงาน';
      el.queueItemsContainer.innerHTML = '<div class="queue-empty">งานนำเข้ากำลังทำงานอยู่</div>';
      return;
    }
    if (!state.activeJobQueue.length) {
      el.queueSummary.innerText = 'ขณะนี้ไม่มีงานแปลค้างอยู่ในคิว';
      el.queueItemsContainer.innerHTML = '<div class="queue-empty">คิวงานว่าง</div>';
      return;
    }
    const total = state.activeJobQueue.length;
    const done = state.activeJobQueue.filter(item => item.status === 'done').length;
    const error = state.activeJobQueue.filter(item => item.status === 'error').length;
    const running = state.activeJobQueue.filter(item => item.status === 'running').length;
    el.queueSummary.innerHTML = `ทั้งหมด <b>${total}</b> ตอน | เสร็จแล้ว: <span style="color:#22c55e;">${done}</span> | กำลังแปล: <span style="color:#3b82f6;">${running}</span> | ล้มเหลว: <span style="color:#ef4444;">${error}</span>`;
    el.queueItemsContainer.innerHTML = state.activeJobQueue.map(item => `
      <div class="queue-item">
        <div>
          <b>ตอนที่ ${item.chapterNo}</b>: ${escapeHTML(item.title || item.message || '')}
          ${item.error ? `<div style="color: var(--danger); font-size: 0.78rem; margin-top: 0.2rem;">${escapeHTML(item.error)}</div>` : ''}
        </div>
        <div style="display:flex;align-items:center;gap:.5rem;">
          <span class="queue-badge ${item.status}">${item.status === 'done' ? '✅ เสร็จแล้ว' : item.status === 'running' ? '🔄 กำลังแปล' : item.status === 'error' ? '❌ ล้มเหลว' : '⏳ รอคิว'}</span>
          ${item.status === 'error' ? `<button class="btn btn-outline btn-sm btn-retry-ch" data-ch="${item.chapterNo}">🔄 แปลซ้ำ</button>` : ''}
        </div>
      </div>
    `).join('');
  }

  function bindJobEvents() {
    if (bound) return;
    bound = true;
    el.floatJobClickable?.addEventListener('click', openQueueModal);
    el.topProgressBar?.addEventListener('click', openQueueModal);
    el.btnCloseQueue?.addEventListener('click', () => closeModal(el.modalQueue));
    el.btnCancelFloatJob?.addEventListener('click', async () => {
      if (!state.currentJobId) return;
      await api(`/api/jobs/${state.currentJobId}/cancel`, { method: 'POST' }).catch(console.error);
    });
    el.queueItemsContainer?.addEventListener('click', event => {
      const button = event.target.closest('.btn-retry-ch');
      if (!button) return;
      const chapterNo = Number.parseInt(button.dataset.ch, 10);
      if (!Number.isFinite(chapterNo)) return;
      triggerQuickTranslate(state.currentSlug, chapterNo, chapterNo);
      closeModal(el.modalQueue);
    });
  }

  return {
    initSSE,
    bindJobEvents,
    beginJob,
  };
}
