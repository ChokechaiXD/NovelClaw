// NovelClaw Reader v2 — frontend logic.
// Vanilla JS, no framework.

const state = {
  novel: null,
  chapters: [],   // [{num, title}, ...]
  index: -1,
  num: null,
  searchQuery: '',
};

const STORAGE_KEY = 'novelclaw-reader-v1';
const THEMES = ['light', 'sepia', 'dark'];
const THEME_ICONS = { light: '☀', sepia: '📜', dark: '🌙' };
const READING_WPM = 250;

// ── Storage helpers ────────────────────────────────────────────────────

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}
function saveState(s) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
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
    else if (k === 'onclick') node.addEventListener('click', v);
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return node;
}

function setNovelTitle(slug, meta) {
  const titleEl = document.getElementById('novel-title');
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
      return el('a', {
        href: `?novel=${slug}&ch=${num}`,
        class: classesFor(num, read),
        'data-num': String(num),
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
      rowEl.className = classesFor(num, read);
      rowEl.setAttribute('href', `?novel=${slug}&ch=${num}`);
      rowEl.setAttribute('data-num', String(num));
      rowEl.setAttribute('title', title);
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
    if (state.list) state.list.setItems([]);
    const list = document.getElementById('chapter-list');
    list.innerHTML = '<li class="empty-list">(ไม่พบ chapter)</li>';
  } else {
    const placeholder = document.querySelector('#chapter-list > .empty-list');
    if (placeholder) placeholder.remove();
    if (!state.list) state.list = createListInstance();
    state.list.setItems(visible);
  }
  const label = q
    ? `${visible.length} / ${state.chapters.length} ตอน`
    : `${state.chapters.length} ตอน`;
  document.getElementById('chapter-count').textContent = label;
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
    document.getElementById(id).disabled = !prev;
  }
  for (const id of ['next-chapter', 'next-chapter-2']) {
    document.getElementById(id).disabled = !next;
  }
  const pos = document.getElementById('chapter-position');
  pos.textContent = state.index >= 0
    ? `${state.index + 1} / ${state.chapters.length}`
    : `— / ${state.chapters.length}`;
  const posTop = document.getElementById('chapter-pos-top');
  if (posTop) posTop.textContent = pos.textContent;
}

function estimateReadingTime(html) {
  const text = html.replace(/<[^>]+>/g, '').replace(/\s+/g, '');
  return Math.max(1, Math.round(text.length / READING_WPM));
}

