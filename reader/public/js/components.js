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
      el.innerHTML = '<div class="c-skel c-skel--block"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line" style="width:45%;"></div>';
    } else {
      el.innerHTML = '<div class="c-skel c-skel--block"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line" style="width:55%;"></div>';
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
    el.innerHTML = `<div class="c-error"><svg class="c-error__mascot"><use xlink:href="#mascot-crab-excited"/></svg><div class="c-error__title">${Ui.esc(title || 'เกิดข้อผิดพลาด')}</div><div class="c-empty__desc">${Ui.esc(desc || '')}</div><button class="c-error__retry" onclick="location.reload()">ลองอีกครั้ง</button></div>`;
  },

  // ── Display Title (fallback: translatedTitle → title → slug) ──────────
  displayTitle(novel) {
    if (!novel) return '';
    return novel.translatedTitle || novel.title || novel.slug || '';
  },

  // ── Toast ──────────────────────────────────────────────────────────────
  showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = Ui.el('div', { id: 'toast-container', class: 'c-toast-container' });
      document.body.appendChild(container);
    }
    const t = Ui.el('div', { class: `c-toast c-toast--${type}` }, message);
    container.appendChild(t);
    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transform = 'translateY(20px)';
      setTimeout(() => t.remove(), 300);
    }, 3000);
  },

  // ── Status Map ─────────────────────────────────────────────────────────
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
  }
};
