// NovelClaw Reader v2 — virtual scroll for chapter list.
// Renders only visible rows + buffer, so 1,239 chapters stay smooth.

/**
 * VirtualScroll
 *
 * Owns a scrollable viewport (.vscroll-viewport) and a spacer (.vscroll-spacer)
 * whose height = items.length * rowHeight. Items are absolutely positioned
 * inside the spacer at top = index * rowHeight. Only rows in
 * [scrollTop - buffer, scrollTop + viewport + buffer] are rendered.
 *
 * No framework, no observer — a single scroll handler (rAF-throttled) is
 * enough for sidebar-scale (1,239 rows × 64px).
 */
class VirtualScroll {
  /**
   * @param {HTMLElement} container — must contain .vscroll-viewport and .vscroll-spacer
   * @param {object} opts
   * @param {number} opts.rowHeight — fixed height per row in px
   * @param {number} [opts.buffer=5] — extra rows above/below to keep mounted
   * @param {(item: any, index: number) => HTMLElement} opts.render
   * @param {(item: any, index: number, el: HTMLElement) => void} [opts.update]
   * @param {(item: any, index: number) => void} [opts.onClick]
   */
  constructor(container, opts) {
    this.container = container;
    this.viewport = container.querySelector('.vscroll-viewport');
    this.spacer = container.querySelector('.vscroll-spacer');
    this.rowHeight = opts.rowHeight;
    this.buffer = opts.buffer ?? 5;
    this.render = opts.render;
    this.update = opts.update;
    this.onClick = opts.onClick;
    this.items = [];
    this.mounted = new Map(); // index -> {item, el}
    this._raf = 0;
    this._needsRender = true;

    if (this.onClick) {
      this.viewport.addEventListener('click', (e) => {
        const row = e.target.closest('.vscroll-row');
        if (!row) return;
        const idx = parseInt(row.dataset.idx, 10);
        if (Number.isFinite(idx)) this.onClick(this.items[idx], idx);
      });
    }

    this.viewport.addEventListener('scroll', () => {
      if (this._raf) return;
      this._raf = requestAnimationFrame(() => {
        this._raf = 0;
        this._schedule();
      });
    });

    // Re-render on resize (viewport height changes -> range changes)
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => this._schedule());
      ro.observe(this.viewport);
    } else {
      window.addEventListener('resize', () => this._schedule());
    }
  }

  setItems(items) {
    this.items = items;
    this.spacer.style.height = `${items.length * this.rowHeight}px`;
    // Drop everything; we will re-mount on next render
    for (const { el } of this.mounted.values()) el.remove();
    this.mounted.clear();
    this.viewport.scrollTop = 0;
    this._needsRender = true;
    this._render();
  }

  /**
   * Update an already-rendered row in place. Use when read/active state changes
   * without re-rendering the whole list.
   */
  refresh() {
    for (const [idx, entry] of this.mounted) {
      if (this.update) this.update(entry.item, idx, entry.el);
    }
  }

  scrollToIndex(idx, { align = 'start' } = {}) {
    if (idx < 0 || idx >= this.items.length) return;
    const top = idx * this.rowHeight;
    if (align === 'center') {
      const h = this.viewport.clientHeight;
      this.viewport.scrollTop = Math.max(0, top - h / 2 + this.rowHeight / 2);
    } else if (align === 'end') {
      this.viewport.scrollTop = top - this.viewport.clientHeight + this.rowHeight;
    } else {
      this.viewport.scrollTop = top;
    }
    this._schedule();
  }

  get scrollTop() { return this.viewport.scrollTop; }
  set scrollTop(v) { this.viewport.scrollTop = v; this._schedule(); }

  _schedule() {
    this._needsRender = true;
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = 0;
      if (this._needsRender) {
        this._needsRender = false;
        this._render();
      }
    });
  }

  _render() {
    const vh = this.viewport.clientHeight;
    if (vh === 0) { this._needsRender = true; return; }
    const scrollTop = this.viewport.scrollTop;
    const startIdx = Math.max(0, Math.floor(scrollTop / this.rowHeight) - this.buffer);
    const endIdx = Math.min(
      this.items.length,
      Math.ceil((scrollTop + vh) / this.rowHeight) + this.buffer,
    );

    // Remove rows that scrolled out
    for (const [idx, entry] of this.mounted) {
      if (idx < startIdx || idx >= endIdx) {
        entry.el.remove();
        this.mounted.delete(idx);
      }
    }

    // Mount missing rows
    for (let i = startIdx; i < endIdx; i++) {
      if (this.mounted.has(i)) continue;
      const item = this.items[i];
      const el = this.render(item, i);
      el.classList.add('vscroll-row');
      el.dataset.idx = String(i);
      el.style.position = 'absolute';
      el.style.top = `${i * this.rowHeight}px`;
      el.style.left = '0';
      el.style.right = '0';
      el.style.height = `${this.rowHeight}px`;
      this.spacer.appendChild(el);
      this.mounted.set(i, { item, el });
    }
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { VirtualScroll };
}
