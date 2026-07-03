/* ═══════════════════════════════════════════════════════════════════════
   admin-provider.js — Single-page AI Settings
   Loaded on demand by admin.js
   ═══════════════════════════════════════════════════════════════════════ */

const AdminProviderSettingsPage = {
  _state: {},

  _setButton(btn, icon, label) {
    if (!btn) return;
    btn.innerHTML = (icon ? Ui.icon(icon, 'xs') : '') + '<span>' + Ui.esc(label || '') + '</span>';
  },

  _providerId(provider = {}) {
    return provider.name || provider.id || '';
  },

  _providerName(provider = {}) {
    return provider.display_name || provider.label || this._providerId(provider);
  },

  _models(provider = {}) {
    return Array.isArray(provider.models) ? provider.models : [];
  },

  _modelOptions(id, models = []) {
    return '<datalist id="' + Ui.esc(id) + '">' + models.map(model =>
      '<option value="' + Ui.esc(model.id) + '" label="' + Ui.esc(model.name || model.label || model.id) + '"></option>'
    ).join('') + '</datalist>';
  },

  _catalogSummary(provider = {}) {
    const count = this._models(provider).length;
    const source = provider.model_source || provider.modelSource || 'static';
    const key = provider.has_key || provider.hasKey ? 'key ready' : 'no local key';
    return `${count} models · ${source}${provider.model_error ? ' fallback' : ''} · ${key}`;
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
        selectedProvider: cfg.active || (cfg.providers || [])[0]?.name || '',
        defaultModel: cfg.default_model || '',
        discoveryModel: cfg.discovery_model || cfg.default_model || '',
      };
      this._render(page);
    } catch (err) {
      Ui.showError(page, 'โหลดข้อมูลไม่สำเร็จ', err.message);
    }
  },

  _render(page) {
    const providers = this._state.providers || [];
    const provider = providers.find(p => this._providerId(p) === this._state.selectedProvider) || providers[0] || {};
    const providerId = this._providerId(provider);
    const models = this._models(provider);
    const defaultModel = this._state.defaultModel || models[0]?.id || '';
    const discoveryModel = this._state.discoveryModel || defaultModel;
    const isCustom = providerId === 'custom';
    const activeProvider = providers.find(p => this._providerId(p) === this._state.active) || provider;
    const activeProviderId = this._providerId(activeProvider);
    const activeModelProvider = providers.find(p => this._models(p).some(model => model.id === this._state.defaultModel)) || activeProvider;
    const selectedIsActive = providerId === activeProviderId;
    const activeKeyLabel = activeProvider.has_key || activeProvider.hasKey ? 'API key ready' : 'Key missing or local model';

    page.innerHTML = `
      <div class="c-container c-container--wide">
        ${Ui.adminNav('provider')}

        <section class="c-control-center c-admin-provider__cockpit">
          <div class="c-control-center__head">
            <div>
              <h2 class="c-control-center__title">${Ui.icon('settings', 'sm')}AI Model Center</h2>
              <p class="c-control-center__subtitle">เห็น provider/model ที่ใช้อยู่จริงก่อนแก้ค่า เพื่อกันสั่งแปลผิดโมเดล</p>
            </div>
            <div class="c-admin-provider__hero-actions">
              <button class="c-btn c-btn--secondary" id="provider-refresh-models" type="button">${Ui.icon('search', 'xs')}<span>Refresh catalog</span></button>
              <a class="c-btn c-btn--ghost" href="#admin/translate" data-nav>${Ui.icon('book', 'xs')}<span>ไปหน้าแปล</span></a>
            </div>
          </div>
          <div class="c-admin-provider__active-card">
            <div>
              <span class="c-badge c-badge--teal">Active provider</span>
              <h4>${Ui.esc(this._providerName(activeProvider))}</h4>
              <p>${Ui.esc(this._catalogSummary(activeProvider))}</p>
            </div>
            <div class="c-admin-provider__active-models">
              <span><strong>${Ui.esc(this._state.defaultModel || '-')}</strong><small>Translate model · ${Ui.esc(this._providerName(activeModelProvider))}</small></span>
              <span><strong>${Ui.esc(this._state.discoveryModel || '-')}</strong><small>Discovery/Judge model</small></span>
              <span><strong>${Ui.esc(activeKeyLabel)}</strong><small>Credential state</small></span>
            </div>
          </div>
        </section>

        <div class="c-admin-provider__layout">
          <section class="c-admin-provider__rail" aria-label="Providers">
            <h4 class="c-admin-translate__subhead">Provider</h4>
            <div class="c-admin-provider__cards c-admin-provider__cards--stack">
              ${providers.map(p => {
                const id = this._providerId(p);
                const active = id === providerId ? ' c-admin-provider__card--active' : '';
                const activeNow = id === activeProviderId ? '<span class="c-badge c-badge--teal">Active</span>' : '';
                return '<button class="c-admin-provider__card' + active + '" data-provider="' + Ui.esc(id) + '" type="button">' +
                  '<span class="c-admin-provider__card-head"><span class="c-admin-provider__card-name">' + Ui.esc(this._providerName(p)) + '</span>' + activeNow + '</span>' +
                  '<span class="c-admin-provider__card-meta">' + Ui.esc(this._catalogSummary(p)) + '</span>' +
                  '</button>';
              }).join('')}
            </div>
          </section>

          <section class="c-admin-provider__main">
            <div class="c-admin-provider__form-card">
              <div class="c-admin-provider__form-head">
                <div>
                  <h4>${Ui.esc(this._providerName(provider))}</h4>
                  <p class="u-text-muted">${Ui.esc(provider.base_url || 'ใช้ endpoint ตาม provider')}</p>
                </div>
                <div class="c-admin-provider__form-badges">
                  <span class="c-badge ${selectedIsActive ? 'c-badge--teal' : 'c-badge--gray'}">${selectedIsActive ? 'Editing active' : 'Editing inactive'}</span>
                  <span class="c-badge ${provider.model_error ? 'c-badge--amber' : 'c-badge--teal'}">${Ui.esc(provider.model_source || 'static')}</span>
                </div>
              </div>

              <div class="c-admin-provider__form-grid">
                <div class="c-form__group">
                  <label class="c-form__label" for="provider-translate-model">Translate model</label>
                  <input class="c-form__input" id="provider-translate-model" list="provider-model-list" value="${Ui.esc(defaultModel)}" placeholder="ค้นหาหรือพิมพ์ model id" />
                  ${this._modelOptions('provider-model-list', models)}
                </div>
                <div class="c-form__group">
                  <label class="c-form__label" for="provider-discovery-model">Discovery/Judge model</label>
                  <input class="c-form__input" id="provider-discovery-model" list="provider-discovery-list" value="${Ui.esc(discoveryModel)}" placeholder="ค้นหาหรือพิมพ์ model id" />
                  ${this._modelOptions('provider-discovery-list', models)}
                </div>
                <div class="c-form__group ${isCustom ? '' : 'c-admin-provider__custom-hidden'}">
                  <label class="c-form__label" for="provider-custom-base-url">Custom endpoint</label>
                  <input class="c-form__input" id="provider-custom-base-url" value="${Ui.esc(provider.base_url || '')}" placeholder="http://localhost:8000/v1" />
                  <p class="c-form__help-text">OpenAI-compatible /v1 endpoint เช่น local model server หรือ proxy ส่วนตัว</p>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label" for="provider-api-key">API key</label>
                  <input class="c-form__input" id="provider-api-key" type="password" autocomplete="off" placeholder="${provider.has_key ? 'มี key แล้ว - ใส่ค่าใหม่เฉพาะตอนต้องการเปลี่ยน' : 'ใส่ API key สำหรับ provider นี้'}" />
                  <p class="c-form__help-text">บันทึกลง llm.json ในเครื่องนี้เท่านั้น ไฟล์นี้ถูก ignore ไม่ขึ้น repo</p>
                </div>
              </div>

              <div id="provider-save-status" class="c-admin-provider__status"></div>
              <div class="c-admin-provider__savebar">
                <a class="c-btn c-btn--ghost" href="#admin/translate" data-nav>${Ui.icon('book', 'xs')}<span>ไปหน้าแปล</span></a>
                <button class="c-btn c-btn--primary" id="provider-save" type="button">${Ui.icon('settings', 'xs')}<span>บันทึกการตั้งค่า</span></button>
              </div>
            </div>
          </section>
        </div>
      </div>`;

    page.querySelectorAll('[data-provider]').forEach(btn => {
      btn.addEventListener('click', () => {
        this._state.selectedProvider = btn.dataset.provider || this._state.selectedProvider;
        const next = providers.find(p => this._providerId(p) === this._state.selectedProvider) || {};
        const nextModels = this._models(next);
        this._state.defaultModel = nextModels.some(m => m.id === this._state.defaultModel)
          ? this._state.defaultModel
          : (nextModels[0]?.id || this._state.defaultModel || '');
        this._state.discoveryModel = nextModels.some(m => m.id === this._state.discoveryModel)
          ? this._state.discoveryModel
          : this._state.defaultModel;
        this._render(page);
      });
    });

    document.getElementById('provider-refresh-models')?.addEventListener('click', async () => {
      const btn = document.getElementById('provider-refresh-models');
      btn.disabled = true;
      this._setButton(btn, 'search', 'Refreshing...');
      try {
        const cfg = await Api.getProviderConfig({ refreshModels: true });
        this._state.providers = cfg.providers || [];
        this._state.active = cfg.active || this._state.active;
        Ui.showToast('อัปเดต model catalog แล้ว');
        this._render(page);
      } catch (err) {
        Ui.showToast('Refresh catalog ไม่สำเร็จ: ' + err.message, 'error');
        btn.disabled = false;
        this._setButton(btn, 'search', 'รีเฟรช catalog');
      }
    });

    document.getElementById('provider-save')?.addEventListener('click', async () => {
      const btn = document.getElementById('provider-save');
      const status = document.getElementById('provider-save-status');
      const selected = this._state.selectedProvider || providerId;
      btn.disabled = true;
      this._setButton(btn, 'settings', 'กำลังบันทึก...');
      if (status) status.innerHTML = '<span class="c-badge c-badge--amber">กำลังบันทึก...</span>';
      try {
        await Api.saveProviderConfig({
          active: selected,
          default_model: document.getElementById('provider-translate-model')?.value.trim() || defaultModel,
          discovery_model: document.getElementById('provider-discovery-model')?.value.trim() || discoveryModel,
          custom_base_url: selected === 'custom' ? (document.getElementById('provider-custom-base-url')?.value.trim() || null) : null,
          api_key_provider: selected,
          api_key: document.getElementById('provider-api-key')?.value.trim() || null,
        });
        if (status) status.innerHTML = '<span class="c-badge c-badge--teal">บันทึกแล้ว</span>';
        Ui.showToast('บันทึกระบบ AI แล้ว');
        const cfg = await Api.getProviderConfig();
        this._state.providers = cfg.providers || [];
        this._state.active = cfg.active || selected;
        this._state.selectedProvider = this._state.active;
        this._state.defaultModel = cfg.default_model || defaultModel;
        this._state.discoveryModel = cfg.discovery_model || discoveryModel;
        this._render(page);
      } catch (err) {
        if (status) status.innerHTML = '<span class="c-badge c-badge--red">' + Ui.esc(err.message) + '</span>';
        btn.disabled = false;
        this._setButton(btn, 'settings', 'ลองอีกครั้ง');
      }
    });
  },
};

window.AdminProviderPage = AdminProviderSettingsPage;
