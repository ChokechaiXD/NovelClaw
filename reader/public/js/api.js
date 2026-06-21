/* ═══════════════════════════════════════════════════════════════════════
   api.js — Network Layer with In-Memory Cache
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const Api = {
  _novelsCache: null,
  _chaptersCache: {},

  async getNovels() {
    if (this._novelsCache) return this._novelsCache;
    const res = await fetch('/api/novels');
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    this._novelsCache = await res.json();
    return this._novelsCache;
  },

  invalidateNovels() { this._novelsCache = null; },

  async getChapters(slug) {
    if (this._chaptersCache[slug]) return this._chaptersCache[slug];
    const res = await fetch(`/api/novel/${slug}/chapters`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    this._chaptersCache[slug] = data.chapters || [];
    return this._chaptersCache[slug];
  },

  invalidateChapters(slug) { delete this._chaptersCache[slug]; },

  async getChapterContent(slug, num) {
    const res = await fetch(`/api/novel/${slug}/chapter/${num}`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async searchChapters(slug, q, mode) {
    const res = await fetch(`/api/novel/${slug}/chapters/search?q=${encodeURIComponent(q)}&mode=${mode || 'title'}`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }
};
