// NovelClaw Reader v2 — frontend logic.
// Vanilla JS, no framework.
(function() {
const state = {
  novel: null,
  chapters: [],   // [{num, title}, ...]
  index: -1,
  num: null,
  searchQuery: '',
};

const STORAGE_KEY = 'novelclaw-reader-v1';
const THEMES = ['dark', 'light', 'sepia'];
const THEME_ICONS = { light: '☀', dark: '🌙', sepia: '📖' };
const READING_WPM = 250;

// ── Storage helpers ────────────────────────────────────────────────────

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}
function saveState(s) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch (err) { console.warn('saveState failed:', err.message || err); }
}
function markRead(slug, num) {
  const s = loadState();
  s[slug] = s[slug] || {};
  s[slug][num] = Date.now();
  saveState(s);
}
function isRead(slug, num) {
  const s = loadState();
  return !!(s[slug] && s[slug][num]);
}
function getLastPosition(slug) {
  return loadState()[slug + '-last'] || null;
}
function setLastPosition(slug, num) {
  const s = loadState();
  s[slug + '-last'] = num;
  saveState(s);
}

// ── API ────────────────────────────────────────────────────────────────

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Rendering ──────────────────────────────────────────────────────────

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k.startsWith('on') && typeof v === 'function') {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    }
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else if (k === 'value' && (tag === 'input' || tag === 'textarea' || tag === 'select')) {
      node.value = v;
    }
    else if (['selected', 'checked', 'disabled', 'readonly', 'required'].includes(k.toLowerCase())) {
      if (v) {
        node.setAttribute(k, '');
        node[k] = true;
      } else {
        node.removeAttribute(k);
        node[k] = false;
      }
    }
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return node;
}

// Safe getElementById — returns null silently instead of throwing.
// Used throughout to guard against missing DOM elements.
function $(id) { return document.getElementById(id); }

function setNovelTitle(slug, meta) {
  const titleEl = $('novel-title');
  if (!titleEl) return;
  if (meta) {
    const m = meta.match(/\*\*Original title \(CN\):\*\*\s*(.+)/);
    titleEl.textContent = m ? m[1].trim() : slug;
    titleEl.title = meta.split('\n')[0].replace(/^#\s*/, '');
  } else {
    titleEl.textContent = slug;
  }
}

function findIndexByNum(num) {
  for (let i = 0; i < state.chapters.length; i++) {
    if (state.chapters[i].num === num) return i;
  }
  return -1;
}

// Build a VirtualScroll instance for the chapter list. The render fn
// captures the current `state.num` and `isRead(slug, num)` so that
// updates to state.recompute the active/read class in place via .update().
function createListInstance() {
  const container = document.getElementById('chapter-list');
  let viewport = document.getElementById('vscroll-viewport');
  let spacer = document.getElementById('vscroll-spacer');
  if (!viewport || !spacer) {
    container.innerHTML =
      '<div class="vscroll-viewport" id="vscroll-viewport">' +
      '<div class="vscroll-spacer" id="vscroll-spacer"></div></div>';
    viewport = document.getElementById('vscroll-viewport');
    spacer = document.getElementById('vscroll-spacer');
  }
  const slug = state.novel;
  function classesFor(num, read) {
    return `vscroll-row ${num === state.num ? 'active' : ''} ${read ? 'read' : ''}`.trim();
  }
  return new VirtualScroll(container, {
    rowHeight: 64,
    buffer: 5,
    render: (ch) => {
      const num = ch.num;
      const title = ch.title || `ตอนที่ ${num}`;
      const read = isRead(slug, num);
      const isActive = num === state.num;
      return el('a', {
        href: `?novel=${slug}&ch=${num}`,
        class: classesFor(num, read),
        'data-num': String(num),
        'role': 'listitem',
        'aria-current': isActive ? 'page' : null,
        title,
        onclick: (e) => { e.preventDefault(); loadChapter(num); },
      },
        el('span', { class: 'chapter-num' }, String(num).padStart(4, '0')),
        el('span', { class: 'chapter-label-text' }, title),
      );
    },
    update: (ch, _idx, rowEl) => {
      const num = ch.num;
      const title = ch.title || `ตอนที่ ${num}`;
      const read = isRead(slug, num);
      const isActive = num === state.num;
      rowEl.className = classesFor(num, read);
      rowEl.setAttribute('href', `?novel=${slug}&ch=${num}`);
      rowEl.setAttribute('data-num', String(num));
      rowEl.setAttribute('title', title);
      rowEl.setAttribute('aria-current', isActive ? 'page' : 'false');
      const label = rowEl.querySelector('.chapter-label-text');
      if (label) label.textContent = title;
    },
  });
}

function renderChapterList() {
  const slug = state.novel;
  const q = (state.searchQuery || '').toLowerCase();
  const visible = state.chapters.filter((ch) => {
    if (!q) return true;
    if (String(ch.num) === q) return true;
    if (String(ch.num).startsWith(q)) return true;
    return (ch.title || '').toLowerCase().includes(q);
  });

  if (visible.length === 0) {
    if (state.list) { state.list.setItems([]); state.list = null; }
    const list = $('chapter-list');
    if (list) list.innerHTML = '<div class="empty-list">(ไม่พบ chapter)</div>';
  } else {
    const placeholder = document.querySelector('#chapter-list > .empty-list');
    if (placeholder) placeholder.remove();
    if (!state.list) state.list = createListInstance();
    state.list.setItems(visible);
  }
  const label = q
    ? `${visible.length} / ${state.chapters.length} ตอน`
    : `${state.chapters.length} ตอน`;
  const chapterCount = $('chapter-count');
  if (chapterCount) chapterCount.textContent = label;
  updateTopProgress();
}

function updateTopProgress() {
  const slug = state.novel;
  if (!slug) return;
  const readCount = state.chapters.filter((c) => isRead(slug, c.num)).length;
  const total = state.chapters.length;
  const pct = total > 0 ? Math.round((readCount / total) * 100) : 0;
  const el = document.getElementById('topbar-progress');
  if (el) el.textContent = `${readCount}/${total} (${pct}%)`;
}

function setActiveInList() {
  if (state.list) state.list.refresh();
}

function updateNavButtons() {
  const prev = state.index > 0;
  const next = state.index < state.chapters.length - 1;
  for (const id of ['prev-chapter', 'prev-chapter-2']) {
    const el = $(id);
    if (el) el.disabled = !prev;
  }
  for (const id of ['next-chapter', 'next-chapter-2']) {
    const el = $(id);
    if (el) el.disabled = !next;
  }
  const pos = $('chapter-position');
  if (pos) pos.textContent = state.index >= 0
    ? `${state.index + 1} / ${state.chapters.length}`
    : `— / ${state.chapters.length}`;
  const posTop = $('chapter-pos-top');
  if (posTop && pos) posTop.textContent = pos.textContent;
}

function estimateReadingTime(html) {
  const text = html.replace(/<[^>]+>/g, '').replace(/\s+/g, '');
  return Math.max(1, Math.round(text.length / READING_WPM));
}

function showChapter(data) {
  const emptyState = $('empty-state');
  if (emptyState) emptyState.hidden = true;
  const article = $('chapter');
  if (article) article.hidden = false;

  const chapterTitle = $('chapter-title');
  if (chapterTitle) chapterTitle.textContent =
    data.title || `ตอนที่ ${data.num}`;
  const chapterContent = $('chapter-content');
  if (chapterContent) chapterContent.innerHTML = data.html;
  // Wrap metaHtml in collapsible <details> if present
  const chapterMeta = $('chapter-meta');
  if (chapterMeta) {
    chapterMeta.innerHTML = data.metaHtml
      ? `<details><summary>หมายเหตุการแปล</summary>${data.metaHtml}</details>`
      : '';
  }

  const rt = $('reading-time');
  if (rt && data.html) {
    rt.textContent = `⏱ ${estimateReadingTime(data.html)} นาที`;
    
    const bookmarked = localDB.isBookmarked(state.novel, data.num);
    const bkBtn = el('a', {
      href: '#',
      class: 'chapter-action-btn',
      onclick: (e) => {
        e.preventDefault();
        if (bookmarked) {
          localDB.removeBookmark(state.novel, data.num);
        } else {
          localDB.addBookmark(state.novel, data.num);
        }
        showChapter(data);
      }
    }, bookmarked ? '🔖 บุ๊กมาร์กแล้ว' : '🔖 บุ๊กมาร์ก');

    const downloaded = localDB.isDownloaded(state.novel, data.num);
    const dlBtn = el('a', {
      href: '#',
      class: 'chapter-action-btn',
      onclick: (e) => {
        e.preventDefault();
        if (downloaded) {
          localDB.removeDownload(state.novel, data.num);
        } else {
          localDB.addDownload(state.novel, data.num, data.title || `ตอนที่ ${data.num}`);
        }
        showChapter(data);
      }
    }, downloaded ? '📥 ดาวน์โหลดแล้ว' : '📥 ดาวน์โหลด');

    rt.appendChild(bkBtn);
    rt.appendChild(dlBtn);
  }

  setActiveInList();
  updateNavButtons();
  updateURL();
  markRead(state.novel, data.num);
  setLastPosition(state.novel, data.num);
  renderChapterList();  // refresh "read" state
  // Keep the active row visible in the sidebar
  if (state.list && state.index >= 0) {
    state.list.scrollToIndex(state.index, { align: 'center' });
  }

  // Browser tab title
  document.title = `ตอนที่ ${data.num} — ${data.title || ''}`.trim() + ` — ${state.novel}`;
}

function updateURL() {
  const url = new URL(window.location);
  url.searchParams.set('novel', state.novel);
  url.searchParams.set('ch', String(state.num));
  // Don't push/replace state — browser tool triggers page reload on URL change
  // which causes init() to re-run and lose the ch param.
}

function showError(msg) {
  const emptyState = $('empty-state');
  if (emptyState) {
    emptyState.hidden = false;
    emptyState.innerHTML = '';
    const p = document.createElement('p');
    p.textContent = msg;
    emptyState.appendChild(p);
  }
  const article = $('chapter');
  if (article) article.hidden = true;
}

// ── Loading ────────────────────────────────────────────────────────────

async function loadNovelBySlug(slug, chNum) {
  const novels = await api('/api/novels');
  const novel = novels.find((n) => n.slug === slug);
  if (!novel) {
    showError(`ไม่พบนิยาย: ${slug}`);
    return;
  }
  // Pass chNum as forceCh so loadNovel loads the right chapter (no double-load)
  await loadNovel(novel, chNum);
}

async function loadNovel(novel, forceCh) {
  state.novel = novel.slug;
  setNovelTitle(novel.slug, novel.meta);
  document.title = `${novel.slug} — NovelClaw`;

  const { chapters } = await api(`/api/novel/${encodeURIComponent(novel.slug)}/chapters`);
  state.chapters = chapters;
  renderChapterList();

  // Determine which chapter to load:
  // 1. forceCh (explicit override from URL or caller)
  // 2. ch param in current URL
  // 3. last read position
  // 4. first chapter
  const nums = chapters.map((c) => c.num);
  let startCh = null;
  if (forceCh != null && nums.includes(forceCh)) {
    startCh = forceCh;
  } else {
    const params = new URL(window.location).searchParams;
    const chParam = parseInt(params.get('ch'), 10);
    const lastPos = getLastPosition(novel.slug);
    startCh = nums.includes(chParam) ? chParam
              : nums.includes(lastPos) ? lastPos
              : nums[0];
  }
  if (startCh != null) await loadChapter(startCh);
  else showError('ยังไม่มีตอนที่แปลแล้วในเรื่องนี้');
}

// ── Search ──────────────────────────────────────────────────────────────
let searchDebounce = null;
let lastQuery = '';

document.getElementById('chapter-search').addEventListener('input', (e) => {
  const q = e.target.value.trim();
  if (q === lastQuery) return;
  lastQuery = q;
  clearTimeout(searchDebounce);
  if (!q) { renderChapterList(); return; }
  searchDebounce = setTimeout(() => runSearch(q), 200);
});

// Escape clears the search input and re-renders the full chapter list.
// Useful when reader hits Esc to dismiss search and see everything again.
document.getElementById('chapter-search').addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    e.target.value = '';
    lastQuery = '';
    clearTimeout(searchDebounce);
    renderChapterList();
    e.target.blur();
  }
});

