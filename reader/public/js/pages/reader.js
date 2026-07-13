/* ═══════════════════════════════════════════════════════════════════════
   reader.js — Chapter Reader Page
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const ReaderPage = {
  _readerAbortController: null,
  _glossaryReturnFocus: null,

  async render(params) {
    // ── Cleanup previous events before re-render ─────────────────────
    this._cleanupEvents();

    const page = Ui.$('page-reader');
    if (!page) return;
    const slug = params.slug;
    const num = parseInt(params.num, 10);
    if (!slug || Number.isNaN(num)) { Ui.showError(page, 'ไม่พบตอน'); return; }

    try {
      const chapters = await Api.getChapters(slug);
      const novels = await Api.getNovels();
      const novel = novels.find(n => n.slug === slug);
      if (!chapters.length) {
        Ui.showError(page, 'ยังไม่มีตอนสำหรับอ่าน', 'เปิดสตูดิโอเรื่องนี้เพื่อนำเข้าต้นฉบับตอนแรก');
        return;
      }

      let idx = chapters.findIndex(c => c.num === num);
      if (idx === -1) idx = 0;

      const novelTitle = novel ? Ui.displayTitle(novel) : slug;
      let html = `
      <div class="reader-page">
        <div class="reader-progress" id="reader-progress" role="progressbar" aria-label="ความคืบหน้าในการอ่าน" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="reader-progress__fill" id="reader-progress-fill"></div></div>

        <header class="c-toolbar reader-toolbar c-reader-masthead">
          <a href="#novel/${Ui.esc(slug)}" class="c-toolbar__back c-reader-masthead__back" data-nav aria-label="กลับไปหน้ารายเรื่อง ${Ui.esc(novelTitle)}">
            <svg class="c-icon c-icon--sm"><use xlink:href="#icon-arrow-left"/></svg>
            <span class="c-reader-masthead__novel">${Ui.esc(novelTitle)}</span>
          </a>
          <nav class="c-reader-masthead__chapter-nav" aria-label="เปลี่ยนตอน">
            <button class="c-reader__nav-btn c-reader__nav-btn--prev" id="reader-prev-top" type="button" aria-label="ไปตอนก่อนหน้า" title="ตอนก่อนหน้า">
              ${Ui.icon('arrow-left', 'xs')}<span class="c-reader-masthead__nav-label">ก่อนหน้า</span>
            </button>
            <span class="c-reader__position" id="reader-position-top" aria-live="polite"></span>
            <button class="c-reader__nav-btn c-reader__nav-btn--primary" id="reader-next-top" type="button" aria-label="ไปตอนถัดไป" title="ตอนถัดไป">
              <span class="c-reader-masthead__nav-label">ถัดไป</span>${Ui.icon('arrow-right', 'xs')}
            </button>
          </nav>
          <div class="c-toolbar__actions c-reader-masthead__actions">
            <button class="c-btn c-btn--sm c-btn--ghost c-reader-toolbar__bookmark" id="reader-bookmark-toggle" type="button" aria-pressed="false" aria-label="บันทึกตอนนี้เป็นบุ๊กมาร์ก" title="บันทึกบุ๊กมาร์ก (B)">
              ${Ui.icon('bookmarks', 'xs')}<span>บุ๊กมาร์ก</span>
            </button>
            <button class="c-btn c-btn--sm c-btn--ghost c-reader-toolbar__editor" id="reader-open-editor" type="button" title="เปิดไฟล์ตอนนี้เพื่อแก้ไข">
              <svg class="c-icon c-icon--xs c-icon--stroke"><use xlink:href="#icon-settings"/></svg>
              <span>แก้ไฟล์</span>
            </button>
          </div>
        </header>

        <div class="reader-shell">
          <article class="reader-body" aria-labelledby="reader-title" tabindex="-1">
            <h1 class="reader-title" id="reader-title"></h1>
            <div id="reader-translator-info" class="c-reader__translator-info"></div>
            <div id="reader-content"></div>
          </article>
          <footer class="c-reader-actions c-reader-footer" aria-label="เครื่องมือท้ายตอน">
            <div class="c-reader-actions__nav" aria-label="เปลี่ยนตอน">
              <button class="c-reader__nav-btn c-reader__nav-btn--prev" id="reader-prev-bottom" type="button" aria-label="ไปตอนก่อนหน้า">${Ui.icon('arrow-left', 'xs')}<span>ตอนก่อนหน้า</span></button>
              <span class="c-reader__position" id="reader-position" aria-live="polite"></span>
              <button class="c-reader__nav-btn" id="reader-back-top" type="button">${Ui.icon('arrow-left', 'xs')}<span>กลับด้านบน</span></button>
              <button class="c-reader__nav-btn c-reader__nav-btn--primary" id="reader-next-bottom" type="button" aria-label="ไปตอนถัดไป"><span>ตอนถัดไป</span>${Ui.icon('arrow-right', 'xs')}</button>
            </div>
            <div class="c-reader-actions__tools" aria-label="ปรับการอ่าน">
              <div class="c-reader-tool-group" aria-label="ขนาดตัวอักษร">
                <button class="c-reader-tool" id="reader-font-sm" type="button" title="ลดขนาดอักษร">A−</button>
                <span class="c-reader-tool__value" id="reader-font-label">18px</span>
                <button class="c-reader-tool" id="reader-font-lg" type="button" title="เพิ่มขนาดอักษร">A+</button>
              </div>
              <div class="c-reader-tool-group" aria-label="ระยะบรรทัด">
                <button class="c-reader-tool" id="reader-leading-sm" type="button" title="ลดช่องว่าง">−</button>
                <span class="c-reader-tool__value" id="reader-leading-label">1.8</span>
                <button class="c-reader-tool" id="reader-leading-lg" type="button" title="เพิ่มช่องว่าง">+</button>
              </div>
              <button class="c-reader-tool c-reader-tool--wide" id="reader-theme-toggle" type="button" title="เปลี่ยนธีม"></button>
            </div>
          </footer>
        </div>

        <div class="c-modal c-reader-glossary-modal" id="reader-glossary-modal" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="reader-glossary-title" aria-describedby="reader-glossary-description" tabindex="-1">
          <div class="c-modal__card c-reader-glossary-modal__card" role="document">
            <div class="c-reader-glossary-modal__header">
              <h2 class="c-reader-glossary-modal__title" id="reader-glossary-title">เพิ่มคำลงคลังคำศัพท์</h2>
              <button type="button" class="c-btn c-btn--ghost c-reader-glossary-modal__close" id="modal-glossary-close" aria-label="ปิดหน้าต่าง">${Ui.icon('close', 'xs')}</button>
            </div>
            <p class="c-reader-glossary-modal__description" id="reader-glossary-description">บันทึกคำแปลที่ต้องการใช้ให้สม่ำเสมอในเรื่องนี้</p>
            
            <div class="c-form c-reader-glossary-modal__form">
              <div class="c-form__group">
                <label class="c-form__label" for="modal-glossary-source">คำต้นฉบับ</label>
                <input type="text" class="c-form__input c-reader-glossary-modal__source" id="modal-glossary-source" readonly />
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="modal-glossary-thai">คำแปลภาษาไทย</label>
                <input type="text" class="c-form__input" id="modal-glossary-thai" placeholder="พิมพ์คำแปลภาษาไทย" autocomplete="off" required />
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="modal-glossary-category">ประเภท</label>
                <select class="c-form__select c-reader-glossary-modal__category" id="modal-glossary-category">
                  <option value="คำศัพท์">คำศัพท์ทั่วไป</option>
                  <option value="ตัวละคร">ตัวละคร</option>
                  <option value="สถานที่">สถานที่</option>
                  <option value="สกิล">สกิล/ทักษะ</option>
                  <option value="ไอเทม">ไอเทม</option>
                </select>
              </div>
              
              <div class="c-reader-glossary-modal__actions">
                <button type="button" class="c-btn c-btn--secondary c-reader-glossary-modal__button" id="modal-glossary-cancel">ยกเลิก</button>
                <button type="button" class="c-btn c-btn--primary c-reader-glossary-modal__button" id="modal-glossary-save">${Ui.icon('bookmarks', 'xs')}<span>บันทึกคำศัพท์</span></button>
              </div>
            </div>
          </div>
        </div>

      </div>`;

      page.innerHTML = html;

      // Keep the established bookmark format so the bookmarks page stays compatible.
      const bookmarkKey = 'novelclaw-bookmarks';
      const readBookmarks = () => {
        try {
          const saved = JSON.parse(localStorage.getItem(bookmarkKey));
          return Array.isArray(saved) ? saved.filter(item => item && item.novel != null && item.num != null) : [];
        } catch (_) {
          return [];
        }
      };
      const isCurrentChapterBookmarked = () => readBookmarks().some(item =>
        String(item.novel) === String(slug) && String(item.num) === String(chapters[idx]?.num)
      );
      const syncBookmarkButton = () => {
        const button = Ui.$('reader-bookmark-toggle');
        if (!button) return;
        const bookmarked = isCurrentChapterBookmarked();
        button.setAttribute('aria-pressed', String(bookmarked));
        button.setAttribute('aria-label', bookmarked ? 'นำตอนนี้ออกจากบุ๊กมาร์ก' : 'บันทึกตอนนี้เป็นบุ๊กมาร์ก');
        button.title = bookmarked ? 'นำบุ๊กมาร์กออก (B)' : 'บันทึกบุ๊กมาร์ก (B)';
        button.classList.toggle('is-bookmarked', bookmarked);
        button.innerHTML = `${Ui.icon('bookmarks', 'xs')}<span>${bookmarked ? 'บันทึกแล้ว' : 'บุ๊กมาร์ก'}</span>`;
      };
      const bookmarkButton = Ui.$('reader-bookmark-toggle');
      if (bookmarkButton) {
        bookmarkButton.onclick = () => {
          const currentNum = chapters[idx]?.num;
          if (currentNum == null) return;
          const bookmarks = readBookmarks();
          const bookmarked = bookmarks.some(item =>
            String(item.novel) === String(slug) && String(item.num) === String(currentNum)
          );
          const nextBookmarks = bookmarked
            ? bookmarks.filter(item => !(String(item.novel) === String(slug) && String(item.num) === String(currentNum)))
            : [...bookmarks, { novel: slug, num: currentNum }];
          try {
            localStorage.setItem(bookmarkKey, JSON.stringify(nextBookmarks));
          } catch (_) {
            Ui.showToast('บันทึกบุ๊กมาร์กในอุปกรณ์นี้ไม่สำเร็จ', 'error');
            return;
          }
          syncBookmarkButton();
          Ui.showToast(bookmarked ? 'นำตอนนี้ออกจากบุ๊กมาร์กแล้ว' : 'บันทึกตอนนี้เป็นบุ๊กมาร์กแล้ว', 'success');
        };
        syncBookmarkButton();
      }

      // Show loading state while chapter loads
      Ui.$('reader-content').innerHTML = '<div class="c-skel c-reader-skel__block"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line c-reader-skel__line--medium"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line c-reader-skel__line--short"></div>';

      // ── Load chapter ─────────────────────────────────────────────────
      const loadChapter = async (chIdx, options = {}) => {
        const ch = chapters[chIdx];
        if (!ch) return;
        try {
          const data = await Api.getChapterContent(slug, ch.num, Store.getSettings().readerLang || 'th', { fresh: options.fresh === true });

          Ui.$('reader-title').textContent = data.title || ch.title || `ตอนที่ ${ch.num}`;
          const positionText = `${chIdx + 1} / ${chapters.length}`;
          Ui.$('reader-position').textContent = positionText;
          Ui.$('reader-position-top').textContent = positionText;

          // Update translator info
          const infoEl = document.getElementById('reader-translator-info');
          if (infoEl) {
            if (data.isTranslated) {
              const modelStr = data.model && data.model !== 'unknown' ? data.model : 'ไม่ทราบโมเดล';
              const providerStr = data.provider && data.provider !== 'unknown' ? ` (${data.provider})` : '';
              const scoreStr = data.score !== undefined ? ` • คุณภาพ: ${data.score}%` : '';
              infoEl.textContent = `ฉบับแปลไทย · ${modelStr}${providerStr}${scoreStr}`;
            } else {
              infoEl.textContent = 'ฉบับต้นฉบับ · ตอนนี้ยังไม่มีฉบับแปลไทย';
            }
          }

          // Update topbar title with novel + chapter info
          const titleEl = document.getElementById('page-title');
          if (titleEl) titleEl.textContent = novelTitle + ' — ตอนที่ ' + ch.num;

          let contentHtml = '';
          if (!data.isTranslated) {
            contentHtml += `
            <div id="inline-translate-banner" class="c-inline-translate">
              <p class="c-inline-translate__text">ตอนนี้มีเฉพาะต้นฉบับ สั่งแปลไทยได้จากหน้านี้</p>
              <div class="c-inline-translate__actions">
                <a class="c-btn c-btn--ghost c-inline-translate__button" href="#admin/provider" data-nav>${Ui.icon('settings', 'xs')}<span>ตั้งค่าการแปล</span></a>
                <button id="inline-translate-btn" class="c-btn c-btn--primary c-inline-translate__button" type="button">${Ui.icon('book', 'xs')}<span>แปลเป็นภาษาไทย</span></button>
              </div>
            </div>`;
          }

          contentHtml += ReaderRenderer.renderChapter(data);
          Ui.$('reader-content').innerHTML = contentHtml;

          // ผูก Event แปลไทยด่วนทันทีเมื่อกดปุ่ม
          const translateBtn = document.getElementById('inline-translate-btn');
          if (translateBtn) {
            translateBtn.addEventListener('click', async () => {
              const banner = document.getElementById('inline-translate-banner');
              translateBtn.disabled = true;
              translateBtn.innerHTML = `${Ui.icon('book', 'xs')}<span>กำลังแปล...</span>`;
              banner?.classList.add('c-inline-translate--running');
              try {
                const res = await Api.translateSingle(slug, ch.num, true);
                if (res.ok) {
                  Store.setSetting('readerLang', 'th');
                  ch.isTranslated = true;
                  ch.status = 'translated';
                  await loadChapter(chIdx, { fresh: true });
                  Ui.showToast('แปลตอนนี้สำเร็จแล้ว', 'success');
                } else {
                  Ui.showToast('การแปลขัดข้อง: ' + (res.error?.message || 'ข้อผิดพลาดระบบ'), 'error');
                }
              } catch (err) {
                if (err.code === 'SOURCE_NOT_READY' && banner) {
                  banner.innerHTML = ReaderPage._sourceNotReadyHtml(slug, ch.num, err);
                }
                Ui.showToast((err.code === 'SOURCE_NOT_READY' ? 'ต้นฉบับยังไม่พร้อมแปล: ' : 'แปลไม่สำเร็จ: ') + err.message, 'error');
              } finally {
                const activeBtn = document.getElementById('inline-translate-btn');
                if (activeBtn) {
                  activeBtn.disabled = false;
                  activeBtn.innerHTML = `${Ui.icon('book', 'xs')}<span>แปลเป็นภาษาไทย</span>`;
                }
                banner?.classList.remove('c-inline-translate--running');
              }
            });
          }

          // Persist one atomic reading-state update for this chapter.
          Store.recordRead(slug, ch.num);

          // Update nav buttons
          ['reader-prev-top', 'reader-prev-bottom'].forEach((id) => {
            const btn = Ui.$(id);
            if (btn) btn.disabled = chIdx <= 0;
          });
          ['reader-next-top', 'reader-next-bottom'].forEach((id) => {
            const btn = Ui.$(id);
            if (btn) btn.disabled = chIdx >= chapters.length - 1;
          });

          // Scroll top
          const scrollContainer = document.querySelector('.c-content');
          if (scrollContainer) scrollContainer.scrollTop = 0;

          // Preload next chapter content in background
          if (chIdx < chapters.length - 1) {
            const nextCh = chapters[chIdx + 1];
            if (nextCh) {
              Api.getChapterContent(slug, nextCh.num, Store.getSettings().readerLang || 'th').catch(() => {});
            }
          }
        } catch (err) {
          Ui.$('reader-title').textContent = 'เกิดข้อผิดพลาด';
          Ui.$('reader-content').innerHTML = `<p class="c-reader__error-message">โหลดไม่สำเร็จ: ${Ui.esc(err.message)}</p>`;
        }
      };

      await loadChapter(idx);
      currentReaderIdx = idx;
      currentReaderChapters = chapters;
      currentReaderSlug = slug;

      // ── Wire Nav Events (navigate via hash — Router handles rendering) ─
      const goPrev = () => {
        if (currentReaderIdx > 0) {
          const prev = chapters[currentReaderIdx - 1];
          if (prev) window.location.hash = `#novel/${slug}/${prev.num}`;
        }
      };
      const goNext = () => {
        if (currentReaderIdx < chapters.length - 1) {
          const next = chapters[currentReaderIdx + 1];
          if (next) window.location.hash = `#novel/${slug}/${next.num}`;
        }
      };
      ['reader-prev-top', 'reader-prev-bottom'].forEach((id) => {
        const btn = Ui.$(id);
        if (btn) btn.onclick = goPrev;
      });
      ['reader-next-top', 'reader-next-bottom'].forEach((id) => {
        const btn = Ui.$(id);
        if (btn) btn.onclick = goNext;
      });
      Ui.$('reader-back-top').onclick = () => {
        const sc = document.querySelector('.c-content');
        if (sc) sc.scrollTo({ top: 0, behavior: 'smooth' });
      };

      // ── Open in Editor ───────────────────────────────────────────────
      Ui.$('reader-open-editor').onclick = async () => {
        try {
          const res = await fetch('/api/local/open-editor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              slug: currentReaderSlug,
              num: currentReaderChapters[currentReaderIdx].num,
              lang: Store.getSettings().readerLang || 'th',
              editor: Store.getSettings().editorType || 'notepad'
            })
          });
          const resData = await res.json();
          if (!resData.ok && !res.ok) {
            Ui.showToast(resData.error?.message || 'ไม่สามารถเปิดไฟล์แก้ไขได้', 'error');
          }
        } catch (err) {
          Ui.showToast('เกิดข้อผิดพลาด: ' + err.message, 'error');
        }
      };

      // ── Font size controls (persisted) ──────────────────────────────────
      const savedFontSize = parseInt(Store.getSettings().fontSize, 10) || 18;
      let fontStep = Math.round((savedFontSize - 18) / 2);
      const applyFont = (step) => {
        const px = Math.max(14, Math.min(28, 18 + step * 2));
        document.documentElement.style.setProperty('--reader-font-size', `${px}px`);
        Store.setSetting('fontSize', px);
        const lbl = Ui.$('reader-font-label');
        if (lbl) lbl.textContent = `${px}px`;
      };
      applyFont(fontStep);
      Ui.$('reader-font-sm').onclick = () => { fontStep = Math.max(-1, fontStep - 1); applyFont(fontStep); };
      Ui.$('reader-font-lg').onclick = () => { fontStep = Math.min(5, fontStep + 1); applyFont(fontStep); };

      // ── Line-height controls (persisted) ────────────────────────────────
      const LEADINGS = [1.6, 1.8, 2.0, 2.2];
      const savedLeading = parseFloat(Store.getSettings().lineHeight) || 1.8;
      let leadingIdx = LEADINGS.indexOf(savedLeading);
      if (leadingIdx === -1) leadingIdx = 1;
      const applyLeading = (idx) => {
        const val = LEADINGS[idx];
        document.documentElement.style.setProperty('--leading-reader', `${val}`);
        document.documentElement.style.setProperty('--reader-line-height', `${val}`);
        Store.setSetting('lineHeight', val);
        const lbl = Ui.$('reader-leading-label');
        if (lbl) lbl.textContent = `${val}`;
      };
      applyLeading(leadingIdx);
      Ui.$('reader-leading-sm').onclick = () => { leadingIdx = Math.max(0, leadingIdx - 1); applyLeading(leadingIdx); };
      Ui.$('reader-leading-lg').onclick = () => { leadingIdx = Math.min(LEADINGS.length - 1, leadingIdx + 1); applyLeading(leadingIdx); };

      // ── Theme toggle ─────────────────────────────────────────────────
      const THEMES = ['sepia', 'night', 'amoled', 'paper'];
      const THEME_ICONS = { sepia: '#icon-book', night: '#icon-moon', amoled: '#icon-moon', paper: '#icon-sun' };
      let currentTheme = Store.getSettings().theme || 'sepia';
      const applyTheme = (t) => {
        document.body.dataset.theme = t;
        Store.setSetting('theme', t);
        updateIcon(t);
      };
      const updateIcon = (t) => {
        const btn = Ui.$('reader-theme-toggle');
        if (btn) btn.innerHTML = `<svg class="c-icon c-icon--sm"><use xlink:href="${THEME_ICONS[t] || '#icon-moon'}"/></svg><span>ธีม</span>`;
      };
      applyTheme(currentTheme);
      Ui.$('reader-theme-toggle').onclick = () => {
        currentTheme = THEMES[(THEMES.indexOf(currentTheme) + 1) % THEMES.length];
        applyTheme(currentTheme);
      };

      // ── Bind events with AbortController for cleanup ──────────────────
      this._bindReaderEvents();

      // ── Scroll progress initial ────────────────────────────────────
      const doUpdateProgress = () => {
        const sc = document.querySelector('.c-content');
        if (!sc) return;
        const scrollable = sc.scrollHeight - sc.clientHeight;
        const pct = scrollable > 0 ? (sc.scrollTop / scrollable) * 100 : 0;
        const safePct = Math.min(100, Math.max(0, pct));
        const fill = Ui.$('reader-progress-fill');
        if (fill) fill.style.width = safePct + '%';
        Ui.$('reader-progress')?.setAttribute('aria-valuenow', String(Math.round(safePct)));
      };
      doUpdateProgress(); // initial

    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },

  _sourceNotReadyHtml(slug, num, err) {
    const first = err.details?.blocking?.[0] || {};
    const issueText = (first.issues || []).map(issue => issue.code).slice(0, 4).join(', ') || 'ตรวจพบปัญหาในต้นฉบับ';
    return `
      <div class="c-inline-translate__blocked">
        <strong>ต้นฉบับยังไม่พร้อมแปล</strong>
        <span>${Ui.esc(issueText)} · ตอน ${Ui.esc(first.num || num)}</span>
      </div>
      <div class="c-inline-translate__actions">
        <a class="c-btn c-btn--secondary c-inline-translate__button" href="#admin/import/${Ui.esc(slug)}/${Ui.esc(first.num || num)}" data-nav>${Ui.icon('search', 'xs')}<span>ตรวจต้นฉบับ</span></a>
        <a class="c-btn c-btn--ghost c-inline-translate__button" href="#admin/chapters/${Ui.esc(slug)}" data-nav>${Ui.icon('book', 'xs')}<span>จัดการตอน</span></a>
      </div>`;
  },

  /* ── Bind persistent events with AbortController cleanup ────────── */
  _bindReaderEvents() {
    this._cleanupEvents();
    this._readerAbortController = new AbortController();
    const { signal } = this._readerAbortController;

    const modal = document.getElementById('reader-glossary-modal');
    const closeGlossaryModal = (restoreFocus = true) => {
      if (!modal) return;
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      if (restoreFocus) this._glossaryReturnFocus?.focus?.();
      this._glossaryReturnFocus = null;
    };
    const modalFocusable = () => modal
      ? Array.from(modal.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'))
      : [];

    Ui.$('modal-glossary-cancel')?.addEventListener('click', () => closeGlossaryModal(), { signal });
    Ui.$('modal-glossary-close')?.addEventListener('click', () => closeGlossaryModal(), { signal });
    modal?.addEventListener('click', (event) => {
      if (event.target === modal) closeGlossaryModal();
    }, { signal });

    const updateProgress = () => {
      const sc = document.querySelector('.c-content');
      if (!sc) return;
      const scrollable = sc.scrollHeight - sc.clientHeight;
      const pct = scrollable > 0 ? (sc.scrollTop / scrollable) * 100 : 0;
      const safePct = Math.min(100, Math.max(0, pct));
      const fill = Ui.$('reader-progress-fill');
      if (fill) fill.style.width = safePct + '%';
      Ui.$('reader-progress')?.setAttribute('aria-valuenow', String(Math.round(safePct)));
    };
    const debouncedProgress = Ui.debounce(updateProgress, 100);
    document.querySelector('.c-content')?.addEventListener('scroll', debouncedProgress, { signal });

    const keyHandler = (event) => {
      if (modal?.classList.contains('is-open')) {
        if (event.key === 'Escape') {
          event.preventDefault();
          closeGlossaryModal();
          return;
        }
        if (event.key === 'Tab') {
          const focusable = modalFocusable();
          if (!focusable.length) {
            event.preventDefault();
            modal.focus();
            return;
          }
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
        return;
      }

      const contextMenu = document.getElementById('glossary-ctx-menu');
      if (event.key === 'Escape' && contextMenu?.classList.contains('is-open')) {
        contextMenu.classList.remove('is-open');
        document.querySelector('.reader-body')?.focus();
        return;
      }
      if (event.target?.matches?.('input, textarea, select, [contenteditable="true"]')) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;

      const shortcuts = {
        ArrowLeft: 'reader-prev-bottom',
        ArrowRight: 'reader-next-bottom',
        t: 'reader-theme-toggle',
        T: 'reader-theme-toggle',
        b: 'reader-bookmark-toggle',
        B: 'reader-bookmark-toggle',
        '+': 'reader-font-lg',
        '=': 'reader-font-lg',
        '-': 'reader-font-sm',
        '[': 'reader-leading-sm',
        ']': 'reader-leading-lg',
      };
      const targetId = shortcuts[event.key];
      if (targetId) {
        event.preventDefault();
        Ui.$(targetId)?.click();
      }
    };
    document.addEventListener('keydown', keyHandler, { signal });

    const bodyEl = document.querySelector('.reader-body');
    if (bodyEl) {
      bodyEl.addEventListener('contextmenu', (event) => {
        const selected = window.getSelection()?.toString().trim();
        if (!selected) return;

        event.preventDefault();

        let menu = document.getElementById('glossary-ctx-menu');
        if (!menu) {
          menu = document.createElement('div');
          menu.id = 'glossary-ctx-menu';
          menu.className = 'c-glossary-context-menu';
          menu.setAttribute('role', 'menu');
          menu.setAttribute('aria-label', 'คำสั่งสำหรับข้อความที่เลือก');
          document.body.appendChild(menu);
        }

        menu.innerHTML = `<button class="c-btn c-glossary-context-menu__button" id="glossary-ctx-add" type="button" role="menuitem">
          <svg class="c-icon c-icon--xs c-icon--stroke"><use xlink:href="#icon-book"/></svg>
          <span>เพิ่มลงคลังคำศัพท์</span>
        </button>`;

        menu.setAttribute('style', `--ctx-x:${event.pageX}px;--ctx-y:${event.pageY}px;`);
        menu.classList.add('is-open');

        const addBtn = document.getElementById('glossary-ctx-add');
        if (addBtn) {
          addBtn.focus();
          addBtn.onclick = () => {
            menu.classList.remove('is-open');
            const sourceInput = document.getElementById('modal-glossary-source');
            const thaiInput = document.getElementById('modal-glossary-thai');
            const categorySelect = document.getElementById('modal-glossary-category');
            const saveBtn = document.getElementById('modal-glossary-save');

            if (!modal || !sourceInput || !thaiInput || !categorySelect || !saveBtn) return;

            sourceInput.value = selected;
            thaiInput.value = '';
            categorySelect.value = 'คำศัพท์';
            this._glossaryReturnFocus = bodyEl;
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
            thaiInput.focus();

            saveBtn.onclick = async () => {
              const thaiVal = thaiInput.value.trim();
              const categoryVal = categorySelect.value;

              if (!thaiVal) {
                Ui.showToast('กรุณากรอกคำแปลภาษาไทย', 'warning');
                thaiInput.focus();
                return;
              }

              try {
                saveBtn.disabled = true;
                saveBtn.innerHTML = `${Ui.icon('bookmarks', 'xs')}<span>กำลังบันทึก...</span>`;

                const res = await fetch(`/api/novel/${encodeURIComponent(currentReaderSlug)}/glossary/add`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    source: selected,
                    thai: thaiVal,
                    category: categoryVal
                  })
                });

                const resData = await res.json();
                if (resData.ok || res.ok) {
                  Ui.showToast(`บันทึก “${selected} → ${thaiVal}” ลงคลังคำศัพท์แล้ว`);
                  closeGlossaryModal(false);
                  Api.invalidateAll(currentReaderSlug);
                  window.location.reload();
                } else {
                  Ui.showToast(resData.error?.message || 'บันทึกคำศัพท์ไม่สำเร็จ', 'error');
                }
              } catch (err) {
                Ui.showToast('บันทึกคำศัพท์ไม่สำเร็จ: ' + err.message, 'error');
              } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = `${Ui.icon('bookmarks', 'xs')}<span>บันทึกคำศัพท์</span>`;
              }
            };
          };
        }

        const hideMenu = () => {
          menu.classList.remove('is-open');
        };
        setTimeout(() => document.addEventListener('pointerdown', hideMenu, { once: true, signal }), 10);
      }, { signal });
    }
  },

  /* ── Cleanup all AbortController-bound events ──────────────────── */
  _cleanupEvents() {
    if (this._readerAbortController) {
      this._readerAbortController.abort();
      this._readerAbortController = null;
    }
    document.getElementById('glossary-ctx-menu')?.remove();
    this._glossaryReturnFocus = null;
  }
};

// Global state for reader nav
let currentReaderIdx = 0;
let currentReaderChapters = [];
let currentReaderSlug = '';
