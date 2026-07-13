/* ═══════════════════════════════════════════════════════════════════════
   app.js — Router + Theme Sync + Sidebar Events
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

// Marker used by Router.register sentinel for routes whose handler will be
// supplied by a lazy-loaded module. Stored as `null` in _routes below.
const LAZY_ROUTE_SENTINEL = Symbol('lazy-route-sentinel');

// ── Simple Hash Router ───────────────────────────────────────────────
let adminModulePromise = null;  // resolves once the admin route registry is fetched
function loadLazyScript(src, errorMessage) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.async = false;  // preserve execution order with the rest
    s.onload = () => setTimeout(resolve, 0);
    s.onerror = () => reject(new Error(errorMessage));
    document.head.appendChild(s);
  });
}

function ensureAdminLoaded() {
  if (!adminModulePromise) {
    adminModulePromise = loadLazyScript(
      '/js/pages/admin.js',
      'Failed to load admin.js'
    );
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
    document.querySelectorAll('.c-nav-item, .c-mobile-nav__item').forEach((navItem) => {
      navItem.classList.remove('c-nav-item--active', 'c-mobile-nav__item--active');
      navItem.removeAttribute('aria-current');
    });
    const navMap = { home: 'home', library: 'library', search: 'search', ranking: 'ranking', profile: 'profile', history: 'history', bookmarks: 'bookmarks', settings: 'settings', admin: 'admin' };
    // Novel/reader routes: clear sidebar highlight (topbar breadcrumb handles context)
    if (page !== 'novel') {
      const navPage = navMap[page] || null;
      if (navPage) {
        document.querySelectorAll('[data-page="' + navPage + '"]').forEach((navItem) => {
          if (navItem.classList.contains('c-nav-item')) navItem.classList.add('c-nav-item--active');
          if (navItem.classList.contains('c-mobile-nav__item')) navItem.classList.add('c-mobile-nav__item--active');
          navItem.setAttribute('aria-current', 'page');
        });
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
let drawerReturnFocus = null;

function openDrawer() {
  const drawer = document.getElementById('drawer-sidebar');
  const toggle = document.getElementById('sidebar-toggle');
  drawerReturnFocus = document.activeElement;
  document.getElementById('drawer-overlay')?.classList.add('c-drawer-overlay--open');
  drawer?.classList.add('c-drawer--open');
  drawer?.setAttribute('aria-hidden', 'false');
  toggle?.setAttribute('aria-expanded', 'true');
  document.body.style.overflow = 'hidden';
  document.getElementById('drawer-close')?.focus();
}

function closeDrawer(restoreFocus = true) {
  const drawer = document.getElementById('drawer-sidebar');
  const toggle = document.getElementById('sidebar-toggle');
  const wasOpen = drawer?.classList.contains('c-drawer--open');
  document.getElementById('drawer-overlay')?.classList.remove('c-drawer-overlay--open');
  drawer?.classList.remove('c-drawer--open');
  drawer?.setAttribute('aria-hidden', 'true');
  toggle?.setAttribute('aria-expanded', 'false');
  document.body.style.overflow = '';
  if (wasOpen && restoreFocus && drawerReturnFocus?.focus) drawerReturnFocus.focus();
  drawerReturnFocus = null;
}

function handleDrawerKeydown(e) {
  const drawer = document.getElementById('drawer-sidebar');
  if (!drawer?.classList.contains('c-drawer--open')) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    closeDrawer();
    return;
  }
  if (e.key !== 'Tab') return;

  const focusable = Array.from(drawer.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  ));
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
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
  document.getElementById('drawer-sidebar')?.addEventListener('keydown', handleDrawerKeydown);
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 1024) closeDrawer(false);
  });
}

// ── Mobile Bottom Nav ────────────────────────────────────────────────
function initMobileNav() {
  document.querySelectorAll('.c-mobile-nav__item').forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      if (page) {
        window.location.hash = '#' + page;
      }
    });
  });
}

// ── Reader full-width mode (called when reader page loads) ───────────
function enableReaderMode() {
  const appShell = document.querySelector('.c-app');
  appShell?.classList.add('c-app--reader-page');
  // Body-level flag so CSS can hide body-level siblings such as mobile nav.
  document.body.classList.add('c-body--reader-mode');
}
function disableReaderMode() {
  const appShell = document.querySelector('.c-app');
  appShell?.classList.remove('c-app--reader-page');
  document.body.classList.remove('c-body--reader-mode');
  // Restore sidebar collapsed state
  if (Store.getSettings().sidebarCollapsed && window.innerWidth >= 1024) {
    appShell?.classList.add('c-app--sidebar-collapsed');
  }
}

// ── Theme Initialization ────────────────────────────────────────────
function initTheme() {
  const settings = Store.getSettings();
  document.body.dataset.theme = settings.theme || 'sepia';

  // Sidebar theme toggle
  const themeToggle = document.getElementById('theme-toggle-new');
  if (themeToggle) {
    const syncThemeToggle = (theme) => {
      const isNight = theme === 'night' || theme === 'amoled';
      themeToggle.classList.toggle('c-toggle--active', isNight);
      themeToggle.setAttribute('aria-checked', String(isNight));
    };
    syncThemeToggle(settings.theme || 'sepia');
    Store.on('setting:theme', syncThemeToggle);
    themeToggle.addEventListener('click', () => {
      const current = Store.getSettings().theme || 'sepia';
      // Toggle between night and sepia (main two modes)
      const target = (current === 'night' || current === 'amoled') ? 'sepia' : 'night';
      Store.setSetting('theme', target);
    });
  }

  // Subscribe to theme changes
  Store.on('setting:theme', (t) => {
    document.body.dataset.theme = t;
    if (themeToggle) themeToggle.classList.toggle('c-toggle--active', t === 'night' || t === 'amoled');
  });
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

  // Wire reader mode toggle
  Router.onPageChange = (page, params) => {
    if (page === 'novel' && params.num) {
      enableReaderMode();
    } else {
      ReaderPage._cleanupEvents?.();
      disableReaderMode();
    }
  };
  // Start router
  Router.init();

}

// Auto-boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
