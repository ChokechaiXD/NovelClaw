import { createAPIClient } from './js/api.js';
import { createProviderController } from './js/providers.js';
import { escapeHTML } from './js/utils.js';
import { createTTSController } from './js/tts.js';
import { createInitialState } from './js/state.js';
import { bindDOM } from './js/dom.js';
import { createJobController } from './js/jobs.js';
import { createLibraryController } from './js/library.js';
import { createIntelligenceController } from './js/intelligence.js';
import { createGlossaryController } from './js/glossary.js';
import { createExportController } from './js/export.js';
import { createProviderEvents } from './js/provider_events.js';
import { createReaderController } from './js/reader.js';
import { createWorkflowController } from './js/workflow.js';

/* ==========================================================================
   NovelClaw - Client Application Logic
   ========================================================================== */

(function () {
  'use strict';

  const state = createInitialState();
  const el = bindDOM();

  const api = createAPIClient({ onError: err => showToast(err.message, 'error') });

  let workflowController = null;
  function triggerQuickTranslate(...args) {
    return workflowController?.triggerQuickTranslate(...args);
  }
  function openImportModal(...args) {
    return workflowController?.openImportModal(...args);
  }


  const {
    loadNovels, openNovelDetail, loadChapters, renderChapterList,
    adjacentChapterNo, maxChapterNo, bindLibraryEvents,
  } = createLibraryController({
    state, el, api, showView, openChapter, openImportModal, formatGenre,
  });

  const { renderQASummary, bindIntelligenceEvents } = createIntelligenceController({
    state, el, api, showToast, openModal, closeModal, loadChapters,
  });

  const { bindGlossaryEvents } = createGlossaryController({
    state, el, api, showToast, openModal, closeModal,
  });

  const { bindExportEvents } = createExportController({
    state, el, showToast, openModal, closeModal, maxChapterNo,
  });

  const { initTTS, stopTTS } = createTTSController({
    state,
    el,
    showToast,
    adjacentChapterNo,
    openChapter,
  });

  const readerController = createReaderController({
    state, el, api, showView, showToast, maxChapterNo,
    openNovelDetail, triggerQuickTranslate, stopTTS,
  });
  const {
    renderReaderParagraphs, cycleReadingMode,
    updateModeButtonText, bindReaderCoreEvents,
  } = readerController;

  const { initSSE, bindJobEvents, beginJob } = createJobController({
    state, el, api, showToast, openModal, closeModal,
    loadChapters, loadChapterContent, loadNovels,
    renderQASummary, triggerQuickTranslate,
  });

  workflowController = createWorkflowController({
    state, el, api, showToast, openModal, closeModal,
    loadNovels, loadChapters, beginJob,
  });
  const { bindWorkflowEvents } = workflowController;

  // Initialization
  async function init() {
    applyTheme(state.theme);
    applyFontSize(state.fontSize);
    updateModeButtonText();
    initTTS();
    bindEvents();
    bindLibraryEvents();
    bindIntelligenceEvents();
    bindGlossaryEvents();
    bindExportEvents();
    bindReaderCoreEvents();
    bindProviderEvents();
    bindWorkflowEvents();
    bindKeyboardShortcuts();
    bindScrollTracker();
    bindTouchGestures();
    bindJobEvents();
    initSSE();
    // Local library rendering must never wait on a slow/unreachable cloud AI.
    // Start both tasks together; provider model discovery continues quietly.
    await Promise.allSettled([loadConfigAndModels(), loadNovels()]);
  }

  // Views Management
  function showView(viewName) {
    state.currentView = viewName;
    document.body.classList.toggle('is-reader', viewName === 'reader');
    el.viewLibrary.classList.toggle('hidden', viewName !== 'library');
    el.viewDetail.classList.toggle('hidden', viewName !== 'detail');
    el.viewReader.classList.toggle('hidden', viewName !== 'reader');
    el.readerToolbar.classList.toggle('hidden', viewName !== 'reader');

    window.scrollTo({ top: 0, behavior: 'auto' });
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
    const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : type === 'warning' ? '⚠️' : '📢';
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

  // Modal focus + scroll lock helpers
  let modalReturnFocus = null;
  const modalElements = () => [el.modalImport, el.modalTranslate, el.modalGlossary, el.modalSettings, el.modalIntelligence, el.modalExport, el.modalQueue].filter(Boolean);
  function openModal(modalEl) {
    if (!modalEl) return;
    modalReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    modalEl.setAttribute('role', 'dialog');
    modalEl.setAttribute('aria-modal', 'true');
    modalEl.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => modalEl.querySelector('button, input, select, textarea, [tabindex]:not([tabindex="-1"])')?.focus({ preventScroll: true }));
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add('hidden');
    document.body.style.overflow = '';
    const target = modalReturnFocus;
    modalReturnFocus = null;
    if (target?.isConnected) requestAnimationFrame(() => target.focus({ preventScroll: true }));
  }

  // Provider control plane is isolated in js/providers.js.
  const {
    getProvider,
    renderProviderStatus,
    populateTranslationModels,
    applyProviderToSettings,
    loadConfigAndModels,
    discoverModels,
    currentSettingsPayload,
    refreshProviderControlPlane,
    testCurrentProvider,
  } = createProviderController({ state, el, api });


  const { bindProviderEvents } = createProviderEvents({
    state, el, api, showToast, openModal, closeModal,
    getProvider, renderProviderStatus, applyProviderToSettings,
    discoverModels, testCurrentProvider, refreshProviderControlPlane,
    currentSettingsPayload,
  });

  // Library and chapter browser live in js/library.js.

  // Reader implementation lives in js/reader.js. These thin wrappers keep
  // cross-module callbacks stable without circular imports.
  async function openChapter(slug, chapterNo) {
    return readerController.openChapter(slug, chapterNo);
  }

  async function loadChapterContent(slug, chapterNo) {
    return readerController.loadChapterContent(slug, chapterNo);
  }

  // Import/translation workflow lives in js/workflow.js.

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

  // Memory and QA UI live in js/intelligence.js.

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
      const openDialog = modalElements().find(modal => !modal.classList.contains('hidden'));
      if (e.key === 'Escape' && openDialog) {
        e.preventDefault();
        closeModal(openDialog);
        return;
      }
      if (e.key === 'Tab' && openDialog) {
        const focusable = [...openDialog.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')].filter(node => node.offsetParent !== null);
        if (focusable.length) {
          const first = focusable[0], last = focusable[focusable.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
        return;
      }
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;

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

    // Import/translation events are bound once by js/workflow.js.

    // Glossary events are bound once by js/glossary.js.

    // Provider settings events are bound once by js/provider_events.js.

    // Export events are bound once by js/export.js.

  }


  // Export UI lives in js/export.js.

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

  // Glossary rendering lives in js/glossary.js.

  // Start app with an observable readiness marker for production smoke tests.
  document.addEventListener('DOMContentLoaded', () => {
    init().then(() => {
      document.documentElement.dataset.appReady = 'true';
    }).catch(err => {
      console.error('NovelClaw bootstrap failed', err);
      document.documentElement.dataset.appReady = 'error';
      showToast(`เริ่มต้นแอปไม่สำเร็จ: ${err.message}`, 'error');
    });
  });
})();
