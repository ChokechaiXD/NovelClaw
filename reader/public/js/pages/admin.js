/* ═══════════════════════════════════════════════════════════════════════
   admin.js — Lazy admin route registry
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

// ── ADMIN DASHBOARD
const AdminDashboardPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'dashboard',
      '/js/pages/admin-dashboard.js?_v=20260704_admin_modular_5',
      'Failed to load admin-dashboard.js'
    );
    return window.AdminDashboardPage.render(params);
  },
};

// ── ADMIN NOVELS ─────────────────────────────────────────────────────────
const AdminNovelsPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'novels',
      '/js/pages/admin-novels.js?_v=20260704_admin_modular_5',
      'Failed to load admin-novels.js'
    );
    return window.AdminNovelsPage.render(params);
  },
};

// ── ADMIN CHAPTERS ───────────────────────────────────────────────────────
const AdminChaptersPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'chapters',
      '/js/pages/admin-chapters.js?_v=20260704_admin_modular_5',
      'Failed to load admin-chapters.js'
    );
    return window.AdminChaptersPage.render(params);
  },
};

// ── ADMIN GLOSSARY ───────────────────────────────────────────────────────
const AdminGlossaryPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'admin-glossary',
      '/js/pages/admin-glossary.js?_v=20260704_admin_modular_7',
      'Failed to load admin-glossary.js'
    );
    return window.AdminGlossaryPage.render(params);
  },
};

const AdminNovelEditPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'novel-edit',
      '/js/pages/admin-novel-edit.js?_v=20260704_admin_modular_5',
      'Failed to load admin-novel-edit.js'
    );
    return window.AdminNovelEditPage.render(params);
  },
};

// ── ADMIN LOGS VIEWER ────────────────────────────────────────────────────
const AdminLogsPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'logs',
      '/js/pages/admin-logs.js?_v=20260704_admin_modular_5',
      'Failed to load admin-logs.js'
    );
    return window.AdminLogsPage.render(params);
  },
};

// ── ADMIN IMPORT SOURCE ──────────────────────────────────────────────────
const AdminImportPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'import',
      '/js/pages/admin-import.js?_v=20260704_admin_modular_6',
      'Failed to load admin-import.js'
    );
    return window.AdminImportPage.render(params);
  },
};

const AdminTranslatePage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'admin-translate-view',
      '/js/pages/admin-translate-view.js?_v=20260704_chapter_state_1',
      'Failed to load admin-translate-view.js'
    );
    await AdminPageLoader.loadOnce(
      'admin-translate-job',
      '/js/pages/admin-translate-job.js?_v=20260704_admin_modular_9',
      'Failed to load admin-translate-job.js'
    );
    await AdminPageLoader.loadOnce(
      'admin-translate-catalog',
      '/js/pages/admin-translate-catalog.js?_v=20260704_admin_modular_10',
      'Failed to load admin-translate-catalog.js'
    );
    await AdminPageLoader.loadOnce(
      'admin-translate-selection',
      '/js/pages/admin-translate-selection.js?_v=20260704_admin_modular_11',
      'Failed to load admin-translate-selection.js'
    );
    await AdminPageLoader.loadOnce(
      'admin-translate-command',
      '/js/pages/admin-translate-command.js?_v=20260704_admin_modular_12',
      'Failed to load admin-translate-command.js'
    );
    await AdminPageLoader.loadOnce(
      'admin-translate',
      '/js/pages/admin-translate.js?_v=20260704_chapter_state_3',
      'Failed to load admin-translate.js'
    );
    return window.AdminTranslatePage.render(params);
  },
};

const AdminProviderPage = {
  async render(params) {
    await AdminPageLoader.loadOnce(
      'provider',
      '/js/pages/admin-provider.js?_v=20260704_admin_modular_5',
      'Failed to load admin-provider.js'
    );
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
  handler.render(p);
});
