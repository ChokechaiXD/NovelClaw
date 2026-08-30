import { clampInt, escapeHTML, uniqueNonEmpty } from './utils.js';

export function createProviderController({ state, el, api }) {
  function getProvider(id) {
    return state.providers.find(provider => provider.id === id) || null;
  }

  function renderProviderStatus() {
    const provider = getProvider(state.activeProvider);
    if (!el.activeProviderLabel || !el.activeModelLabel) return;
    const ready = Boolean(provider?.configured && state.defaultModel);
    el.activeProviderLabel.textContent = provider?.name || state.activeProvider || 'ยังไม่ได้ตั้ง Provider';
    el.activeModelLabel.textContent = provider?.configured
      ? (state.defaultModel || 'ยังไม่ได้เลือกโมเดล')
      : 'ต้องตั้งค่า Provider / API Key';
    if (!el.btnProviderStatus) return;
    el.btnProviderStatus.classList.toggle('is-ready', ready);
    el.btnProviderStatus.classList.toggle('needs-setup', Boolean(provider && !ready));
    el.btnProviderStatus.title = ready
      ? `${provider.name} • ${state.defaultModel}`
      : 'AI Provider ยังตั้งค่าไม่ครบ — คลิกเพื่อแก้ไข';
  }

  function providerFreeModels(provider) {
    return uniqueNonEmpty([
      ...(provider?.liveFreeModels || []),
      ...(provider?.freeModels || []),
    ]);
  }

  function isFreeModel(provider, model) {
    const id = String(model || '').trim().toLowerCase();
    if (!id) return false;
    return providerFreeModels(provider).includes(model)
      || id === 'openrouter/free'
      || id.endsWith(':free')
      || id.endsWith('-free')
      || (provider?.id === 'opencode-zen' && id === 'big-pickle');
  }

  function providerCandidateModels(provider, remoteModels = []) {
    if (!provider) return remoteModels;
    return uniqueNonEmpty([
      provider.model,
      ...providerFreeModels(provider),
      ...(remoteModels || []),
      ...(provider.modelHints || []),
    ]);
  }

  function renderModelOptions(models, selected, provider) {
    const option = model => `<option value="${escapeHTML(model)}" ${model === selected ? 'selected' : ''}>${isFreeModel(provider, model) ? '🆓 ' : ''}${escapeHTML(model)}</option>`;
    const free = models.filter(model => isFreeModel(provider, model));
    const regular = models.filter(model => !isFreeModel(provider, model));
    if (!free.length) return regular.map(option).join('');
    const freeGroup = `<optgroup label="🆓 ฟรี">${free.map(option).join('')}</optgroup>`;
    const regularGroup = regular.length ? `<optgroup label="โมเดลอื่น">${regular.map(option).join('')}</optgroup>` : '';
    return freeGroup + regularGroup;
  }

  function renderFreeModelHints(provider) {
    const free = providerFreeModels(provider);
    if (!free.length) {
      el.providerFreeModels.innerHTML = '';
      return;
    }
    const keyNote = provider?.keyRequired ? ' · ต้องใช้ API Key' : '';
    el.providerFreeModels.innerHTML = `<span>🆓 พบโมเดลฟรี ${free.length} รุ่น${keyNote}:</span> ${free.map(model => `<button type="button" class="model-hint" data-model="${escapeHTML(model)}">${escapeHTML(model)}</button>`).join(' ')}`;
  }

  function renderProviderOptions() {
    el.cfgProvider.innerHTML = state.providers.map(provider => {
      const scope = provider.local ? 'Local' : 'Cloud';
      const ready = provider.configured ? ' • ตั้งค่าแล้ว' : '';
      return `<option value="${escapeHTML(provider.id)}">${escapeHTML(provider.name)} — ${scope}${ready}</option>`;
    }).join('');
  }

  function renderSettingsModelOptions(provider, remoteModels = []) {
    const selected = (el.cfgModelCustom.value || provider?.model || '').trim();
    const models = providerCandidateModels(provider, remoteModels);
    el.cfgModelSelect.innerHTML = models.length
      ? renderModelOptions(models, selected, provider)
      : '<option value="">ยังไม่มีรายชื่อโมเดล — ทดสอบการเชื่อมต่อหรือพิมพ์ Model ID</option>';
  }

  function populateTranslationModels() {
    const provider = getProvider(state.activeProvider);
    const models = providerCandidateModels(provider, state.availableModels);
    if (state.defaultModel && !models.includes(state.defaultModel)) models.unshift(state.defaultModel);
    el.transModelSelect.innerHTML = models.length
      ? renderModelOptions(models, state.defaultModel, provider)
      : '<option value="">ยังไม่มีโมเดลที่พร้อมใช้งาน</option>';
  }

  function applyProviderToSettings(providerID) {
    const provider = getProvider(providerID);
    if (!provider) return;
    state.settingsProvider = provider.id;
    state.clearProviderKey = false;
    el.cfgProvider.value = provider.id;
    el.cfgRouterUrl.value = provider.profileUrl || provider.baseUrl || '';
    el.cfgApiKey.value = '';
    el.cfgApiKey.placeholder = provider.keyMasked
      ? `ใช้ Key ที่จำไว้ (${provider.keyMasked})`
      : (provider.keyRequired ? 'ใส่ API Key' : 'ไม่จำเป็นต้องใช้ Key');
    el.cfgKeyStatus.textContent = provider.keyMasked
      ? `บันทึกแล้ว ${provider.keyMasked}`
      : (provider.keyRequired ? 'ยังไม่ได้ตั้ง Key' : 'ไม่บังคับใช้ Key');
    el.cfgKeyStatus.className = `key-status ${provider.keyMasked ? 'is-set' : ''}`;
    el.cfgModelCustom.value = '';
    el.cfgProtocol.value = provider.profileProtocol || provider.protocol || 'openai-chat';
    el.cfgProtocolWrap.hidden = provider.id !== 'custom';
    renderSettingsModelOptions(provider);

    const badges = [
      provider.local ? 'Local' : 'Cloud',
      provider.keyRequired ? 'ต้องใช้ API Key' : 'Key ไม่บังคับ',
    ];
    el.providerSummary.innerHTML = `<div><strong>${escapeHTML(provider.name)}</strong><span>${escapeHTML(provider.description || '')}</span></div><div>${badges.map(value => `<span class="provider-pill">${escapeHTML(value)}</span>`).join('')}</div>`;
    renderFreeModelHints(provider);
  }

  async function discoverModels(providerID = state.activeProvider, options = {}) {
    const updateTranslation = options.updateTranslation ?? providerID === state.activeProvider;
    const quiet = options.quiet ?? false;
    const provider = getProvider(providerID);
    try {
      const res = await api(`/api/models?provider=${encodeURIComponent(providerID)}`, { silent: quiet });
      const models = res.models || [];
      if (provider) provider.liveFreeModels = res.freeModels || [];
      if (updateTranslation) {
        state.availableModels = models;
        populateTranslationModels();
      }
      if (providerID === state.settingsProvider) {
        renderSettingsModelOptions(provider, models);
        renderFreeModelHints(provider);
      }
      return models;
    } catch (err) {
      if (!quiet) console.warn('Model discovery warning:', err);
      if (provider) provider.liveFreeModels = [];
      if (updateTranslation) {
        state.availableModels = [];
        populateTranslationModels();
      }
      if (providerID === state.settingsProvider) {
        renderSettingsModelOptions(provider);
        renderFreeModelHints(provider);
      }
      return [];
    }
  }

  async function loadConfigAndModels() {
    try {
      const [cfg, providerRes] = await Promise.all([
        api('/api/config'),
        api('/api/providers'),
      ]);
      state.providers = providerRes.providers || [];
      state.activeProvider = cfg.provider || providerRes.active || 'custom';
      state.defaultModel = cfg.defaultModel || '';
      localStorage.setItem('nc_model', state.defaultModel);
      renderProviderOptions();
      renderProviderStatus();
      applyProviderToSettings(state.activeProvider);
      el.cfgTemp.value = cfg.temperature ?? 0.3;
      el.cfgParallel.value = cfg.parallel ?? 2;
      el.cfgMaxTokens.value = cfg.maxTokens ?? 8192;
      void discoverModels(state.activeProvider, { updateTranslation: true, quiet: true });
    } catch (err) {
      console.warn('Config load warning:', err);
      populateTranslationModels();
    }
  }

  function currentSettingsPayload({ includeTuning = true } = {}) {
    const provider = getProvider(state.settingsProvider);
    const payload = {
      provider: state.settingsProvider,
      routerUrl: el.cfgRouterUrl.value.trim(),
      defaultModel: el.cfgModelCustom.value.trim() || el.cfgModelSelect.value || provider?.model || '',
      protocol: provider?.id === 'custom'
        ? el.cfgProtocol.value
        : (provider?.profileProtocol || provider?.protocol || ''),
    };
    const typedKey = el.cfgApiKey.value.trim();
    if (state.clearProviderKey) payload.apiKey = '';
    else if (typedKey) payload.apiKey = typedKey;
    if (includeTuning) {
      const temperature = Number.parseFloat(el.cfgTemp.value);
      payload.temperature = Number.isFinite(temperature) ? Math.max(0, Math.min(2, temperature)) : 0.3;
      payload.parallel = clampInt(el.cfgParallel.value, 1, 8, 2);
      payload.maxTokens = clampInt(el.cfgMaxTokens.value, 512, 131072, 8192);
    }
    return payload;
  }

  async function refreshProviderControlPlane(preferredProvider = '') {
    const [cfg, providerRes] = await Promise.all([
      api('/api/config', { silent: true }),
      api('/api/providers', { silent: true }),
    ]);
    state.providers = providerRes.providers || [];
    state.activeProvider = cfg.provider || providerRes.active || 'custom';
    state.defaultModel = cfg.defaultModel || '';
    renderProviderOptions();
    renderProviderStatus();
    const selected = preferredProvider && getProvider(preferredProvider)
      ? preferredProvider
      : state.activeProvider;
    applyProviderToSettings(selected);
    el.cfgTemp.value = cfg.temperature ?? 0.3;
    el.cfgParallel.value = cfg.parallel ?? 2;
    el.cfgMaxTokens.value = cfg.maxTokens ?? 8192;
    return cfg;
  }

  async function testCurrentProvider() {
    const provider = getProvider(state.settingsProvider);
    if (!provider) return [];
    el.providerTestResult.className = 'provider-test-result is-loading';
    el.providerTestResult.textContent = `กำลังทดสอบ ${provider.name}...`;
    el.btnTestProvider.disabled = true;
    try {
      const res = await api('/api/providers/test', {
        method: 'POST',
        body: JSON.stringify(currentSettingsPayload({ includeTuning: false })),
      });
      const models = res.models || [];
      provider.liveFreeModels = res.freeModels || [];
      renderSettingsModelOptions(provider, models);
      renderFreeModelHints(provider);
      el.providerTestResult.className = 'provider-test-result is-success';
      el.providerTestResult.textContent = `เชื่อมต่อสำเร็จ • พบ ${models.length} โมเดล`;
      return models;
    } catch (err) {
      el.providerTestResult.className = 'provider-test-result is-error';
      el.providerTestResult.textContent = `เชื่อมต่อไม่สำเร็จ: ${err.message}`;
      return [];
    } finally {
      el.btnTestProvider.disabled = false;
    }
  }

  return {
    getProvider,
    renderProviderStatus,
    populateTranslationModels,
    applyProviderToSettings,
    loadConfigAndModels,
    discoverModels,
    currentSettingsPayload,
    refreshProviderControlPlane,
    testCurrentProvider,
  };
}