function showChapter(data) {
  document.getElementById('empty-state').hidden = true;
  const article = document.getElementById('chapter');
  article.hidden = false;

  document.getElementById('chapter-title').textContent =
    data.title || `ตอนที่ ${data.num}`;
  document.getElementById('chapter-content').innerHTML = data.html;
  // Wrap metaHtml in collapsible <details> if present
  if (data.metaHtml) {
    document.getElementById('chapter-meta').innerHTML =
      `<details><summary>หมายเหตุการแปล</summary>${data.metaHtml}</details>`;
  } else {
    document.getElementById('chapter-meta').innerHTML = '';
  }

  const rt = document.getElementById('reading-time');
  if (rt && data.html) {
    rt.textContent = `⏱ ${estimateReadingTime(data.html)} นาที`;
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
  history.replaceState({}, '', url);
}

function showError(msg) {
  document.getElementById('empty-state').hidden = false;
  document.getElementById('empty-state').innerHTML = `<p>${msg}</p>`;
  document.getElementById('chapter').hidden = true;
}

// ── Loading ────────────────────────────────────────────────────────────

async function loadNovels() {
  const novels = await api('/api/novels');
  if (novels.length === 0) {
    showError('ยังไม่มีนิยายในระบบ — รัน NovelClaw translation ก่อน');
    return;
  }
  const params = new URL(window.location).searchParams;
  const wanted = params.get('novel');
  const novel = novels.find((n) => n.slug === wanted) || novels[0];
  await loadNovel(novel);
}

async function loadNovel(novel) {
  state.novel = novel.slug;
  setNovelTitle(novel.slug, novel.meta);
  document.title = `${novel.slug} — NovelClaw`;

  const { chapters } = await api(`/api/novel/${encodeURIComponent(novel.slug)}/chapters`);
  state.chapters = chapters;
  renderChapterList();

  const params = new URL(window.location).searchParams;
  const chParam = parseInt(params.get('ch'), 10);
  const lastPos = getLastPosition(novel.slug);
  const nums = chapters.map((c) => c.num);
  const startCh = nums.includes(chParam) ? chParam
                : nums.includes(lastPos) ? lastPos
                : nums[0];
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
  list.innerHTML = '';
  if (results.length === 0) {
    list.appendChild(el('li', { class: 'empty' }, `ไม่พบ "${q}"`));
    document.getElementById('chapter-count').textContent = `0 / ${state.chapters.length}`;
    return;
  }
  // Search results: use VirtualScroll if many (UX stays smooth), or a
  // plain list if few (rendering one card with a snippet looks better
  // than a virtualised row at that scale).
  if (results.length <= 12) {
    renderSearchResultsSimple(results);
  } else {
    renderSearchResultsVirtual(results);
  }
  document.getElementById('chapter-count').textContent = `${results.length} / ${state.chapters.length}`;
}

function renderSearchResultsSimple(results) {
  const list = document.getElementById('chapter-list');
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
      title: c.title,
      onclick: (e) => { e.preventDefault(); loadChapter(c.num); },
    }, ...rowChildren);
    list.appendChild(el('li', {}, a));
  }
}

