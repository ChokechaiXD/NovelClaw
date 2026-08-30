import { escapeHTML } from './utils.js';

export function createLibraryController({
  state, el, api, showView, openChapter, openImportModal, formatGenre,
}) {
  function renderEmptyLibrary() {
    el.novelGrid.innerHTML = `
      <div class="library-empty">
        <div class="library-empty-icon">📖</div>
        <p>ยังไม่มีนิยายในคลัง</p>
        <button class="btn btn-primary" type="button" data-action="import-first">📥 นำเข้านิยายเรื่องแรก</button>
      </div>`;
  }

  function renderNovelCard(novel) {
    const total = novel.totalChapters || 0;
    const translated = novel.translatedChapters || 0;
    const pct = total ? Math.round((translated / total) * 100) : 0;
    const genreBadge = novel.genre
      ? `<span class="badge badge-info novel-genre">${escapeHTML(formatGenre(novel.genre))}</span>`
      : '';
    return `
      <article class="novel-card" data-slug="${escapeHTML(novel.slug)}" tabindex="0" role="button">
        <div>
          <div class="novel-card-heading">
            <div class="novel-card-title">${escapeHTML(novel.translatedTitle || novel.title)}</div>
            ${genreBadge}
          </div>
          <div class="novel-card-subtitle">${escapeHTML(novel.description || novel.title)}</div>
        </div>
        <div>
          <div class="novel-card-badges">
            <span class="badge badge-info">${total} ตอน</span>
            <span class="badge badge-success">แปลแล้ว ${translated}</span>
          </div>
          ${total ? `<div class="novel-progress" title="แปลแล้ว ${pct}%"><span style="width:${pct}%"></span></div>` : ''}
          <div class="novel-card-meta">
            <span>${escapeHTML(novel.author || 'ไม่ระบุผู้แต่ง')}</span>
            <span class="btn btn-primary btn-sm">อ่าน</span>
          </div>
        </div>
      </article>`;
  }
  async function loadNovels() {
    try {
      const res = await api('/api/novels');
      state.novels = res.novels || [];
      el.novelCount.textContent = `${state.novels.length} เรื่อง`;
      if (state.novels.length === 0) {
        renderEmptyLibrary();
        return;
      }
      el.novelGrid.innerHTML = state.novels.map(renderNovelCard).join('');
    } catch (err) {
      console.error('loadNovels failed', err);
    }
  }

  function resetChapterBrowser() {
    state.chapterPage = 1;
    state.chapterQuery = '';
    state.chapterFilter = 'all';
    if (el.chapterSearch) el.chapterSearch.value = '';
    if (el.chapterFilter) el.chapterFilter.value = 'all';
  }
  async function openNovelDetail(slug) {
    const switchingNovel = state.currentSlug !== slug;
    state.currentSlug = slug;
    if (switchingNovel) resetChapterBrowser();
    showView('detail');

    try {
      const [novel, bookmark] = await Promise.all([
        api(`/api/novels/${slug}`),
        api(`/api/novels/${slug}/bookmark`, { silent: true }).catch(() => ({ chapterNo: 1 })),
      ]);
      state.currentNovel = novel;
      const latestCh = bookmark.chapterNo || 1;
      renderNovelDetailHeader(novel, latestCh);
      if (novel.genre && el.transGenre) el.transGenre.value = novel.genre;
      await loadChapters(slug);
    } catch (err) {
      console.error('openNovelDetail failed', err);
    }
  }
  function renderNovelDetailHeader(novel, latestCh) {
    const genreBadge = novel.genre
      ? `<span class="badge badge-info">${escapeHTML(formatGenre(novel.genre))}</span>`
      : '';
    el.detailHeader.innerHTML = `
      <div class="novel-detail-heading">
        <div>
          <div class="novel-detail-title-row">
            <h1>${escapeHTML(novel.translatedTitle || novel.title)}</h1>
            ${genreBadge}
          </div>
          <div class="novel-detail-meta">
            ${escapeHTML(novel.title)} • ผู้แต่ง: ${escapeHTML(novel.author || 'ไม่ระบุ')}
          </div>
          <p class="novel-detail-description">${escapeHTML(novel.description || 'ไม่มีคำอธิบาย')}</p>
        </div>
        <button class="btn btn-primary" type="button" data-continue-ch="${latestCh}">
          ▶️ อ่านต่อ (ตอนที่ ${latestCh})
        </button>
      </div>`;
  }
  async function loadChapters(slug) {
    try {
      const [chapterRes, qaRes] = await Promise.all([
        api(`/api/novels/${slug}/chapters`),
        api(`/api/novels/${slug}/qa`),
      ]);
      state.chapters = chapterRes.chapters || [];
      state.qaReports = qaRes.reports || [];
      renderChapterList(slug);
    } catch (err) {
      console.error('loadChapters failed', err);
    }
  }

  function filterChapters() {
    const qaByChapter = new Map((state.qaReports || []).map(report => [report.chapterNo, report]));
    const query = (state.chapterQuery || '').trim().toLowerCase();
    const filter = state.chapterFilter || 'all';
    const chapters = (state.chapters || []).filter(chapter => {
      const qa = qaByChapter.get(chapter.chapterNo);
      if (filter === 'translated' && !chapter.hasTranslated) return false;
      if (filter === 'source' && chapter.hasTranslated) return false;
      if (filter === 'qa-review' && (!qa || qa.score >= 90)) return false;
      if (filter === 'qa-bad' && (!qa || qa.score >= 75)) return false;
      if (!query) return true;
      const haystack = `${chapter.chapterNo} ${chapter.titleSource || ''} ${chapter.titleTranslated || ''}`.toLowerCase();
      return haystack.includes(query);
    });
    return { chapters, qaByChapter };
  }

  function renderChapterList() {
    const { chapters: filtered, qaByChapter } = filterChapters();
    const pageSize = state.chapterPageSize;
    const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
    state.chapterPage = Math.max(1, Math.min(state.chapterPage, pageCount));
    const start = (state.chapterPage - 1) * pageSize;
    const visible = filtered.slice(start, start + pageSize);

    el.chapterList.innerHTML = visible.length
      ? visible.map(chapter => renderChapterRow(chapter, qaByChapter.get(chapter.chapterNo))).join('')
      : '<div class="chapter-empty">ไม่พบตอนที่ตรงกับเงื่อนไข</div>';
    const shownFrom = filtered.length === 0 ? 0 : start + 1;
    const shownTo = Math.min(start + visible.length, filtered.length);
    el.chapterPageInfo.textContent = `${shownFrom}-${shownTo} จาก ${filtered.length} ตอน • หน้า ${state.chapterPage}/${pageCount}`;
    el.btnChapterPagePrev.disabled = state.chapterPage <= 1;
    el.btnChapterPageNext.disabled = state.chapterPage >= pageCount;
  }

  function renderChapterRow(chapter, qa) {
    const titleCandidate = (chapter.titleTranslated || '').trim();
    const titleText = titleCandidate && !/^ตอนที่\s*\d+$/.test(titleCandidate)
      ? chapter.titleTranslated
      : (chapter.titleSource || '');
    const qaClass = qa ? (qa.score >= 90 ? 'qa-good' : qa.score >= 75 ? 'qa-review' : 'qa-bad') : '';
    return `
      <button type="button" class="chapter-item ${chapter.hasTranslated ? 'translated' : ''}" data-ch="${chapter.chapterNo}">
        <span class="chapter-number">ตอนที่ ${chapter.chapterNo}</span>
        <span class="chapter-title-text">${escapeHTML(titleText)}</span>
        <span class="chapter-item-spacer"></span>
        ${qa ? `<span class="badge qa-badge ${qaClass}">QA ${qa.score}</span>` : ''}
        <span class="badge ${chapter.hasTranslated ? 'badge-success' : 'badge-info'}">${chapter.hasTranslated ? 'แปลแล้ว' : 'ต้นฉบับ'}</span>
      </button>`;
  }
  function adjacentChapterNo(chapterNo, direction) {
    if (!state.chapters || state.chapters.length === 0) {
      const candidate = chapterNo + direction;
      return candidate >= 1 ? candidate : null;
    }
    const index = state.chapters.findIndex(chapter => chapter.chapterNo === chapterNo);
    if (index === -1) {
      const candidate = chapterNo + direction;
      return candidate >= 1 ? candidate : null;
    }
    return state.chapters[index + direction]?.chapterNo ?? null;
  }

  function maxChapterNo() {
    if (!state.chapters || state.chapters.length === 0) return 1;
    return state.chapters[state.chapters.length - 1].chapterNo;
  }

  function activateNovelCard(target) {
    const card = target.closest?.('.novel-card[data-slug]');
    if (card?.dataset.slug) openNovelDetail(card.dataset.slug);
  }
  function bindLibraryEvents() {
    el.novelGrid?.addEventListener('click', event => {
      if (event.target.closest('[data-action="import-first"]')) {
        openImportModal();
        return;
      }
      activateNovelCard(event.target);
    });
    el.novelGrid?.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activateNovelCard(event.target);
      }
    });
    el.detailHeader?.addEventListener('click', event => {
      const button = event.target.closest('[data-continue-ch]');
      if (!button || !state.currentSlug) return;
      const chapterNo = Number.parseInt(button.dataset.continueCh, 10);
      if (chapterNo > 0) openChapter(state.currentSlug, chapterNo);
    });
    el.chapterSearch?.addEventListener('input', () => {
      state.chapterQuery = el.chapterSearch.value;
      state.chapterPage = 1;
      renderChapterList();
    });
    el.chapterFilter?.addEventListener('change', () => {
      state.chapterFilter = el.chapterFilter.value;
      state.chapterPage = 1;
      renderChapterList();
    });
    el.btnChapterPagePrev?.addEventListener('click', () => {
      if (state.chapterPage <= 1) return;
      state.chapterPage -= 1;
      renderChapterList();
    });
    el.btnChapterPageNext?.addEventListener('click', () => {
      state.chapterPage += 1;
      renderChapterList();
    });
    el.chapterList?.addEventListener('click', event => {
      const item = event.target.closest('[data-ch]');
      if (!item || !state.currentSlug) return;
      const chapterNo = Number.parseInt(item.dataset.ch, 10);
      if (chapterNo > 0) openChapter(state.currentSlug, chapterNo);
    });
  }
  return {
    loadNovels,
    openNovelDetail,
    loadChapters,
    renderChapterList,
    adjacentChapterNo,
    maxChapterNo,
    bindLibraryEvents,
  };
}