async function runSearch(q) {
  try {
    // mode=all: title filter + FTS5 content search union, deduped, title first.
    // limit=30: more than enough for sidebar; virtual scroll handles overflow.
    const results = await api(
      `/api/novel/${encodeURIComponent(state.novel)}/chapters/search?` +
      `q=${encodeURIComponent(q)}&mode=all&limit=30`,
    );
    renderSearchResults(results, q);
  } catch (err) {
    // Search failure: just log to console (search is best-effort, the
    // chapter list itself still works). Surface as a soft warning so
    // a misconfigured server doesn't silently break search.
    console.warn('Search failed:', err);
    const list = document.getElementById('chapter-list');
    if (list) list.appendChild(el('li', { class: 'empty' }, `ค้นหาไม่สำเร็จ: ${err.message || 'เชื่อมต่อล้มเหลว'}`));
  }
}

function renderSearchResults(results, q) {
  const list = document.getElementById('chapter-list');
  // Destroy virtual scroll instance while search is active
  if (state.list) { state.list.setItems([]); state.list = null; }
  list.innerHTML = '';
  if (results.length === 0) {
    list.appendChild(el('div', { class: 'empty' }, `ไม่พบ "${q}"`));
    document.getElementById('chapter-count').textContent = `0 / ${state.chapters.length}`;
    return;
  }
  for (const c of results) {
    const snippetText = c.snippet ? stripSnippetMarkers(c.snippet) : null;
    const rowChildren = [
      el('span', { class: 'chapter-num' }, String(c.num).padStart(4, '0')),
      el('div', { class: 'chapter-text-col' },
        el('span', { class: 'chapter-label-text' }, c.title || `ตอนที่ ${c.num}`),
        snippetText ? el('span', { class: 'chapter-snippet' }, snippetText) : null,
      ),
    ];
    const a = el('a', {
      href: `?novel=${state.novel}&ch=${c.num}`,
      class: `search-row ${c.num === state.num ? 'active' : ''} ${c.source === 'content' ? 'from-content' : 'from-title'}`,
      'data-num': String(c.num),
      'role': 'listitem',
      'aria-current': c.num === state.num ? 'page' : null,
      title: c.title,
      onclick: (e) => { e.preventDefault(); loadChapter(c.num); },
    }, ...rowChildren);
    list.appendChild(a);
  }
  document.getElementById('chapter-count').textContent = `${results.length} / ${state.chapters.length}`;
}

// FTS5 wraps the matched substring in <<...>>. Strip them for display
// but keep the substring so the user can see what was matched.
function stripSnippetMarkers(snippet) {
  return snippet
    .replace(/<</g, '')
    .replace(/>>/g, '')
    .replace(/\n+/g, ' ')
    .trim();
}

async function loadChapter(num) {
  state.num = num;
  state.index = findIndexByNum(num);
  localDB.addHistory(state.novel, num);
  // Close mobile sidebar on chapter click
  if (window.innerWidth <= 768) {
    const sidebar = $('sidebar');
    if (sidebar) sidebar.classList.remove('open');
    document.body.classList.remove('sidebar-open');
  }
  const chapterTitle = $('chapter-title');
  if (chapterTitle) chapterTitle.textContent = 'กำลังโหลด...';
  const chapterContent = $('chapter-content');
  if (chapterContent) {
    chapterContent.innerHTML = '<p class="loading-placeholder" style="text-align:center;padding:2em;color:var(--text-muted);">กำลังโหลด...</p>';
  }
  try {
    const data = await api(`/api/novel/${encodeURIComponent(state.novel)}/chapter/${num}`);
    showChapter(data);
    // Scroll to top so user sees chapter title and meta on chapter switch
    window.scrollTo({ top: 0, behavior: 'auto' });
  } catch (err) {
      // Translate HTTP errors into Thai so the reader sees a friendly
      // message instead of "404 Not Found" or "Failed to fetch".
      // api() throws new Error("STATUS STATUS_TEXT") — parse status from message.
      let msg;
      const statusMatch = err && err.message && err.message.match(/^(\d{3})\s/);
      const httpStatus = statusMatch ? parseInt(statusMatch[1], 10) : null;
      if (httpStatus === 404) {
          msg = 'ยังไม่มีตอนนี้ในระบบ';
      } else if (httpStatus && httpStatus >= 500) {
          msg = 'เซิร์ฟเวอร์มีปัญหา ลองใหม่อีกครั้ง';
      } else if (err && err.message) {
          msg = 'เชื่อมต่อล้มเหลว';
      } else {
          msg = 'เกิดข้อผิดพลาด';
      }
      const chapterContent = document.getElementById('chapter-content');
      const friendly = `โหลดตอนที่ ${num} ไม่สำเร็จ — ${msg}`;
      if (chapterContent) chapterContent.innerHTML = `<p style="text-align:center;padding:2em;color:var(--text-muted);">${friendly}</p>`;
  }
}

// ── Nav ────────────────────────────────────────────────────────────────

let _stepLock = 0;
function step(delta) {
  // Debounce: ignore rapid successive calls (< 200ms apart)
  const now = Date.now();
  if (now - _stepLock < 200) return;
  _stepLock = now;
  const next = state.index + delta;
  if (next < 0 || next >= state.chapters.length) return;
  loadChapter(state.chapters[next].num);
}

// ── Theme ──────────────────────────────────────────────────────────────

function getTheme() { return document.body.dataset.theme || 'light'; }
function setTheme(theme) {
  document.body.dataset.theme = theme;
  for (const id of ['theme-toggle', 'reader-theme-toggle']) {
    const el = $(id);
    if (el) el.textContent = THEME_ICONS[theme] || '🌙';
  }
  const s = loadState(); s.theme = theme; saveState(s);
}
function cycleTheme() {
  const cur = getTheme();
  setTheme(THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
}

// ── Wiring ────────────────────────────────────────────────────────────

document.getElementById('toggle-sidebar').addEventListener('click', () => {
  const sidebar = document.getElementById('sidebar');
  const toggleBtn = document.getElementById('toggle-sidebar');
  const isMobile = window.innerWidth <= 768;
  if (isMobile) {
    const opening = !sidebar.classList.contains('open');
    sidebar.classList.toggle('open');
    document.body.classList.toggle('sidebar-open', opening);
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', String(opening));
  } else {
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', String(!isCollapsed));
  }
});
for (const id of ['prev-chapter', 'prev-chapter-2']) {
  document.getElementById(id).addEventListener('click', () => step(-1));
}
for (const id of ['next-chapter', 'next-chapter-2']) {
  document.getElementById(id).addEventListener('click', () => step(+1));
}
document.getElementById('back-to-top').addEventListener('click', () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

let fontStep = 0;
document.getElementById('font-smaller').addEventListener('click', () => {
  fontStep = Math.max(-2, fontStep - 1); applyFontSize();
});
document.getElementById('font-larger').addEventListener('click', () => {
  fontStep = Math.min(3, fontStep + 1); applyFontSize();
});
function applyFontSize() {
  document.documentElement.style.setProperty('--font-size', `${17 + fontStep * 2}px`);
}

// Backdrop click closes sidebar on mobile
document.body.addEventListener('click', (e) => {
  if (window.innerWidth > 768) return;
  const sidebar = document.getElementById('sidebar');
  if (!sidebar.classList.contains('open')) return;
  // Close if click target is outside the sidebar
  if (sidebar.contains(e.target)) return;
  sidebar.classList.remove('open');
  document.getElementById('sidebar-overlay').style.display = 'none';
});

// Sidebar close button removed — hamburger toggle handles open/close.
// Click-outside and Escape key still close mobile sidebar (below).

for (const id of ['theme-toggle', 'reader-theme-toggle']) {
  const el = document.getElementById(id);
  if (el) el.addEventListener('click', cycleTheme);
}

document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea')) return;
  // Escape closes mobile sidebar
  if (e.key === 'Escape' && window.innerWidth <= 768) {
    const sidebar = document.getElementById('sidebar');
    if (sidebar.classList.contains('open')) {
      sidebar.classList.remove('open');
      document.body.classList.remove('sidebar-open');
    }
  }
  if (e.key === 'ArrowLeft') step(-1);
  if (e.key === 'ArrowRight') step(+1);
  if (e.key === 't' || e.key === 'T') cycleTheme();
  if (e.key === 's' || e.key === 'S') {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar');
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      const opening = !sidebar.classList.contains('open');
      sidebar.classList.toggle('open');
      document.body.classList.toggle('sidebar-open', opening);
      const overlay = document.getElementById('sidebar-overlay');
      if (overlay) overlay.style.display = opening ? 'block' : 'none';
      if (toggleBtn) toggleBtn.setAttribute('aria-expanded', String(opening));
    } else {
      sidebar.classList.toggle('collapsed');
      const isCollapsed = sidebar.classList.contains('collapsed');
      if (toggleBtn) toggleBtn.setAttribute('aria-expanded', String(!isCollapsed));
    }
  }
  if (e.key === 'Home') window.scrollTo({ top: 0, behavior: 'smooth' });
  if (e.key === 'End') window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
});

