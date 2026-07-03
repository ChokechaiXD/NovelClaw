/* Model catalog helpers for the admin translate workflow. */

(function () {
  const Model = window.AdminTranslateModel;

  function providerForModel(cfg = {}, modelId = '') {
    return (cfg.providers || []).find(provider => (provider.models || []).some(model => model.id === modelId))
      || (cfg.providers || []).find(provider => provider.id === cfg.default_provider)
      || (cfg.providers || [])[0]
      || {};
  }

  function modelOptions(cfg = {}) {
    const providerByModel = {};
    const html = (cfg.providers || []).flatMap(provider =>
      (provider.models || []).map(model => {
        providerByModel[model.id] = provider.id;
        return '<option value="' + Ui.esc(model.id) + '" label="' + Ui.esc(Model.modelLabel(provider, model)) + '"></option>';
      })
    ).join('');
    return { html, providerByModel };
  }

  function readout(cfg = {}, modelId = '') {
    const selectedModel = modelId || cfg.default_model || '';
    const provider = providerForModel(cfg, selectedModel);
    return {
      provider,
      providerLabel: provider.label || provider.id || cfg.default_provider || '-',
      modelLabel: selectedModel || '-',
      keyLabel: provider.hasKey ? 'API key ready' : 'Key missing or local model',
      catalogSummary: Model.modelCatalogSummary(cfg),
    };
  }

  function providerCheck(cfg = {}, modelId = '') {
    const provider = providerForModel(cfg, modelId);
    const modelExists = !!provider?.models?.some(model => model.id === modelId);
    const lines = [
      'Provider/model health',
      'provider: ' + (provider?.label || provider?.id || '-'),
      'model: ' + (modelId || '-'),
      'model exists: ' + (modelExists ? 'yes' : 'no'),
      'key: ' + (provider?.hasKey ? 'present' : 'missing/local not required'),
      'catalog: ' + Model.modelCatalogSummary(cfg),
      provider?.modelError ? 'fallback reason: ' + provider.modelError : '',
    ].filter(Boolean).join('\n');
    return { provider, modelExists, lines };
  }

  window.AdminTranslateCatalog = {
    providerForModel,
    modelOptions,
    readout,
    providerCheck,
  };
})();
