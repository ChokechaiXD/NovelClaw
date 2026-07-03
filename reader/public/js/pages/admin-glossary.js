/* AdminGlossaryPage. Loaded lazily from admin.js. */

(function () {
  const AdminUi = window.AdminUi;
  const AdminGlossaryModel = window.AdminGlossaryModel;

const AdminGlossaryPage = {
  _terms: [],
  _slug: '',
  _editingIndex: -1,

  _setStatus(message, type = 'success') {
    AdminUi.setStatus('glossary-status', 'c-glossary-admin__status', message, type);
  },

  async _saveTerms() {
    const res = await fetch('/api/novel/' + this._slug + '/glossary/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ terms: this._terms })
    });
    if (!res.ok) throw new Error('ไม่สามารถเซฟข้อมูลลง Server ได้');
    return res.json();
  },

  async render(params) {
    const page = Ui.$('page-admin-glossary');
    if (!page) return;
    
    try {
      const res = await fetch('/api/novels');
      const novels = await res.json();
      this._novels = novels || [];
      this._slug = AdminGlossaryModel.resolveSlug(this._novels, this._slug, params?.slug || '');
      
      if (!this._slug) {
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('glossary') + '<p class="u-text-center u-text-muted">ไม่พบนิยายที่จะแก้ไข Glossary</p></div>';
        return;
      }

      // Load terms
      const glossRes = await fetch(`/api/novel/${this._slug}/glossary/data`);
      if (glossRes.ok) {
        const data = await glossRes.json();
        this._terms = data.terms || data || [];
      } else {
        this._terms = [];
      }

      this._editingIndex = -1;
      this._renderUI(page);
    } catch (err) {
      page.innerHTML = '<div class="c-container">' + Ui.adminNav('glossary') + '<p class="u-text-center c-error__title">เกิดข้อผิดพลาด</p><p class="u-text-center u-text-muted">' + Ui.esc(err.message) + '</p></div>';
    }
  },

  _renderUI(page) {
    const novelOptions = (this._novels || []).map(n =>
      `<option value="${Ui.esc(n.slug)}" ${n.slug === this._slug ? 'selected' : ''}>${Ui.esc(Ui.displayTitle(n) || n.slug)}</option>`
    ).join('');
    const stats = AdminGlossaryModel.stats(this._terms);
    const novel = (this._novels || []).find(n => n.slug === this._slug) || { slug: this._slug };

    let html = '<div class="c-container">' + Ui.adminNav('glossary') +
      '<section class="c-control-center c-admin-cockpit c-glossary-admin__cockpit">' +
      '<div class="c-control-center__head"><div>' +
      '<h2 class="c-control-center__title">' + Ui.icon('bookmarks', 'sm') + 'Glossary Workspace</h2>' +
      '<p class="c-control-center__subtitle">' + Ui.esc(Ui.displayTitle(novel) || this._slug) + ' · คุมชื่อคน สถานที่ สกิล และคำเฉพาะให้แปลสม่ำเสมอ</p>' +
      '</div><a class="c-btn c-btn--primary" href="#admin/translate/' + Ui.esc(this._slug) + '" data-nav>' + Ui.icon('book', 'xs') + '<span>แปลเรื่องนี้</span></a></div>' +
      '<div class="c-control-center__stats">' +
      Ui.stat('terms', stats.total) +
      Ui.stat('verified', stats.verified, { tone: 'success' }) +
      Ui.stat('locked', stats.locked) +
      Ui.stat('needs review', stats.needsReview, { tone: stats.needsReview ? 'warn' : 'success' }) +
      '</div>' +
      '<div class="c-control-center__actions">' +
      '<a class="c-btn c-btn--secondary" href="#novel/' + Ui.esc(this._slug) + '" data-nav>' + Ui.icon('book', 'xs') + '<span>เปิดนิยาย</span></a>' +
      '<a class="c-btn c-btn--ghost" href="#admin/import/' + Ui.esc(this._slug) + '" data-nav>' + Ui.icon('library', 'xs') + '<span>ตรวจ source</span></a>' +
      '</div></section>' +
      '<div class="c-form__group c-glossary-admin__novel-select">' +
        '<label class="c-form__label">เลือกนิยายเพื่อจัดการ Glossary</label>' +
        '<select class="c-form__select" id="glossary-novel-select">' +
          novelOptions +
        '</select>' +
      '</div>' +
      '<div class="c-section__header"><h3 class="c-section__title">คลังคำศัพท์ของเรื่องนี้</h3><span class="c-section__count">' + stats.total + ' terms</span></div>' +
      
      // Two-column responsive layout for Forms
      '<div class="c-glossary-admin__grid">' +
        // Card 1: Add/Edit Term
        '<div class="c-settings-form c-glossary-admin__panel">' +
          '<h4 id="glossary-form-title" class="c-glossary-admin__title">เพิ่มคำศัพท์ใหม่</h4>' +
          '<div class="c-form c-glossary-admin__form">' +
            '<div class="c-glossary-admin__fields">' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">คำศัพท์เดิม (จีน)</label>' +
                '<input class="c-form__input" id="glossary-source" placeholder="เช่น 曹星" />' +
              '</div>' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">คำแปล (ไทย)</label>' +
                '<input class="c-form__input" id="glossary-thai" placeholder="เช่น เฉาซิง" />' +
              '</div>' +
            '</div>' +
            '<div class="c-glossary-admin__fields">' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">ประเภท</label>' +
                '<select class="c-form__select" id="glossary-category">' +
                  '<option value="คำศัพท์">คำศัพท์ทั่วไป</option>' +
                  '<option value="ตัวละคร">ตัวละคร</option>' +
                  '<option value="สถานที่">สถานที่</option>' +
                  '<option value="สกิล">สกิล/ทักษะ</option>' +
                  '<option value="ไอเทม">ไอเทม</option>' +
                '</select>' +
              '</div>' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">การล็อก</label>' +
                '<select class="c-form__select" id="glossary-lock">' +
                  '<option value="auto">Auto (ลื่นไหล)</option>' +
                  '<option value="locked">Locked (ห้ามเปลี่ยน)</option>' +
                  '<option value="reference">Reference (อ้างอิง)</option>' +
                '</select>' +
              '</div>' +
            '</div>' +
            '<div class="c-glossary-admin__actions">' +
              '<button class="c-btn c-btn--primary" id="glossary-save-btn" type="button">' + Ui.icon('bookmarks', 'xs') + '<span>บันทึกคำศัพท์</span></button>' +
              '<button class="c-btn c-btn--secondary" id="glossary-cancel-btn" type="button" hidden>' + Ui.icon('close', 'xs') + '<span>ยกเลิก</span></button>' +
            '</div>' +
          '</div>' +
          '<div id="glossary-status" class="c-glossary-admin__status" aria-live="polite"></div>' +
        '</div>' +

        // Card 2: AI Glossary Suggestion
        '<div class="c-settings-form c-glossary-admin__panel c-glossary-admin__panel--ai">' +
          '<h4 class="c-glossary-admin__title">แนะนำคำศัพท์ใหม่ด้วย AI</h4>' +
          '<div class="c-glossary-admin__scan-row">' +
            '<div class="c-form__group c-glossary-admin__scan-input">' +
              '<label class="c-form__label">ตอนที่ต้องการสแกน</label>' +
              '<input type="number" min="1" class="c-form__input" id="ai-glossary-ch" placeholder="เช่น 1" />' +
            '</div>' +
            '<button class="c-btn c-btn--secondary" id="ai-glossary-scan-btn" type="button">' + Ui.icon('search', 'xs') + '<span>สแกน</span></button>' +
          '</div>' +
          '<div id="ai-glossary-loading" class="c-glossary-admin__loading" hidden>' +
            'กำลังสแกนหาศัพท์จีนที่ยังไม่ได้แปล...' +
          '</div>' +
          '<div id="ai-glossary-results-box" class="c-glossary-admin__results" hidden>' +
            '<div id="ai-glossary-results-list" class="c-glossary-admin__results-list"></div>' +
          '</div>' +
        '</div>' +
      '</div>';

    // Glossary Table
    html += '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>จีน</th><th>ไทย</th><th>ประเภท</th><th>ระดับ</th><th>การตรวจสอบ</th><th class="c-glossary-admin__actions-col">การจัดการ</th></tr></thead><tbody>';
    
    if (this._terms.length === 0) {
      html += '<tr><td colspan="6" class="u-text-center u-text-muted">ไม่มีคำศัพท์ในคลัง</td></tr>';
    } else {
      this._terms.forEach((t, index) => {
        const lockClass = AdminGlossaryModel.lockBadgeClass(t.lock);
        const verifyState = AdminGlossaryModel.verificationState(t);
        
        html += '<tr>' +
          '<td><strong>' + Ui.esc(t.source || '') + '</strong></td>' +
          '<td>' + Ui.esc(t.thai || '') + '</td>' +
          '<td>' + Ui.esc(t.category || 'คำศัพท์') + '</td>' +
          '<td><span class="c-badge ' + lockClass + '">' + Ui.esc(t.lock || 'auto') + '</span></td>' +
          '<td>' +
            '<span class="c-badge ' + verifyState.badgeClass + ' glossary-verify-toggle c-glossary-admin__verify" data-index="' + index + '" title="คลิกเพื่อสลับสถานะการตรวจสอบ">' +
              verifyState.label +
            '</span>' +
          '</td>' +
          '<td><div class="c-glossary-admin__table-actions">' +
            '<button class="c-btn c-btn--xs c-btn--secondary glossary-edit-btn" data-index="' + index + '" type="button">' + Ui.icon('settings', 'xs') + '<span>แก้ไข</span></button>' +
            '<button class="c-btn c-btn--xs c-btn--danger glossary-del-btn" data-index="' + index + '" type="button">' + Ui.icon('close', 'xs') + '<span>ลบ</span></button>' +
          '</div></td>' +
        '</tr>';
      });
    }

    html += '</tbody></table></div></div>';
    page.innerHTML = html;

    this._bindEvents(page);
  },

  _bindEvents(page) {
    const novelSelect = document.getElementById('glossary-novel-select');
    if (novelSelect) {
      novelSelect.onchange = async () => {
        this._slug = novelSelect.value;
        try {
          const glossRes = await fetch(`/api/novel/${this._slug}/glossary/data`);
          if (glossRes.ok) {
            const data = await glossRes.json();
            this._terms = data.terms || data || [];
          } else {
            this._terms = [];
          }
          this._editingIndex = -1;
          this._renderUI(page);
        } catch (err) {
          Ui.showToast('โหลด Glossary ไม่สำเร็จ: ' + err.message, 'error');
        }
      };
    }

    const sourceInput = document.getElementById('glossary-source');
    const thaiInput = document.getElementById('glossary-thai');
    const categorySelect = document.getElementById('glossary-category');
    const lockSelect = document.getElementById('glossary-lock');
    const saveBtn = document.getElementById('glossary-save-btn');
    const cancelBtn = document.getElementById('glossary-cancel-btn');
    const formTitle = document.getElementById('glossary-form-title');

    // Save click handler
    saveBtn.onclick = async () => {
      const source = sourceInput.value.trim();
      const thai = thaiInput.value.trim();
      const category = categorySelect.value;
      const lock = lockSelect.value;

      const validation = AdminGlossaryModel.validateInput({
        source,
        thai,
        terms: this._terms,
        editingIndex: this._editingIndex,
      });
      if (!validation.ok) {
        this._setStatus(validation.message, 'error');
        Ui.showToast(validation.message, 'error');
        return;
      }

      if (this._editingIndex === -1) {
        this._terms.push(AdminGlossaryModel.termFromInput({ source, thai, category, lock }));
        this._setStatus('เพิ่มคำศัพท์สำเร็จแล้ว');
      } else {
        this._terms[this._editingIndex] = AdminGlossaryModel.termFromInput({
          source,
          thai,
          category,
          lock,
          existing: this._terms[this._editingIndex],
        });
        this._setStatus('แก้ไขคำศัพท์สำเร็จแล้ว');
        this._editingIndex = -1;
      }

      // Save to server
      try {
        saveBtn.disabled = true;
        AdminUi.setButton(saveBtn, 'bookmarks', 'กำลังบันทึก...');
        await this._saveTerms();
        Ui.showToast('บันทึกคำศัพท์แล้ว');
        this._renderUI(page);
      } catch (err) {
        this._setStatus('บันทึกไม่สำเร็จ: ' + err.message, 'error');
        Ui.showToast('บันทึกคำศัพท์ไม่สำเร็จ', 'error');
      } finally {
        saveBtn.disabled = false;
        AdminUi.setButton(saveBtn, 'bookmarks', 'บันทึกคำศัพท์');
      }
    };

    // Cancel click handler
    cancelBtn.onclick = () => {
      this._editingIndex = -1;
      this._renderUI(page);
    };

    // Edit click handlers
    page.querySelectorAll('.glossary-edit-btn').forEach(btn => {
      btn.onclick = () => {
        const index = parseInt(btn.dataset.index, 10);
        const t = this._terms[index];
        if (!t) return;

        this._editingIndex = index;
        formTitle.textContent = 'แก้ไขคำศัพท์: ' + t.source;
        sourceInput.value = t.source;
        thaiInput.value = t.thai;
        categorySelect.value = t.category || 'คำศัพท์';
        lockSelect.value = t.lock || 'auto';

        cancelBtn.hidden = false;
        sourceInput.focus();
      };
    });

    // Delete click handlers
    page.querySelectorAll('.glossary-del-btn').forEach(btn => {
      btn.onclick = async () => {
        const index = parseInt(btn.dataset.index, 10);
        const t = this._terms[index];
        if (!t) return;

        if (confirm('คุณแน่ใจว่าต้องการลบคำศัพท์ "' + t.source + '" ใช่หรือไม่?')) {
          this._terms.splice(index, 1);
          try {
            await this._saveTerms();
            Ui.showToast('ลบคำศัพท์แล้ว');
            this._renderUI(page);
          } catch (err) {
            Ui.showToast('ลบไม่สำเร็จ: ' + err.message, 'error');
          }
        }
      };
    });

    // Toggle Verification Badge Handler
    page.querySelectorAll('.glossary-verify-toggle').forEach(badge => {
      badge.onclick = async () => {
        const index = parseInt(badge.dataset.index, 10);
        const currentVerified = this._terms[index].verified !== false;
        const newVerified = !currentVerified;
        
        try {
          badge.classList.add('is-busy');
          const res = await Api.verifyGlossaryTerm(this._slug, index, newVerified);
          this._terms[index].verified = res.data.verified;
          Ui.showToast(newVerified ? 'ยืนยันคำศัพท์แล้ว' : 'ตั้งเป็นรอตรวจแล้ว');
          this._renderUI(page);
        } catch (err) {
          Ui.showToast('สลับสถานะไม่สำเร็จ: ' + err.message, 'error');
          badge.classList.remove('is-busy');
        }
      };
    });

    // AI Glossary Suggestion Handlers
    const aiScanBtn = document.getElementById('ai-glossary-scan-btn');
    const aiChInput = document.getElementById('ai-glossary-ch');
    const aiLoading = document.getElementById('ai-glossary-loading');
    const aiResultsBox = document.getElementById('ai-glossary-results-box');
    const aiResultsList = document.getElementById('ai-glossary-results-list');

    if (aiScanBtn && aiChInput) {
      aiScanBtn.onclick = async () => {
        const chNum = parseInt(aiChInput.value, 10);
        if (isNaN(chNum) || chNum < 1) {
          this._setStatus('กรุณากรอกเลขตอนที่ถูกต้อง', 'error');
          Ui.showToast('กรุณากรอกเลขตอนที่ถูกต้อง', 'error');
          return;
        }

        try {
          aiScanBtn.disabled = true;
          AdminUi.setButton(aiScanBtn, 'search', 'กำลังสแกน...');
          aiLoading.hidden = false;
          aiResultsBox.hidden = true;
          aiResultsList.innerHTML = '';

          const res = await Api.getUnknownTerms(this._slug, chNum);
          const terms = res.terms || [];

          aiLoading.hidden = true;
          aiResultsBox.hidden = false;

          if (terms.length === 0) {
            aiResultsList.innerHTML = '<div class="c-glossary-admin__empty">ไม่พบคำศัพท์ภาษาจีนใหม่ในตอนนี้นะคะ</div>';
          } else {
            terms.forEach((term, termIdx) => {
              const resultId = `ai-suggest-res-${termIdx}`;
              const item = document.createElement('div');
              item.className = 'c-glossary-admin__result-item';
              item.innerHTML = `
                <span class="c-glossary-admin__term">${Ui.esc(term)}</span>
                <div class="c-glossary-admin__result-actions">
                  <span id="${resultId}" class="c-glossary-admin__suggestion"></span>
                  <button class="c-btn c-btn--xs c-btn--secondary ai-suggest-btn c-glossary-admin__mini-btn" data-term="${Ui.esc(term)}" data-result-id="${resultId}" type="button">${Ui.icon('search', 'xs')}<span>ขอไอเดีย</span></button>
                  <button class="c-btn c-btn--xs c-btn--primary ai-add-btn c-glossary-admin__mini-btn" data-term="${Ui.esc(term)}" type="button" hidden>${Ui.icon('arrow-right', 'xs')}<span>ย้ายเข้าฟอร์ม</span></button>
                </div>
              `;
              aiResultsList.appendChild(item);
            });

            // Bind Suggest Idea Event
            aiResultsList.querySelectorAll('.ai-suggest-btn').forEach(btn => {
              btn.onclick = async () => {
                const term = btn.dataset.term;
                const resSpan = document.getElementById(btn.dataset.resultId);
                const addBtn = btn.nextElementSibling;
                if (!resSpan || !addBtn) return;

                try {
                  btn.disabled = true;
                  AdminUi.setButton(btn, 'search', 'กำลังแปล...');
                  resSpan.textContent = 'กำลังแปล...';

                  // Fetch context from source chapter
                  let context = '';
                  try {
                    const sourceRes = await fetch(`/api/novel/${this._slug}/source/${chNum}`);
                    if (sourceRes.ok) {
                      const sourceText = await sourceRes.text();
                      const idx = sourceText.indexOf(term);
                      if (idx !== -1) {
                        const start = Math.max(0, idx - 100);
                        const end = Math.min(sourceText.length, idx + term.length + 100);
                        context = sourceText.substring(start, end).replace(/\n+/g, ' ').trim();
                      }
                    }
                  } catch (errContext) {
                    console.warn('Could not grab context from source:', errContext);
                  }

                  // Call API
                  const suggestRes = await Api.translateTerm(term, context);
                  const thai = suggestRes.data.thai || '';
                  const cat = suggestRes.data.category || 'คำศัพท์';
                  
                  resSpan.innerHTML = `<span class="c-badge c-badge--gray c-glossary-admin__mini-badge">${Ui.esc(cat)}</span> <strong>${Ui.esc(thai)}</strong>`;
                  btn.hidden = true;
                  
                  addBtn.hidden = false;
                  addBtn.dataset.thai = thai;
                  addBtn.dataset.category = cat;
                } catch (errSuggest) {
                  resSpan.textContent = 'ขัดข้อง';
                  btn.disabled = false;
                  AdminUi.setButton(btn, 'search', 'ขอไอเดีย');
                  Ui.showToast('แนะนำคำศัพท์ไม่สำเร็จ: ' + errSuggest.message, 'error');
                }
              };
            });

            // Bind Add to Form Event
            aiResultsList.querySelectorAll('.ai-add-btn').forEach(btn => {
              btn.onclick = () => {
                const term = btn.dataset.term;
                const thai = btn.dataset.thai;
                const cat = btn.dataset.category;

                sourceInput.value = term;
                thaiInput.value = thai;
                categorySelect.value = cat;
                lockSelect.value = 'auto';

                this._setStatus('โหลดแนะนำจาก AI เข้าฟอร์มแล้ว กรุณากดบันทึกค่ะ');
                Ui.showToast('ย้ายคำแนะนำเข้าฟอร์มแล้ว');
                thaiInput.focus();
                
                // Smooth scroll to form
                formTitle.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              };
            });
          }
        } catch (errScan) {
          Ui.showToast('สแกนคำศัพท์ไม่สำเร็จ: ' + errScan.message, 'error');
        } finally {
          aiScanBtn.disabled = false;
          AdminUi.setButton(aiScanBtn, 'search', 'สแกน');
          aiLoading.hidden = true;
        }
      };
    }
  }
};

// ── ADMIN NOVEL EDIT ─────────────────────────────────────────────────────

  window.AdminGlossaryPage = AdminGlossaryPage;
})();
