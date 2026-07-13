/* ═══════════════════════════════════════════════════════════════════════
   admin.js — Lazy admin route registry
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const AdminPageLoader = (() => {
  const promises = {};

  function loadOnce(key, src) {
    if (!promises[key]) {
      promises[key] = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.async = false;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
      });
    }
    return promises[key];
  }

  return { loadOnce };
})();

const ADMIN_UI = ['admin-ui', '/js/pages/admin-ui.js'];
const ADMIN_FORMAT = ['admin-format', '/js/pages/admin-format.js'];
const ADMIN_TRANSLATE_MODEL = ['admin-translate-model', '/js/pages/admin-translate-model.js'];
const ADMIN_GLOSSARY_MODEL = ['admin-glossary-model', '/js/pages/admin-glossary-model.js'];
const ADMIN_IMPORT_MODEL = ['admin-import-model', '/js/pages/admin-import-model.js'];

function loadAdminDependencies(assets = []) {
  return Promise.all(assets.map(([key, src]) => AdminPageLoader.loadOnce(key, src)));
}

async function loadAdminPage(key, src, dependencies = []) {
  await loadAdminDependencies(dependencies);
  await AdminPageLoader.loadOnce(key, src);
}

// ── ADMIN DASHBOARD
const AdminDashboardPage = {
  async render(params) {
    await loadAdminPage('dashboard', '/js/pages/admin-dashboard.js');
    return window.AdminDashboardPage.render(params);
  },
};

// ── ADMIN NOVELS ─────────────────────────────────────────────────────────
const AdminNovelsPage = {
  async render(params) {
    await loadAdminPage('novels', '/js/pages/admin-novels.js', [ADMIN_UI, ADMIN_FORMAT]);
    return window.AdminNovelsPage.render(params);
  },
};

// ── ADMIN CHAPTERS ───────────────────────────────────────────────────────
const AdminChaptersPage = {
  async render(params) {
    await loadAdminPage('chapters', '/js/pages/admin-chapters.js', [ADMIN_UI]);
    return window.AdminChaptersPage.render(params);
  },
};

// ── ADMIN GLOSSARY ───────────────────────────────────────────────────────
const AdminGlossaryPage = {
  async render(params) {
    await loadAdminPage('admin-glossary', '/js/pages/admin-glossary.js', [ADMIN_UI, ADMIN_GLOSSARY_MODEL]);
    return window.AdminGlossaryPage.render(params);
  },
};

const AdminNovelEditPage = {
  async render(params) {
    await loadAdminPage('novel-edit', '/js/pages/admin-novel-edit.js', [ADMIN_UI]);
    return window.AdminNovelEditPage.render(params);
  },
};

// ── ADMIN LOGS VIEWER ────────────────────────────────────────────────────
const AdminLogsPage = {
  async render(params) {
    await loadAdminPage('logs', '/js/pages/admin-logs.js');
    return window.AdminLogsPage.render(params);
  },
};

// ── ADMIN IMPORT SOURCE ──────────────────────────────────────────────────
const AdminImportPage = {
  async render(params) {
    await loadAdminPage('import', '/js/pages/admin-import.js', [ADMIN_UI, ADMIN_FORMAT, ADMIN_IMPORT_MODEL]);
    return window.AdminImportPage.render(params);
  },
};

const AdminTranslatePage = {
  async render(params) {
    await loadAdminDependencies([ADMIN_UI, ADMIN_FORMAT, ADMIN_TRANSLATE_MODEL]);
    await loadAdminDependencies([
      ['admin-translate-view', '/js/pages/admin-translate-view.js'],
      ['admin-translate-job', '/js/pages/admin-translate-job.js'],
      ['admin-translate-catalog', '/js/pages/admin-translate-catalog.js'],
      ['admin-translate-selection', '/js/pages/admin-translate-selection.js'],
      ['admin-translate-command', '/js/pages/admin-translate-command.js'],
    ]);
    await loadAdminPage('admin-translate', '/js/pages/admin-translate.js');
    return window.AdminTranslatePage.render(params);
  },
};

const AdminProviderPage = {
  async render(params) {
    await loadAdminPage('provider', '/js/pages/admin-provider.js');
    return window.AdminProviderPage.render(params);
  },
};

// ── Lazy-load registration ─────────────────────────────────────────
// admin.js is loaded on demand by app.js Router (see ensureAdminLoaded()).
// Register the real 'admin' route handler at module load so the router
// can resolve #admin/* URLs without re-loading a second copy of admin.js.
Router.register('admin', (p) => {
  const sub = p && p.page ? p.page : 'dash';
  const adminRoutes = {
    'dash': AdminDashboardPage,
    'novels': AdminNovelsPage,
    'chapters': AdminChaptersPage,
    'glossary': AdminGlossaryPage,
    'import': AdminImportPage,
    'novel-edit': AdminNovelEditPage,
    'logs': AdminLogsPage,
    'translate': AdminTranslatePage,
    'provider': AdminProviderPage,
  };
  const handler = adminRoutes[sub] || AdminDashboardPage;
  return handler.render(p);
});