// ── Dashboard ───────────────────────────────────────────────────────────

// Derive a stable hue from a slug string for cover gradient backgrounds.
function slugToHue(slug) {
  return slug.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
}

async function showDashboard() {
  const dashboard = document.getElementById('dashboard');
  const readerLayout = document.getElementById('reader-layout');
  const novelSelector = document.getElementById('novel-selector');
  const novelTitle = document.getElementById('novel-title');

  dashboard.classList.add('visible');
  readerLayout.hidden = true;
  novelSelector.hidden = true;
  if (novelTitle) novelTitle.textContent = 'NovelClaw';
  document.body.classList.add('dashboard-mode');
  document.body.classList.remove('reader-mode');

  // Activate menu item
  document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
  const menuHome = document.getElementById('menu-home');
  if (menuHome) menuHome.classList.add('active');

  try {
    const novels = await api('/api/novels');
    const featuredNovel = novels[0] || null;

    // Compute progress for each novel
    const enriched = novels.map(n => {
      const lastRead = getLastPosition(n.slug);
      const readCount = n.chapterCount || 0;
      const totalCount = n.totalChapters || readCount;
      const progressPct = totalCount > 0 ? Math.round((readCount / totalCount) * 100) : 0;
      const hue = slugToHue(n.slug);
      return { ...n, lastRead, readCount, totalCount, progressPct, hue };
    });

    // ── 1. Hero Banner ──────────────────────────────────────────────────
    if (featuredNovel) {
      const fn = enriched[0];
      const heroTitle = $('hero-title');
      const heroSubtitle = $('hero-subtitle');
      const heroLangTag = $('hero-lang-tag');
      const heroStatusTag = $('hero-status-tag');
      const heroProgressText = $('hero-progress-text');
      const heroProgressPercent = $('hero-progress-percent');
      const heroProgressFill = $('hero-progress-fill');
      const heroCta = $('hero-cta');
      const heroLastReadCh = $('hero-last-read-ch');

      if (heroTitle) heroTitle.textContent = fn.title || fn.slug;
      if (heroSubtitle) heroSubtitle.textContent = fn.slug;
      if (heroLangTag) heroLangTag.textContent = `${fn.source_lang || 'cn'} → ${fn.target_lang || 'th'}`;
      
      const statusMap = { ongoing: 'กำลังแปล', complete: 'จบ', in_progress: 'กำลังแปล' };
      if (heroStatusTag) heroStatusTag.textContent = statusMap[fn.status] || 'ไม่ระบุ';
      if (heroProgressText) heroProgressText.textContent = `ตอนที่ ${fn.readCount} / ${fn.totalCount}`;
      if (heroProgressPercent) heroProgressPercent.textContent = `${fn.progressPct}%`;
      if (heroProgressFill) heroProgressFill.style.width = `${fn.progressPct}%`;

      if (heroCta) {
        heroCta.href = `?novel=${fn.slug}`;
        heroCta.onclick = (e) => { e.preventDefault(); openNovel(fn); };
      }
      if (heroLastReadCh) {
        heroLastReadCh.textContent = fn.lastRead ? `ตอนที่ ${fn.lastRead}` : 'ตอนที่ —';
      }
    }

    // ── 2. "อ่านต่อ" (Continue Reading) Section ────────────────────────
    const continueGrid = $('continue-grid');
    if (continueGrid) {
      continueGrid.innerHTML = '';
      for (const n of enriched) {
        const card = el('a', {
          href: `?novel=${n.slug}`,
          class: 'continue-card',
          onclick: (e) => { e.preventDefault(); openNovel(n); }
        },
          el('div', {
            class: 'continue-cover',
            style: `background: linear-gradient(135deg, hsl(${n.hue}, 70%, 40%) 0%, hsl(${(n.hue + 40) % 360}, 60%, 30%) 100%);`
          }, (n.title || n.slug).charAt(0)),
          el('div', { class: 'continue-info' },
            el('span', { class: 'continue-title' }, n.title || n.slug),
            el('span', { class: 'continue-ch' }, n.lastRead ? `ตอนที่ ${n.lastRead} / ${n.totalCount}` : `ตอนที่ — / ${n.totalCount}`),
            el('div', { class: 'continue-progress' },
              el('div', { class: 'continue-progress-bar' },
                el('div', { class: 'continue-progress-fill', style: `width: ${n.progressPct}%` })
              ),
              el('span', { class: 'continue-progress-pct' }, `${n.progressPct}%`)
            )
          )
        );
        continueGrid.appendChild(card);
      }
      // "+ เพิ่มนิยาย" card
      const addCard = el('a', {
        href: '#',
        class: 'continue-card add-novel-card',
        onclick: (e) => { e.preventDefault(); showView('view-admin'); }
      },
        el('div', {
          class: 'continue-cover',
          style: 'background: var(--glass-bg); border: 2px dashed var(--border); display:flex; align-items:center; justify-content:center; font-size:2rem; color:var(--text-soft);'
        }, '+'),
        el('div', { class: 'continue-info' },
          el('span', { class: 'continue-title', style: 'color:var(--text-soft);' }, 'เพิ่มนิยายใหม่'),
          el('span', { class: 'continue-ch' }, 'เพิ่มเรื่องที่ต้องการแปล')
        )
      );
      continueGrid.appendChild(addCard);
    }

    // ── 3. "อัปเดตล่าสุด" (Latest Updates) Section ───────────────────────
    const updatesRow = $('updates-row');
    if (updatesRow) {
      updatesRow.innerHTML = '';
      for (const n of enriched) {
        const card = el('a', {
          href: `?novel=${n.slug}`,
          class: 'update-card',
          onclick: (e) => { e.preventDefault(); openNovel(n); }
        },
          el('div', { class: 'update-cover-wrapper' },
            el('span', { class: 'new-badge' }, 'NEW'),
            el('div', {
              class: 'update-cover',
              style: `background: linear-gradient(135deg, hsl(${n.hue}, 70%, 40%) 0%, hsl(${(n.hue + 40) % 360}, 60%, 30%) 100%);`
            }, (n.title || n.slug).charAt(0))
          ),
          el('span', { class: 'update-title' }, n.title || n.slug),
          el('span', { class: 'update-ch' }, `ตอนที่ ${n.readCount}`)
        );
        updatesRow.appendChild(card);
      }
    }

    // ── 4. "ยอดนิยมประจำสัปดาห์" (Weekly Popular) Section ──────────────────
    const popularList = $('popular-list');
    if (popularList) {
      popularList.innerHTML = '';
      let rank = 1;
      for (const n of enriched) {
        const badgeColor = rank === 1 ? '#f59e0b' : rank === 2 ? '#94a3b8' : rank === 3 ? '#b45309' : 'var(--text-soft)';
        const item = el('a', {
          href: `?novel=${n.slug}`,
          class: 'popular-item',
          onclick: (e) => { e.preventDefault(); openNovel(n); }
        },
          el('span', { class: 'rank-badge', style: `color: ${badgeColor};` }, String(rank++)),
          el('div', {
            class: 'popular-cover',
            style: `background: linear-gradient(135deg, hsl(${n.hue}, 70%, 40%) 0%, hsl(${(n.hue + 40) % 360}, 60%, 30%) 100%);`
          }, (n.title || n.slug).charAt(0)),
          el('div', { class: 'popular-info' },
            el('span', { class: 'popular-title' }, n.title || n.slug),
            el('span', { class: 'popular-meta' }, `${n.source_lang || 'cn'} → ${n.target_lang || 'th'} • โดย ${n.author || 'Mika'}`),
            el('span', { class: 'popular-views' }, `👁 ${n.readCount}+ ตอน`)
          )
        );
        popularList.appendChild(item);
      }
    }

  } catch (err) {
    console.error('showDashboard failed:', err);
  }
}

async function openNovel(novel) {
  const readerLayout = document.getElementById('reader-layout');
  const novelSelector = document.getElementById('novel-selector');
  const novelSelect = document.getElementById('novel-select');

  showView('reader-layout');
  if (novelSelector) novelSelector.hidden = false;

  // Populate selector
  const novels = await api('/api/novels');
  if (novelSelect) {
    novelSelect.innerHTML = '';
    for (const n of novels) {
      const opt = document.createElement('option');
      opt.value = n.slug;
      opt.textContent = n.title || n.slug;
      if (n.slug === novel.slug) opt.selected = true;
      novelSelect.appendChild(opt);
    }
  }

  await loadNovel(novel);
}

