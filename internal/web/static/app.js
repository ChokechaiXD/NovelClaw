/* ==========================================================================
   NovelClaw — Client Application Logic (Full Quality Audit Edition)
   ========================================================================== */

(function () {
  'use strict';

  // State
  const state = {
    currentView: 'library',
    currentSlug: null,
    currentNovel: null,
    currentChapterNo: 1,
    currentChapterData: null,
    currentJobId: null,
    readingMode: localStorage.getItem('nc_reading_mode') || 'thai', // 'thai' | 'bilingual' | 'source'
    novels: [],
    chapters: [],
    glossaryTerms: [],
    availableModels: [],
    defaultModel: localStorage.getItem('nc_model') || '',
    fontSize: parseInt(localStorage.getItem('nc_font_size') || '18', 10),
    theme: localStorage.getItem('nc_theme') || 'dark',
    tts: {
      speaking: false,
      paused: false,
      paragraphs: [],
      currentIdx: 0,
      speed: 1.0,
      voice: localStorage.getItem('nc_tts_voice') || 'edge-tts/th-TH-NiwatNeural',
      audioElement: null,
      audioBlobs: {},
    },
    activeJobQueue: [],
  };

  // DOM Elements
  const el = {
    viewLibrary: document.getElementById('view-library'),
    viewDetail: document.getElementById('view-detail'),
    viewReader: document.getElementById('view-reader'),
    novelGrid: document.getElementById('novel-grid'),
    novelCount: document.getElementById('novel-count'),
    detailHeader: document.getElementById('detail-header'),
    chapterList: document.getElementById('chapter-list'),
    readerNovelTitle: document.getElementById('reader-novel-title'),
    readerChapterTitle: document.getElementById('reader-chapter-title'),
    readerContent: document.getElementById('reader-content'),
    readerToolbar: document.getElementById('reader-toolbar'),
    toastContainer: document.getElementById('toast-container'),

    // Top Progress Bar & Floating Job Bar
    topProgressBar: document.getElementById('top-progress-bar'),
    floatingJobBar: document.getElementById('floating-job-bar'),
    floatJobClickable: document.getElementById('float-job-clickable'),
    floatJobTitle: document.getElementById('float-job-title'),
    floatJobPct: document.getElementById('float-job-pct'),
    floatJobBar: document.getElementById('float-job-bar'),
    btnCancelFloatJob: document.getElementById('btn-cancel-float-job'),

    // Buttons
    btnBrand: document.getElementById('btn-brand'),
    btnBackLibrary: document.getElementById('btn-back-library'),
    btnOpenImport: document.getElementById('btn-open-import'),
    btnOpenSettings: document.getElementById('btn-open-settings'),
    btnThemeToggle: document.getElementById('btn-theme-toggle'),
    btnQuickTranslate: document.getElementById('btn-quick-translate'),
    btnOpenExport: document.getElementById('btn-open-export'),
    btnOpenGlossary: document.getElementById('btn-open-glossary'),
    btnPrevChapter: document.getElementById('btn-prev-chapter'),
    btnNextChapter: document.getElementById('btn-next-chapter'),
    btnReaderChapters: document.getElementById('btn-reader-chapters'),
    btnPrevChapterTop: document.getElementById('btn-prev-chapter-top'),
    btnNextChapterTop: document.getElementById('btn-next-chapter-top'),
    btnReaderChaptersTop: document.getElementById('btn-reader-chapters-top'),
    btnReaderBack: document.getElementById('btn-reader-back'),
    btnReaderTTS: document.getElementById('btn-reader-tts'),
    btnFontDecrease: document.getElementById('btn-font-decrease'),
    btnFontIncrease: document.getElementById('btn-font-increase'),
    btnReaderMode: document.getElementById('btn-reader-mode'),
    btnReaderTranslate: document.getElementById('btn-reader-translate'),
    btnReaderTheme: document.getElementById('btn-reader-theme'),

    // Modals
    modalExport: document.getElementById('modal-export'),
    btnCloseExport: document.getElementById('btn-close-export'),
    exportFormat: document.getElementById('export-format'),
    exportStart: document.getElementById('export-start'),
    exportEnd: document.getElementById('export-end'),
    btnDoExport: document.getElementById('btn-do-export'),

    modalQueue: document.getElementById('modal-queue'),
    btnCloseQueue: document.getElementById('btn-close-queue'),
    queueSummary: document.getElementById('queue-summary'),
    queueItemsContainer: document.getElementById('queue-items-container'),

    ttsPlayerBar: document.getElementById('tts-player-bar'),
    ttsStatus: document.getElementById('tts-status'),
    ttsVoice: document.getElementById('tts-voice'),
    btnTTSPrev: document.getElementById('btn-tts-prev'),
    btnTTSPlayPause: document.getElementById('btn-tts-playpause'),
    btnTTSNext: document.getElementById('btn-tts-next'),
    ttsSpeed: document.getElementById('tts-speed'),
    btnTTSClose: document.getElementById('btn-tts-close'),

    // Modals
    modalImport: document.getElementById('modal-import'),
    btnCloseImport: document.getElementById('btn-close-import'),
    tabImportUrl: document.getElementById('tab-import-url'),
    tabImportPaste: document.getElementById('tab-import-paste'),
    formImportUrl: document.getElementById('form-import-url'),
    formImportPaste: document.getElementById('form-import-paste'),
    importGenre: document.getElementById('import-genre'),
    pasteNovelSelect: document.getElementById('paste-novel-select'),
    pasteNewNovelFields: document.getElementById('paste-new-novel-fields'),
    pasteNovelTitle: document.getElementById('paste-novel-title'),
    pasteSlug: document.getElementById('paste-slug'),
    pasteGenre: document.getElementById('paste-genre'),
    pasteTitle: document.getElementById('paste-title'),
    pasteChNum: document.getElementById('paste-ch-num'),
    pasteContent: document.getElementById('paste-content'),

    modalTranslate: document.getElementById('modal-translate'),
    btnCloseTranslate: document.getElementById('btn-close-translate'),
    formTranslate: document.getElementById('form-translate'),
    transStart: document.getElementById('trans-start'),
    transEnd: document.getElementById('trans-end'),
    transModelSelect: document.getElementById('trans-model-select'),
    cfgProvider: document.getElementById('cfg-provider'),
    btnDetectProviders: document.getElementById('btn-detect-providers'),
    detectProviders: document.getElementById('detect-providers'),
    btnRefreshModels: document.getElementById('btn-refresh-models'),
    transGenre: document.getElementById('trans-genre'),
    transForce: document.getElementById('trans-force'),
    transProgressBox: document.getElementById('trans-progress-box'),
    transProgressMsg: document.getElementById('trans-progress-msg'),
    transProgressPct: document.getElementById('trans-progress-pct'),
    transProgressBar: document.getElementById('trans-progress-bar'),
    transErrorMsg: document.getElementById('trans-error-msg'),

    modalGlossary: document.getElementById('modal-glossary'),
    btnCloseGlossary: document.getElementById('btn-close-glossary'),
    discStart: document.getElementById('disc-start'),
    discEnd: document.getElementById('disc-end'),
    btnRunDiscovery: document.getElementById('btn-run-discovery'),
    discStatus: document.getElementById('disc-status'),
    formAddTerm: document.getElementById('form-add-term'),
    glossaryTbody: document.getElementById('glossary-tbody'),
    btnSaveGlossary: document.getElementById('btn-save-glossary'),
    btnGlossaryCheck: document.getElementById('btn-glossary-check'),
    glossaryQaResults: document.getElementById('glossary-qa-results'),

    modalSettings: document.getElementById('modal-settings'),
    btnCloseSettings: document.getElementById('btn-close-settings'),
    formSettings: document.getElementById('form-settings'),
    cfgRouterUrl: document.getElementById('cfg-router-url'),
    cfgApiKey: document.getElementById('cfg-api-key'),
    cfgModelSelect: document.getElementById('cfg-model-select'),
    cfgModelCustom: document.getElementById('cfg-model-custom'),
    btnCfgRefreshModels: document.getElementById('btn-cfg-refresh-models'),
    cfgTemp: document.getElementById('cfg-temp'),
  };

  // Initialization
  async function init() {
    applyTheme(state.theme);
    applyFontSize(state.fontSize);
    updateModeButtonText();
    initTTS();
    bindEvents();
    bindKeyboardShortcuts();
    bindScrollTracker();
    bindTouchGestures();
    initSSE();
    await loadConfigAndModels();
    loadNovels();
  }

  // Views Management
  function showView(viewName) {
    state.currentView = viewName;
    el.viewLibrary.classList.toggle('hidden', viewName !== 'library');
    el.viewDetail.classList.toggle('hidden', viewName !== 'detail');
    el.viewReader.classList.toggle('hidden', viewName !== 'reader');
    el.readerToolbar.classList.toggle('hidden', viewName !== 'reader');

    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  // API Helpers
  async function api(path, options = {}) {
    try {
      const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      showToast(err.message, 'error');
      throw err;
    }
  }

  // Toast Notifications
  function showToast(msg, type = 'info') {
    // Limit visible toasts to prevent flooding
    const existing = el.toastContainer.querySelectorAll('.toast');
    if (existing.length >= 5) {
      existing[0].remove();
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : '📢';
    // Escape: messages can carry server/LLM error text.
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHTML(msg)}</span>`;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Modal Scroll Lock Helpers
  function openModal(modalEl) {
    if (modalEl) {
      modalEl.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal(modalEl) {
    if (modalEl) {
      modalEl.classList.add('hidden');
      document.body.style.overflow = '';
    }
  }

  // SSE Realtime Events
  function initSSE() {
    const evtSource = new EventSource('/events');
    evtSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        handleSSEEvent(data);
      } catch (err) {
        console.error('SSE JSON error', err);
      }
    };
  }

  // Parallel jobs emit one event per chapter; coalesce TOC refetches so a
  // 100-chapter batch triggers one reload instead of 100.
  let tocRefreshTimer = null;
  function scheduleLoadChapters(slug) {
    clearTimeout(tocRefreshTimer);
    tocRefreshTimer = setTimeout(() => loadChapters(slug), 2000);
  }

  function handleSSEEvent(data) {
    if (data.type === 'chapter_translated') {
            showToast(`แปล ${data.title} เสร็จเรียบร้อยแล้ว ✨`, 'success');
                  if (Array.isArray(data.warnings) && data.warnings.length > 0) {
                    showToast(`⚠️ ${data.warnings[0]}${data.warnings.length > 1 ? ` (+${data.warnings.length - 1} จุด)` : ''}`, 'warning');
                  }
      
      const existing = state.activeJobQueue.find(i => i.chapterNo === data.chapterNo);
      if (existing) {
        existing.status = 'done';
        existing.title = data.title;
      } else {
        state.activeJobQueue.push({ chapterNo: data.chapterNo, status: 'done', title: data.title });
      }
      if (el.modalQueue && !el.modalQueue.classList.contains('hidden')) {
        renderQueueDrawer();
      }

      // Auto Hot-Swap if reader is viewing this chapter
      if (state.currentSlug === data.novelSlug) {
        scheduleLoadChapters(state.currentSlug);
        if (state.currentView === 'reader' && state.currentChapterNo === data.chapterNo) {
          loadChapterContent(state.currentSlug, data.chapterNo);
        }
      }
    } else if (data.status === 'running') {
      state.currentJobId = data.jobId;
      
      const existing = state.activeJobQueue.find(i => i.chapterNo === data.currentChapter);
      if (existing) {
        existing.status = 'running';
        existing.message = data.message;
      } else {
        state.activeJobQueue.push({ chapterNo: data.currentChapter, status: 'running', message: data.message });
      }
      if (el.modalQueue && !el.modalQueue.classList.contains('hidden')) {
        renderQueueDrawer();
      }

      el.topProgressBar.classList.remove('hidden');
      el.topProgressBar.style.width = `${data.percentage}%`;

      el.floatingJobBar.classList.remove('hidden');
      el.floatJobTitle.innerText = data.message;
      el.floatJobPct.innerText = `${data.percentage}%`;
      el.floatJobBar.style.width = `${data.percentage}%`;

      el.transProgressBox.classList.remove('hidden');
      el.transErrorMsg.classList.add('hidden');
      el.transProgressMsg.innerText = data.message;
      el.transProgressPct.innerText = `${data.percentage}%`;
      el.transProgressBar.style.width = `${data.percentage}%`;
      el.transProgressBar.style.background = 'var(--accent)';
    } else if (data.status === 'error') {
      showToast(data.message, 'error');
      
      const existing = state.activeJobQueue.find(i => i.chapterNo === data.currentChapter);
      if (existing) {
        existing.status = 'error';
        existing.error = data.errorDetails || data.message;
      } else {
        state.activeJobQueue.push({ chapterNo: data.currentChapter, status: 'error', error: data.errorDetails || data.message });
      }
      if (el.modalQueue && !el.modalQueue.classList.contains('hidden')) {
        renderQueueDrawer();
      }

      el.transProgressBox.classList.remove('hidden');
      el.transProgressMsg.innerText = data.message;
      el.transErrorMsg.innerText = data.errorDetails || data.message;
      el.transErrorMsg.classList.remove('hidden');
      el.transProgressBar.style.background = 'var(--danger)';
    } else if (data.status === 'completed') {
      showToast(data.message || 'การแปลเสร็จสิ้นเรียบร้อยแล้ว!', 'success');
      el.topProgressBar.style.width = '100%';
      el.floatJobPct.innerText = '100%';
      el.floatJobBar.style.width = '100%';
      el.floatJobTitle.innerText = 'แปลเสร็จสมบูรณ์ ✨';

      setTimeout(() => {
        el.topProgressBar.classList.add('hidden');
        el.floatingJobBar.classList.add('hidden');
      }, 3000);

      if (state.currentSlug === data.novelSlug) {
        scheduleLoadChapters(state.currentSlug);
      }
    } else if (data.status === 'cancelled') {
      showToast('ยกเลิกคิวการแปลแล้ว', 'info');
      el.topProgressBar.classList.add('hidden');
      el.floatingJobBar.classList.add('hidden');
    } else if (data.type === 'import_done') {
      showToast('นำเข้านิยายเสร็จสิ้นเรียบร้อยแล้ว', 'success');
      loadNovels();
      if (state.currentSlug === data.novelSlug) {
        loadChapters(state.currentSlug);
      }
    } else if (data.type === 'import_error') {
      showToast(data.message || 'นำเข้านิยายล้มเหลว', 'error');
    }
  }

  // Load Config and Discover Available Models
  // Provider presets: one click fills in the standard Base URL of each
  // provider; "custom" leaves the field untouched.
  const PROVIDER_PRESETS = {
    '9router': { url: 'http://localhost:20128/v1', apiKeyHint: 'ไม่ต้องใส่ key ถ้า 9Router ไม่ได้เปิด auth' },
    openai: { url: 'https://api.openai.com/v1', apiKeyHint: 'sk-...' },
    openrouter: { url: 'https://openrouter.ai/api/v1', apiKeyHint: 'sk-or-...' },
    deepseek: { url: 'https://api.deepseek.com/v1', apiKeyHint: 'sk-...' },
    ollama: { url: 'http://localhost:11434/v1', apiKeyHint: 'ไม่ต้องใช้ key' },
    lmstudio: { url: 'http://localhost:1234/v1', apiKeyHint: 'ไม่ต้องใช้ key' },
    custom: null,
  };

  function applyProviderPreset(provider) {
    const preset = PROVIDER_PRESETS[provider];
    if (!preset) return;
    el.cfgRouterUrl.value = preset.url;
    el.cfgApiKey.placeholder = preset.apiKeyHint;
  }

  async function loadConfigAndModels() {
    try {
      const cfg = await api('/api/config');
      const savedModel = localStorage.getItem('nc_model');
      state.defaultModel = savedModel || cfg.defaultModel || 'cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast';
      el.cfgRouterUrl.value = cfg.routerUrl || '';
      el.cfgProvider.value = cfg.provider || 'custom';
      // API key is never returned in full — show masked value as placeholder,
      // leave the field empty so submitting without changes keeps the real key.
      el.cfgApiKey.value = '';
      el.cfgApiKey.placeholder = cfg.apiKey ? `ตังค่าไว้อยู่แล้ว (${cfg.apiKey})` : 'sk-...';
      el.cfgTemp.value = cfg.temperature || 0.3;

      await discoverModels();
    } catch (err) {
      console.warn('Config load warning:', err);
    }
  }

  async function discoverModels() {
    try {
      const res = await api('/api/models');
      state.availableModels = res.models || [];
      populateModelDropdowns();
    } catch (err) {
      console.warn('Model discovery warning:', err);
      state.availableModels = [
        state.defaultModel,
        'cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast',
        'cf/@cf/deepseek-ai/deepseek-r1-distill-qwen-32b',
        'cf/@cf/qwen/qwen2.5-coder-32b-instruct',
        'kgw/nvidia/nemotron-3-super-120b-a12b:free',
        'gemini/gemini-3.7-flash',
        'deepseek/deepseek-chat',
      ];
      populateModelDropdowns();
    }
  }

  function populateModelDropdowns() {
    const models = Array.from(new Set(state.availableModels.filter(Boolean)));
    const optionsHTML = models.map(m => `
      <option value="${escapeHTML(m)}" ${m === state.defaultModel ? 'selected' : ''}>
        ${escapeHTML(m)}
      </option>
    `).join('');

    el.transModelSelect.innerHTML = optionsHTML;
    el.cfgModelSelect.innerHTML = optionsHTML;
  }

  // Load Novels Library
  async function loadNovels() {
    try {
      const res = await api('/api/novels');
      state.novels = res.novels || [];
      const novels = state.novels;
      el.novelCount.innerText = `${novels.length} เรื่อง`;

      if (novels.length === 0) {
        el.novelGrid.innerHTML = `
          <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📖</div>
            <p style="font-size: 1.1rem; margin-bottom: 1rem;">ยังไม่มีนิยายในคลัง</p>
            <button class="btn btn-primary" id="btn-empty-import">📥 นำเข้านิยายเรื่องแรก</button>
          </div>
        `;
        document.getElementById('btn-empty-import')?.addEventListener('click', () => {
          openImportModal();
        });
        return;
      }

      el.novelGrid.innerHTML = novels.map(n => {
        const genreBadge = n.genre ? `<span class="badge badge-info" style="font-size: 0.72rem;">${formatGenre(n.genre)}</span>` : '';
        return `
          <div class="novel-card" data-slug="${escapeHTML(n.slug)}">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.35rem;">
                <div class="novel-card-title">${escapeHTML(n.translatedTitle || n.title)}</div>
                ${genreBadge}
              </div>
              <div class="novel-card-subtitle">${escapeHTML(n.description || n.title)}</div>
            </div>
            <div>
              <div style="display: flex; gap: 0.4rem; margin-bottom: 0.5rem;">
                <span class="badge badge-info">${n.totalChapters || 0} ตอน</span>
                <span class="badge badge-success">แปลแล้ว ${n.translatedChapters || 0}</span>
              </div>
              ${n.totalChapters ? (() => {
                const pct = Math.round((n.translatedChapters || 0) / n.totalChapters * 100);
                return `<div style="height:4px; background:var(--bg-elevated); border-radius:2px; overflow:hidden; margin-bottom:0.5rem;" title="แปลแล้ว ${pct}%">
                  <div style="height:100%; width:${pct}%; background:var(--accent);"></div>
                </div>`;
              })() : ''}
              <div class="novel-card-meta">
                <span>${escapeHTML(n.author || 'ไม่ระบุผู้แต่ง')}</span>
                <button class="btn btn-primary btn-sm btn-read-novel" data-slug="${escapeHTML(n.slug)}">อ่าน</button>
              </div>
            </div>
          </div>
        `;
      }).join('');

      el.novelGrid.querySelectorAll('.novel-card').forEach(card => {
        card.addEventListener('click', () => {
          const slug = card.dataset.slug;
          openNovelDetail(slug);
        });
      });
    } catch (err) {
      console.error(err);
    }
  }

  // Open Novel Detail
  async function openNovelDetail(slug) {
    state.currentSlug = slug;
    showView('detail');

    try {
      const [novel, bm] = await Promise.all([
        api(`/api/novels/${slug}`),
        api(`/api/novels/${slug}/bookmark`).catch(() => ({ chapterNo: 1 })),
      ]);
      state.currentNovel = novel;

      const latestCh = bm.chapterNo || 1;
      const genreBadge = novel.genre ? `<span class="badge badge-info">${formatGenre(novel.genre)}</span>` : '';

      el.detailHeader.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;">
              <h1 style="font-size: 1.5rem; font-weight: 700;">
                ${escapeHTML(novel.translatedTitle || novel.title)}
              </h1>
              ${genreBadge}
            </div>
            <div style="font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
              ${escapeHTML(novel.title)} • ผู้แต่ง: ${escapeHTML(novel.author || 'ไม่ระบุ')}
            </div>
            <p style="font-size: 0.9rem; color: var(--text-muted); line-height: 1.5; max-width: 700px;">
              ${escapeHTML(novel.description || 'ไม่มีคำอธิบาย')}
            </p>
          </div>
          <button class="btn btn-primary" id="btn-continue-read" style="white-space: nowrap;">
            ▶️ อ่านต่อ (ตอนที่ ${latestCh})
          </button>
        </div>
      `;

      document.getElementById('btn-continue-read')?.addEventListener('click', () => {
        openChapter(slug, latestCh);
      });

      if (novel.genre) {
        el.transGenre.value = novel.genre;
      }

      await loadChapters(slug);
    } catch (err) {
      console.error(err);
    }
  }

  // Load Chapter List
  async function loadChapters(slug) {
    try {
      const res = await api(`/api/novels/${slug}/chapters`);
      state.chapters = res.chapters || [];

      if (state.chapters.length === 0) {
        el.chapterList.innerHTML = `<div style="grid-column: 1 / -1; color: var(--text-muted); padding: 1rem;">ยังไม่มีตอนในระบบ</div>`;
        return;
      }

      el.chapterList.innerHTML = state.chapters.map(ch => {
              const isActive = ch.chapterNo === state.currentChapterNo;
              const titleText = (() => {
          const t = (ch.titleTranslated || '').trim();
          return t && !/^ตอนที่\s*\d+$/.test(t) ? ch.titleTranslated : (ch.titleSource || '');
        })();
              return `
                <div class="chapter-item ${ch.hasTranslated ? 'translated' : ''} ${isActive ? 'active' : ''}" data-ch="${ch.chapterNo}">
                  <div style="display:flex;align-items:center;gap:0.5rem;min-width:0;">
                    <span style="font-weight:500;flex-shrink:0;">ตอนที่ ${ch.chapterNo}</span>
                    ${titleText ? `<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-muted);font-size:0.85rem;">${escapeHTML(titleText)}</span>` : ''}
                    <span class="badge ${ch.hasTranslated ? 'badge-success' : 'badge-info'}" style="font-size:0.7rem;flex-shrink:0;margin-left:auto;">
                      ${ch.hasTranslated ? 'แปลแล้ว' : 'ต้นฉบับ'}
                    </span>
                  </div>
                </div>`;
            }).join('');

      el.chapterList.querySelectorAll('.chapter-item').forEach(item => {
        item.addEventListener('click', () => {
          const chNo = parseInt(item.dataset.ch, 10);
          openChapter(slug, chNo);
        });
      });
    } catch (err) {
      console.error(err);
    }
  }

  // Open Chapter in Reader
  async function openChapter(slug, chapterNo) {
    // Leaving the current chapter must silence any ongoing read-back,
    // otherwise the old chapter's audio keeps playing over the new one.
    if (state.tts.speaking) stopTTS();
    state.currentSlug = slug;
    state.currentChapterNo = chapterNo;
    showView('reader');

    await loadChapterContent(slug, chapterNo);

    api(`/api/novels/${slug}/bookmark`, {
      method: 'POST',
      body: JSON.stringify({ chapterNo: chapterNo, scrollPercentage: 0 }),
    }).catch(console.error);
  }

  // Chapter numbers can have gaps (e.g. 1..72 then 86..88). Navigate by
  // position in the real chapter list, not by ±1 arithmetic, so "next" from
  // chapter 72 jumps to 86 instead of a non-existent 73.
  function adjacentChapterNo(chapterNo, dir) {
    if (!state.chapters || state.chapters.length === 0) {
      const n = chapterNo + dir;
      return n >= 1 ? n : null;
    }
    const idx = state.chapters.findIndex(c => c.chapterNo === chapterNo);
    if (idx === -1) {
      const n = chapterNo + dir;
      return n >= 1 ? n : null;
    }
    const target = state.chapters[idx + dir];
    return target ? target.chapterNo : null;
  }

  // Highest real chapter number (list is sorted ascending by chapterNo).
  function maxChapterNo() {
    if (!state.chapters || state.chapters.length === 0) return 1;
    return state.chapters[state.chapters.length - 1].chapterNo;
  }

  async function loadChapterContent(slug, chapterNo) {
    el.readerContent.innerHTML = `<div style="text-align: center; padding: 3rem; color: var(--text-muted);">กำลังโหลด...</div>`;

    try {
      const ch = await api(`/api/novels/${slug}/chapters/${chapterNo}`);
      state.currentChapterData = ch;
      const novel = state.currentNovel || { title: slug };

      el.readerNovelTitle.innerText = novel.translatedTitle || novel.title || slug;
      // Clicking the novel title returns to that novel's detail page (easy
      // switching between novels while reading).
      el.readerNovelTitle.style.cursor = 'pointer';
      el.readerNovelTitle.title = 'กลับไปหน้ารายละเอียดเรื่อง';
      el.readerNovelTitle.onclick = () => openNovelDetail(state.currentSlug);
      el.readerChapterTitle.innerText = ch.translatedTitle || ch.sourceTitle || `ตอนที่ ${chapterNo}`;

      renderReaderParagraphs();

      // Update Nav Buttons (Both Top and Bottom Nav)
      const chIdx = state.chapters.findIndex(c => c.chapterNo === chapterNo);
            let hasPrev, hasNext;
            if (chIdx === -1) {
              hasPrev = chapterNo > 1;
              hasNext = chapterNo < maxChapterNo();
            } else {
              hasPrev = chIdx > 0;
              hasNext = chIdx < state.chapters.length - 1;
            }

      el.btnPrevChapter.disabled = !hasPrev;
      el.btnNextChapter.disabled = !hasNext;
      if (el.btnPrevChapterTop) el.btnPrevChapterTop.disabled = !hasPrev;
      if (el.btnNextChapterTop) el.btnNextChapterTop.disabled = !hasNext;

    } catch (err) {
      el.readerContent.innerHTML = `<div style="text-align: center; color: var(--danger); padding: 2rem;">ไม่พบเนื้อหาตอนที่ ${chapterNo}</div>`;
    }
  }

  function renderReaderParagraphs() {
    const ch = state.currentChapterData;
    if (!ch) return;

    const hasTrans = ch.translatedText && ch.translatedText.length > 0;
    const isUntranslated = !hasTrans;

    let contentHTML = '';
    if (isUntranslated) {
      contentHTML += `
        <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid var(--warning); padding: 1rem; border-radius: var(--radius-sm); margin-bottom: 1.5rem; text-align: center;">
          <p style="color: var(--warning); margin-bottom: 0.5rem; font-weight: 500;">ตอนนี้ยังไม่ได้แปล (แสดงภาษาต้นฉบับ)</p>
          <button class="btn btn-primary btn-sm" id="btn-inline-translate">⚡ สั่งแปลตอนนี้</button>
        </div>
      `;
    }

    if (state.readingMode === 'bilingual' && hasTrans && ch.sourceText && ch.sourceText.length > 0) {
      const maxLen = Math.max(ch.translatedText.length, ch.sourceText.length);
      for (let i = 0; i < maxLen; i++) {
        const th = ch.translatedText[i] || '';
        const src = ch.sourceText[i] || '';
        contentHTML += `
          <div class="bilingual-pair">
            ${th ? `<p class="para-th">${escapeHTML(th)}</p>` : ''}
            ${src ? `<p class="para-src">${escapeHTML(src)}</p>` : ''}
          </div>
        `;
      }
    } else if (state.readingMode === 'source' && ch.sourceText && ch.sourceText.length > 0) {
      contentHTML += ch.sourceText.map(p => `<p>${escapeHTML(p)}</p>`).join('');
    } else {
      const paragraphs = hasTrans ? ch.translatedText : ch.sourceText || [];
      contentHTML += paragraphs.map((p, idx) => `<p class="reader-p" data-p-idx="${idx}">${escapeHTML(p)}</p>`).join('');
    }

    el.readerContent.innerHTML = contentHTML;

    // Restore scroll position
    const savedScroll = localStorage.getItem(`nc_scroll_${state.currentSlug}_${state.currentChapterNo}`);
    if (savedScroll) {
      setTimeout(() => {
        window.scrollTo({ top: parseInt(savedScroll, 10), behavior: 'smooth' });
      }, 100);
    }

    document.getElementById('btn-inline-translate')?.addEventListener('click', () => {
      triggerQuickTranslate(state.currentSlug, state.currentChapterNo, state.currentChapterNo);
    });
  }

  function cycleReadingMode() {
    if (state.readingMode === 'thai') state.readingMode = 'bilingual';
    else if (state.readingMode === 'bilingual') state.readingMode = 'source';
    else state.readingMode = 'thai';

    localStorage.setItem('nc_reading_mode', state.readingMode);
    updateModeButtonText();
    renderReaderParagraphs();
    showToast(`โหมดอ่าน: ${getModeLabel(state.readingMode)}`, 'info');
  }

  function updateModeButtonText() {
    if (!el.btnReaderMode) return;
    el.btnReaderMode.innerText = `🌐 ${getModeLabel(state.readingMode)}`;
  }

  function getModeLabel(mode) {
    if (mode === 'bilingual') return '2 ภาษา';
    if (mode === 'source') return 'ต้นฉบับ';
    return 'ไทย';
  }

  // Quick Translate Trigger
  function triggerQuickTranslate(slug, start, end) {
    el.transStart.value = start;
    el.transEnd.value = end;
    el.transProgressBox.classList.add('hidden');
    el.transErrorMsg.classList.add('hidden');
    if (state.defaultModel) {
      el.transModelSelect.value = state.defaultModel;
    }
    openModal(el.modalTranslate);
  }

  // Import Modal Handling
  function openImportModal() {
    openModal(el.modalImport);
    populatePasteNovelSelect();
  }

  function populatePasteNovelSelect() {
    if (!el.pasteNovelSelect) return;
    let html = '<option value="__new__">+ สร้างนิยายเรื่องใหม่...</option>';

    state.novels.forEach(n => {
      const isCurrent = state.currentSlug === n.slug;
      const nextCh = (n.totalChapters || 0) + 1;
      html += `<option value="${escapeHTML(n.slug)}" ${isCurrent ? 'selected' : ''}>
        ${escapeHTML(n.translatedTitle || n.title)} (ตอนต่อไป: ${nextCh})
      </option>`;
    });

    el.pasteNovelSelect.innerHTML = html;
    updatePasteFormFields();
  }

  function updatePasteFormFields() {
    const selected = el.pasteNovelSelect.value;
    const isNew = selected === '__new__';

    if (el.pasteNewNovelFields) {
      el.pasteNewNovelFields.style.display = isNew ? 'block' : 'none';
    }

    if (isNew) {
      el.pasteSlug.required = true;
      el.pasteChNum.value = 1;
    } else {
      el.pasteSlug.required = false;
      const novel = state.novels.find(n => n.slug === selected);
      if (novel) {
        el.pasteChNum.value = (novel.totalChapters || 0) + 1;
      }
    }
  }

  // Themes & Font Size
  function applyTheme(theme) {
    state.theme = theme;
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('nc_theme', theme);
  }

  function toggleTheme() {
    const themes = ['dark', 'sepia', 'light', 'black'];
    const nextIdx = (themes.indexOf(state.theme) + 1) % themes.length;
    applyTheme(themes[nextIdx]);
  }

  function applyFontSize(size) {
    state.fontSize = size;
    document.documentElement.style.setProperty('--reading-font-size', `${size}px`);
    localStorage.setItem('nc_font_size', size);
  }

  function formatGenre(genre) {
    switch (genre) {
      case 'apocalypse': return '❄️ วันสิ้นโลก';
      case 'xianxia': return '🥋 กำลังภายใน';
      case 'system': return '🎮 ระบบเกม';
      case 'fantasy': return '🧙 แฟนตาซี';
      case 'urban': return '🏙️ ชีวิตในเมือง';
      case 'scifi': return '🌌 ไซไฟ';
      case 'historical': return '🏰 ย้อนยุค';
      case 'horror': return '👻 ระทึกขวัญ';
      case 'romance': return '💖 โรแมนติก';
      default: return genre;
    }
  }

  // Debounced Scroll Tracker — saves bookmark to backend + localStorage
  function bindScrollTracker() {
    let scrollTimeout = null;
    window.addEventListener('scroll', () => {
      if (state.currentView !== 'reader' || !state.currentSlug || !state.currentChapterNo) return;
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;

        // Save to localStorage for instant restore
        localStorage.setItem(`nc_scroll_${state.currentSlug}_${state.currentChapterNo}`, window.scrollY);

        // Save to backend for cross-device sync
        api(`/api/novels/${state.currentSlug}/bookmark`, {
          method: 'POST',
          body: JSON.stringify({ chapterNo: state.currentChapterNo, scrollPercentage: pct }),
        }).catch(() => {});
      }, 1200);
    }, { passive: true });
  }

  // Keyboard Shortcuts (PC Ergonomics)
  function bindKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
        return;
      }

      if (e.key === 'Escape') {
        el.modalImport.classList.add('hidden');
        el.modalTranslate.classList.add('hidden');
        el.modalGlossary.classList.add('hidden');
        el.modalSettings.classList.add('hidden');
        if (el.modalExport) el.modalExport.classList.add('hidden');
        if (el.modalQueue) el.modalQueue.classList.add('hidden');
        document.body.style.overflow = '';
        return;
      }

      if (state.currentView === 'reader') {
        if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
          const prev = adjacentChapterNo(state.currentChapterNo, -1);
          if (prev) openChapter(state.currentSlug, prev);
        } else if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
          const next = adjacentChapterNo(state.currentChapterNo, 1);
          if (next) openChapter(state.currentSlug, next);
        } else if (e.key === 't' || e.key === 'T') {
          triggerQuickTranslate(state.currentSlug, state.currentChapterNo, state.currentChapterNo);
        } else if (e.key === 'b' || e.key === 'B') {
          toggleTheme();
        } else if (e.key === 'm' || e.key === 'M') {
          cycleReadingMode();
        } else if (e.key === 'f' || e.key === 'F') {
          if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
          } else {
            document.exitFullscreen().catch(() => {});
          }
        }
      }
    });
  }

  // Event Listeners
  function bindEvents() {
    // Nav
    el.btnBrand.addEventListener('click', () => {
      showView('library');
      loadNovels();
    });
    el.btnBackLibrary.addEventListener('click', () => {
      showView('library');
      loadNovels();
    });
    el.btnReaderBack.addEventListener('click', () => {
      if (state.currentSlug) openNovelDetail(state.currentSlug);
      else showView('library');
    });
    el.btnReaderChapters.addEventListener('click', () => {
      if (state.currentSlug) openNovelDetail(state.currentSlug);
    });
    if (el.btnReaderChaptersTop) {
      el.btnReaderChaptersTop.addEventListener('click', () => {
        if (state.currentSlug) openNovelDetail(state.currentSlug);
      });
    }

    // Theme & Font & Mode
    el.btnThemeToggle.addEventListener('click', toggleTheme);
    el.btnReaderTheme.addEventListener('click', toggleTheme);
    el.btnReaderMode.addEventListener('click', cycleReadingMode);
    el.btnFontIncrease.addEventListener('click', () => applyFontSize(Math.min(32, state.fontSize + 2)));
    el.btnFontDecrease.addEventListener('click', () => applyFontSize(Math.max(14, state.fontSize - 2)));

    // Next / Prev Chapter (Footer Nav)
    el.btnPrevChapter.addEventListener('click', () => {
      const prev = adjacentChapterNo(state.currentChapterNo, -1);
      if (prev) openChapter(state.currentSlug, prev);
    });
    el.btnNextChapter.addEventListener('click', () => {
      const next = adjacentChapterNo(state.currentChapterNo, 1);
      if (next) openChapter(state.currentSlug, next);
    });

    // Next / Prev Chapter (Top Nav)
    if (el.btnPrevChapterTop) {
      el.btnPrevChapterTop.addEventListener('click', () => {
        const prev = adjacentChapterNo(state.currentChapterNo, -1);
        if (prev) openChapter(state.currentSlug, prev);
      });
    }
    if (el.btnNextChapterTop) {
      el.btnNextChapterTop.addEventListener('click', () => {
        const next = adjacentChapterNo(state.currentChapterNo, 1);
        if (next) openChapter(state.currentSlug, next);
      });
    }

    // Cancel Floating Job
    el.btnCancelFloatJob.addEventListener('click', async () => {
      if (state.currentJobId) {
        await api(`/api/jobs/${state.currentJobId}/cancel`, { method: 'POST' }).catch(console.error);
      }
    });

    // Reader Translate button
    el.btnReaderTranslate.addEventListener('click', () => {
      triggerQuickTranslate(state.currentSlug, state.currentChapterNo, state.currentChapterNo);
    });

    // Quick Translate Button in Detail View
    el.btnQuickTranslate.addEventListener('click', () => {
      const maxCh = state.chapters.length > 0 ? state.chapters[state.chapters.length - 1].chapterNo : 10;
      triggerQuickTranslate(state.currentSlug, 1, Math.min(10, maxCh));
    });

    // Refresh Models Buttons
    el.btnRefreshModels.addEventListener('click', async () => {
      showToast('กำลังค้นหาโมเดลจาก 9Router...', 'info');
      await discoverModels();
      showToast(`พบโมเดลทั้งหมด ${state.availableModels.length} รายการ`, 'success');
    });
    el.btnCfgRefreshModels.addEventListener('click', async () => {
      showToast('กำลังค้นหาโมเดลจาก 9Router...', 'info');
      await discoverModels();
      showToast(`พบโมเดลทั้งหมด ${state.availableModels.length} รายการ`, 'success');
    });

    // Model selection persistence on dropdown change
    el.transModelSelect.addEventListener('change', () => {
      const chosen = el.transModelSelect.value;
      if (chosen) {
        state.defaultModel = chosen;
        localStorage.setItem('nc_model', chosen);
        api('/api/config', {
          method: 'POST',
          body: JSON.stringify({ defaultModel: chosen }),
        }).catch(console.warn);
      }
    });

    // Import Modals
    el.btnOpenImport.addEventListener('click', openImportModal);
    el.btnCloseImport.addEventListener('click', () => closeModal(el.modalImport));
    el.tabImportUrl.addEventListener('click', () => {
      el.tabImportUrl.className = 'btn btn-primary btn-sm';
      el.tabImportPaste.className = 'btn btn-outline btn-sm';
      el.formImportUrl.classList.remove('hidden');
      el.formImportPaste.classList.add('hidden');
    });
    el.tabImportPaste.addEventListener('click', () => {
      el.tabImportPaste.className = 'btn btn-primary btn-sm';
      el.tabImportUrl.className = 'btn btn-outline btn-sm';
      el.formImportPaste.classList.remove('hidden');
      el.formImportUrl.classList.add('hidden');
      populatePasteNovelSelect();
    });

    if (el.pasteNovelSelect) {
      el.pasteNovelSelect.addEventListener('change', updatePasteFormFields);
    }

    // Submit URL Import
    el.formImportUrl.addEventListener('submit', async (e) => {
      e.preventDefault();
      const url = document.getElementById('import-url').value.trim();
      const genre = el.importGenre.value;
      const start = parseInt(document.getElementById('import-start').value, 10) || 1;
      const end = parseInt(document.getElementById('import-end').value, 10) || 0;

      closeModal(el.modalImport);
      showToast('เริ่มดาวน์โหลดนิยายจาก URL แล้ว...', 'info');

      await api('/api/import', {
        method: 'POST',
        body: JSON.stringify({ url, genre, startChapter: start, endChapter: end }),
      });
    });

    // Submit Paste Import
    el.formImportPaste.addEventListener('submit', async (e) => {
      e.preventDefault();
      const selected = el.pasteNovelSelect ? el.pasteNovelSelect.value : '__new__';
      let slug = '';
      let novelTitle = '';
      let genre = 'apocalypse';

      if (selected === '__new__') {
        novelTitle = el.pasteNovelTitle.value.trim();
        slug = el.pasteSlug.value.trim();
        if (!slug && novelTitle) {
          slug = novelTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-');
        }
        if (!slug) {
          showToast('กรุณาระบุชื่อเรื่องหรือ Slug', 'error');
          return;
        }
        genre = el.pasteGenre.value;
      } else {
        slug = selected;
        const novel = state.novels.find(n => n.slug === slug);
        if (novel) {
          novelTitle = novel.title;
          genre = novel.genre;
        }
      }

      const chNum = parseInt(el.pasteChNum.value, 10) || 1;
      const chTitle = el.pasteTitle.value.trim() || `ตอนที่ ${chNum}`;
      const rawContent = el.pasteContent.value.trim();

      if (!rawContent) {
        showToast('กรุณาวางเนื้อหาบทความ', 'error');
        return;
      }

      await api('/api/import', {
        method: 'POST',
        body: JSON.stringify({
          novelSlug: slug,
          title: chTitle,
          genre: genre,
          startChapter: chNum,
          rawContent,
        }),
      });

      closeModal(el.modalImport);
      el.pasteContent.value = '';
      el.pasteTitle.value = '';
      showToast(`บันทึกตอนที่ ${chNum} เรียบร้อยแล้ว`, 'success');
      await loadNovels();
      if (state.currentSlug === slug) {
        await loadChapters(slug);
      }
    });

    // Translate Modal Submit
    el.btnCloseTranslate.addEventListener('click', () => closeModal(el.modalTranslate));
    el.formTranslate.addEventListener('submit', async (e) => {
      e.preventDefault();
      const start = parseInt(el.transStart.value, 10) || 1;
      const end = parseInt(el.transEnd.value, 10) || start;
      const model = el.transModelSelect.value.trim();
      const genre = el.transGenre.value;
      const force = el.transForce.checked;
      // Fallback chain: other available models from the same gateway get
                  // tried automatically if the chosen model keeps failing.
      const fallbackModels = (state.availableModels || [])
        .filter(m => m && m !== model)
        .slice(0, 3);

      // Save selected model permanently
      if (model) {
        state.defaultModel = model;
        localStorage.setItem('nc_model', model);
      }

      closeModal(el.modalTranslate);
      showToast(`เริ่มคิวแปลตอนที่ ${start} - ${end} ในพื้นหลังแล้ว`, 'info');

      el.topProgressBar.classList.remove('hidden');
      el.topProgressBar.style.width = '5%';
      el.floatingJobBar.classList.remove('hidden');
      el.floatJobTitle.innerText = `กำลังแปลตอนที่ ${start}... (0/${end - start + 1})`;
      el.floatJobPct.innerText = '0%';
      el.floatJobBar.style.width = '5%';

      const res = await api('/api/translate', {
        method: 'POST',
        body: JSON.stringify({
          novelSlug: state.currentSlug,
          startChapter: start,
          endChapter: end,
          model,
          fallbackModels,
          genre,
          force,
        }),
      });

      if (res.jobId) {
        state.currentJobId = res.jobId;
      }
    });

    // Glossary Modal
    el.btnOpenGlossary.addEventListener('click', async () => {
      if (!state.currentSlug) return;
      openModal(el.modalGlossary);
      el.discStatus.innerText = '';
      const res = await api(`/api/novels/${state.currentSlug}/glossary`);
      state.glossaryTerms = res.terms || [];
      renderGlossaryTable();
    });

    el.btnCloseGlossary.addEventListener('click', () => closeModal(el.modalGlossary));

    // Auto-Glossary Discovery
    el.btnRunDiscovery.addEventListener('click', async () => {
      if (!state.currentSlug) return;
      const start = parseInt(el.discStart.value, 10) || 1;
      const end = parseInt(el.discEnd.value, 10) || start;
      const model = el.transModelSelect.value || state.defaultModel;

      el.discStatus.innerText = '⏳ กำลังสแกนชื่อตัวละคร...';
      try {
        const res = await api(`/api/novels/${state.currentSlug}/glossary/discover`, {
          method: 'POST',
          body: JSON.stringify({
            novelSlug: state.currentSlug,
            startChapter: start,
            endChapter: end,
            model: model,
          }),
        });

        const count = res.discovered ? res.discovered.length : 0;
        state.glossaryTerms = res.glossary.terms || [];
        renderGlossaryTable();
        el.discStatus.innerText = `✅ พบศัพท์ใหม่ ${count} คำ — ตรวจรายการแล้วกด "บันทึก Glossary" เพื่อเก็บถาวร`;
        showToast(`สแกนพบศัพท์ใหม่ ${count} คำ (ยังไม่บันทึก — กดบันทึก Glossary เมื่อตรวจแล้ว)`, 'info');
      } catch (err) {
        el.discStatus.innerText = '❌ สแกนล้มเหลว';
        showToast(`การสแกนศัพท์ล้มเหลว: ${err.message}`, 'error');
      }
    });

    // Add manual term
    el.formAddTerm.addEventListener('submit', (e) => {
      e.preventDefault();
      const term = document.getElementById('term-orig').value.trim();
      const target = document.getElementById('term-target').value.trim();
      const category = document.getElementById('term-cat').value;
      if (term && target) {
        state.glossaryTerms.push({ term, target, category });
        renderGlossaryTable();
        document.getElementById('term-orig').value = '';
        document.getElementById('term-target').value = '';
      }
    });

    el.btnSaveGlossary.addEventListener('click', async () => {
      await api(`/api/novels/${state.currentSlug}/glossary`, {
        method: 'POST',
        body: JSON.stringify({ novelSlug: state.currentSlug, terms: state.glossaryTerms }),
      });
      showToast('บันทึก Glossary เรียบร้อยแล้ว', 'success');
      closeModal(el.modalGlossary);
    });

    // Glossary QA: scan a range for term/translation mismatches, offer repair
    el.btnGlossaryCheck?.addEventListener('click', async () => {
      const start = parseInt(document.getElementById('qa-start').value, 10) || 1;
      const end = parseInt(document.getElementById('qa-end').value, 10) || start;
      el.btnGlossaryCheck.disabled = true;
      el.btnGlossaryCheck.innerText = '⏳ กำลังตรวจ...';
      try {
        const res = await api(`/api/novels/${state.currentSlug}/glossary/check?start=${start}&end=${end}`);
        const issues = res.issues || [];
        if (issues.length === 0) {
          el.glossaryQaResults.innerHTML = `<div style="color: var(--success); font-size: 0.85rem;">✅ ตรวจ ${res.scanned} ตอน — ศัพท์สอดคล้องทั้งหมด</div>`;
        } else {
          const byChapter = {};
          issues.forEach(i => { (byChapter[i.chapterNo] = byChapter[i.chapterNo] || []).push(i); });
          el.glossaryQaResults.innerHTML =
            `<div style="font-size: 0.85rem; color: var(--warning); margin-bottom: 0.4rem;">⚠️ พบ ${issues.length} จุดใน ${Object.keys(byChapter).length} ตอน (สแกน ${res.scanned} ตอน)</div>` +
            Object.entries(byChapter).map(([chNo, list]) => `
              <div style="display:flex; align-items:center; gap:0.5rem; padding:0.25rem 0; font-size:0.82rem;">
                <span style="min-width:70px;">ตอนที่ ${chNo}</span>
                <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--text-muted);">
                  ${list.map(i => `${escapeHTML(i.term)} → ${escapeHTML(i.expected)}`).join(', ')}
                </span>
                <button type="button" class="btn btn-outline btn-sm btn-qa-repair" data-ch="${chNo}">🔧 ซ่อม</button>
              </div>`).join('');
          el.glossaryQaResults.querySelectorAll('.btn-qa-repair').forEach(btn => {
            btn.addEventListener('click', async () => {
              btn.disabled = true;
              btn.innerText = '⏳';
              try {
                await api(`/api/novels/${state.currentSlug}/chapters/${btn.dataset.ch}/repair`, { method: 'POST' });
                showToast(`ซ่อมตอนที่ ${btn.dataset.ch} เรียบร้อย`, 'success');
                btn.innerText = '✅';
              } catch (err) {
                showToast(`ซ่อมตอนที่ ${btn.dataset.ch} ล้มเหลว: ${err.message}`, 'error');
                btn.innerText = '❌';
              }
            });
          });
        }
        el.glossaryQaResults.style.display = 'block';
      } catch (err) {
        showToast(`การตรวจสอบล้มเหลว: ${err.message}`, 'error');
      } finally {
        el.btnGlossaryCheck.disabled = false;
        el.btnGlossaryCheck.innerText = '🔍 ตรวจสอบ';
      }
    });

    // Settings Modal
    el.btnOpenSettings.addEventListener('click', async () => {
      openModal(el.modalSettings);
      const cfg = await api('/api/config');
      el.cfgRouterUrl.value = cfg.routerUrl || '';
      el.cfgApiKey.value = '';
      el.cfgApiKey.placeholder = cfg.apiKey ? `ตังค่าไว้อยู่แล้ว (${cfg.apiKey})` : 'sk-...';
      el.cfgTemp.value = cfg.temperature || 0.3;
      if (cfg.defaultModel) {
        el.cfgModelSelect.value = cfg.defaultModel;
      }
    });

    el.btnCloseSettings.addEventListener('click', () => closeModal(el.modalSettings));

    // Provider preset selection + local gateway detection
    el.cfgProvider.addEventListener('change', () => {
      applyProviderPreset(el.cfgProvider.value);
    });
    el.btnDetectProviders.addEventListener('click', async () => {
      el.detectProviders.innerHTML = '<span class="badge badge-info">กำลังตรวจจับ...</span>';
      try {
        const res = await api('/api/detect-providers');
        const found = res.providers || [];
        if (found.length === 0) {
          el.detectProviders.innerHTML = '<span style="font-size:0.8rem;color:var(--text-muted);">ไม่พบ LLM gateway ในเครื่อง — กำหนดเองได้เลย</span>';
          return;
        }
        el.detectProviders.innerHTML = found.map(p => `
          <button type="button" class="btn btn-outline btn-sm" data-provider="${p.provider}" data-url="${p.url}" style="font-size:0.75rem;padding:0.2rem 0.5rem;">
            🟢 ${p.provider} (${p.url})${p.modelCount ? ` — ${p.modelCount} โมเดล` : ''}
          </button>`).join('');
        el.detectProviders.querySelectorAll('[data-provider]').forEach(btn => {
          btn.addEventListener('click', () => {
            el.cfgProvider.value = btn.dataset.provider;
            el.cfgRouterUrl.value = btn.dataset.url;
            showToast(`ใช้ ${btn.dataset.provider} แล้ว — กดบันทึกเพื่อยืนยัน`, 'info');
          });
        });
      } catch (err) {
        el.detectProviders.innerHTML = '<span style="font-size:0.8rem;color:var(--danger);">ตรวจจับไม่สำเร็จ</span>';
      }
    });

    el.formSettings.addEventListener('submit', async (e) => {
      e.preventDefault();
      const chosenModel = el.cfgModelCustom.value.trim() || el.cfgModelSelect.value;
      const routerUrl = el.cfgRouterUrl.value.trim();
      const apiKey = el.cfgApiKey.value.trim();
      const temperature = parseFloat(el.cfgTemp.value) || 0.3;

      await api('/api/config', {
        method: 'POST',
        body: JSON.stringify({
                  routerUrl,
                  apiKey,
                  defaultModel: chosenModel,
                  temperature,
                  provider: el.cfgProvider.value,
                }),
      });

      state.defaultModel = chosenModel;
      localStorage.setItem('nc_model', chosenModel);
      showToast('บันทึกการตั้งค่าถาวรเรียบร้อยแล้ว', 'success');
      closeModal(el.modalSettings);
    });

    // Export Modal Events
    el.btnOpenExport?.addEventListener('click', openExportModal);
    el.btnCloseExport?.addEventListener('click', () => closeModal(el.modalExport));
    el.btnDoExport?.addEventListener('click', doExport);

    // TTS Events
    el.ttsVoice?.addEventListener('change', () => {
      state.tts.voice = el.ttsVoice.value;
      localStorage.setItem('nc_tts_voice', state.tts.voice);
      state.tts.audioBlobs = {};
      if (state.tts.speaking) {
        speakCurrentParagraph();
      }
    });
    el.btnReaderTTS?.addEventListener('click', toggleTTS);
    el.btnTTSPlayPause?.addEventListener('click', togglePlayPauseTTS);
    el.btnTTSNext?.addEventListener('click', nextTTSParagraph);
    el.btnTTSPrev?.addEventListener('click', prevTTSParagraph);
    el.btnTTSClose?.addEventListener('click', stopTTS);
    el.ttsSpeed?.addEventListener('change', () => {
      state.tts.speed = parseFloat(el.ttsSpeed.value) || 1.0;
      state.tts.audioBlobs = {};
      if (state.tts.speaking) speakCurrentParagraph();
    });

    // Queue Drawer Events
    el.floatJobClickable?.addEventListener('click', openQueueModal);
    el.topProgressBar?.addEventListener('click', openQueueModal);
    el.btnCloseQueue?.addEventListener('click', () => closeModal(el.modalQueue));
  }

  // =========================================================================
  // Studio Neural & Web Speech TTS Engine
  // =========================================================================
  function initTTS() {
    if (el.ttsVoice) {
      const validOptions = Array.from(el.ttsVoice.options).map(o => o.value);
      if (!validOptions.includes(state.tts.voice)) {
        state.tts.voice = 'edge-tts/th-TH-NiwatNeural';
        localStorage.setItem('nc_tts_voice', state.tts.voice);
      }
      el.ttsVoice.value = state.tts.voice;
    }
  }

  function toggleTTS() {
    if (state.tts.speaking) {
      stopTTS();
    } else {
      startTTS();
    }
  }

  function startTTS() {
    const ch = state.currentChapterData;
    if (!ch) return;

    const paras = (ch.translatedText && ch.translatedText.length > 0) ? ch.translatedText : ch.sourceText || [];
    if (paras.length === 0) {
      showToast('ไม่มีเนื้อหาสำหรับอ่านเสียง', 'warning');
      return;
    }

    state.tts.paragraphs = paras;
    state.tts.currentIdx = 0;
    state.tts.speaking = true;
    state.tts.paused = false;

    if (el.ttsPlayerBar) el.ttsPlayerBar.classList.remove('hidden');
    if (el.btnTTSPlayPause) el.btnTTSPlayPause.innerText = '⏸️ หยุด';

    speakCurrentParagraph();
  }

  function stopTTS() {
    if (state.tts.audioElement) {
      state.tts.audioElement.pause();
      state.tts.audioElement = null;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    state.tts.speaking = false;
    state.tts.paused = false;
    clearParagraphHighlight();
    if (el.ttsPlayerBar) el.ttsPlayerBar.classList.add('hidden');
  }

  function togglePlayPauseTTS() {
    if (!state.tts.speaking) {
      startTTS();
      return;
    }

    if (state.tts.voice === 'browser') {
      if (state.tts.paused) {
        window.speechSynthesis.resume();
        state.tts.paused = false;
        if (el.btnTTSPlayPause) el.btnTTSPlayPause.innerText = '⏸️ หยุด';
      } else {
        window.speechSynthesis.pause();
        state.tts.paused = true;
        if (el.btnTTSPlayPause) el.btnTTSPlayPause.innerText = '▶️ เล่นต่อ';
      }
    } else {
      if (state.tts.audioElement) {
        if (state.tts.paused) {
          state.tts.audioElement.play().catch(e => console.warn(e));
          state.tts.paused = false;
          if (el.btnTTSPlayPause) el.btnTTSPlayPause.innerText = '⏸️ หยุด';
        } else {
          state.tts.audioElement.pause();
          state.tts.paused = true;
          if (el.btnTTSPlayPause) el.btnTTSPlayPause.innerText = '▶️ เล่นต่อ';
        }
      } else {
        speakCurrentParagraph();
      }
    }
  }

  async function speakCurrentParagraph() {
    if (state.tts.currentIdx >= state.tts.paragraphs.length) {
          const next = adjacentChapterNo(state.currentChapterNo, 1);
          if (next) {
            stopTTS();
            showToast(`จบตอน ${state.currentChapterNo} — อ่านเสียงต่อตอน ${next}... 📖`, 'info');
            openChapter(state.currentSlug, next).then(() => startTTS());
            return;
          }
          stopTTS();
          showToast('อ่านเสียงจบทั้งเรื่องแล้ว 🎉', 'success');
          return;
        }

    // Stop previous audio
    if (state.tts.audioElement) {
      state.tts.audioElement.pause();
      state.tts.audioElement = null;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    const idx = state.tts.currentIdx;
    const text = state.tts.paragraphs[idx];
    const speed = parseFloat(el.ttsSpeed ? el.ttsSpeed.value : '1.0') || 1.0;

    highlightParagraph(idx);

    if (el.ttsStatus) {
      el.ttsStatus.innerText = `อ่านย่อหน้า ${idx + 1}/${state.tts.paragraphs.length}`;
    }

    // Trigger pre-fetch of next paragraph audio
    prefetchNextAudio(idx + 1);

    if (state.tts.voice === 'browser') {
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'th-TH';
      utter.rate = speed;

      utter.onend = () => {
        if (state.tts.speaking && !state.tts.paused) {
          state.tts.currentIdx++;
          speakCurrentParagraph();
        }
      };

      utter.onerror = (e) => {
        if (e.error !== 'interrupted' && e.error !== 'canceled') {
          console.warn('TTS error:', e);
        }
      };

      window.speechSynthesis.speak(utter);
      return;
    }

    // Studio Neural Voice via /api/audio/speech
    try {
      let audioBlobUrl = state.tts.audioBlobs[`${state.tts.voice}_${speed}_${idx}`];
      if (!audioBlobUrl) {
        const resp = await fetch('/api/audio/speech', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            voice: state.tts.voice,
            speed: speed,
          }),
        });

        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }

        const blob = await resp.blob();
        audioBlobUrl = URL.createObjectURL(blob);
        state.tts.audioBlobs[`${state.tts.voice}_${speed}_${idx}`] = audioBlobUrl;
      }

      if (!state.tts.speaking || state.tts.currentIdx !== idx) return;

      const audio = new Audio(audioBlobUrl);
      audio.playbackRate = speed;
      state.tts.audioElement = audio;

      audio.onended = () => {
        if (state.tts.speaking && !state.tts.paused) {
          state.tts.currentIdx++;
          speakCurrentParagraph();
        }
      };

      audio.onerror = (e) => {
        console.warn('Audio playback error, falling back to next:', e);
        if (state.tts.speaking && !state.tts.paused) {
          state.tts.currentIdx++;
          speakCurrentParagraph();
        }
      };

      await audio.play();
    } catch (err) {
      console.warn('Neural TTS failed, fallback to Web Speech:', err);
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'th-TH';
      utter.rate = speed;
      utter.onend = () => {
        if (state.tts.speaking && !state.tts.paused) {
          state.tts.currentIdx++;
          speakCurrentParagraph();
        }
      };
      window.speechSynthesis.speak(utter);
    }
  }

  async function prefetchNextAudio(nextIdx) {
    if (state.tts.voice === 'browser' || !state.tts.speaking) return;
    if (nextIdx >= state.tts.paragraphs.length) return;

    const cacheKey = `${state.tts.voice}_${state.tts.speed}_${nextIdx}`;
    if (state.tts.audioBlobs[cacheKey]) return;

    const text = state.tts.paragraphs[nextIdx];
    try {
      const resp = await fetch('/api/audio/speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
                  text: text,
                  voice: state.tts.voice,
                  speed: state.tts.speed,
                }),
      });
      if (resp.ok) {
        const blob = await resp.blob();
        state.tts.audioBlobs[cacheKey] = URL.createObjectURL(blob);
      }
    } catch (e) {
      // Ignore prefetch error
    }
  }

  function nextTTSParagraph() {
    if (state.tts.currentIdx < state.tts.paragraphs.length - 1) {
      state.tts.currentIdx++;
      speakCurrentParagraph();
    }
  }

  function prevTTSParagraph() {
    if (state.tts.currentIdx > 0) {
      state.tts.currentIdx--;
      speakCurrentParagraph();
    }
  }

  function highlightParagraph(idx) {
    clearParagraphHighlight();
    const pEl = el.readerContent.querySelector(`p[data-p-idx="${idx}"]`);
    if (pEl) {
      pEl.classList.add('reading-active');
      pEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function clearParagraphHighlight() {
    el.readerContent.querySelectorAll('p.reading-active').forEach(p => p.classList.remove('reading-active'));
  }

  // =========================================================================
  // Export System
  // =========================================================================
  function openExportModal() {
    if (!state.currentSlug) return;
    openModal(el.modalExport);
    el.exportStart.value = 1;
    el.exportEnd.value = maxChapterNo();
  }

  function doExport() {
    const slug = state.currentSlug;
    const format = el.exportFormat.value;
    const start = el.exportStart.value || 1;
    const end = el.exportEnd.value || maxChapterNo();

    const url = `/api/novels/${slug}/export?format=${format}&start=${start}&end=${end}`;
    window.open(url, '_blank');
    closeModal(el.modalExport);
    showToast('เริ่มดาวน์โหลดไฟล์ E-Book เรียบร้อยแล้ว', 'success');
  }

  // =========================================================================
  // Detailed Queue Drawer
  // =========================================================================
  function openQueueModal() {
    openModal(el.modalQueue);
    renderQueueDrawer();
  }

  function renderQueueDrawer() {
    if (!state.activeJobQueue || state.activeJobQueue.length === 0) {
      el.queueSummary.innerText = 'ขณะนี้ไม่มีงานแปลค้างอยู่ในคิว';
      el.queueItemsContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">คิวงานว่าง</div>';
      return;
    }

    const total = state.activeJobQueue.length;
    const done = state.activeJobQueue.filter(i => i.status === 'done').length;
    const error = state.activeJobQueue.filter(i => i.status === 'error').length;
    const running = state.activeJobQueue.filter(i => i.status === 'running').length;

    el.queueSummary.innerHTML = `ทั้งหมด <b>${total}</b> ตอน | เสร็จแล้ว: <span style="color:#22c55e;">${done}</span> | กำลังแปล: <span style="color:#3b82f6;">${running}</span> | ล้มเหลว: <span style="color:#ef4444;">${error}</span>`;

    el.queueItemsContainer.innerHTML = state.activeJobQueue.map(item => `
      <div class="queue-item">
        <div>
          <b>ตอนที่ ${item.chapterNo}</b>: ${escapeHTML(item.title || item.message || '')}
          ${item.error ? `<div style="color: var(--danger); font-size: 0.78rem; margin-top: 0.2rem;">${escapeHTML(item.error)}</div>` : ''}
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="queue-badge ${item.status}">${item.status === 'done' ? '✅ เสร็จแล้ว' : item.status === 'running' ? '🔄 กำลังแปล' : item.status === 'error' ? '❌ ล้มเหลว' : '⏳ รอคิว'}</span>
          ${item.status === 'error' ? `<button class="btn btn-outline btn-sm btn-retry-ch" data-ch="${item.chapterNo}" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;">🔄 แปลซ้ำ</button>` : ''}
        </div>
      </div>
    `).join('');

    el.queueItemsContainer.querySelectorAll('.btn-retry-ch').forEach(btn => {
      btn.addEventListener('click', () => {
        const ch = parseInt(btn.dataset.ch, 10);
        triggerQuickTranslate(state.currentSlug, ch, ch);
        closeModal(el.modalQueue);
      });
    });
  }

  // =========================================================================
  // Mobile Touch Gestures & Scroll Memory
  // =========================================================================
  function bindTouchGestures() {
    let touchStartX = 0;
    let touchStartY = 0;

    window.addEventListener('touchstart', (e) => {
      if (state.currentView !== 'reader') return;
      touchStartX = e.changedTouches[0].clientX;
      touchStartY = e.changedTouches[0].clientY;
    }, { passive: true });

    window.addEventListener('touchend', (e) => {
      if (state.currentView !== 'reader') return;
      const deltaX = e.changedTouches[0].clientX - touchStartX;
      const deltaY = e.changedTouches[0].clientY - touchStartY;

      // Only horizontal swipes (> 70px) and not vertical scrolling
      if (Math.abs(deltaX) > 70 && Math.abs(deltaY) < 50) {
        if (deltaX < 0) {
          // Swipe Left -> Next chapter
          const next = adjacentChapterNo(state.currentChapterNo, 1);
          if (next) openChapter(state.currentSlug, next);
        } else {
          // Swipe Right -> Previous chapter
          const prev = adjacentChapterNo(state.currentChapterNo, -1);
          if (prev) openChapter(state.currentSlug, prev);
        }
      }
    }, { passive: true });
  }

  function renderGlossaryTable() {
    if (state.glossaryTerms.length === 0) {
      el.glossaryTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 1rem; color: var(--text-muted);">ยังไม่มีคำศัพท์</td></tr>`;
      return;
    }

    el.glossaryTbody.innerHTML = state.glossaryTerms.map((t, idx) => `
      <tr style="border-bottom: 1px solid var(--border-subtle);">
        <td style="padding: 0.5rem 0.75rem; font-weight: 500;">${escapeHTML(t.term)}</td>
        <td style="padding: 0.5rem 0.75rem;">${escapeHTML(t.target)}</td>
        <td style="padding: 0.5rem 0.75rem; color: var(--text-muted);">${escapeHTML(t.category)}</td>
        <td style="padding: 0.5rem;">
          <button class="btn btn-outline btn-sm" style="color: var(--danger); padding: 0.2rem 0.4rem;" data-idx="${idx}">✕</button>
        </td>
      </tr>
    `).join('');

    el.glossaryTbody.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.idx, 10);
        state.glossaryTerms.splice(idx, 1);
        renderGlossaryTable();
      });
    });
  }

  function escapeHTML(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Start app
  document.addEventListener('DOMContentLoaded', init);
})();
