/* ═══════════════════════════════════════════════════════════════════════
   components.js — Shared UI Components
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const Ui = {
  // ── DOM Builder ──────────────────────────────────────────────────────
  el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') node.className = v;
      else if (k.startsWith('on') && typeof v === 'function')
        node.addEventListener(k.slice(2).toLowerCase(), v);
      else if (['selected', 'checked', 'disabled', 'readonly', 'required'].includes(k.toLowerCase())) {
        if (v) { node.setAttribute(k, ''); node[k] = true; }
        else { node.removeAttribute(k); node[k] = false; }
      } else node.setAttribute(k, v);
    }
    for (const c of children.flat()) {
      if (c == null) continue;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return node;
  },

  $(id) { return document.getElementById(id); },

  esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  },

  // ── Slug → Hue (deterministic color for cover placeholders) ──────────
  slugToHue(slug) {
    return slug.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
  },

  // ── Loading States ────────────────────────────────────────────────────
  showSkeleton(container, type) {
    const el = typeof container === 'string' ? Ui.$(container) : container;
    if (!el) return;
    if (type === 'card') {
      el.innerHTML = '<div class="c-skel c-skel--card"></div>'.repeat(3);
    } else if (type === 'list') {
      el.innerHTML = '<div class="c-skel c-skel--line"></div>'.repeat(6);
    } else if (type === 'detail') {
      el.innerHTML = '<div class="c-skel c-skel--block"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line c-skel--w-45"></div>';
    } else {
      el.innerHTML = '<div class="c-skel c-skel--block"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line c-skel--w-55"></div>';
    }
  },

  showEmpty(container, title, desc) {
    const el = typeof container === 'string' ? Ui.$(container) : container;
    if (!el) return;
    el.innerHTML = `<div class="c-empty"><svg class="c-empty__mascot"><use xlink:href="#mascot-crab-reading"/></svg><div class="c-empty__title">${Ui.esc(title || 'ยังไม่มีข้อมูล')}</div><div class="c-empty__desc">${Ui.esc(desc || '')}</div></div>`;
  },

  showError(container, title, desc) {
    const el = typeof container === 'string' ? Ui.$(container) : container;
    if (!el) return;
    el.innerHTML = `<div class="c-error"><svg class="c-error__mascot"><use xlink:href="#mascot-crab-excited"/></svg><div class="c-error__title">${Ui.esc(title || 'เกิดข้อผิดพลาด')}</div><div class="c-empty__desc">${Ui.esc(desc || '')}</div><button class="c-error__retry" data-ui-reload>ลองอีกครั้ง</button></div>`;
  },

  // ── Display Title (fallback: translatedTitle → title → slug) ──────────
  displayTitle(novel) {
    if (!novel) return '';
    return novel.translatedTitle || novel.title || novel.slug || '';
  },

  // ── Cover SVG generator (NovelClaw brand fallback) ───────────────
  coverSVG(slug, title) {
    const initial = (title || slug || '?').charAt(0).toUpperCase();
    const coverLabel = (slug || title || '').slice(0, 18);
    const hue = Ui.slugToHue(slug || '');
    // NovelClaw palette: teal gradient base + purple accent
    const c1 = `hsl(${hue % 360}, 60%, 35%)`;
    const c2 = `hsl(${(hue + 40) % 360}, 50%, 25%)`;
    const id = `c${slug || 'x'}`;
    return `<svg viewBox="0 0 200 260" xmlns="http://www.w3.org/2000/svg" class="c-cover-svg">
      <defs>
        <linearGradient id="g-${id}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${c1}"/>
          <stop offset="100%" stop-color="${c2}"/>
        </linearGradient>
        <linearGradient id="c-${id}" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.6"/>
          <stop offset="100%" stop-color="#14b8a6" stop-opacity="0.6"/>
        </linearGradient>
      </defs>
      <rect width="200" height="260" rx="10" fill="url(#g-${id})"/>
      <g transform="translate(70,30) scale(0.8)">
        <path d="M2 28C3 24 6 22 10 21 11.5 22.5 11 25 7 28 5 29.5 3 29 2 28Z" fill="url(#c-${id})"/>
        <path d="M8 20C6.5 13 10.5 7 18 9.5 16 11 12 12 11 16.5 10.5 18 9.5 19.5 8 20Z" fill="url(#c-${id})"/>
        <rect x="13" y="7" width="12" height="18" rx="2" fill="#a78bfa" opacity="0.8"/>
        <rect x="14.5" y="8" width="9.5" height="16" rx="1" fill="#fffdf5"/>
      </g>
      <text x="100" y="220" text-anchor="middle" fill="rgba(255,255,255,0.15)" font-size="60" font-weight="700" font-family="system-ui,sans-serif">${Ui.esc(initial)}</text>
      <text x="100" y="248" text-anchor="middle" fill="rgba(255,255,255,0.85)" font-size="14" font-weight="600" font-family="system-ui,sans-serif">${Ui.esc(coverLabel)}</text>
    </svg>`;
  },

  showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = Ui.el('div', { id: 'toast-container', class: 'c-toast-container' });
      document.body.appendChild(container);
    }
    const t = Ui.el('div', { class: `c-toast c-toast--${type}` }, message);
    container.appendChild(t);
    setTimeout(() => {
      t.classList.add('c-toast--leaving');
      setTimeout(() => t.remove(), 300);
    }, 3000);
  },

  // ── Shared Admin Nav ─────────────────────────────────────────────────────
  adminNav(active) {
    const links = [
      { name: 'dashboard', label: 'ภาพรวม', page: 'admin' },
      { name: 'translate', label: 'สั่งแปล & AI', page: 'admin/translate' },
      { name: 'novels', label: 'นิยาย', page: 'admin/novels' },
      { name: 'chapters', label: 'ตอน', page: 'admin/chapters' },
      { name: 'glossary', label: 'คำศัพท์', page: 'admin/glossary' },
      { name: 'logs', label: 'ล็อก', page: 'admin/logs' },
    ];
    return '<div class="c-admin-nav">' + links.map(l =>
      '<a href="#' + l.page + '" class="c-admin-nav__link' + (l.name === active ? ' c-admin-nav__link--active' : '') + '" data-nav>' + l.label + '</a>'
    ).join('') + '</div>';
  },
  statusMap: {
    ongoing: 'กำลังแปล',
    complete: 'จบแล้ว',
    in_progress: 'กำลังแปล',
    paused: 'พักการแปล'
  },

  // ── Enriched novel helper ──────────────────────────────────────────────
  enrichNovel(n) {
    const lastRead = Store.getLastPosition(n.slug);
    const totalCount = n.totalChapters || n.chapterCount || 0;
    const translatedCount = n.translatedChapters || 0;
    const translationPct = totalCount > 0 ? Math.round((translatedCount / totalCount) * 100) : 0;
    return {
      ...n,
      lastRead,
      translatedCount,
      totalCount,
      translationPct,
      hue: Ui.slugToHue(n.slug)
    };
  },

  // ── Update topbar avatar ───────────────────────────────────────────────
  updateAvatar() {
    const prof = Store.getProfile();
    const el = document.getElementById('profile-avatar');
    if (!el) return;
    el.textContent = prof.name ? prof.name.charAt(0).toUpperCase() : 'P';
    const GRADIENTS = [
      'linear-gradient(135deg,#f59e0b,#ef4444)',
      'linear-gradient(135deg,#00f5d4,#38bdf8)',
      'linear-gradient(135deg,#10b981,#059669)',
      'linear-gradient(135deg,#a78bfa,#ec4899)',
      'linear-gradient(135deg,#64748b,#1e293b)'
    ];
    el.style.background = GRADIENTS[prof.avatarColorIndex] || GRADIENTS[0];
  },

  // ── Debounce Utility ──────────────────────────────────────────────────
  debounce(fn, delay) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  },

  /* ── Template helpers ──────────────────────────────────────────── */

  /**
   * Create a stat card (for dashboards).
   * @param {string} label — short label text
   * @param {string|number} value — numeric/stat value
   * @param {object} opts — { tone: 'accent'|'success'|'warn'|'muted', class: '' }
   */
  stat(label, value, opts = {}) {
    const tone = opts.tone || 'accent';
    const numClass = tone === 'warn' ? 'c-mini-stat__num--warn'
      : tone === 'success' ? 'c-mini-stat__num--success'
      : '';
    return `<div class="c-mini-stat${opts.class ? ' ' + opts.class : ''}">`
      + `<div class="c-mini-stat__num ${numClass}">${value}</div>`
      + `<div class="c-mini-stat__label">${this.esc(String(label))}</div></div>`;
  },

  /**
   * Create a card container.
   * @param {object} opts — { title, body, href, icon }
   */
  card(opts = {}) {
    const tag = opts.href ? 'a' : 'div';
    const hrefAttr = opts.href ? ` href="${opts.href}"` : '';
    const navAttr = opts.href ? ' data-nav' : '';
    const iconHtml = opts.icon
      ? `<svg class="c-icon c-icon--sm"><use xlink:href="${opts.icon}"/></svg> `
      : '';
    return `<${tag} class="c-card"${hrefAttr}${navAttr}>`
      + (opts.title ? `<div class="c-card__title">${iconHtml}${this.esc(opts.title)}</div>` : '')
      + (opts.body ? `<div class="c-card__body">${opts.body}</div>` : '')
      + `</${tag}>`;
  },

  /**
   * Create a copy-to-clipboard button.
   * @param {string} text — text to copy
   */
  copyButton(text) {
    const encoded = this.esc(encodeURIComponent(text || ''));
    return `<button class="c-btn c-btn--sm c-btn--ghost c-copy-btn" data-copy-text="${encoded}" title="คัดลอก">📋</button>`;
  },
};

document.addEventListener('click', (event) => {
  const reloadBtn = event.target.closest('[data-ui-reload]');
  if (reloadBtn) {
    location.reload();
    return;
  }

  const copyBtn = event.target.closest('[data-copy-text]');
  if (!copyBtn) return;

  const text = decodeURIComponent(copyBtn.dataset.copyText || '');
  const fallbackCopy = () => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.className = 'u-sr-only';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    if (!copied) throw new Error('copy failed');
  };

  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => Ui.showToast('คัดลอกแล้ว', 'success'))
      .catch(() => {
        try { fallbackCopy(); Ui.showToast('คัดลอกแล้ว', 'success'); }
        catch { Ui.showToast('คัดลอกไม่สำเร็จ', 'error'); }
      });
    return;
  }

  try { fallbackCopy(); Ui.showToast('คัดลอกแล้ว', 'success'); }
  catch { Ui.showToast('คัดลอกไม่สำเร็จ', 'error'); }
});