// ── localDB Persistent Storage Helper (Ponytail Style) ──────────────────
const localDB = {
  get(key, fallback = []) {
    try {
      return JSON.parse(localStorage.getItem(`nc-${key}`)) || fallback;
    } catch {
      return fallback;
    }
  },
  set(key, val) {
    try {
      localStorage.setItem(`nc-${key}`, JSON.stringify(val));
    } catch (err) {
      console.error('localDB.set failed:', err);
    }
  },
  addBookmark(novelSlug, chNum) {
    const list = this.get('bookmarks');
    if (!list.some(b => b.novel === novelSlug && b.num === chNum)) {
      list.push({ novel: novelSlug, num: chNum, ts: Date.now() });
      this.set('bookmarks', list);
    }
  },
  removeBookmark(novelSlug, chNum) {
    const list = this.get('bookmarks').filter(b => !(b.novel === novelSlug && b.num === chNum));
    this.set('bookmarks', list);
  },
  isBookmarked(novelSlug, chNum) {
    return this.get('bookmarks').some(b => b.novel === novelSlug && b.num === chNum);
  },
  addHistory(novelSlug, chNum) {
    const list = this.get('history').filter(h => !(h.novel === novelSlug && h.num === chNum));
    list.unshift({ novel: novelSlug, num: chNum, ts: Date.now() });
    this.set('history', list.slice(0, 100));
    
    const stats = this.get('stats', { totalMin: 0, chapters: 0, daily: [0, 0, 0, 0, 0, 0, 0] });
    stats.chapters += 1;
    stats.totalMin += 15;
    const day = new Date().getDay();
    stats.daily[day] = (stats.daily[day] || 0) + 15;
    this.set('stats', stats);
  },
  addDownload(novelSlug, chNum, title) {
    const list = this.get('downloads');
    if (!list.some(d => d.novel === novelSlug && d.num === chNum)) {
      list.push({ novel: novelSlug, num: chNum, title, ts: Date.now() });
      this.set('downloads', list);
    }
  },
  removeDownload(novelSlug, chNum) {
    const list = this.get('downloads').filter(d => !(d.novel === novelSlug && d.num === chNum));
    this.set('downloads', list);
  },
  isDownloaded(novelSlug, chNum) {
    return this.get('downloads').some(d => d.novel === novelSlug && d.num === chNum);
  }
};

// ── Client-Side Views Router ───────────────────────────────────────────
function showView(viewId, params = {}) {
  const views = [
    'dashboard', 'reader-layout', 'view-library', 'view-search', 'view-rankings',
    'view-history', 'view-bookmarks', 'view-downloads', 'view-analytics', 'view-settings',
    'view-notifications', 'view-novel-detail', 'view-admin-dashboard', 'view-admin-novels',
    'view-admin-novel-edit', 'view-admin-chapters', 'view-admin-translation-center', 'view-admin-users',
    'view-admin-glossary'
  ];
  views.forEach(v => {
    const el = document.getElementById(v);
    if (el) {
      el.hidden = true;
      el.classList.remove('visible');
    }
  });

  document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));

  if (viewId === 'reader-layout') {
    document.body.classList.add('reader-mode');
    document.body.classList.remove('dashboard-mode');
  } else {
    document.body.classList.add('dashboard-mode');
    document.body.classList.remove('reader-mode');
  }

  const viewEl = document.getElementById(viewId);
  if (viewEl) {
    viewEl.hidden = false;
    viewEl.classList.add('visible');
    viewEl.scrollTo(0, 0);
  }

  const menuMap = {
    'dashboard': 'menu-home',
    'view-library': 'menu-library',
    'view-search': 'menu-recommend',
    'view-rankings': 'menu-rankings',
    'view-history': 'menu-history',
    'view-bookmarks': 'menu-bookmarks',
    'view-downloads': 'menu-downloads',
    'view-analytics': 'menu-analytics',
    'view-admin-dashboard': 'menu-admin',
    'view-admin-novels': 'menu-admin',
    'view-admin-novel-edit': 'menu-admin',
    'view-admin-chapters': 'menu-admin',
    'view-admin-translation-center': 'menu-admin',
    'view-admin-users': 'menu-admin',
    'view-admin-glossary': 'menu-admin'
  };
  const activeMenuId = menuMap[viewId];
  if (activeMenuId) {
    const menuEl = document.getElementById(activeMenuId);
    if (menuEl) menuEl.classList.add('active');
  }

  // Trigger render functions
  if (viewId === 'dashboard') showDashboard();
  else if (viewId === 'view-library') renderLibrary();
  else if (viewId === 'view-search') renderSearch(params.genre || 'all');
  else if (viewId === 'view-rankings') renderRankings();
  else if (viewId === 'view-history') renderHistory();
  else if (viewId === 'view-bookmarks') renderBookmarks();
  else if (viewId === 'view-downloads') renderDownloads();
  else if (viewId === 'view-analytics') renderAnalytics();
  else if (viewId === 'view-settings') renderSettings();
  else if (viewId === 'view-notifications') renderNotifications();
  else if (viewId === 'view-novel-detail') renderNovelDetail(params.slug);
  else if (viewId === 'view-admin-dashboard') renderAdminDashboard();
  else if (viewId === 'view-admin-novels') renderAdminNovels();
  else if (viewId === 'view-admin-chapters') renderAdminChapters(params.slug);
  else if (viewId === 'view-admin-translation-center') renderAdminTranslationCenter(params.slug, params.num);
  else if (viewId === 'view-admin-users') renderAdminUsers();
  else if (viewId === 'view-admin-glossary') renderAdminGlossary(params.slug || 'global-descent');
}
window.showView = showView;

// ── Views Rendering Logics (Ponytail style) ─────────────────────────────

async function renderLibrary() {
  const grid = document.getElementById('library-grid');
  if (!grid) return;
  grid.innerHTML = '<p class="loading-placeholder">กำลังโหลดหอสมุด...</p>';
  try {
    const novels = await api('/api/novels');
    const bookmarkedSlugs = localDB.get('bookmarks').map(b => b.novel);
    const libraryNovels = novels.filter(n => bookmarkedSlugs.includes(n.slug) || getLastPosition(n.slug) !== null);
    
    grid.innerHTML = '';
    if (libraryNovels.length === 0) {
      grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-soft); padding: 32px;">หอสมุดของคุณว่างเปล่า เริ่มบันทึกและอ่านนิยายเลยค่ะ! 📚</p>';
      return;
    }
    
    for (const n of libraryNovels) {
      const hash = n.slug.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
      const hue = hash % 360;
      const progress = getLastPosition(n.slug);
      
      const card = el('a', {
        href: `#novel-${n.slug}`,
        class: 'continue-card',
        onclick: (e) => {
          e.preventDefault();
          showView('view-novel-detail', { slug: n.slug });
        }
      },
        el('div', {
          class: 'continue-cover',
          style: `background: linear-gradient(135deg, hsl(${hue}, 70%, 40%) 0%, hsl(${(hue + 40) % 360}, 60%, 30%) 100%);`
        }, n.title.charAt(0)),
        el('div', { class: 'continue-info' },
          el('span', { class: 'continue-title' }, n.title),
          el('span', { class: 'continue-ch' }, progress ? `ตอนล่าสุดที่อ่าน: ตอนที่ ${progress}` : 'ยังไม่ได้เริ่มอ่าน'),
          el('span', { style: 'font-size:0.7rem; color:var(--accent); font-weight:600; margin-top:4px;' }, `ทั้งหมด ${n.chapterCount} ตอน`)
        )
      );
      grid.appendChild(card);
    }
  } catch (err) {
    grid.innerHTML = `<p class="error">โหลดไม่สำเร็จ: ${err.message}</p>`;
  }
}

let allNovelsCache = null;
async function renderSearch(genre = 'all') {
  const grid = document.getElementById('search-results-grid');
  const searchInput = document.getElementById('search-input-field');
  if (!grid || !searchInput) return;
  
  const tags = document.querySelectorAll('#category-tags .tag');
  tags.forEach(t => {
    t.classList.toggle('active', t.dataset.genre === genre);
  });

  try {
    if (!allNovelsCache) {
      allNovelsCache = await api('/api/novels');
    }

    const query = searchInput.value.trim().toLowerCase();
    
    const filtered = allNovelsCache.filter(n => {
      if (genre !== 'all') {
        const nGenre = n.genre || 'all';
        if (nGenre !== genre) return false;
      }
      if (query) {
        return (n.title || '').toLowerCase().includes(query) || n.slug.toLowerCase().includes(query) || (n.author && n.author.toLowerCase().includes(query));
      }
      return true;
    });

    grid.innerHTML = '';
    if (filtered.length === 0) {
      grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-soft); padding: 32px;">ไม่พบนิยายตามเงื่อนไขค้นหาค่ะ 🔍</p>';
      return;
    }

    for (const n of filtered) {
      const hue = slugToHue(n.slug);
      const card = el('a', {
        href: '#',
        class: 'continue-card',
        onclick: (e) => {
          e.preventDefault();
          showView('view-novel-detail', { slug: n.slug });
        }
      },
        el('div', {
          class: 'continue-cover',
          style: `background: linear-gradient(135deg, hsl(${hue}, 70%, 40%) 0%, hsl(${(hue + 40) % 360}, 60%, 30%) 100%);`
        }, (n.title || n.slug).charAt(0)),
        el('div', { class: 'continue-info' },
          el('span', { class: 'continue-title' }, n.title || n.slug),
          el('span', { class: 'continue-ch' }, `โดย: ${n.author || 'Mika'}`),
          el('span', { style: 'font-size:0.7rem; color:var(--text-muted);' }, `${(n.source_lang || 'cn').toUpperCase()} → ${(n.target_lang || 'th').toUpperCase()} • ${n.chapterCount || 0} ตอน`)
        )
      );
      grid.appendChild(card);
    }
  } catch (err) {
    grid.innerHTML = `<p class="error">โหลดไม่สำเร็จ: ${err.message}</p>`;
  }
}

async function renderRankings() {
  const list = document.getElementById('rankings-list-all');
  if (!list) return;
  list.innerHTML = '';
  try {
    const novels = await api('/api/novels');
    // Sort by chapter count (most translated = most popular)
    const sorted = [...novels].sort((a, b) => (b.chapterCount || 0) - (a.chapterCount || 0));

    let rank = 1;
    for (const n of sorted) {
      const hue = slugToHue(n.slug);
      const badgeColor = rank === 1 ? '#f59e0b' : rank === 2 ? '#94a3b8' : rank === 3 ? '#b45309' : 'var(--text-soft)';
      
      const item = el('a', {
        href: '#',
        class: 'popular-item',
        onclick: (e) => {
          e.preventDefault();
          showView('view-novel-detail', { slug: n.slug });
        }
      },
        el('span', { class: 'rank-badge', style: `color: ${badgeColor};` }, String(rank++)),
        el('div', {
          class: 'popular-cover',
          style: `background: linear-gradient(135deg, hsl(${hue}, 70%, 40%) 0%, hsl(${(hue + 40) % 360}, 60%, 30%) 100%);`
        }, (n.title || n.slug).charAt(0)),
        el('div', { class: 'popular-info' },
          el('span', { class: 'popular-title' }, n.title || n.slug),
          el('span', { class: 'popular-meta' }, `${n.source_lang || 'cn'} → ${n.target_lang || 'th'} • โดย ${n.author || 'Mika'}`),
          el('span', { class: 'popular-views' }, `📖 ${n.chapterCount || 0} ตอน`)
        )
      );
      list.appendChild(item);
    }
  } catch (err) {
    list.innerHTML = `<p class="error">โหลดอันดับยอดนิยมไม่สำเร็จ: ${err.message}</p>`;
  }
}

