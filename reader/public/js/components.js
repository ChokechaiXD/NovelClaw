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

  icon(id, size = 'sm') {
    return `<svg class="c-icon c-icon--${size} c-icon--stroke" aria-hidden="true"><use xlink:href="#icon-${Ui.esc(id)}"/></svg>`;
  },

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
    el.innerHTML = `<div class="c-empty"><svg class="c-empty__mascot" aria-hidden="true"><use href="#brand-mark"/></svg><div class="c-empty__title">${Ui.esc(title || 'ยังไม่มีข้อมูล')}</div><div class="c-empty__desc">${Ui.esc(desc || '')}</div></div>`;
  },

  showError(container, title, desc) {
    const el = typeof container === 'string' ? Ui.$(container) : container;
    if (!el) return;
    el.innerHTML = `<div class="c-error"><svg class="c-error__mascot" aria-hidden="true"><use href="#brand-mark"/></svg><div class="c-error__title">${Ui.esc(title || 'เกิดข้อผิดพลาด')}</div><div class="c-empty__desc">${Ui.esc(desc || '')}</div><button class="c-error__retry" data-ui-reload>ลองอีกครั้ง</button></div>`;
  },

  // ── Display Title (fallback: translatedTitle → title → slug) ──────────
  displayTitle(novel) {
    if (!novel) return '';
    return novel.translatedTitle || novel.title || novel.slug || '';
  },

  isVisibleNovel(novel) {
    if (!novel) return false;
    const slug = novel.slug || '';
    return !slug.startsWith('test-')
      && !slug.startsWith('tmp-')
      && !slug.startsWith('fixture-')
      && (novel.totalChapters || novel.chapterCount || 0) > 0;
  },

  // ── Cover SVG generator (NovelClaw brand fallback) ───────────────
  coverSVG(slug, title) {
    const initial = (title || slug || '?').charAt(0).toUpperCase();
    const coverLabel = (slug || title || '').slice(0, 18);
    const hue = Ui.slugToHue(slug || '');
    const base = `hsl(${hue % 360} 28% 24%)`;
    const accent = `hsl(${(hue + 32) % 360} 48% 62%)`;
    return `<svg viewBox="0 0 200 260" xmlns="http://www.w3.org/2000/svg" class="c-cover-svg" role="img" aria-label="ปก ${Ui.esc(title || slug)}">
      <rect width="200" height="260" rx="8" fill="${base}"/>
      <rect x="14" width="6" height="260" fill="${accent}"/>
      <path d="M40 42h120M40 48h74" stroke="rgba(255,255,255,.38)" stroke-width="2" stroke-linecap="round"/>
      <text x="100" y="152" text-anchor="middle" fill="rgba(255,255,255,.92)" font-size="72" font-weight="600" font-family="ui-serif,serif">${Ui.esc(initial)}</text>
      <path d="M68 176h64" stroke="${accent}" stroke-width="3" stroke-linecap="round"/>
      <text x="100" y="226" text-anchor="middle" fill="rgba(255,255,255,.9)" font-size="13" font-weight="600" font-family="system-ui,sans-serif">${Ui.esc(coverLabel)}</text>
      <text x="100" y="244" text-anchor="middle" fill="rgba(255,255,255,.55)" font-size="8" letter-spacing="2" font-family="system-ui,sans-serif">NOVELCLAW</text>
    </svg>`;
  },

  coverHtml(novel, options = {}) {
    const title = Ui.displayTitle(novel);
    const src = novel?.coverImage || '';
    if (src) {
      const priority = options.priority === true;
      return `<img class="c-cover-img" src="${Ui.esc(src)}" alt="${Ui.esc(title || 'ปกนิยาย')}" width="200" height="260" loading="${priority ? 'eager' : 'lazy'}"${priority ? ' fetchpriority="high"' : ''}>`;
    }
    return Ui.coverSVG(novel?.slug || '', title);
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
      { name: 'dashboard', label: 'ภาพรวม', page: 'admin', icon: 'home' },
      { name: 'import', label: 'นำเข้า', page: 'admin/import', icon: 'library' },
      { name: 'translate', label: 'สั่งแปล', page: 'admin/translate', icon: 'book' },
      { name: 'novels', label: 'นิยาย', page: 'admin/novels', icon: 'library' },
      { name: 'chapters', label: 'ตอน', page: 'admin/chapters', icon: 'book' },
      { name: 'glossary', label: 'คำศัพท์', page: 'admin/glossary', icon: 'bookmarks' },
      { name: 'provider', label: 'ระบบ AI', page: 'admin/provider', icon: 'settings' },
      { name: 'logs', label: 'ล็อก', page: 'admin/logs', icon: 'info' },
    ];
    return '<div class="c-admin-nav">' + links.map(l =>
      '<a href="#' + l.page + '" class="c-admin-nav__link' + (l.name === active ? ' c-admin-nav__link--active' : '') + '" data-nav>' + Ui.icon(l.icon, 'xs') + '<span>' + l.label + '</span></a>'
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

  progressClass(percent) {
    const bucket = Math.max(0, Math.min(100, Math.round((Number(percent) || 0) / 10) * 10));
    return `u-progress-w-${bucket}`;
  },

  novelStatus(novel) {
    const n = Ui.enrichNovel(novel || {});
    if (!n.totalCount) return { label: 'ไม่มีตอน', tone: 'gray' };
    if (n.translatedCount >= n.totalCount) return { label: 'แปลครบ', tone: 'teal' };
    if (n.translatedCount > 0) return { label: 'กำลังทำ', tone: 'amber' };
    return { label: 'พร้อมแปล', tone: 'gray' };
  },

  novelCard(novel, options = {}) {
    const n = Ui.enrichNovel(novel || {});
    const title = Ui.displayTitle(n);
    const status = Ui.novelStatus(n);
    const pct = n.translationPct || 0;
    const readHref = n.lastRead ? `#novel/${Ui.esc(n.slug)}/${Ui.esc(n.lastRead)}` : `#novel/${Ui.esc(n.slug)}`;
    const meta = `${Ui.esc(n.author || 'ไม่ระบุผู้แต่ง')} · ${n.totalCount || 0} ตอน`;
    const compact = options.compact ? ' c-novel-card--compact' : '';
    return `
      <article class="c-card c-novel-card${compact}">
        <a class="c-card__cover c-novel-card__cover" href="#novel/${Ui.esc(n.slug)}" data-nav aria-label="เปิด ${Ui.esc(title)}">${Ui.coverHtml(n)}</a>
        <div class="c-card__info c-novel-card__body">
          <div class="c-novel-card__head">
            <a class="c-card__title c-novel-card__title" href="#novel/${Ui.esc(n.slug)}" data-nav>${Ui.esc(title)}</a>
            <span class="c-badge c-badge--${status.tone}">${Ui.esc(status.label)}</span>
          </div>
          <div class="c-card__meta">${meta}</div>
          <div class="c-card__progress" aria-label="Translation progress ${pct}%">
            <span class="c-card__progress-bar"><span class="c-card__progress-fill ${Ui.progressClass(pct)}"></span></span>
            <span class="c-card__progress-pct">${pct}%</span>
          </div>
          <div class="c-novel-card__meta-row">
            <span>${n.translatedCount || 0}/${n.totalCount || 0} แปลแล้ว</span>
            <span>${n.lastRead ? 'อ่านล่าสุด ตอน ' + Ui.esc(n.lastRead) : 'ยังไม่ได้อ่าน'}</span>
          </div>
          <div class="c-novel-card__actions">
            <a class="c-btn c-btn--xs c-btn--primary" href="${readHref}" data-nav>${Ui.icon('book', 'xs')}<span>${n.lastRead ? 'อ่านต่อ' : 'เริ่มอ่าน'}</span></a>
            <a class="c-novel-card__detail-link" href="#novel/${Ui.esc(n.slug)}" data-nav><span>สารบัญ</span>${Ui.icon('arrow-right', 'xs')}</a>
          </div>
        </div>
      </article>`;
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
    const safeValue = this.esc(String(value ?? ''));
    return `<div class="c-mini-stat${opts.class ? ' ' + opts.class : ''}">`
      + `<div class="c-mini-stat__num ${numClass}">${safeValue}</div>`
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
    return `<button class="c-btn c-btn--sm c-btn--ghost c-copy-btn" data-copy-text="${encoded}" title="คัดลอก">${this.icon('book', 'xs')}<span>คัดลอก</span></button>`;
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
