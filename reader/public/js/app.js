/* ═══════════════════════════════════════════════════════════════════════
   app.js — Router + Theme Sync + Sidebar Events
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

// Marker used by Router.register sentinel for routes whose handler will be
// supplied by a lazy-loaded module. Stored as `null` in _routes below.
const LAZY_ROUTE_SENTINEL = Symbol('lazy-route-sentinel');

// ── Simple Hash Router ───────────────────────────────────────────────
let adminModulePromise = null;  // resolves once admin.js is fetched
function ensureAdminLoaded() {
  if (!adminModulePromise) {
    adminModulePromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = '/js/pages/admin.js?_v=20260626d';
      s.async = false;  // preserve execution order with the rest
      s.onload = () => {
        // admin.js attaches Admin* globals to window via the existing wiring
        // (Router.register('admin', ...) at the bottom of admin.js).
        // Resolve on next tick so its top-level Router.register fires.
        setTimeout(resolve, 0);
      };
      s.onerror = () => reject(new Error('Failed to load admin.js'));
      document.head.appendChild(s);
    });
  }
  return adminModulePromise;
}

const Router = {
  _routes: {},
  _current: null,
  onPageChange: null,

  register(name, handler) {
    this._routes[name] = handler;
  },

  init() {
    window.addEventListener('hashchange', () => this._resolve());
    this._resolve();
  },

  async _resolve() {
    const hash = window.location.hash.replace(/^#/, '') || 'home';
    const parts = hash.split('/');
    const page = parts[0];
    const params = {};

    const safeDecode = (val) => {
      try { return decodeURIComponent(val || ''); } catch (e) { return val || ''; }
    };

    // Parse params: #novel/slug, #novel/slug/num, #admin/page etc
    if (page === 'novel' && parts.length >= 2) {
      params.slug = safeDecode(parts[1]);
      if (parts.length >= 3) params.num = safeDecode(parts[2]);
    } else if (page === 'admin' && parts.length >= 2) {
      params.page = safeDecode(parts[1]);
      if (parts.length >= 3) params.slug = safeDecode(parts[2]);
      if (parts.length >= 4) params.num = safeDecode(parts[3]);
    }

    const handler = this._routes[page];
    const fire = (resolvedFn) => {
      if (this._current !== hash) {
        this._current = hash;
        this._activatePage(page, params);
        if (resolvedFn) {
          try { resolvedFn(params); } catch(e) { console.error('Router error', page, e); }
        }
        this.onPageChange?.(page, params);
      }
    };
    // Real handler registered already.
    if (handler && typeof handler === 'function') {
      fire(handler);
    // Sentinel = lazy module not yet loaded; load admin.js, then fire
    // the real handler it registers at the bottom of itself.
    } else if (handler === LAZY_ROUTE_SENTINEL && page === 'admin') {
      try {
        await ensureAdminLoaded();
      } catch (e) {
        console.error('Admin module load failed:', e);
        return;
      }
      // After admin.js runs, this._routes[admin] is now a real function.
      fire(this._routes[page]);
    } else if (!handler && this._current !== hash) {
      this._current = hash;
      this._activatePage('home');
      try { this._routes.home?.(); } catch(e) { console.error('Router error home', e); }
      this.onPageChange?.('home', {});
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

// ── Sidebar Events (Desktop) ───────────────────────────────────────────
function initSidebar() {
  const appShell = document.querySelector('.c-app');
  const toggleBtn = document.getElementById('sidebar-toggle');
  const closeBtn = document.getElementById('sidebar-close');

  // Desktop: toggle sidebar collapse
  toggleBtn?.addEventListener('click', (e) => {
    // On mobile, use drawer instead
    if (window.innerWidth < 1024) {
      openDrawer();
      return;
    }
    appShell?.classList.toggle('c-app--sidebar-collapsed');
    Store.setSetting('sidebarCollapsed', appShell?.classList.contains('c-app--sidebar-collapsed'));
  });

  closeBtn?.addEventListener('click', () => {
    // On mobile, close drawer
    if (window.innerWidth < 1024) {
      closeDrawer();
      return;
    }
    appShell?.classList.add('c-app--sidebar-collapsed');
    Store.setSetting('sidebarCollapsed', true);
  });

  // Restore persisted state (desktop only)
  if (Store.getSettings().sidebarCollapsed && window.innerWidth >= 1024) {
    appShell?.classList.add('c-app--sidebar-collapsed');
  }

  // Nav item clicks (desktop)
  document.querySelectorAll('.c-nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      if (page) window.location.hash = '#' + page;
    });
  });
}

// ── Mobile Drawer ─────────────────────────────────────────────────────
function openDrawer() {
  document.getElementById('drawer-overlay')?.classList.add('c-drawer-overlay--open');
  document.getElementById('drawer-sidebar')?.classList.add('c-drawer--open');
  document.body.style.overflow = 'hidden';
}
function closeDrawer() {
  document.getElementById('drawer-overlay')?.classList.remove('c-drawer-overlay--open');
  document.getElementById('drawer-sidebar')?.classList.remove('c-drawer--open');
  document.body.style.overflow = '';
}

function initDrawer() {
  const overlay = document.getElementById('drawer-overlay');
  const drawerClose = document.getElementById('drawer-close');
  const drawerNav = document.getElementById('drawer-nav');

  // Bind clicks on drawer items
  drawerNav?.querySelectorAll('.c-nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      if (page) {
        window.location.hash = '#' + page;
        closeDrawer();
      }
    });
  });

  overlay?.addEventListener('click', closeDrawer);
  drawerClose?.addEventListener('click', closeDrawer);
}

// ── Mobile Bottom Nav ────────────────────────────────────────────────
function initMobileNav() {
  document.querySelectorAll('.c-mobile-nav__item').forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      if (page) {
        window.location.hash = '#' + page;
        // Update active state
        document.querySelectorAll('.c-mobile-nav__item').forEach(i => i.classList.remove('c-mobile-nav__item--active'));
        item.classList.add('c-mobile-nav__item--active');
      }
    });
  });
}

// ── Reader full-width mode (called when reader page loads) ───────────
function enableReaderMode() {
  const appShell = document.querySelector('.c-app');
  appShell?.classList.remove('c-app--book-mode');
  appShell?.classList.add('c-app--reader-page');
  // Body-level flag so CSS can hide body-level siblings (.c-mobile-nav,
  // .c-reader-bottom-toolbar) which sit OUTSIDE .c-app in the DOM and
  // therefore can't be targeted by '.c-app--reader-page X' selectors.
  document.body.classList.add('c-body--reader-mode');
}
function disableReaderMode() {
  const appShell = document.querySelector('.c-app');
  appShell?.classList.remove('c-app--reader-page');
  appShell?.classList.remove('c-app--book-mode');
  document.body.classList.remove('c-body--reader-mode');
  // Restore sidebar collapsed state
  if (Store.getSettings().sidebarCollapsed && window.innerWidth >= 1024) {
    appShell?.classList.add('c-app--sidebar-collapsed');
  }
}

// ── Bottom reader toolbar (initialized once) ──────────────────────
function initReaderBottomToolbar() {
  const toolbar = document.getElementById('reader-bottom-toolbar');
  if (!toolbar) return;
  if (toolbar.dataset.initialized) return; // already wired
  toolbar.dataset.initialized = 'true';

  toolbar.classList.add('c-reader-bottom-toolbar--show');

  // Wire bottom toolbar buttons
  document.getElementById('reader-bottom-back')?.addEventListener('click', () => {
    window.history.back();
  });

  document.getElementById('reader-bottom-sm')?.addEventListener('click', () => {
    const btn = document.getElementById('reader-font-sm');
    if (btn) btn.click();
  });

  document.getElementById('reader-bottom-lg')?.addEventListener('click', () => {
    const btn = document.getElementById('reader-font-lg');
    if (btn) btn.click();
  });

  document.getElementById('reader-bottom-book')?.addEventListener('click', () => {
    const btn = document.getElementById('reader-distraction-toggle');
    if (btn) btn.click();
  });

  document.getElementById('reader-bottom-theme')?.addEventListener('click', () => {
    const btn = document.getElementById('reader-theme-toggle');
    if (btn) btn.click();
  });
}
function hideReaderBottomToolbar() {
  const toolbar = document.getElementById('reader-bottom-toolbar');
  if (toolbar) toolbar.classList.remove('c-reader-bottom-toolbar--show');
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
    document.body.dataset.theme = t;
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
      feed.innerHTML = '<div class="c-rc__item c-rc__item--empty">ยังไม่มีกิจกรรม</div>';
      return;
    }
    feed.innerHTML = recent.map(e => {
      const n = novels.find(x => x.slug === e.slug);
      const title = Ui.displayTitle(n) || e.slug;
      const dateStr = (e.ts && !isNaN(new Date(e.ts)))
        ? new Date(e.ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
        : '';
      const href = e.slug && e.num ? `#novel/${encodeURIComponent(e.slug)}/${e.num}` : '';
      const tag = href ? 'a' : 'div';
      const attrs = href ? ` href="${href}" class="c-rc__item" data-nav` : ' class="c-rc__item"';
      return `<${tag}${attrs}>${Ui.esc(title)} <span class="c-rc__item-time">ตอนที่ ${e.num}</span><br><span class="c-rc__item-date">${dateStr}</span></${tag}>`;
    }).join('');
  } catch(e) { feed.innerHTML = '<div class="c-rc__item">ไม่สามารถโหลดกิจกรรม</div>'; }

  // Stats section
  const stats = document.getElementById('rightbar-stats');
  if (stats) {
    const novels = await Api.getNovels();
    const totalRead = Store.getHistory().length;
    const translated = novels.reduce((a, n) => a + (n.translatedChapters || 0), 0);
    const total = novels.reduce((a, n) => a + (n.totalChapters || n.chapterCount || 0), 0);
    stats.innerHTML = '<div class="c-mini-stat-grid">' +
      '<div class="c-mini-stat"><div class="c-mini-stat__num">' + novels.length + '</div><div class="c-mini-stat__label">นิยาย</div></div>' +
      '<div class="c-mini-stat"><div class="c-mini-stat__num">' + totalRead + '</div><div class="c-mini-stat__label">อ่านแล้ว</div></div>' +
      '<div class="c-mini-stat"><div class="c-mini-stat__num">' + translated + '</div><div class="c-mini-stat__label">แปลแล้ว</div></div>' +
      '<div class="c-mini-stat"><div class="c-mini-stat__num ' + (total - translated > 0 ? 'c-mini-stat__num--warn' : 'c-mini-stat__num--success') + '">' + (total - translated) + '</div><div class="c-mini-stat__label">รอแปล</div></div></div>';
  }
}

// ── Activity polling control (start/stop per page) ──────────────────
let _activityTimer = null;
function startActivityPolling() {
  if (_activityTimer) return;
  _activityTimer = setInterval(updateActivityFeed, 30000);
}
function stopActivityPolling() {
  if (_activityTimer) {
    clearInterval(_activityTimer);
    _activityTimer = null;
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
  // Admin is registered by admin.js itself when it loads (lazy). We
  // register a sentinel here so the router knows the page name; admin.js
  // overwrites it with a real handler once loaded. _resolve() detects
  // the sentinel and triggers ensureAdminLoaded() before running.
  Router.register('admin', LAZY_ROUTE_SENTINEL);

  // Init UI
  initSidebar();
  initDrawer();
  initMobileNav();
  initTheme();

  // Update activity feed when state is synced from server (LAN sync)
  Store.on('state-synced', () => {
    updateActivityFeed();
  });
  // Wire reader mode toggle
  Router.onPageChange = (page, params) => {
    if (page === 'novel' && params.num) {
      enableReaderMode();
      initReaderBottomToolbar();
    } else {
      ReaderPage._cleanupEvents?.();
      disableReaderMode();
      hideReaderBottomToolbar();
    }
    // Activity polling: only when rightbar might be visible (home)
    if (page === 'home') {
      startActivityPolling();
    } else {
      stopActivityPolling();
    }
  };
  Ui.updateAvatar();

  // Start router
  Router.init();

  // Initial activity — only start polling if on home page
  updateActivityFeed();
  const currentPage = (window.location.hash.replace(/^#/, '') || 'home').split('/')[0];
  if (currentPage === 'home') {
    startActivityPolling();
  }
}

// Auto-boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