function renderHistory() {
  const container = document.getElementById('history-list');
  if (!container) return;
  const list = localDB.get('history');
  container.innerHTML = '';
  if (list.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--text-soft); padding: 32px;">ไม่มีประวัติการอ่านตอนนิยายค่ะ ⏱</p>';
    return;
  }
  list.forEach(h => {
    const timeString = new Date(h.ts).toLocaleString('th-TH', { hour: '2-digit', minute:'2-digit', day: 'numeric', month: 'short' });
    const row = el('a', {
      href: `?novel=${h.novel}&ch=${h.num}`,
      class: 'list-item-row',
      onclick: (e) => {
        e.preventDefault();
        state.novel = h.novel;
        openNovel({ slug: h.novel }).then(() => loadChapter(h.num));
      }
    },
      el('div', { class: 'list-item-info' },
        el('span', { class: 'list-item-title' }, `เรื่อง ${h.novel} — ตอนที่ ${h.num}`),
        el('span', { class: 'list-item-meta' }, `อ่านเมื่อ: ${timeString}`)
      ),
      el('span', { style: 'color: var(--accent); font-weight:600;' }, 'อ่านต่อ →')
    );
    container.appendChild(row);
  });
}

function renderBookmarks() {
  const container = document.getElementById('bookmarks-list');
  if (!container) return;
  const list = localDB.get('bookmarks');
  container.innerHTML = '';
  if (list.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--text-soft); padding: 32px;">ไม่มีตอนนิยายที่บุ๊กมาร์กไว้ค่ะ 🔖</p>';
    return;
  }
  list.forEach(b => {
    const row = el('div', {
      class: 'list-item-row',
      style: 'cursor: default;'
    },
      el('div', { class: 'list-item-info' },
        el('a', {
          href: `?novel=${b.novel}&ch=${b.num}`,
          class: 'list-item-title',
          onclick: (e) => {
            e.preventDefault();
            state.novel = b.novel;
            openNovel({ slug: b.novel }).then(() => loadChapter(b.num));
          }
        }, `เรื่อง ${b.novel} — ตอนที่ ${b.num}`),
        el('span', { class: 'list-item-meta' }, `บุ๊กมาร์กเมื่อ: ${new Date(b.ts).toLocaleDateString('th-TH')}`)
      ),
      el('button', {
        class: 'list-item-action-btn',
        onclick: () => {
          localDB.removeBookmark(b.novel, b.num);
          renderBookmarks();
        }
      }, 'ลบออก')
    );
    container.appendChild(row);
  });
}

function renderDownloads() {
  const container = document.getElementById('downloads-list');
  if (!container) return;
  const list = localDB.get('downloads');
  container.innerHTML = '';
  if (list.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--text-soft); padding: 32px;">ไม่มีไฟล์ดาวน์โหลดนิยายออฟไลน์ค่ะ 📥</p>';
    return;
  }
  list.forEach(d => {
    const row = el('div', {
      class: 'list-item-row',
      style: 'cursor: default;'
    },
      el('div', { class: 'list-item-info' },
        el('a', {
          href: `?novel=${d.novel}&ch=${d.num}`,
          class: 'list-item-title',
          onclick: (e) => {
            e.preventDefault();
            state.novel = d.novel;
            openNovel({ slug: d.novel }).then(() => loadChapter(d.num));
          }
        }, `เรื่อง ${d.novel} — ตอนที่ ${d.num} (${d.title})`),
        el('span', { class: 'list-item-meta' }, `ดาวน์โหลดเมื่อ: ${new Date(d.ts).toLocaleDateString('th-TH')} • ขนาด 12 KB (ออฟไลน์)`)
      ),
      el('button', {
        class: 'list-item-action-btn',
        onclick: () => {
          localDB.removeDownload(d.novel, d.num);
          renderDownloads();
        }
      }, 'ลบออก')
    );
    container.appendChild(row);
  });
}

function renderNotifications() {
  const container = document.getElementById('notifications-list');
  if (!container) return;
  
  let list = localDB.get('notifications');
  if (list.length === 0) {
    list = [
      { id: 1, title: 'อัปเดตนิยายตอนใหม่!', desc: 'Global Descent ตอนที่ 79 ได้รับการแปลภาษาไทยแล้ว อ่านเลย!', ts: Date.now() - 3600000 },
      { id: 2, title: 'ต้อนรับ P Choke เข้าสู่ระบบหลังบ้าน 🛡️', desc: 'ระบบแอดมินจำลองและระบบจัดการไฟล์บทเรียนเปิดให้ใช้งานเรียบร้อยค่ะพี่โชค', ts: Date.now() - 86400000 }
    ];
    localDB.set('notifications', list);
  }
  
  container.innerHTML = '';
  list.forEach(n => {
    const row = el('div', {
      class: 'list-item-row',
      style: 'cursor: default;'
    },
      el('div', { class: 'list-item-info' },
        el('span', { class: 'list-item-title' }, n.title),
        el('span', { class: 'list-item-meta' }, n.desc)
      ),
      el('button', {
        class: 'list-item-action-btn',
        style: 'background: rgba(255,255,255,0.06); color: var(--text-secondary);',
        onclick: () => {
          const updated = localDB.get('notifications').filter(item => item.id !== n.id);
          localDB.set('notifications', updated);
          renderNotifications();
        }
      }, 'ลบ')
    );
    container.appendChild(row);
  });
}

function renderAnalytics() {
  const stats = localDB.get('stats', { totalMin: 0, chapters: 0, daily: [0, 0, 0, 0, 0, 0, 0] });
  
  const readingTimeEl = document.getElementById('stat-reading-time');
  const chaptersCountEl = document.getElementById('stat-chapters-count');
  if (readingTimeEl) readingTimeEl.textContent = stats.totalMin;
  if (chaptersCountEl) chaptersCountEl.textContent = stats.chapters;

  const chart = document.getElementById('daily-reading-chart');
  if (!chart) return;
  chart.innerHTML = '';
  
  const days = ['อา.', 'จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.'];
  const maxMins = Math.max(60, ...stats.daily);
  
  days.forEach((day, idx) => {
    const mins = stats.daily[idx] || 0;
    const pct = Math.round((mins / maxMins) * 100);
    
    const barWrap = el('div', { class: 'chart-bar-wrap' },
      el('div', {
        class: 'chart-bar',
        style: `height: ${pct}%`,
        title: `${mins} นาที`
      }),
      el('span', { class: 'chart-label' }, day)
    );
    chart.appendChild(barWrap);
  });
}

function renderSettings() {
  const themeSelect = document.getElementById('settings-theme-select');
  const langSelect = document.getElementById('settings-lang-select');
  
  if (themeSelect) {
    themeSelect.value = getTheme();
    themeSelect.onchange = (e) => {
      setTheme(e.target.value);
    };
  }
  
  if (langSelect) {
    langSelect.value = localDB.get('settings-lang', 'th');
    langSelect.onchange = (e) => {
      localDB.set('settings-lang', e.target.value);
    };
  }
}

async function renderNovelDetail(slug) {
  const detailTitle = document.getElementById('detail-title');
  const detailAuthor = document.getElementById('detail-author');
  const detailLang = document.getElementById('detail-lang');
  const detailStatus = document.getElementById('detail-status');
  const detailSynopsis = document.getElementById('detail-synopsis');
  const startBtn = document.getElementById('detail-start-btn');
  const chaptersGrid = document.getElementById('detail-chapters-grid');
  const coverDiv = document.getElementById('detail-cover');

  if (!chaptersGrid) return;
  chaptersGrid.innerHTML = '<p class="loading-placeholder">กำลังโหลดตอน...</p>';

  try {
    const novels = await api('/api/novels');
    const novel = novels.find(n => n.slug === slug);
    if (!novel) {
      chaptersGrid.innerHTML = `<p class="error">ไม่พบข้อมูลนิยายเรื่อง: ${slug}</p>`;
      return;
    }

    if (detailTitle) detailTitle.textContent = novel.title;
    if (detailAuthor) detailAuthor.textContent = `ผู้แต่ง: ${novel.author || 'Mika'}`;
    if (detailLang) detailLang.textContent = `${novel.source_lang.toUpperCase()} → ${novel.target_lang.toUpperCase()}`;
    
    const statusMap = { ongoing: 'กำลังแปล', complete: 'จบแล้ว', in_progress: 'กำลังแปล' };
    if (detailStatus) detailStatus.textContent = statusMap[novel.status] || 'ไม่ระบุ';
    
    let synopsisText = 'ยังไม่มีบทแนะนำเรื่องย่อในระบบค่ะ';
    if (novel.meta) {
      const match = novel.meta.match(/\*\*Synopsis\*\*:\s*([\s\S]*)/i);
      if (match) synopsisText = match[1].trim();
    }
    if (detailSynopsis) detailSynopsis.textContent = synopsisText;
    
    if (coverDiv) {
      coverDiv.innerHTML = '';
      if (novel.slug === 'global-descent') {
        coverDiv.appendChild(el('img', {
          src: '/covers/global-descent.png',
          alt: novel.title,
          class: 'detail-cover-img'
        }));
      } else {
        const hash = novel.slug.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
        coverDiv.style.background = `linear-gradient(135deg, hsl(${hash % 360}, 70%, 40%) 0%, hsl(${(hash % 360 + 40) % 360}, 60%, 30%) 100%)`;
        coverDiv.textContent = novel.title.charAt(0);
      }
    }

    const { chapters } = await api(`/api/novel/${encodeURIComponent(slug)}/chapters`);
    chaptersGrid.innerHTML = '';
    
    if (chapters.length === 0) {
      chaptersGrid.innerHTML = '<p style="grid-column:1/-1; text-align:center; color:var(--text-soft);">ยังไม่มีตอนแปลพร้อมอ่านในเรื่องนี้ค่ะ 📚</p>';
      if (startBtn) startBtn.style.display = 'none';
      return;
    }
    
    if (startBtn) {
      startBtn.style.display = 'block';
      startBtn.onclick = () => {
        state.novel = novel.slug;
        openNovel(novel).then(() => loadChapter(chapters[0].num));
      };
    }

    chapters.forEach(ch => {
      const read = isRead(slug, ch.num);
      const btn = el('button', {
        class: `detail-ch-btn ${read ? 'read' : ''}`,
        style: read ? 'border-color: var(--border-strong); opacity: 0.7;' : '',
        onclick: () => {
          state.novel = novel.slug;
          openNovel(novel).then(() => loadChapter(ch.num));
        }
      }, `ตอนที่ ${ch.num}`);
      chaptersGrid.appendChild(btn);
    });
  } catch (err) {
    chaptersGrid.innerHTML = `<p class="error">โหลดหน้าเนื้อหารายละเอียดไม่สำเร็จ: ${err.message}</p>`;
  }
}

