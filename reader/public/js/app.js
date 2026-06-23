/* ═══════════════════════════════════════════════════════════════════════
   app.js — Router + Theme Sync + Sidebar Events
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

// ── Simple Hash Router ───────────────────────────────────────────────
const Router = {
  _routes: {},
  _current: null,

  register(name, handler) {
    this._routes[name] = handler;
  },

  init() {
    window.addEventListener('hashchange', () => this._resolve());
    this._resolve();
  },

  _resolve() {
    const hash = window.location.hash.replace(/^#/, '') || 'home';
    const parts = hash.split('/');
    const page = parts[0];
    const params = {};

    // Parse params: #novel/slug, #novel/slug/num, #admin/page etc
    if (page === 'novel' && parts.length >= 2) {
      params.slug = parts[1];
      if (parts.length >= 3) params.num = parts[2];
    } else if (page === 'admin' && parts.length >= 2) {
      params.page = parts[1];
      if (parts.length >= 3) params.slug = parts[2];
    }

    const handler = this._routes[page];
    if (handler && this._current !== hash) {
      this._current = hash;
      this._activatePage(page, params);
      try { handler(params); } catch(e) { console.error('Router error', page, e); }
    } else if (!handler && this._current !== hash) {
      this._current = hash;
      this._activatePage('home');
      try { this._routes.home?.(); } catch(e) { console.error('Router error home', e); }
    }
  },

  _activatePage(page, params) {
    // Determine which page div to show
    let pageId = 'page-' + page;
    if (page === 'admin') {
      const sub = (params && params.page) || '';
      pageId = sub ? 'page-admin-' + sub : 'page-admin';
    }
    if (page === 'novel') {
      pageId = params && params.num ? 'page-reader' : 'page-novel-detail';
    }

    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('page--active'));

    // Show target
    const target = document.getElementById(pageId);
    if (target) target.classList.add('page--active');

    // Update sidebar active state
    document.querySelectorAll('.c-nav-item').forEach(n => n.classList.remove('c-nav-item--active'));
    const navMap = { home: 'home', library: 'library', search: 'search', ranking: 'ranking', profile: 'profile', history: 'history', bookmarks: 'bookmarks', settings: 'settings', admin: 'admin' };
    // Novel/reader routes: clear sidebar highlight (topbar breadcrumb handles context)
    if (page !== 'novel') {
      const navPage = navMap[page] || null;
      if (navPage) {
        const navItem = document.querySelector('.c-nav-item[data-page="' + navPage + '"]');
        if (navItem) navItem.classList.add('c-nav-item--active');
      }
    }

    // Update page title
    const titleEl = document.getElementById('page-title');
    if (titleEl) {
      const titles = { home: 'หน้าหลัก', library: 'หอสมุด', search: 'ค้นหา', ranking: 'อันดับ', profile: 'โปรไฟล์', history: 'ประวัติ', bookmarks: 'บุ๊กมาร์ก', settings: 'ตั้งค่า', admin: 'จัดการ' };
      if (page === 'novel' && params && params.num) {
        titleEl.textContent = 'กำลังอ่าน...';
      } else if (page === 'novel' && params && params.slug) {
        titleEl.textContent = 'รายละเอียด';
      } else {
        titleEl.textContent = titles[page] || 'หน้าหลัก';
      }
    }
  }
};

// ── Sidebar Events ───────────────────────────────────────────────────
function initSidebar() {
  const sidebar = document.querySelector('.c-app__sidebar');
  const toggleBtn = document.getElementById('sidebar-toggle');
  const closeBtn = document.getElementById('sidebar-close');

  toggleBtn?.addEventListener('click', () => {
    sidebar?.classList.toggle('c-app__sidebar--collapsed');
    Store.setSetting('sidebarCollapsed', sidebar?.classList.contains('c-app__sidebar--collapsed'));
  });

  closeBtn?.addEventListener('click', () => {
    sidebar?.classList.add('c-app__sidebar--collapsed');
    Store.setSetting('sidebarCollapsed', true);
  });

  // Nav item clicks
  document.querySelectorAll('.c-nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      if (page) window.location.hash = '#' + page;
    });
  });
}

// ── Theme Initialization ────────────────────────────────────────────
function initTheme() {
  const settings = Store.getSettings();
  document.body.dataset.theme = settings.theme || 'sepia';

  // Sidebar theme toggle
  const themeToggle = document.getElementById('theme-toggle-new');
  if (themeToggle) {
    const isNight = (settings.theme || 'sepia') === 'night' || (settings.theme || 'sepia') === 'amoled';
    themeToggle.classList.toggle('c-toggle--active', isNight);
    themeToggle.addEventListener('click', () => {
      const current = Store.getSettings().theme || 'sepia';
      // Toggle between night and sepia (main two modes)
      const target = (current === 'night' || current === 'amoled') ? 'sepia' : 'night';
      Store.setSetting('theme', target);
      themeToggle.classList.toggle('c-toggle--active', target === 'night');

      // Sync settings page select element
      const settingsSel = document.getElementById('settings-theme');
      if (settingsSel) settingsSel.value = target;
    });
  }

  // Subscribe to theme changes
  Store.on('setting:theme', (t) => {
    if (themeToggle) themeToggle.classList.toggle('c-toggle--active', t === 'night' || t === 'amoled');
  });
}

// ── Activity Feed ───────────────────────────────────────────────────
async function updateActivityFeed() {
  const feed = document.getElementById('activity-feed');
  if (!feed) return;
  try {
    const novels = await Api.getNovels();
    const recent = Store.getHistory().slice(0, 5);
    if (recent.length === 0) {
      feed.innerHTML = '<div class="c-rc__item" style="font-size:11px;color:var(--c-text-muted);padding:8px 0;">ยังไม่มีกิจกรรม</div>';
      return;
    }
    feed.innerHTML = recent.map(e => {
      const n = novels.find(x => x.slug === e.slug);
      const title = Ui.displayTitle(n) || e.slug;
      const dateStr = (e.ts && !isNaN(new Date(e.ts)))
        ? new Date(e.ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
        : '';
      return '<div class="c-rc__item">' + Ui.esc(title) + ' <span style="font-size:10px;color:var(--c-text-soft);">ตอนที่ ' + e.num + '</span><br><span style="font-size:10px;color:var(--c-text-muted);">' + dateStr + '</span></div>';
    }).join('');
  } catch(e) { feed.innerHTML = '<div class="c-rc__item">ไม่สามารถโหลดกิจกรรม</div>'; }

  // Stats section
  const stats = document.getElementById('rightbar-stats');
  if (stats) {
    const novels = await Api.getNovels();
    const totalRead = Store.getHistory().length;
    const translated = novels.reduce((a, n) => a + (n.translatedChapters || 0), 0);
    const total = novels.reduce((a, n) => a + (n.totalChapters || n.chapterCount || 0), 0);
    stats.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">' +
      '<div style="background:var(--c-surface);border-radius:var(--radius-sm);padding:10px;text-align:center;"><div style="font-size:16px;font-weight:800;color:var(--c-accent);">' + novels.length + '</div><div style="font-size:10px;color:var(--c-text-muted);">นิยาย</div></div>' +
      '<div style="background:var(--c-surface);border-radius:var(--radius-sm);padding:10px;text-align:center;"><div style="font-size:16px;font-weight:800;color:var(--c-accent);">' + totalRead + '</div><div style="font-size:10px;color:var(--c-text-muted);">อ่านแล้ว</div></div>' +
      '<div style="background:var(--c-surface);border-radius:var(--radius-sm);padding:10px;text-align:center;"><div style="font-size:16px;font-weight:800;color:var(--c-accent);">' + translated + '</div><div style="font-size:10px;color:var(--c-text-muted);">แปลแล้ว</div></div>' +
      '<div style="background:var(--c-surface);border-radius:var(--radius-sm);padding:10px;text-align:center;"><div style="font-size:16px;font-weight:800;' + (total - translated > 0 ? 'color:var(--c-warning);' : 'color:var(--c-success);') + '">' + (total - translated) + '</div><div style="font-size:10px;color:var(--c-text-muted);">รอแปล</div></div></div>';
  }
}

// ── Init ────────────────────────────────────────────────────────────────
function init() {
  // Register routes
  Router.register('home', (p) => HomePage.render(p));
  Router.register('library', (p) => LibraryPage.render(p));
  Router.register('search', (p) => SearchPage.render(p));
  Router.register('novel', (p) => {
    if (p.num) ReaderPage.render(p);
    else NovelPage.render(p);
  });
  Router.register('ranking', (p) => RankingPage.render(p));
  Router.register('profile', (p) => ProfilePage.render(p));
  Router.register('history', (p) => HistoryPage.render(p));
  Router.register('bookmarks', (p) => BookmarksPage.render(p));
  Router.register('settings', (p) => SettingsPage.render(p));
  Router.register('admin', (p) => {
    const sub = p && p.page ? p.page : 'dash';
    const adminRoutes = {
      'dash': AdminDashboardPage,
      'jobs': AdminJobsPage,
      'novels': AdminNovelsPage,
      'chapters': AdminChaptersPage,
      'glossary': AdminGlossaryPage,
      'novel-edit': AdminNovelEditPage,
    };
    const handler = adminRoutes[sub] || AdminDashboardPage;
    handler.render(p);
  });

  // Init UI
  initSidebar();
  initTheme();
  Ui.updateAvatar();

  // Start router
  Router.init();

  // Activity feed
  updateActivityFeed();
  setInterval(updateActivityFeed, 30000);
}

// Auto-boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
