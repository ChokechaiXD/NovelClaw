/* ═══════════════════════════════════════════════════════════════════════
   admin-provider.js — Admin Provider Wizard
   Loaded on demand by admin.js
   ═══════════════════════════════════════════════════════════════════════ */

const AdminProviderWizardPage = {
  _state: {},

  _setButton(btn, icon, label) {
    if (!btn) return;
    btn.innerHTML = (icon ? Ui.icon(icon, 'xs') : '') + '<span>' + Ui.esc(label || '') + '</span>';
  },

  async render(params) {
    const page = Ui.$('page-admin-provider');
    if (!page) {
      const container = document.getElementById('page-admin');
      if (!container) return;
      container.innerHTML = '<div id="page-admin-provider"></div>';
      return this.render(params);
    }
    Ui.showSkeleton('page-admin-provider');
    try {
      const cfg = await Api.getProviderConfig();
      this._state = {
        providers: cfg.providers || [],
        active: cfg.active || '',
        default_model: cfg.default_model || '',
        discovery_model: cfg.discovery_model || '',
        step: 1,
        selected_provider: cfg.active || '',
        selected_model: cfg.default_model || '',
        selected_discovery: cfg.discovery_model || '',
        selected_custom_base_url: (cfg.providers || []).find(p => p.name === 'custom')?.base_url || '',
      };
      this._renderStep(page);
    } catch (err) {
      Ui.showError(page, 'โหลดข้อมูลไม่สำเร็จ', err.message);
    }
  },

  _renderStep(page) {
    switch (this._state.step) {
      case 1: this._renderStep1(page); break;
      case 2: this._renderStep2(page); break;
      case 3: this._renderStep3(page); break;
      default: this._renderDone(page); break;
    }
  },

  _stepIndicator(page, current) {
    const steps = [
      { num: 1, label: 'เลือก Provider' },
      { num: 2, label: 'เลือกโมเดลแปล' },
      { num: 3, label: 'ตั้งค่า + บันทึก' },
    ];
    return '<div class="c-admin-wizard__steps">' +
      steps.map(s => {
        const cls = s.num === current ? 'c-admin-wizard__step--active' :
                    s.num < current ? 'c-admin-wizard__step--done' : '';
        return '<div class="c-admin-wizard__step ' + cls + '">' +
          '<span class="c-admin-wizard__step-num">' + (s.num < current ? '✓' : s.num) + '</span>' +
          '<span class="c-admin-wizard__step-label">' + s.label + '</span></div>';
      }).join(' → ') + '</div>';
  },

  _renderStep1(page) {
    const { providers, selected_provider } = this._state;
    const selectedProvider = providers.find(p => p.name === selected_provider) || {};
    const showCustom = selected_provider === 'custom';
    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">' + Ui.icon('settings', 'sm') + 'ตั้งค่าระบบ AI</h3></div>' +
      this._stepIndicator(page, 1) +
      '<div class="c-admin-wizard__body">' +
      '<h4>ขั้นตอนที่ 1: เลือกผู้ให้บริการ AI</h4>' +
      '<p class="u-text-muted">เลือก Provider ที่ต้องการใช้ หรือกด refresh เพื่อดึงรายชื่อโมเดลล่าสุดจาก endpoint ที่รองรับ</p>' +
      '<div class="c-admin-provider__cards">' +
      providers.map(p => {
        const act = p.name === selected_provider ? ' c-admin-provider__card--active' : '';
        const modelCount = (p.models || []).length;
        const sourceText = p.model_source === 'live' ? 'live' : 'static';
        const errorText = p.model_error ? ' · fallback' : '';
        return '<div class="c-card c-admin-provider__card' + act + '" data-provider="' + Ui.esc(p.name) + '">' +
          '<div class="c-admin-provider__card-name">' + Ui.esc(p.display_name || p.name) + '</div>' +
          '<div class="c-admin-provider__card-meta">' + modelCount + ' โมเดล · ' + Ui.esc(sourceText + errorText) + '</div>' +
          '</div>';
      }).join('') +
      '</div>' +
      '<div class="c-admin-provider__custom-panel"' + (showCustom ? '' : ' hidden') + '>' +
      '<div class="c-form__group">' +
      '<label class="c-form__label" for="provider-custom-base-url">Custom endpoint</label>' +
      '<input class="c-form__input" id="provider-custom-base-url" value="' + Ui.esc(this._state.selected_custom_base_url || selectedProvider.base_url || '') + '" placeholder="http://localhost:8000/v1" />' +
      '<p class="c-form__help-text">รองรับ OpenAI-compatible /v1 endpoint เช่น LM Studio, Ollama proxy หรือ server ส่วนตัว</p>' +
      '</div></div>' +
      '<div class="c-admin-wizard__actions">' +
      '<button class="c-btn c-btn--secondary" id="provider-refresh-models" type="button">' + Ui.icon('search', 'xs') + '<span>รีเฟรชโมเดล</span></button>' +
      '<button class="c-btn c-btn--primary" id="wizard-next-1" type="button"' + (selected_provider ? '' : ' disabled') + '><span>ต่อไป</span>' + Ui.icon('arrow-right', 'xs') + '</button>' +
      '</div></div>';

    page.querySelectorAll('.c-admin-provider__card').forEach(card => {
      card.addEventListener('click', () => {
        page.querySelectorAll('.c-admin-provider__card').forEach(c => c.classList.remove('c-admin-provider__card--active'));
        card.classList.add('c-admin-provider__card--active');
        this._state.selected_provider = card.dataset.provider;
        document.getElementById('wizard-next-1').disabled = false;
        this._renderStep(page);
      });
    });

    document.getElementById('wizard-next-1').addEventListener('click', () => {
      const customInput = document.getElementById('provider-custom-base-url');
      if (customInput) this._state.selected_custom_base_url = customInput.value.trim();
      this._state.step = 2;
      this._renderStep(page);
    });

    document.getElementById('provider-refresh-models').addEventListener('click', async () => {
      const btn = document.getElementById('provider-refresh-models');
      const customInput = document.getElementById('provider-custom-base-url');
      if (customInput) this._state.selected_custom_base_url = customInput.value.trim();
      btn.disabled = true;
      this._setButton(btn, 'search', 'Refreshing...');
      try {
        const cfg = await Api.getProviderConfig({ refreshModels: true });
        this._state.providers = cfg.providers || [];
        Ui.showToast('อัปเดตรายชื่อโมเดลแล้ว');
        this._renderStep(page);
      } catch (err) {
        Ui.showToast('Refresh models ไม่สำเร็จ: ' + err.message, 'error');
        btn.disabled = false;
        this._setButton(btn, 'search', 'รีเฟรชโมเดล');
      }
    });
  },

  _renderStep2(page) {
    const { providers, selected_provider, selected_model, selected_discovery } = this._state;
    const activeProvider = providers.find(p => p.name === selected_provider) || {};
    const models = activeProvider.models || [];

    let translateOpts = models.map(m =>
      `<option value="${Ui.esc(m.id)}" ${m.id === selected_model ? 'selected' : ''}>${Ui.esc(m.name || m.id)}</option>`
    ).join('');
    if (!models.some(m => m.id === selected_model) && selected_model) {
      translateOpts = `<option value="${Ui.esc(selected_model)}" selected>${Ui.esc(selected_model)}</option>` + translateOpts;
    }

    let discOpts = models.map(m =>
      `<option value="${Ui.esc(m.id)}" ${m.id === selected_discovery ? 'selected' : ''}>${Ui.esc(m.name || m.id)}</option>`
    ).join('');
    discOpts += '<option value="openai/gpt-oss-120b:free"' + (selected_discovery === 'openai/gpt-oss-120b:free' ? ' selected' : '') + '>openai/gpt-oss-120b:free</option>';

    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">' + Ui.icon('settings', 'sm') + 'ตั้งค่าระบบ AI</h3></div>' +
      this._stepIndicator(page, 2) +
      '<div class="c-admin-wizard__body">' +
      '<h4>ขั้นตอนที่ 2: เลือกโมเดล</h4>' +
      '<p class="u-text-muted">Provider: <strong>' + Ui.esc(activeProvider.display_name || selected_provider) + '</strong></p>' +
      '<div class="c-form__group">' +
      '<label class="c-form__label">โมเดลสำหรับแปล (Translate)</label>' +
      '<select class="c-form__select" id="wiz-model-select">' + translateOpts + '</select>' +
      '<input class="c-form__input c-admin-provider__manual-model" id="wiz-model-manual" placeholder="หรือพิมพ์ model id เอง" />' +
      '</div>' +
      '<div class="c-form__group">' +
      '<label class="c-form__label">โมเดลค้นหาคำศัพท์ (Discovery)</label>' +
      '<p class="c-form__help-text">ใช้ LLM อีกตัวเพื่อค้นหา + เสนอคำแปลคำศัพท์ใหม่</p>' +
      '<select class="c-form__select" id="wiz-discovery-select">' + discOpts + '</select>' +
      '<input class="c-form__input c-admin-provider__manual-model" id="wiz-discovery-manual" placeholder="หรือพิมพ์ discovery model id เอง" />' +
      '</div>' +
      '</div>' +
      '<div class="c-admin-wizard__actions">' +
      '<button class="c-btn c-btn--ghost" id="wizard-prev-2" type="button">' + Ui.icon('arrow-left', 'xs') + '<span>ย้อนกลับ</span></button>' +
      '<button class="c-btn c-btn--primary" id="wizard-next-2" type="button"><span>ต่อไป</span>' + Ui.icon('arrow-right', 'xs') + '</button>' +
      '</div></div>';

    document.getElementById('wizard-prev-2').addEventListener('click', () => {
      this._state.step = 1;
      this._renderStep(page);
    });
    document.getElementById('wizard-next-2').addEventListener('click', () => {
      const manualModel = document.getElementById('wiz-model-manual')?.value.trim();
      const manualDiscovery = document.getElementById('wiz-discovery-manual')?.value.trim();
      this._state.selected_model = manualModel || document.getElementById('wiz-model-select').value;
      this._state.selected_discovery = manualDiscovery || document.getElementById('wiz-discovery-select').value;
      this._state.step = 3;
      this._renderStep(page);
    });
  },

  _renderStep3(page) {
    const { selected_provider, selected_model, selected_discovery, providers } = this._state;
    const p = providers.find(x => x.name === selected_provider) || {};
    const pName = p.display_name || selected_provider;
    const isCustom = selected_provider === 'custom';

    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">' + Ui.icon('settings', 'sm') + 'ตั้งค่าระบบ AI</h3></div>' +
      this._stepIndicator(page, 3) +
      '<div class="c-admin-wizard__body">' +
      '<h4>ขั้นตอนที่ 3: ตรวจสอบและบันทึก</h4>' +
      '<div class="c-card c-admin-wizard__summary">' +
      '<table class="c-table"><tbody>' +
      '<tr><td>ผู้ให้บริการ</td><td><strong>' + Ui.esc(pName) + '</strong></td></tr>' +
      '<tr><td>โมเดลแปล</td><td><strong>' + Ui.esc(selected_model) + '</strong></td></tr>' +
      '<tr><td>โมเดลค้นหาคำศัพท์</td><td><strong>' + Ui.esc(selected_discovery) + '</strong></td></tr>' +
      '</tbody></table>' +
      '</div>' +
      (isCustom ? '<div class="c-admin-provider__custom-panel">' +
      '<div class="c-form__group"><label class="c-form__label" for="provider-custom-base-url-final">Custom endpoint</label>' +
      '<input class="c-form__input" id="provider-custom-base-url-final" value="' + Ui.esc(this._state.selected_custom_base_url || p.base_url || '') + '" placeholder="http://localhost:8000/v1" /></div>' +
      '<div class="c-form__group"><label class="c-form__label" for="provider-custom-api-key">Custom API key (optional)</label>' +
      '<input class="c-form__input" id="provider-custom-api-key" type="password" autocomplete="off" placeholder="ปล่อยว่างได้ถ้า endpoint local ไม่ใช้ key" /></div>' +
      '</div>' : '') +
      '<div id="wizard-status"></div>' +
      '<div class="c-admin-wizard__actions">' +
      '<button class="c-btn c-btn--ghost" id="wizard-prev-3" type="button">' + Ui.icon('arrow-left', 'xs') + '<span>ย้อนกลับ</span></button>' +
      '<button class="c-btn c-btn--primary" id="wizard-save" type="button">' + Ui.icon('settings', 'xs') + '<span>บันทึก</span></button>' +
      '</div></div></div>';

    document.getElementById('wizard-prev-3').addEventListener('click', () => {
      this._state.step = 2;
      this._renderStep(page);
    });

    document.getElementById('wizard-save').addEventListener('click', async () => {
      const btn = document.getElementById('wizard-save');
      const statusEl = document.getElementById('wizard-status');
      btn.disabled = true;
      this._setButton(btn, 'settings', 'กำลังบันทึก...');
      statusEl.innerHTML = '<span class="c-badge c-badge--amber">กำลังบันทึก...</span>';
      try {
        await Api.saveProviderConfig({
          active: this._state.selected_provider,
          default_model: this._state.selected_model,
          discovery_model: this._state.selected_discovery,
          custom_base_url: document.getElementById('provider-custom-base-url-final')?.value.trim() || null,
          custom_api_key: document.getElementById('provider-custom-api-key')?.value.trim() || null,
        });
        statusEl.innerHTML = '<span class="c-badge c-badge--teal">บันทึกสำเร็จ</span>';
        this._setButton(btn, 'settings', 'บันทึกแล้ว');
        Ui.showToast('บันทึกการตั้งค่าเรียบร้อย');
        this._state.step = 4;
        setTimeout(() => this._renderStep(page), 1000);
      } catch (err) {
        statusEl.innerHTML = '<span class="c-badge c-badge--red">' + Ui.esc(err.message) + '</span>';
        btn.disabled = false;
        this._setButton(btn, 'settings', 'ลองอีกครั้ง');
      }
    });
  },

  _renderDone(page) {
    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">' + Ui.icon('settings', 'sm') + 'ตั้งค่าระบบ AI</h3></div>' +
      '<div class="c-admin-wizard__body c-admin-wizard__done">' +
      '<div class="c-admin-wizard__done-icon">🎉</div>' +
      '<h4>ตั้งค่าเสร็จสมบูรณ์!</h4>' +
      '<p class="u-text-muted">ระบบ AI พร้อมทำงานแล้ว ต่อไปก็แค่กดแปล!</p>' +
      '<a href="#admin/translate" class="c-btn c-btn--primary c-btn--lg" data-nav>' + Ui.icon('book', 'xs') + '<span>ไปหน้าแปล</span>' + Ui.icon('arrow-right', 'xs') + '</a>' +
      '</div></div>';
  },
};

window.AdminProviderPage = AdminProviderWizardPage;
