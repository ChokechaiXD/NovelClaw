/* ═══════════════════════════════════════════════════════════════════════
   api.js — Network Layer with In-Memory Cache
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const Api = {
  _novelsCache: null,
  _novelsCacheTime: 0,
  _chaptersCache: {},
  _chaptersCacheTime: {},
  _CACHE_TTL: 5 * 60 * 1000, // 5 min TTL — translate pipeline runs outside frontend

  async getNovels() {
    const now = Date.now();
    if (this._novelsCache && (now - this._novelsCacheTime) < this._CACHE_TTL) return this._novelsCache;
    const res = await fetch('/api/novels');
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    this._novelsCache = await res.json();
    this._novelsCacheTime = now;
    return this._novelsCache;
  },

  invalidateNovels() { this._novelsCache = null; this._novelsCacheTime = 0; },

  async getChapters(slug) {
    const now = Date.now();
    const cached = this._chaptersCache[slug];
    if (cached && (now - (this._chaptersCacheTime[slug] || 0)) < this._CACHE_TTL) return cached;
    const res = await fetch(`/api/novel/${slug}/chapters`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    this._chaptersCache[slug] = data.chapters || [];
    this._chaptersCacheTime[slug] = now;
    return this._chaptersCache[slug];
  },

  invalidateChapters(slug) { delete this._chaptersCache[slug]; delete this._chaptersCacheTime[slug]; },

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
