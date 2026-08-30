import { escapeHTML } from './utils.js';

export function createReaderController({
  state, el, api, showView, showToast,
  maxChapterNo, openNovelDetail, triggerQuickTranslate, stopTTS,
}) {
  async function openChapter(slug, chapterNo) {
    if (state.tts.speaking) stopTTS();
    state.currentSlug = slug;
    state.currentChapterNo = chapterNo;
    showView('reader');
    await loadChapterContent(slug, chapterNo);
    api(`/api/novels/${encodeURIComponent(slug)}/bookmark`, {
      method: 'POST',
      body: JSON.stringify({ chapterNo, scrollPercentage: 0 }),
      silent: true,
    }).catch(err => console.warn('bookmark save failed', err));
  }

  function qaBadge(report) {
    if (!report) return '';
    const level = report.score >= 90 ? 'good' : report.score >= 75 ? 'review' : 'bad';
    return `<span class="badge reader-qa-badge qa-${level}">QA ${report.score}</span>`;
  }
  async function loadChapterContent(slug, chapterNo) {
    el.readerContent.innerHTML = '<div class="reader-state">กำลังโหลด...</div>';
    try {
      const chapter = await api(`/api/novels/${encodeURIComponent(slug)}/chapters/${chapterNo}`);
      state.currentChapterData = chapter;
      const novel = state.currentNovel || { title: slug };
      el.readerNovelTitle.textContent = novel.translatedTitle || novel.title || slug;
      el.readerNovelTitle.classList.add('reader-novel-link');
      el.readerNovelTitle.title = 'กลับไปหน้ารายละเอียดเรื่อง';

      const title = chapter.translatedTitle || chapter.sourceTitle || `ตอนที่ ${chapterNo}`;
      const qa = (state.qaReports || []).find(report => report.chapterNo === chapterNo);
      el.readerChapterTitle.innerHTML = `${escapeHTML(title)} ${qaBadge(qa)}`;
      renderReaderParagraphs();
      updateNavigationState(chapterNo);
    } catch (err) {
      el.readerContent.innerHTML = `<div class="reader-state reader-state-error">ไม่พบเนื้อหาตอนที่ ${chapterNo}</div>`;
      console.error('load chapter failed', err);
    }
  }

  function updateNavigationState(chapterNo) {
    const index = (state.chapters || []).findIndex(chapter => chapter.chapterNo === chapterNo);
    const hasPrev = index >= 0 ? index > 0 : chapterNo > 1;
    const hasNext = index >= 0 ? index < state.chapters.length - 1 : chapterNo < maxChapterNo();
    el.btnPrevChapter.disabled = !hasPrev;
    el.btnNextChapter.disabled = !hasNext;
    if (el.btnPrevChapterTop) el.btnPrevChapterTop.disabled = !hasPrev;
    if (el.btnNextChapterTop) el.btnNextChapterTop.disabled = !hasNext;
  }

  function renderReaderParagraphs() {
    const chapter = state.currentChapterData;
    if (!chapter) return;
    const translated = chapter.translatedText || [];
    const source = chapter.sourceText || [];
    const hasTranslation = translated.length > 0;
    const blocks = [];

    if (!hasTranslation) {
      blocks.push(`
        <div class="reader-untranslated">
          <p>ตอนนี้ยังไม่ได้แปล (แสดงภาษาต้นฉบับ)</p>
          <button class="btn btn-primary btn-sm" type="button" data-action="translate-current">⚡ สั่งแปลตอนนี้</button>
        </div>`);
    }

    if (state.readingMode === 'bilingual' && hasTranslation && source.length) {
      const maxLength = Math.max(translated.length, source.length);
      for (let index = 0; index < maxLength; index++) {
        const thai = translated[index] || '';
        const original = source[index] || '';
        blocks.push(`
          <div class="bilingual-pair">
            ${thai ? `<p class="para-th">${escapeHTML(thai)}</p>` : ''}
            ${original ? `<p class="para-src">${escapeHTML(original)}</p>` : ''}
          </div>`);
      }
    } else if (state.readingMode === 'source' && source.length) {
      blocks.push(source.map(paragraph => `<p>${escapeHTML(paragraph)}</p>`).join(''));
    } else {
      const paragraphs = hasTranslation ? translated : source;
      blocks.push(paragraphs.map((paragraph, index) =>
        `<p class="reader-p" data-p-idx="${index}">${escapeHTML(paragraph)}</p>`).join(''));
    }

    el.readerContent.innerHTML = blocks.join('');
    restoreScrollPosition();
  }

  function restoreScrollPosition() {
    const saved = Number.parseInt(localStorage.getItem(`nc_scroll_${state.currentSlug}_${state.currentChapterNo}`), 10);
    if (!Number.isFinite(saved) || saved <= 0) return;
    window.setTimeout(() => window.scrollTo({ top: saved, behavior: 'auto' }), 80);
  }
  function getModeLabel(mode) {
    if (mode === 'bilingual') return '2 ภาษา';
    if (mode === 'source') return 'ต้นฉบับ';
    return 'ไทย';
  }

  function updateModeButtonText() {
    if (el.btnReaderMode) el.btnReaderMode.textContent = `🌐 ${getModeLabel(state.readingMode)}`;
  }

  function cycleReadingMode() {
    state.readingMode = state.readingMode === 'thai'
      ? 'bilingual'
      : state.readingMode === 'bilingual' ? 'source' : 'thai';
    localStorage.setItem('nc_reading_mode', state.readingMode);
    updateModeButtonText();
    renderReaderParagraphs();
    showToast(`โหมดอ่าน: ${getModeLabel(state.readingMode)}`, 'info');
  }

  function bindReaderCoreEvents() {
    el.readerNovelTitle?.addEventListener('click', () => {
      if (state.currentSlug) openNovelDetail(state.currentSlug);
    });
    el.readerNovelTitle?.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      if (state.currentSlug) openNovelDetail(state.currentSlug);
    });
    el.readerContent?.addEventListener('click', event => {
      if (!event.target.closest('[data-action="translate-current"]')) return;
      triggerQuickTranslate(state.currentSlug, state.currentChapterNo, state.currentChapterNo);
    });
  }

  return {
    openChapter,
    loadChapterContent,
    renderReaderParagraphs,
    cycleReadingMode,
    updateModeButtonText,
    getModeLabel,
    bindReaderCoreEvents,
  };
}