// ── Admin Controllers ──────────────────────────────────────────────────

async function renderAdminDashboard() {
  try {
    const novels = await api('/api/novels');
    const novelCountEl = document.getElementById('admin-total-novels');
    if (novelCountEl) novelCountEl.textContent = novels.length;
    
    const chart = document.getElementById('admin-transactions-chart');
    if (chart) {
      chart.innerHTML = '';
      const months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.'];
      const values = [5400, 7200, 8900, 10200, 11500, 12450];
      const maxVal = 15000;
      months.forEach((m, idx) => {
        const val = values[idx];
        const pct = Math.round((val / maxVal) * 100);
        const barWrap = el('div', { class: 'chart-bar-wrap' },
          el('div', {
            class: 'chart-bar',
            style: `height: ${pct}%; background: linear-gradient(to top, rgba(59, 130, 246, 0.4) 0%, var(--accent-2) 100%);`,
            title: `₿ ${val}`
          }),
          el('span', { class: 'chart-label' }, m)
        );
        chart.appendChild(barWrap);
      });
    }
  } catch (err) {
    console.error('renderAdminDashboard failed:', err);
  }
}

async function renderAdminNovels() {
  const tbody = document.getElementById('admin-novels-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">กำลังโหลดนิยาย...</td></tr>';
  try {
    const novels = await api('/api/novels');
    tbody.innerHTML = '';
    novels.forEach(n => {
      const row = el('tr', {},
        el('td', { style: 'font-weight:600; font-family:var(--font-mono);' }, n.slug),
        el('td', {}, n.title),
        el('td', {}, `${n.source_lang.toUpperCase()} → ${n.target_lang.toUpperCase()}`),
        el('td', { style: 'font-family:var(--font-mono);' }, String(n.chapterCount)),
        el('td', {}, el('span', { class: `admin-badge ${n.status}` }, n.status === 'ongoing' ? 'แปลต่อ' : 'จบแล้ว')),
        el('td', {},
          el('div', { class: 'admin-action-row' },
            el('button', {
              class: 'admin-btn edit',
              onclick: () => editNovelMeta(n)
            }, 'ตั้งค่าเรื่อง'),
            el('button', {
              class: 'admin-btn edit',
              style: 'background:var(--accent-soft); color:var(--accent);',
              onclick: () => showView('view-admin-chapters', { slug: n.slug })
            }, 'จัดการตอน'),
            el('button', {
              class: 'admin-btn delete',
              onclick: () => deleteNovel(n.slug)
            }, 'ลบ')
          )
        )
      );
      tbody.appendChild(row);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="error" style="text-align:center;">โหลดไม่สำเร็จ: ${err.message}</td></tr>`;
  }
}

function editNovelMeta(novel = null) {
  const titleTitle = document.getElementById('admin-novel-edit-title');
  const formOldSlug = document.getElementById('admin-form-old-slug');
  const formSlug = document.getElementById('admin-form-slug');
  const formTitle = document.getElementById('admin-form-title');
  const formAuthor = document.getElementById('admin-form-author');
  const formSrcLang = document.getElementById('admin-form-src-lang');
  const formTgtLang = document.getElementById('admin-form-tgt-lang');
  const formStatus = document.getElementById('admin-form-status');
  const formTotalChapters = document.getElementById('admin-form-total-chapters');

  if (novel) {
    if (titleTitle) titleTitle.textContent = `แก้ไขข้อมูลนิยาย: ${novel.slug}`;
    if (formOldSlug) formOldSlug.value = novel.slug;
    if (formSlug) { formSlug.value = novel.slug; formSlug.disabled = true; }
    if (formTitle) formTitle.value = novel.title;
    if (formAuthor) formAuthor.value = novel.author || '';
    if (formSrcLang) formSrcLang.value = novel.source_lang;
    if (formTgtLang) formTgtLang.value = novel.target_lang;
    if (formStatus) formStatus.value = novel.status || 'ongoing';
    if (formTotalChapters) formTotalChapters.value = novel.totalChapters || 100;
  } else {
    if (titleTitle) titleTitle.textContent = 'เพิ่มนิยายเรื่องใหม่';
    if (formOldSlug) formOldSlug.value = '';
    if (formSlug) { formSlug.value = ''; formSlug.disabled = false; }
    if (formTitle) formTitle.value = '';
    if (formAuthor) formAuthor.value = '';
    if (formSrcLang) formSrcLang.value = 'cn';
    if (formTgtLang) formTgtLang.value = 'th';
    if (formStatus) formStatus.value = 'ongoing';
    if (formTotalChapters) formTotalChapters.value = 100;
  }
  showView('view-admin-novel-edit');
}

async function saveNovelMeta() {
  const slug = document.getElementById('admin-form-slug').value.trim();
  const title = document.getElementById('admin-form-title').value.trim();
  const author = document.getElementById('admin-form-author').value.trim();
  const source_lang = document.getElementById('admin-form-src-lang').value.trim();
  const target_lang = document.getElementById('admin-form-tgt-lang').value.trim();
  const status = document.getElementById('admin-form-status').value;
  const total_chapters = parseInt(document.getElementById('admin-form-total-chapters').value, 10) || 100;

  if (!slug || !title) {
    alert('กรุณากรอกข้อมูลที่จำเป็นให้ครบถ้วนด้วยค่ะพี่โชค! 🦊');
    return;
  }

  try {
    const res = await fetch('/api/novel/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, title, author, source_lang, target_lang, status, total_chapters })
    });
    if (!res.ok) throw new Error(res.statusText);
    allNovelsCache = null;
    showView('view-admin-novels');
  } catch (err) {
    alert(`บันทึกข้อมูลนิยายไม่สำเร็จ: ${err.message}`);
  }
}

async function deleteNovel(slug) {
  if (!confirm(`พี่โชคแน่ใจที่จะลบนิยายเรื่อง "${slug}" และตอนทั้งหมดใช่ไหมคะ? บันทึกไฟล์จะหายถาวรนะคะ!`)) return;
  try {
    const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/delete`, { method: 'POST' });
    if (!res.ok) throw new Error(res.statusText);
    allNovelsCache = null;
    renderAdminNovels();
  } catch (err) {
    alert(`ลบนิยายไม่สำเร็จ: ${err.message}`);
  }
}

async function renderAdminChapters(slug) {
  const titleEl = document.getElementById('admin-chapters-title');
  const subtitleEl = document.getElementById('admin-chapters-subtitle');
  const tbody = document.getElementById('admin-chapters-tbody');
  
  if (titleEl) titleEl.textContent = `จัดการตอนในเรื่อง: ${slug}`;
  if (subtitleEl) subtitleEl.textContent = `Slug: ${slug}`;
  
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">กำลังโหลดตอน...</td></tr>';
  
  try {
    const { chapters } = await api(`/api/novel/${encodeURIComponent(slug)}/chapters`);
    tbody.innerHTML = '';
    
    if (chapters.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-soft); padding: 24px;">ยังไม่มีตอนแปลใด ๆ ในเรื่องนี้ เริ่มเพิ่มตอนใหม่ได้เลยค่ะ! 📝</td></tr>';
    }
    
    chapters.forEach(ch => {
      const row = el('tr', {},
        el('td', { style: 'font-weight:600; font-family:var(--font-mono);' }, String(ch.num).padStart(4, '0')),
        el('td', {}, ch.title || `ตอนที่ ${ch.num}`),
        el('td', {}, 'JSON Canonical'),
        el('td', {},
          el('div', { class: 'admin-action-row' },
            el('button', {
              class: 'admin-btn edit',
              onclick: () => showView('view-admin-translation-center', { slug, num: ch.num })
            }, 'แปล / แก้ไข'),
            el('button', {
              class: 'admin-btn delete',
              onclick: () => deleteChapter(slug, ch.num)
            }, 'ลบ')
          )
        )
      );
      tbody.appendChild(row);
    });

    const createBtn = document.getElementById('admin-btn-create-chapter');
    if (createBtn) {
      createBtn.onclick = () => {
        const nextNum = chapters.length > 0 ? chapters[chapters.length - 1].num + 1 : 1;
        showView('view-admin-translation-center', { slug, num: nextNum });
      };
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="error" style="text-align:center;">โหลดไม่สำเร็จ: ${err.message}</td></tr>`;
  }
}

async function deleteChapter(slug, num) {
  if (!confirm(`พี่โชคแน่ใจที่จะลบตอนที่ ${num} ใช่ไหมคะ?`)) return;
  try {
    const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}/delete`, { method: 'POST' });
    if (!res.ok) throw new Error(res.statusText);
    renderAdminChapters(slug);
  } catch (err) {
    alert(`ลบตอนไม่สำเร็จ: ${err.message}`);
  }
}

async function renderAdminTranslationCenter(slug, num) {
  const headerTitle = document.getElementById('trans-novel-ch-title');
  const titleInput = document.getElementById('trans-title-input');
  const sourceBlocksContainer = document.getElementById('trans-source-blocks');
  const langSelect = document.getElementById('trans-lang-select');
  const sourceFooterInput = document.getElementById('trans-source-footer');

  if (headerTitle) headerTitle.textContent = `แปลตอนที่ ${num} — เรื่อง: ${slug}`;
  if (sourceBlocksContainer) sourceBlocksContainer.innerHTML = '<p class="loading-placeholder">กำลังโหลดโครงสร้างตอน...</p>';

  let chapterTitle = `ตอนที่ ${num}`;
  let lang = 'cn';
  let blocks = [];
  let sourceFooter = '';

  try {
    const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}`);
    const detail = await res.json();
    
    if (detail.title) chapterTitle = detail.title;
    
    if (detail.html) {
      const parser = new DOMParser();
      const doc = parser.parseFromString(detail.html, 'text/html');
      const paragraphs = doc.querySelectorAll('p');
      paragraphs.forEach(p => {
        let type = 'narration';
        let speaker = '';
        let text = p.innerText.trim();
        if (p.classList.contains('system-msg')) {
          type = 'system';
        } else if (p.classList.contains('dialogue')) {
          type = 'dialogue';
          speaker = p.dataset.speaker || '';
        } else if (p.classList.contains('game-title')) {
          type = 'game_title';
        } else if (p.classList.contains('end-marker')) {
          type = 'end';
        }
        blocks.push({ type, text, speaker });
      });
      
      const footerEl = doc.querySelector('.source-footer');
      if (footerEl) {
        sourceFooter = footerEl.innerText.trim();
        blocks = blocks.filter(b => b.text !== sourceFooter);
      }
    }
  } catch (err) {
    blocks = [
      { type: 'narration', text: '', speaker: '' }
    ];
  }

  if (titleInput) titleInput.value = chapterTitle;
  if (langSelect) langSelect.value = lang;
  if (sourceFooterInput) sourceFooterInput.value = sourceFooter;

  const renderBlocks = () => {
    if (!sourceBlocksContainer) return;
    sourceBlocksContainer.innerHTML = '';
    
    blocks.forEach((b, idx) => {
      const card = el('div', { class: 'trans-block-card' },
        el('div', { class: 'trans-block-meta' },
          el('select', {
            style: 'background:var(--surface); border:1px solid var(--border); color:var(--text); padding:4px 8px; border-radius:var(--radius-sm); font-size:0.75rem;',
            onclick: (e) => e.stopPropagation(),
            onchange: (e) => {
              blocks[idx].type = e.target.value;
              renderBlocks();
            }
          },
            el('option', { value: 'narration', selected: b.type === 'narration' }, 'คำบรรยาย (Narration)'),
            el('option', { value: 'dialogue', selected: b.type === 'dialogue' }, 'บทสนทนา (Dialogue)'),
            el('option', { value: 'system', selected: b.type === 'system' }, 'ข้อความระบบ 【System】'),
            el('option', { value: 'game_title', selected: b.type === 'game_title' }, 'ชื่อเกม/ชื่อเรื่อง 《Title》'),
            el('option', { value: 'end', selected: b.type === 'end' }, 'ป้ายปิดท้าย (End Marker)')
          ),
          b.type === 'dialogue' ? el('input', {
            type: 'text',
            placeholder: 'ชื่อผู้พูด...',
            value: b.speaker || '',
            style: 'background:var(--surface); border:1px solid var(--border); color:var(--text); padding:4px 8px; border-radius:var(--radius-sm); font-size:0.8rem; width:120px;',
            oninput: (e) => { blocks[idx].speaker = e.target.value; }
          }) : null,
          el('span', {
            class: 'trans-block-delete',
            onclick: () => {
              blocks.splice(idx, 1);
              renderBlocks();
            }
          }, '✕ ลบย่อหน้านี้')
        ),
        el('textarea', {
          class: 'trans-textarea',
          placeholder: 'กรอกเนื้อหาข้อความตรงนี้...',
          value: b.text || '',
          oninput: (e) => { blocks[idx].text = e.target.value; }
        })
      );
      sourceBlocksContainer.appendChild(card);
    });
  };
  
  renderBlocks();

  const saveBtn = document.getElementById('trans-btn-save');
  if (saveBtn) {
    saveBtn.onclick = async () => {
      const saveTitle = titleInput.value.trim() || `ตอนที่ ${num}`;
      const saveLang = langSelect.value;
      const saveSourceFooter = sourceFooterInput.value.trim();
      
      try {
        const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: saveTitle,
            lang: saveLang,
            blocks,
            source: saveSourceFooter
          })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.details || errData.error || res.statusText);
        }
        showView('view-admin-chapters', { slug });
      } catch (err) {
        alert(`บันทึกตอนไม่สำเร็จ:\n${err.message}`);
      }
    };
  }
  const cancelBtn = document.getElementById('trans-btn-cancel');
  if (cancelBtn) {
    cancelBtn.onclick = () => {
      showView('view-admin-chapters', { slug });
    };
  }

  const addBlockBtn = document.getElementById('trans-btn-add-block');
  if (addBlockBtn) {
    addBlockBtn.onclick = () => {
      blocks.push({ type: 'narration', text: '', speaker: '' });
      renderBlocks();
      const col = sourceBlocksContainer.closest('.translation-column');
      if (col) col.scrollTop = col.scrollHeight;
    };
  }
}

function renderAdminUsers() {
  const tbody = document.getElementById('admin-users-tbody');
  if (!tbody) return;
  
  const users = [
    { name: 'PChoke', email: 'chokechai@gmail.com', role: 'admin', active: 'ออนไลน์', usage: '53 ตอนอ่าน' },
    { name: 'Mika', email: 'mika.secretary@internal', role: 'translator', active: 'ออนไลน์', usage: '21 ตอนแปล' },
    { name: 'ReaderBoy', email: 'reader101@outlook.com', role: 'reader', active: 'ออฟไลน์', usage: '12 ตอนอ่าน' }
  ];
  
  tbody.innerHTML = '';
  users.forEach(u => {
    const row = el('tr', {},
      el('td', { style: 'font-weight:600;' }, u.name),
      el('td', { style: 'color: var(--text-soft); font-family:var(--font-mono);' }, u.email),
      el('td', {}, el('span', { class: `admin-badge ${u.role}` }, u.role.toUpperCase())),
      el('td', {}, u.usage),
      el('td', { style: u.active === 'ออนไลน์' ? 'color: var(--accent);' : 'color: var(--text-soft);' }, u.active)
    );
    tbody.appendChild(row);
  });
}

async function renderAdminGlossary(slug) {
  const tbody = document.getElementById('glossary-tbody');
  const rulesContainer = document.getElementById('style-rules-container');
  if (!tbody || !rulesContainer) return;

  // Show loading
  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-soft);">กำลังโหลดคลังคำศัพท์...</td></tr>';
  rulesContainer.innerHTML = '<p style="color:var(--text-soft); font-size:0.85rem;">กำลังโหลดกฎ...</p>';

  try {
    const data = await api(`/api/novel/${encodeURIComponent(slug)}/glossary/data`);
    const terms = data.terms || [];
    const rules = data.rules || {};

    // 1. Render Glossary terms table
    tbody.innerHTML = '';
    
    function renderRow(t) {
      const tr = el('tr', {},
        el('td', {}, el('input', { type: 'text', value: t.source || '', class: 'glossary-in-source', style: 'width:100%; background:transparent; border:none; color:var(--text); font-size:0.8rem;' })),
        el('td', {}, el('input', { type: 'text', value: t.thai || '', class: 'glossary-in-thai', style: 'width:100%; background:transparent; border:none; color:var(--text); font-size:0.8rem;' })),
        el('td', {}, el('input', { type: 'text', value: t.category || '', class: 'glossary-in-category', style: 'width:100%; background:transparent; border:none; color:var(--text); font-size:0.8rem;' })),
        el('td', {}, el('select', { class: 'glossary-in-lock', style: 'background:transparent; border:none; color:var(--text); font-size:0.8rem;' },
          el('option', { value: 'locked', selected: t.lock === 'locked' }, 'locked'),
          el('option', { value: 'reference', selected: t.lock === 'reference' }, 'reference'),
          el('option', { value: 'auto', selected: t.lock === 'auto' || !t.lock }, 'auto')
        )),
        el('td', {}, el('input', { type: 'text', value: t.notes || '', class: 'glossary-in-notes', style: 'width:100%; background:transparent; border:none; color:var(--text); font-size:0.8rem;' })),
        el('td', { style: 'text-align:center;' }, el('span', {
          style: 'cursor:pointer; color:#ef4444; font-weight:bold; font-size:1.1rem;',
          onclick: () => tr.remove()
        }, '✕'))
      );
      return tr;
    }

    terms.forEach(t => {
      tbody.appendChild(renderRow(t));
    });

    // 2. Render Style rules
    rulesContainer.innerHTML = '';
    const groups = ['punctuation', 'naturalness', 'policies'];
    groups.forEach(group => {
      const items = rules[group] || [];
      const lines = items.map(item => item.text || item).join('\n');
      
      const ruleGroup = el('div', { style: 'display:flex; flex-direction:column; gap:6px;' },
        el('label', { style: 'font-size:0.8rem; font-weight:600; color:var(--accent); text-transform:uppercase;' }, group),
        el('textarea', {
          class: 'style-rule-textarea',
          dataset: { group },
          style: 'background:var(--bg-elevated); border:1px solid var(--border); color:var(--text); padding:8px 12px; border-radius:var(--radius-sm); font-size:0.8rem; font-family:var(--font-mono); height:120px; resize:vertical;',
          value: lines
        })
      );
      rulesContainer.appendChild(ruleGroup);
    });

    // 3. Search Filter wiring
    const searchInput = document.getElementById('glossary-search');
    if (searchInput) {
      searchInput.value = '';
      searchInput.oninput = (e) => {
        const q = e.target.value.toLowerCase().trim();
        const rows = tbody.querySelectorAll('tr');
        rows.forEach(row => {
          const srcInput = row.querySelector('.glossary-in-source');
          const thInput = row.querySelector('.glossary-in-thai');
          const catInput = row.querySelector('.glossary-in-category');
          const notesInput = row.querySelector('.glossary-in-notes');
          
          const src = srcInput ? srcInput.value.toLowerCase() : '';
          const th = thInput ? thInput.value.toLowerCase() : '';
          const cat = catInput ? catInput.value.toLowerCase() : '';
          const notes = notesInput ? notesInput.value.toLowerCase() : '';
          
          if (!q || src.includes(q) || th.includes(q) || cat.includes(q) || notes.includes(q)) {
            row.style.display = '';
          } else {
            row.style.display = 'none';
          }
        });
      };
    }

    // 4. Add Term button wiring
    const addTermBtn = document.getElementById('glossary-btn-add-term');
    if (addTermBtn) {
      addTermBtn.onclick = () => {
        if (searchInput) {
          searchInput.value = '';
          tbody.querySelectorAll('tr').forEach(r => r.style.display = '');
        }
        const newRow = renderRow({ source: '', thai: '', category: 'ตัวละคร', lock: 'auto', notes: '' });
        tbody.appendChild(newRow);
        const sourceIn = newRow.querySelector('.glossary-in-source');
        if (sourceIn) sourceIn.focus();
      };
    }

    // 5. Back to Dash button wiring
    const backBtn = document.getElementById('glossary-btn-back-to-dash');
    if (backBtn) {
      backBtn.onclick = () => {
        showView('view-admin-dashboard');
      };
    }

    // 6. Save button wiring
    const saveBtn = document.getElementById('glossary-btn-save');
    if (saveBtn) {
      saveBtn.onclick = async () => {
        saveBtn.disabled = true;
        saveBtn.textContent = 'กำลังบันทึก...';
        
        const saveTermsPayload = [];
        tbody.querySelectorAll('tr').forEach(tr => {
          const srcIn = tr.querySelector('.glossary-in-source');
          const thIn = tr.querySelector('.glossary-in-thai');
          const catIn = tr.querySelector('.glossary-in-category');
          const lockSel = tr.querySelector('.glossary-in-lock');
          const notesIn = tr.querySelector('.glossary-in-notes');
          
          const source = srcIn ? srcIn.value.trim() : '';
          const thai = thIn ? thIn.value.trim() : '';
          if (!source || !thai) return; // skip incomplete
          
          saveTermsPayload.push({
            source,
            thai,
            category: catIn ? catIn.value.trim() : 'ตัวละคร',
            lock: lockSel ? lockSel.value : 'auto',
            notes: notesIn ? notesIn.value.trim() : '',
            priority: 3
          });
        });

        const saveRulesPayload = {};
        rulesContainer.querySelectorAll('.style-rule-textarea').forEach(ta => {
          const group = ta.dataset.group;
          const lines = ta.value.split('\n').map(l => l.trim()).filter(Boolean);
          saveRulesPayload[group] = lines.map(text => ({ text }));
        });

        try {
          const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/glossary/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ terms: saveTermsPayload, rules: saveRulesPayload })
          });
          if (!res.ok) throw new Error(res.statusText);
          alert('บันทึกคลังคำศัพท์และกฎสำเร็จเรียบร้อยแล้วค่ะพี่โชค! 🦊✨');
          renderAdminGlossary(slug);
        } catch (saveErr) {
          alert(`บันทึกไม่สำเร็จ: ${saveErr.message}`);
        } finally {
          saveBtn.disabled = false;
          saveBtn.textContent = 'บันทึกข้อมูลทั้งหมด';
        }
      };
    }

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="error" style="text-align:center;">โหลดคำศัพท์ไม่สำเร็จ: ${err.message}</td></tr>`;
    rulesContainer.innerHTML = `<p class="error">โหลดกฎไม่สำเร็จ: ${err.message}</p>`;
  }
}

