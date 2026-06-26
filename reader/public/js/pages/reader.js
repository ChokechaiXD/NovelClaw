/* ═══════════════════════════════════════════════════════════════════════
   reader.js — Chapter Reader Page
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const ReaderPage = {
  _readerAbortController: null,

  async render(params) {
    // ── Cleanup previous events before re-render ─────────────────────
    this._cleanupEvents();

    const page = Ui.$('page-reader');
    if (!page) return;
    const slug = params.slug;
    const num = parseInt(params.num, 10);
    if (!slug || isNaN(num)) { Ui.showError(page, 'ไม่พบตอน'); return; }

    try {
      const chapters = await Api.getChapters(slug);
      const novels = await Api.getNovels();
      const novel = novels.find(n => n.slug === slug);

      let idx = chapters.findIndex(c => c.num === num);
      if (idx === -1) idx = 0;

      let html = `
      <div class="reader-page">
        <!-- Progress bar -->
        <div class="reader-progress" id="reader-progress"><div class="reader-progress__fill" id="reader-progress-fill"></div></div>

        <div class="c-toolbar reader-toolbar">
          <a href="#novel/${slug}" class="c-toolbar__back" data-nav>
            <svg style="width:16px;height:16px;"><use xlink:href="#icon-arrow-left"/></svg>
            <span>กลับ</span>
          </a>
          <span class="c-toolbar__title">${novel ? Ui.esc(Ui.displayTitle(novel)) : slug}</span>
          <span class="c-toolbar__divider"></span>
          
          <button class="c-btn" id="reader-open-editor" style="font-size:var(--text-xs);display:flex;align-items:center;gap:4px;color:var(--c-text-secondary);min-height:36px;padding:0 var(--space-xs);border:1px solid var(--c-border);border-radius:var(--radius-sm);" title="แก้ไข">
            <svg style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;"><use xlink:href="#icon-settings"/></svg>
            <span>แก้ไข</span>
          </button>
          <span class="c-toolbar__divider"></span>
          
          <select id="reader-model-select" style="font-size:11px;height:36px;padding:0 var(--space-xs);border:1px solid var(--c-border);background:var(--c-bg-secondary);color:var(--c-text-primary);border-radius:var(--radius-sm);cursor:pointer;max-width:180px;outline:none;" title="เลือกโมเดลแปล AI"></select>
          <span class="c-toolbar__divider"></span>
          
          <button class="c-btn c-btn--icon" id="reader-theme-toggle" title="เปลี่ยนธีม"></button>
          <button class="c-btn c-btn--icon" id="reader-distraction-toggle" title="โหมดอ่านหนังสือ">
            <svg style="width:16px;height:16px;"><use xlink:href="#icon-fullscreen"/></svg>
          </button>
        </div>

        <div class="reader-shell">
          <div class="c-reader__nav">
            <button class="c-reader__nav-btn" id="reader-prev">◀ ก่อนหน้า</button>
            <span class="c-reader__position" id="reader-position"></span>
            <button class="c-reader__nav-btn" id="reader-next">ถัดไป ▶</button>
          </div>
          <div class="reader-body">
            <h1 class="reader-title" id="reader-title"></h1>
            <div id="reader-translator-info" style="font-size:var(--text-xs);color:var(--c-text-muted);margin-top:-8px;margin-bottom:var(--space-sm);text-align:center;font-family:var(--font-sans);"></div>
            <div class="c-reader__meta">
              <button class="c-btn c-btn--icon" id="reader-font-sm" title="ลดขนาดอักษร">A−</button>
              <span style="font-size:var(--text-sm);color:var(--c-text-muted);" id="reader-font-label">18px</span>
              <button class="c-btn c-btn--icon" id="reader-font-lg" title="เพิ่มขนาดอักษร">A+</button>
              <span class="c-toolbar__divider"></span>
              <button class="c-btn c-btn--icon" id="reader-leading-sm" title="ลดช่องว่าง">↑↓</button>
              <span style="font-size:var(--text-sm);color:var(--c-text-muted);" id="reader-leading-label">1.8</span>
              <button class="c-btn c-btn--icon" id="reader-leading-lg" title="เพิ่มช่องว่าง">↑↑</button>
            </div>
            <div id="reader-content"></div>
          </div>
          <div class="c-reader__nav">
            <button class="c-reader__nav-btn" id="reader-prev-2">◀ ก่อนหน้า</button>
            <button class="c-reader__nav-btn" id="reader-back-top">↑ กลับบน</button>
            <button class="c-reader__nav-btn" id="reader-next-2">ถัดไป ▶</button>
          </div>
        </div>

        <!-- Custom Glossary Dialog Modal -->
        <div class="c-modal" id="reader-glossary-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:2000; align-items:center; justify-content:center; padding:16px; backdrop-filter:blur(4px);">
          <div class="c-modal__card" style="background:var(--c-bg-secondary); border:1px solid var(--c-border); padding:var(--space-md); border-radius:var(--radius); width:100%; max-width:400px; box-shadow:var(--shadow-lg); box-sizing:border-box;">
            <h3 style="margin-top:0; margin-bottom:var(--space-sm); font-size:var(--text-md); font-weight:600; color:var(--c-text-primary);">เพิ่มคำศัพท์ลง Glossary</h3>
            
            <div class="c-form" style="display:flex; flex-direction:column; gap:var(--space-sm);">
              <div class="c-form__group">
                <label class="c-form__label">คำศัพท์ภาษาจีน</label>
                <input type="text" class="c-form__input" id="modal-glossary-source" readonly style="opacity:0.8; font-weight:600;" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">คำแปลภาษาไทย</label>
                <input type="text" class="c-form__input" id="modal-glossary-thai" placeholder="ระบุคำแปลภาษาไทย..." required />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">ประเภท</label>
                <select class="c-form__select" id="modal-glossary-category" style="height:44px; padding:0 var(--space-sm);">
                  <option value="คำศัพท์">คำศัพท์ทั่วไป</option>
                  <option value="ตัวละคร">ตัวละคร</option>
                  <option value="สถานที่">สถานที่</option>
                  <option value="สกิล">สกิล/ทักษะ</option>
                  <option value="ไอเทม">ไอเทม</option>
                </select>
              </div>
              
              <div style="display:flex; justify-content:flex-end; gap:var(--space-xs); margin-top:var(--space-sm);">
                <button type="button" class="c-btn c-btn--secondary" id="modal-glossary-cancel" style="min-height:36px; font-size:var(--text-sm);">ยกเลิก</button>
                <button type="button" class="c-btn c-btn--primary" id="modal-glossary-save" style="min-height:36px; font-size:var(--text-sm);">บันทึก</button>
              </div>
            </div>
          </div>
        </div>

      </div>`;

      page.innerHTML = html;

      // โหลดและซิงค์การตั้งค่าโมเดล AI ล่าสุดจากเซิร์ฟเวอร์
      const modelSelect = document.getElementById('reader-model-select');
      try {
        Api.getLlmConfig().then(cfg => {
          if (modelSelect) {
            const providers = Array.isArray(cfg.providers) ? cfg.providers : [];
            const optionHtml = providers.map(provider => {
              const models = Array.isArray(provider.models) ? provider.models : [];
              return `<optgroup label="${Ui.esc(provider.label || provider.id)}">` +
                models.map(model => `<option value="${Ui.esc(model.id)}" data-provider="${Ui.esc(provider.id)}">${Ui.esc(model.label || model.id)}</option>`).join('') +
                '</optgroup>';
            }).join('');
            modelSelect.innerHTML = optionHtml || `<option value="${Ui.esc(cfg.default_model || '')}" data-provider="${Ui.esc(cfg.default_provider || '')}">${Ui.esc(cfg.default_model || 'เลือกโมเดล')}</option>`;
            modelSelect.value = cfg.default_model;
          }
        });
      } catch (err) {
        console.error('Failed to load LLM config:', err);
      }

      if (modelSelect) {
        modelSelect.addEventListener('change', async function() {
          const val = this.value;
          const provider = this.selectedOptions[0]?.dataset?.provider || 'openrouter';
          try {
            await Api.saveLlmConfig({ default_model: val, default_provider: provider });
            console.log(`Saved default model to llm.json: ${val} (${provider})`);
          } catch (err) {
            alert('ไม่สามารถบันทึกการตั้งค่าโมเดลได้: ' + err.message);
          }
        });
      }

      // Show loading state while chapter loads
      Ui.$('reader-content').innerHTML = '<div class="c-skel c-skel--block" style="height:200px;"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line" style="width:75%;"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line" style="width:60%;"></div>';

      // ── Load chapter ─────────────────────────────────────────────────
      const loadChapter = async (chIdx) => {
        const ch = chapters[chIdx];
        if (!ch) return;
        try {
          const data = await Api.getChapterContent(slug, ch.num, Store.getSettings().readerLang || 'th');

          Ui.$('reader-title').textContent = data.title || ch.title || `ตอนที่ ${ch.num}`;
          Ui.$('reader-position').textContent = `${chIdx + 1} / ${chapters.length}`;

          // Update translator info
          const infoEl = document.getElementById('reader-translator-info');
          if (infoEl) {
            if (data.isTranslated) {
              const modelStr = data.model && data.model !== 'unknown' ? data.model : 'ไม่ทราบโมเดล';
              const providerStr = data.provider && data.provider !== 'unknown' ? ` (${data.provider})` : '';
              const scoreStr = data.score !== undefined ? ` • คุณภาพ: ${data.score}%` : '';
              infoEl.textContent = `แปลโดย AI: ${modelStr}${providerStr}${scoreStr}`;
            } else {
              infoEl.textContent = 'แสดงบทต้นฉบับภาษาจีน (ยังไม่แปล)';
            }
          }

          // Update topbar title with novel + chapter info
          const titleEl = document.getElementById('page-title');
          if (titleEl) titleEl.textContent = Ui.esc(Ui.displayTitle(novel) || slug) + ' — ตอนที่ ' + ch.num;

          let contentHtml = '';
          if (!data.isTranslated) {
            contentHtml += `
            <div id="inline-translate-banner" style="background:var(--c-accent-soft); border:1px solid var(--c-accent); padding:var(--space-md); border-radius:var(--radius-sm); margin-bottom:var(--space-md); text-align:center; font-family:var(--font-sans);">
              <p style="margin:0 0 var(--space-xs) 0; font-size:var(--text-sm); font-weight:600; color:var(--c-text-primary);">📖 ตอนศึกษานี้ยังไม่ได้แปลเป็นภาษาไทย</p>
              <button id="inline-translate-btn" class="c-btn c-btn--primary" style="font-size:var(--text-xs); min-height:36px; padding:0 var(--space-sm); cursor:pointer; font-weight:600;">⚡ แปลไทยด้วย AI ทันที</button>
            </div>`;
          }

          contentHtml += ReaderRenderer.renderChapter(data);
          Ui.$('reader-content').innerHTML = contentHtml;

          // ผูก Event แปลไทยด่วนทันทีเมื่อกดปุ่ม
          const translateBtn = document.getElementById('inline-translate-btn');
          if (translateBtn) {
            translateBtn.addEventListener('click', async () => {
              const loader = document.getElementById('reader-translation-loader');
              if (loader) loader.style.display = 'flex';
              try {
                const res = await Api.translateSingle(slug, ch.num, true);
                if (res.ok) {
                  Api.invalidateChapterContent(slug, ch.num);
                  await loadChapter(chIdx);
                } else {
                  alert('การแปลขัดข้อง: ' + (res.error?.message || 'ข้อผิดพลาดระบบ'));
                }
              } catch (err) {
                alert('เกิดข้อผิดพลาดในการแปล: ' + err.message);
              } finally {
                if (loader) loader.style.display = 'none';
              }
            });
          }

          // Mark as read
          Store.markRead(slug, ch.num);
          Store.setLastPosition(slug, ch.num);

          // Update nav buttons
          Ui.$('reader-prev').disabled = chIdx <= 0;
          Ui.$('reader-prev-2').disabled = chIdx <= 0;
          Ui.$('reader-next').disabled = chIdx >= chapters.length - 1;
          Ui.$('reader-next-2').disabled = chIdx >= chapters.length - 1;

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
          Ui.$('reader-content').innerHTML = `<p style="text-align:center;padding:2em;color:var(--c-error);">โหลดไม่สำเร็จ: ${err.message}</p>`;
        }
      };

      await loadChapter(idx);
      currentReaderIdx = idx;
      currentReaderChapters = chapters;
      currentReaderSlug = slug;

      // ── Wire Nav Events (navigate via hash — Router handles rendering) ─
      Ui.$('reader-prev').onclick = () => {
        if (currentReaderIdx > 0) {
          const prev = chapters[currentReaderIdx - 1];
          if (prev) window.location.hash = `#novel/${slug}/${prev.num}`;
        }
      };
      Ui.$('reader-next').onclick = () => {
        if (currentReaderIdx < chapters.length - 1) {
          const next = chapters[currentReaderIdx + 1];
          if (next) window.location.hash = `#novel/${slug}/${next.num}`;
        }
      };
      Ui.$('reader-prev-2').onclick = () => {
        if (currentReaderIdx > 0) {
          const prev = chapters[currentReaderIdx - 1];
          if (prev) window.location.hash = `#novel/${slug}/${prev.num}`;
        }
      };
      Ui.$('reader-next-2').onclick = () => {
        if (currentReaderIdx < chapters.length - 1) {
          const next = chapters[currentReaderIdx + 1];
          if (next) window.location.hash = `#novel/${slug}/${next.num}`;
        }
      };
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
            alert(resData.error?.message || 'ไม่สามารถเปิดไฟล์แก้ไขได้');
          }
        } catch (err) {
          alert('เกิดข้อผิดพลาด: ' + err.message);
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
      Ui.$('reader-font-lg').onclick = () => { fontStep = Math.min(2, fontStep + 1); applyFont(fontStep); };

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
        if (btn) btn.innerHTML = `<svg style="width:16px;height:16px;"><use xlink:href="${THEME_ICONS[t] || '#icon-moon'}"/></svg>`;
      };
      applyTheme(currentTheme);
      Ui.$('reader-theme-toggle').onclick = () => {
        currentTheme = THEMES[(THEMES.indexOf(currentTheme) + 1) % THEMES.length];
        applyTheme(currentTheme);
      };

      // ── Distraction-free / book mode ───────────────────────────────
      Ui.$('reader-distraction-toggle').onclick = () => {
        const app = document.querySelector('.c-app');
        if (!app) return;
        app.classList.toggle('c-app--book-mode');
        const isActive = app.classList.contains('c-app--book-mode');
        Ui.showToast(isActive ? 'โหมดอ่านหนังสือ' : 'ออกจากโหมดอ่านหนังสือ');
      };


      // ── Bind events with AbortController for cleanup ──────────────────
      this._bindReaderEvents();

      // ── Scroll progress initial ────────────────────────────────────
      const doUpdateProgress = () => {
        const sc = document.querySelector('.c-content');
        if (!sc) return;
        const pct = (sc.scrollTop / (sc.scrollHeight - sc.clientHeight)) * 100;
        const fill = Ui.$('reader-progress-fill');
        if (fill) fill.style.width = Math.min(100, Math.max(0, pct)) + '%';
      };
      doUpdateProgress(); // initial

    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },

  /* ── Bind persistent events with AbortController cleanup ────────── */
  _bindReaderEvents() {
    this._cleanupEvents();
    this._readerAbortController = new AbortController();
    const { signal } = this._readerAbortController;

    // Scroll progress bar (debounced)
    const updateProgress = () => {
      const sc = document.querySelector('.c-content');
      if (!sc) return;
      const pct = (sc.scrollTop / (sc.scrollHeight - sc.clientHeight)) * 100;
      const fill = Ui.$('reader-progress-fill');
      if (fill) fill.style.width = Math.min(100, Math.max(0, pct)) + '%';
    };
    const debouncedProgress = Ui.debounce(updateProgress, 100);
    document.querySelector('.c-content')?.addEventListener('scroll', debouncedProgress, { signal });

    // Keyboard shortcuts
    const keyHandler = (e) => {
      if (e.target.matches('input, textarea')) return;
      
      // Page navigation
      if (e.key === 'ArrowLeft') Ui.$('reader-prev')?.click();
      if (e.key === 'ArrowRight') Ui.$('reader-next')?.click();
      
      // Toggle Book Mode
      if (e.key === 'b' || e.key === 'B' || e.key === 'd' || e.key === 'D') {
        Ui.$('reader-distraction-toggle')?.click();
      }
      
      // Toggle Themes
      if (e.key === 't' || e.key === 'T') {
        Ui.$('reader-theme-toggle')?.click();
      }
      
      // Adjust Font Size
      if (e.key === '+' || e.key === '=') {
        Ui.$('reader-font-lg')?.click();
      }
      if (e.key === '-') {
        Ui.$('reader-font-sm')?.click();
      }
      
      // Adjust line spacing
      if (e.key === '[') {
        Ui.$('reader-leading-sm')?.click();
      }
      if (e.key === ']') {
        Ui.$('reader-leading-lg')?.click();
      }
      
      // Exit Book Mode
      if (e.key === 'Escape') {
        const app = document.querySelector('.c-app');
        if (app && app.classList.contains('c-app--book-mode')) {
          app.classList.remove('c-app--book-mode');
          Ui.showToast('ออกจากโหมดอ่านหนังสือ');
        }
      }
    };
    document.addEventListener('keydown', keyHandler, { signal });

    // Context menu for Glossary addition (right-click selection)
    const bodyEl = document.querySelector('.reader-body');
    if (bodyEl) {
      bodyEl.addEventListener('contextmenu', (e) => {
        const selected = window.getSelection().toString().trim();
        if (!selected) return; // Native context menu if no selection

        e.preventDefault();

        // Create or show custom menu
        let menu = document.getElementById('glossary-ctx-menu');
        if (!menu) {
          menu = document.createElement('div');
          menu.id = 'glossary-ctx-menu';
          menu.style.position = 'absolute';
          menu.style.background = 'var(--c-bg-secondary)';
          menu.style.border = '1px solid var(--c-border)';
          menu.style.borderRadius = 'var(--radius-sm)';
          menu.style.boxShadow = 'var(--shadow-md)';
          menu.style.zIndex = '1000';
          menu.style.padding = '4px 0';
          menu.style.minWidth = '140px';
          document.body.appendChild(menu);
        }

        menu.innerHTML = `<button class="c-btn" style="width:100%;text-align:left;padding:8px 12px;font-size:var(--text-sm);display:flex;align-items:center;gap:6px;" id="glossary-ctx-add">
          <svg style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;"><use xlink:href="#icon-book"/></svg>
          <span>เพิ่มลง Glossary</span>
        </button>`;

        menu.style.left = `${e.pageX}px`;
        menu.style.top = `${e.pageY}px`;
        menu.style.display = 'block';

        const addBtn = document.getElementById('glossary-ctx-add');
        if (addBtn) {
          addBtn.onclick = () => {
            menu.style.display = 'none';
            
            const modal = document.getElementById('reader-glossary-modal');
            const sourceInput = document.getElementById('modal-glossary-source');
            const thaiInput = document.getElementById('modal-glossary-thai');
            const categorySelect = document.getElementById('modal-glossary-category');
            const cancelBtn = document.getElementById('modal-glossary-cancel');
            const saveBtn = document.getElementById('modal-glossary-save');
            
            if (!modal) return;
            
            sourceInput.value = selected;
            thaiInput.value = '';
            categorySelect.value = 'คำศัพท์';
            
            modal.style.display = 'flex';
            thaiInput.focus();
            
            cancelBtn.onclick = () => {
              modal.style.display = 'none';
            };
            
            saveBtn.onclick = async () => {
              const thaiVal = thaiInput.value.trim();
              const categoryVal = categorySelect.value;
              
              if (!thaiVal) {
                alert('กรุณากรอกคำแปลภาษาไทย');
                thaiInput.focus();
                return;
              }
              
              try {
                saveBtn.disabled = true;
                saveBtn.textContent = 'กำลังบันทึก...';
                
                const res = await fetch(`/api/novel/${currentReaderSlug}/glossary/add`, {
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
                  Ui.showToast(`เพิ่ม "${selected} → ${thaiVal}" สำเร็จ`);
                  modal.style.display = 'none';
                  
                  // Invalidate API caches & reload page
                  Api.invalidateAll(currentReaderSlug);
                  window.location.reload();
                } else {
                  alert(resData.error?.message || 'ไม่สามารถเพิ่มศัพท์ลง Glossary ได้');
                }
              } catch (err) {
                alert('เกิดข้อผิดพลาด: ' + err.message);
              } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = 'บันทึก';
              }
            };
          };
        }

        // Hide menu on click elsewhere
        const hideMenu = () => {
          menu.style.display = 'none';
          document.removeEventListener('click', hideMenu);
        };
        setTimeout(() => document.addEventListener('click', hideMenu), 10);
      }, { signal });
    }
  },

  /* ── Cleanup all AbortController-bound events ──────────────────── */
  _cleanupEvents() {
    if (this._readerAbortController) {
      this._readerAbortController.abort();
      this._readerAbortController = null;
    }
  }
};

// Global state for reader nav
let currentReaderIdx = 0;
let currentReaderChapters = [];
let currentReaderSlug = '';