function renderSearchResultsVirtual(results) {
  if (!state.list) state.list = createListInstance();
  // Override the list's items with search results by giving it a
  // shallow copy where each item has the snippet/source tags. We can't
  // reuse the main list instance cleanly (it reads state.chapters shape),
  // so we fall back to simple render but cap at the limit. With limit=30
  // it's still manageable.
  renderSearchResultsSimple(results);
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
  // Close mobile sidebar on chapter click
  if (window.innerWidth <= 768) {
    document.getElementById('sidebar').classList.add('collapsed');
    document.body.classList.remove('sidebar-open');
  }
  try {
    const data = await api(`/api/novel/${encodeURIComponent(state.novel)}/chapter/${num}`);
    showChapter(data);
    // Scroll to top so user sees chapter title and meta on chapter switch
    window.scrollTo({ top: 0, behavior: 'auto' });
  } catch (err) {
      // Translate HTTP errors into Thai so the reader sees a friendly
      // message instead of "404 Not Found" or "Failed to fetch".
      let msg;
      if (err && err.status === 404) {
          msg = 'ยังไม่มีตอนนี้ในระบบ';
      } else if (err && err.status >= 500) {
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

function step(delta) {
  const next = state.index + delta;
  if (next < 0 || next >= state.chapters.length) return;
  loadChapter(state.chapters[next].num);
}

// ── Theme ──────────────────────────────────────────────────────────────

function getTheme() { return document.body.dataset.theme || 'light'; }
function setTheme(theme) {
  document.body.dataset.theme = theme;
  document.getElementById('theme-toggle').textContent = THEME_ICONS[theme];
  const s = loadState(); s.theme = theme; saveState(s);
}
function cycleTheme() {
  const cur = getTheme();
  setTheme(THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
}

// ── Wiring ────────────────────────────────────────────────────────────

document.getElementById('toggle-sidebar').addEventListener('click', () => {
  const sidebar = document.getElementById('sidebar');
  const isMobile = window.innerWidth <= 768;
  if (isMobile) {
    const opening = sidebar.classList.contains('collapsed');
    sidebar.classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-open', opening);
  } else {
    sidebar.classList.toggle('collapsed');
    document.body.classList.remove('sidebar-open');
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
  if (!document.body.classList.contains('sidebar-open')) return;
  // Click on the backdrop (pseudo-element on body): target === body
  if (e.target !== document.body) return;
  document.getElementById('sidebar').classList.add('collapsed');
  document.body.classList.remove('sidebar-open');
});

document.getElementById('theme-toggle').addEventListener('click', cycleTheme);

document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea')) return;
  if (e.key === 'ArrowLeft') step(-1);
  if (e.key === 'ArrowRight') step(+1);
  if (e.key === 't' || e.key === 'T') cycleTheme();
  if (e.key === 's' || e.key === 'S') {
    const sidebar = document.getElementById('sidebar');
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      const opening = sidebar.classList.contains('collapsed');
      sidebar.classList.toggle('collapsed');
      document.body.classList.toggle('sidebar-open', opening);
    } else {
      sidebar.classList.toggle('collapsed');
    }
  }
  if (e.key === 'Home') window.scrollTo({ top: 0, behavior: 'smooth' });
  if (e.key === 'End') window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
});

// ── Dashboard ───────────────────────────────────────────────────────────

async function showDashboard() {
  const dashboard = document.getElementById('dashboard');
  const readerLayout = document.getElementById('reader-layout');
  const novelSelector = document.getElementById('novel-selector');
  const novelTitle = document.getElementById('novel-title');

  dashboard.classList.add('visible');
  readerLayout.hidden = true;
  novelSelector.hidden = true;
  novelTitle.textContent = 'NovelClaw';

  const novels = await api('/api/novels');
  const grid = document.getElementById('novel-grid');
  grid.innerHTML = '';

  for (const novel of novels) {
    const card = el('div', { class: 'novel-card', onclick: () => openNovel(novel) });

    const statusClass = novel.status === 'ongoing' ? 'ongoing'
      : novel.status === 'complete' ? 'complete' : 'unknown';
    const statusText = novel.status === 'ongoing' ? 'กำลังแปล'
      : novel.status === 'complete' ? 'จบ' : 'ไม่ระบุ';

    const readCount = novel.chapterCount || 0;
    const totalCount = novel.totalChapters || readCount;
    const pct = totalCount > 0 ? Math.round((readCount / totalCount) * 100) : 0;

    card.innerHTML = `
      <span class="card-status ${statusClass}">${statusText}</span>
      <p class="card-title">${novel.title || novel.slug}</p>
      <p class="card-slug">${novel.slug}</p>
      <div class="card-stats">
        <span>📖 ${readCount}/${totalCount} ตอน</span>
        <span>🌐 ${novel.source_lang || 'cn'} → ${novel.target_lang || 'th'}</span>
      </div>
      <div class="card-progress">
        <div class="card-progress-bar" style="width: ${pct}%"></div>
      </div>
    `;
    grid.appendChild(card);
  }
}

async function openNovel(novel) {
  const dashboard = document.getElementById('dashboard');
  const readerLayout = document.getElementById('reader-layout');
  const novelSelector = document.getElementById('novel-selector');
  const novelSelect = document.getElementById('novel-select');

  dashboard.classList.remove('visible');
  readerLayout.hidden = false;
  novelSelector.hidden = false;

  // Populate selector
  const novels = await api('/api/novels');
  novelSelect.innerHTML = '';
  for (const n of novels) {
    const opt = document.createElement('option');
    opt.value = n.slug;
    opt.textContent = n.title || n.slug;
    if (n.slug === novel.slug) opt.selected = true;
    novelSelect.appendChild(opt);
  }

  await loadNovel(novel);
}

// ── Boot ──────────────────────────────────────────────────────────────

(function init() {
  const saved = loadState();
  setTheme(saved.theme || 'light');

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

  // Show dashboard first
  showDashboard().catch((err) => {
    showError(`เริ่มต้นไม่สำเร็จ: ${err.message}`);
  });
})();