// ── Boot ──────────────────────────────────────────────────────────────

(function init() {
  const saved = loadState();
  setTheme(THEMES.includes(saved.theme) ? saved.theme : 'dark');

  // Novel selector change
  const novelSelect = document.getElementById('novel-select');
  if (novelSelect) {
    novelSelect.addEventListener('change', async (e) => {
      const slug = e.target.value;
      if (slug) {
        const novels = await api('/api/novels');
        const novel = novels.find(n => n.slug === slug);
        if (novel) await openNovel(novel);
      }
    });
  }

  // Back to dashboard
  const backBtn = document.getElementById('back-to-dash');
  if (backBtn) {
    backBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showDashboard();
    });
  }

  // App sidebar menu triggers (Ponytail Style Routing)
  const viewsMapping = {
    'menu-home': 'dashboard',
    'menu-library': 'view-library',
    'menu-history': 'view-history',
    'menu-bookmarks': 'view-bookmarks',
    'menu-downloads': 'view-downloads',
    'menu-recommend': 'view-search',
    'menu-rankings': 'view-rankings',
    'menu-analytics': 'view-analytics',
    'menu-admin': 'view-admin-dashboard',
    'footer-settings': 'view-settings',
    'footer-notifications': 'view-notifications'
  };

  for (const [id, viewId] of Object.entries(viewsMapping)) {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        showView(viewId);
      });
    }
  }

  // Admin Sub-tabs wiring
  const btnAdminDash = document.getElementById('btn-admin-dash');
  if (btnAdminDash) btnAdminDash.onclick = () => showView('view-admin-dashboard');
  const btnAdminNovels = document.getElementById('btn-admin-novels');
  if (btnAdminNovels) btnAdminNovels.onclick = () => showView('view-admin-novels');
  const btnAdminUsers = document.getElementById('btn-admin-users');
  if (btnAdminUsers) btnAdminUsers.onclick = () => showView('view-admin-users');
  const btnAdminGlossary = document.getElementById('btn-admin-glossary');
  if (btnAdminGlossary) btnAdminGlossary.onclick = () => showView('view-admin-glossary');

  // Novel meta form cancel/submit
  const adminCancelBtn = document.getElementById('admin-novel-form-cancel');
  if (adminCancelBtn) adminCancelBtn.onclick = () => showView('view-admin-novels');
  const adminSubmitBtn = document.getElementById('admin-novel-form-submit');
  if (adminSubmitBtn) adminSubmitBtn.onclick = () => saveNovelMeta();
  const adminCreateBtn = document.getElementById('admin-btn-create-novel');
  if (adminCreateBtn) adminCreateBtn.onclick = () => editNovelMeta(null);
  const adminBackNovelsBtn = document.getElementById('admin-btn-back-to-novels');
  if (adminBackNovelsBtn) adminBackNovelsBtn.onclick = () => showView('view-admin-novels');

  // Large search and genre filters
  const largeSearchInput = document.getElementById('search-input-field');
  if (largeSearchInput) {
    largeSearchInput.addEventListener('input', () => {
      const activeTag = document.querySelector('#category-tags .tag.active');
      const genre = activeTag ? activeTag.dataset.genre : 'all';
      renderSearch(genre);
    });
  }

  const tagContainer = document.getElementById('category-tags');
  if (tagContainer) {
    tagContainer.addEventListener('click', (e) => {
      const tag = e.target.closest('.tag');
      if (tag) {
        renderSearch(tag.dataset.genre);
      }
    });
  }

  // Settings font adjusters
  const fontDec = document.getElementById('sett-font-dec');
  if (fontDec) {
    fontDec.onclick = () => {
      fontStep = Math.max(-2, fontStep - 1);
      applyFontSize();
      const valEl = document.getElementById('sett-font-val');
      if (valEl) valEl.textContent = `${17 + fontStep * 2}px`;
    };
  }
  const fontInc = document.getElementById('sett-font-inc');
  if (fontInc) {
    fontInc.onclick = () => {
      fontStep = Math.min(3, fontStep + 1);
      applyFontSize();
      const valEl = document.getElementById('sett-font-val');
      if (valEl) valEl.textContent = `${17 + fontStep * 2}px`;
    };
  }

  // Check URL params — if ?novel= and ?ch= present, load chapter directly
  const urlParams = new URL(window.location).searchParams;
  const urlNovel = urlParams.get('novel');
  const urlCh = urlParams.get('ch');

  if (urlNovel && urlCh) {
    // Direct chapter load — same flow as clicking a novel card
    const chNum = parseInt(urlCh, 10);
    api('/api/novels').then(async (novels) => {
      const novel = novels.find((n) => n.slug === urlNovel);
      if (!novel) { showError(`ไม่พบนิยาย: ${urlNovel}`); return; }
      await openNovel(novel);
      // Override: load the specific chapter from URL
      if (Number.isFinite(chNum) && state.chapters.length > 0) {
        const nums = state.chapters.map((c) => c.num);
        if (nums.includes(chNum)) await loadChapter(chNum);
      }
    }).catch((err) => {
      showError(`โหลดไม่สำเร็จ: ${err.message}`);
    });
  } else if (urlNovel && !urlCh) {
    // Novel without chapter — show reader with first/last chapter
    api('/api/novels').then(async (novels) => {
      const novel = novels.find((n) => n.slug === urlNovel);
      if (!novel) { showError(`ไม่พบนิยาย: ${urlNovel}`); return; }
      await openNovel(novel);
    }).catch((err) => {
      showError(`โหลดไม่สำเร็จ: ${err.message}`);
    });
  } else {
    // Show dashboard first
    document.body.classList.add('dashboard-mode');
    showDashboard().catch((err) => {
      showError(`เริ่มต้นไม่สำเร็จ: ${err.message}`);
    });
  }
  // Listen for browser back/forward navigation (popstate)
  window.addEventListener('popstate', () => {
    const p = new URL(window.location).searchParams;
    if (p.get('novel') && p.get('ch')) {
      // Reader view — use openNovel for consistent initialization
      const chNum = parseInt(p.get('ch'), 10);
      api('/api/novels').then(async (novels) => {
        const novel = novels.find((n) => n.slug === p.get('novel'));
        if (!novel) return;
        await openNovel(novel);
        if (Number.isFinite(chNum) && state.chapters.length > 0) {
          const nums = state.chapters.map((c) => c.num);
          if (nums.includes(chNum)) await loadChapter(chNum);
        }
      }).catch(() => {});
    } else {
      // Dashboard view — show dashboard, hide reader-layout
      document.body.classList.add('dashboard-mode');
      document.body.classList.remove('reader-mode');
      const readerLayout = document.getElementById('reader-layout');
      const dashboard = document.getElementById('dashboard');
      if (readerLayout) readerLayout.hidden = true;
      if (dashboard) dashboard.classList.add('visible');
      showDashboard().catch(() => {});
    }
  });
  window.__appLoaded = true;
})();
})();
