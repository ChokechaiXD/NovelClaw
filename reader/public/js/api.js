/* ═══════════════════════════════════════════════════════════════════════
   api.js — Network Layer with In-Memory Cache
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const Api = {
  _novelsCache: null,
  _novelsCacheTime: 0,
  _novelsInFlight: null,           // dedup concurrent getNovels() requests
  _chaptersCache: {},
  _chaptersCacheTime: {},
  _chapterContentCache: {},       // key: slug:num:lang → { data, time }
  _CACHE_TTL: 5 * 60 * 1000,     // 5 min standard TTL
  _CONTENT_TTL: 10 * 60 * 1000,  // 10 min for chapter content (changes less often)

  async getNovels() {
    const now = Date.now();
    if (this._novelsCache && (now - this._novelsCacheTime) < this._CACHE_TTL) return this._novelsCache;
    // Coalesce concurrent callers onto a single in-flight request
    if (this._novelsInFlight) return this._novelsInFlight;
    this._novelsInFlight = (async () => {
      try {
        const res = await fetch('/api/novels');
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        this._novelsCache = await res.json();
        this._novelsCacheTime = Date.now();
        return this._novelsCache;
      } finally {
        this._novelsInFlight = null;
      }
    })();
    return this._novelsInFlight;
  },

  invalidateNovels() {
    this._novelsCache = null;
    this._novelsCacheTime = 0;
    this._novelsInFlight = null;
  },

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

  async getChapterContent(slug, num, lang) {
    lang = lang || 'th';
    const key = `${slug}:${num}:${lang}`;
    const now = Date.now();
    const cached = this._chapterContentCache[key];
    if (cached && (now - cached.time) < this._CONTENT_TTL) return cached.data;

    const res = await fetch(`/api/novel/${slug}/chapter/${num}?lang=${lang}`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    this._chapterContentCache[key] = { data, time: now };
    return data;
  },

  invalidateChapterContent(slug, num) {
    // Invalidate all languages for this chapter
    for (const key of Object.keys(this._chapterContentCache)) {
      if (key.startsWith(`${slug}:${num}:`)) {
        delete this._chapterContentCache[key];
      }
    }
  },

  // Invalidate all content caches for a slug (after save/rebuild)
  invalidateAll(slug) {
    this.invalidateNovels();
    this.invalidateChapters(slug);
    for (const key of Object.keys(this._chapterContentCache)) {
      if (key.startsWith(`${slug}:`)) {
        delete this._chapterContentCache[key];
      }
    }
  },

  async searchChapters(slug, q, mode) {
    const res = await fetch(`/api/novel/${slug}/chapters/search?q=${encodeURIComponent(q)}&mode=${mode || 'title'}`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async getLlmConfig() {
    const res = await fetch('/api/local/llm-config');
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async getLlmOptions() {
    return this.getLlmConfig();
  },

  async saveLlmConfig(config) {
    const res = await fetch('/api/local/llm-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async translateSingle(slug, num, score, options = {}) {
    const res = await fetch(`/api/novel/${slug}/translate/single`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ num, score, ...options })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error?.message || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },

  async translateBatch(slug, range, concurrent = 1) {
    const res = await fetch(`/api/novel/${slug}/translate/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ range, concurrent })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error?.message || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },

  async getUnknownTerms(slug, num) {
    const res = await fetch(`/api/novel/${slug}/chapter/${num}/unknown-terms`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async translateTerm(term, context) {
    const res = await fetch('/api/local/translate-term', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term, context })
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async verifyGlossaryTerm(slug, index, verified) {
    const res = await fetch(`/api/novel/${slug}/glossary/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index, verified })
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async deleteNovel(slug) {
    const res = await fetch(`/api/novel/${slug}/delete`, {
      method: 'POST'
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error?.message || `${res.status} ${res.statusText}`);
    }
    this.invalidateNovels();
    return res.json();
  },

  // ── Provider Config API (YAML-based) ──────────────────────────
  async getProviderConfig() {
    const res = await fetch('/api/admin/provider-config');
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  async saveProviderConfig(config) {
    const res = await fetch('/api/admin/provider-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }
};
