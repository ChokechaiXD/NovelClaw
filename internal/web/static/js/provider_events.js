import { escapeHTML } from './utils.js';

export function createProviderEvents({
  state, el, api, showToast, openModal, closeModal,
  getProvider, renderProviderStatus, applyProviderToSettings,
  discoverModels, testCurrentProvider, refreshProviderControlPlane,
  currentSettingsPayload,
}) {
  async function refreshActiveModels() {
    const provider = getProvider(state.activeProvider);
    showToast(`กำลังดึงโมเดลจาก ${provider?.name || 'Provider'}...`, 'info');
    const models = await discoverModels(state.activeProvider, { updateTranslation: true });
    showToast(`พบโมเดล ${models.length} รายการ`, models.length ? 'success' : 'warning');
  }

  async function persistTranslationModel() {
    const chosen = el.transModelSelect.value;
    if (!chosen || chosen === state.defaultModel) return;
    const previousModel = state.defaultModel;
    el.transModelSelect.disabled = true;
    try {
      const cfg = await api('/api/config', {
        method: 'POST',
        body: JSON.stringify({ provider: state.activeProvider, defaultModel: chosen }),
      });
      state.defaultModel = cfg.defaultModel || chosen;
      localStorage.setItem('nc_model', state.defaultModel);
      const provider = getProvider(state.activeProvider);
      if (provider) provider.model = state.defaultModel;
      renderProviderStatus();
    } catch (err) {
      el.transModelSelect.value = previousModel;
      showToast(`เปลี่ยนโมเดลไม่สำเร็จ: ${err.message}`, 'error');
    } finally {
      el.transModelSelect.disabled = false;
    }
  }

  async function openSettings() {
    openModal(el.modalSettings);
    el.providerTestResult.textContent = '';
    try {
      await refreshProviderControlPlane();
      await discoverModels(state.settingsProvider, { updateTranslation: false, quiet: true });
    } catch (err) {
      el.providerTestResult.className = 'provider-test-result is-error';
      el.providerTestResult.textContent = `โหลดการตั้งค่าไม่สำเร็จ: ${err.message}`;
    }
  }
  async function detectLocalProviders() {
    el.detectProviders.innerHTML = '<span class="provider-pill">กำลังตรวจ Local gateway...</span>';
    try {
      const res = await api('/api/detect-providers');
      const found = res.providers || [];
      if (!found.length) {
        el.detectProviders.innerHTML = '<span class="provider-muted">ไม่พบ Local gateway ที่กำลังทำงาน</span>';
        return;
      }
      el.detectProviders.innerHTML = found.map(provider => `
        <button type="button" class="provider-detected-item" data-provider="${escapeHTML(provider.provider)}" data-url="${escapeHTML(provider.url)}">
          <span>● ${escapeHTML(provider.provider)}</span><small>${provider.modelCount || 0} models</small>
        </button>`).join('');
    } catch (err) {
      el.detectProviders.innerHTML = '<span class="provider-error">ตรวจ Local gateway ไม่สำเร็จ</span>';
    }
  }

  async function activateDetectedProvider(button) {
    applyProviderToSettings(button.dataset.provider);
    el.cfgRouterUrl.value = button.dataset.url || el.cfgRouterUrl.value;
    await discoverModels(state.settingsProvider, { updateTranslation: false, quiet: true });
  }
  async function saveSettings(event) {
    event.preventDefault();
    const payload = currentSettingsPayload();
    if (!payload.routerUrl) {
      showToast('กรุณาระบุ Base URL', 'warning');
      return;
    }
    if (!payload.defaultModel) {
      showToast('กรุณาเลือกหรือระบุ Model ID', 'warning');
      return;
    }
    el.btnSaveSettings.disabled = true;
    el.btnSaveSettings.textContent = 'กำลังบันทึก...';
    try {
      const cfg = await api('/api/config', { method: 'POST', body: JSON.stringify(payload) });
      state.activeProvider = cfg.provider;
      state.defaultModel = cfg.defaultModel || payload.defaultModel;
      localStorage.setItem('nc_model', state.defaultModel);
      await refreshProviderControlPlane(cfg.provider);
      await discoverModels(cfg.provider, { updateTranslation: true, quiet: true });
      showToast(`ใช้งาน ${getProvider(cfg.provider)?.name || cfg.provider} แล้ว`, 'success');
      closeModal(el.modalSettings);
    } finally {
      el.btnSaveSettings.disabled = false;
      el.btnSaveSettings.textContent = '✓ บันทึกและใช้งาน';
    }
  }
  function bindProviderEvents() {
    el.btnRefreshModels?.addEventListener('click', refreshActiveModels);
    el.btnCfgRefreshModels?.addEventListener('click', testCurrentProvider);
    el.transModelSelect?.addEventListener('change', persistTranslationModel);
    el.btnProviderStatus?.addEventListener('click', () => el.btnOpenSettings.click());
    el.btnOpenSettings?.addEventListener('click', openSettings);
    el.btnCloseSettings?.addEventListener('click', () => closeModal(el.modalSettings));
    el.cfgProvider?.addEventListener('change', async () => {
      applyProviderToSettings(el.cfgProvider.value);
      el.providerTestResult.textContent = '';
      await discoverModels(state.settingsProvider, { updateTranslation: false, quiet: true });
    });
    el.cfgModelSelect?.addEventListener('change', () => {
      if (el.cfgModelSelect.value) el.cfgModelCustom.value = '';
      el.providerFreeModels?.querySelectorAll('[data-model]').forEach(button => {
        const active = button.dataset.model === el.cfgModelSelect.value;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
    });
    el.providerFreeModels?.addEventListener('click', event => {
      const button = event.target.closest('[data-model]');
      if (!button) return;
      const model = button.dataset.model || '';
      const inSelect = [...el.cfgModelSelect.options].some(option => option.value === model);
      if (inSelect) {
        el.cfgModelSelect.value = model;
        el.cfgModelCustom.value = '';
      } else {
        el.cfgModelCustom.value = model;
      }
      el.providerFreeModels.querySelectorAll('[data-model]').forEach(item => {
        const active = item.dataset.model === model;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      showToast(`????? ${model}`, 'info');
    });
    el.btnClearApiKey?.addEventListener('click', () => {
      state.clearProviderKey = true;
      el.cfgApiKey.value = '';
      el.cfgKeyStatus.textContent = 'จะล้าง Key เมื่อกดบันทึก';
      el.cfgKeyStatus.className = 'key-status is-warning';
    });
    el.cfgApiKey?.addEventListener('input', () => {
      if (!el.cfgApiKey.value.trim()) return;
      state.clearProviderKey = false;
      el.cfgKeyStatus.textContent = 'มี Key ใหม่รอบันทึก';
      el.cfgKeyStatus.className = 'key-status is-pending';
    });
    el.btnTestProvider?.addEventListener('click', testCurrentProvider);
    el.btnDetectProviders?.addEventListener('click', detectLocalProviders);
    el.detectProviders?.addEventListener('click', event => {
      const button = event.target.closest('[data-provider]');
      if (button) activateDetectedProvider(button);
    });
    el.formSettings?.addEventListener('submit', saveSettings);
  }

  return { bindProviderEvents };
}
