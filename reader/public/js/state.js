/* ═══════════════════════════════════════════════════════════════════════
   state.js — Store with Observer Pattern
   NovelClaw Reader — Single source of truth
   ═══════════════════════════════════════════════════════════════════════ */

const Store = {
  _state: {},
  _listeners: {},

  // ── Reading State (novelclaw-state) ────────────────────────────────
  _STATE_KEY: 'novelclaw-state',

  loadState() {
    try {
      this._state = JSON.parse(localStorage.getItem(this._STATE_KEY)) || {};
    } catch(e) { this._state = {}; }
    return this._state;
  },

  saveState() {
    try { localStorage.setItem(this._STATE_KEY, JSON.stringify(this._state)); } catch(e) {}
  },

  get(key) { return this._state[key]; },
  set(key, val) { this._state[key] = val; this.saveState(); this._notify(key, val); },

  // Chapter read tracking
  markRead(slug, num) {
    if (!this._state[slug]) this._state[slug] = {};
    this._state[slug][num] = Date.now();
    this.saveState();
  },

  setLastPosition(slug, num) {
    this._state[slug + '-last'] = num;
    this.saveState();
  },

  getLastPosition(slug) { return this._state[slug + '-last'] || null; },

  isRead(slug, num) {
    return !!(this._state[slug] && this._state[slug][num]);
  },

  // Get reading history (filtered — excludes known non-slug keys)
  getHistory() {
    const entries = [];
    for (const key of Object.keys(this._state)) {
      if (key.endsWith('-last')) continue;
      const positions = this._state[key];
      if (!positions || typeof positions !== 'object') continue;
      const nums = Object.keys(positions).map(Number).filter(n => !isNaN(n)).sort((a, b) => b - a);
      for (const num of nums.slice(0, 5)) {
        const ts = positions[num];
        if (!ts) continue;
        entries.push({ slug: key, num, ts });
      }
    }
    entries.sort((a, b) => b.ts - a.ts);
    return entries.slice(0, 30);
  },

  // ── Settings (novelclaw-settings) ──────────────────────────────────
  _SETTINGS_KEY: 'novelclaw-settings',
  _settings: {
    theme: 'sepia',
    autoTranslate: false,
    sidebarCollapsed: false,
    rightbarCollapsed: false,
  },

  loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(this._SETTINGS_KEY)) || {};
      this._settings = { ...this._settings, ...saved };
    } catch(e) {}
    return this._settings;
  },

  getSettings() { return this._settings; },

  setSetting(key, val) {
    this._settings[key] = val;
    try { localStorage.setItem(this._SETTINGS_KEY, JSON.stringify(this._settings)); } catch(e) {}
    this._notify('setting:' + key, val);
    if (key === 'theme') document.body.dataset.theme = val;
  },

  // ── Profile (novelclaw-profile) ────────────────────────────────────
  _PROFILE_KEY: 'novelclaw-profile',
  _profile: null,

  getProfile() {
    if (this._profile) return this._profile;
    const def = { name: "P'Choke", email: 'chokechai@gmail.com', role: 'admin', avatarColorIndex: 0 };
    try {
      const saved = localStorage.getItem(this._PROFILE_KEY);
      if (saved) { this._profile = { ...def, ...JSON.parse(saved) }; }
      else { this._profile = def; localStorage.setItem(this._PROFILE_KEY, JSON.stringify(def)); }
    } catch(e) { this._profile = def; }
    return this._profile;
  },

  saveProfile(prof) {
    this._profile = prof;
    try { localStorage.setItem(this._PROFILE_KEY, JSON.stringify(prof)); } catch(e) {}
    this._notify('profile', prof);
  },

  // ── Observer pattern ───────────────────────────────────────────────
  on(key, fn) {
    if (!this._listeners[key]) this._listeners[key] = [];
    this._listeners[key].push(fn);
    return () => { this._listeners[key] = this._listeners[key].filter(f => f !== fn); };
  },

  _notify(key, val) {
    (this._listeners[key] || []).forEach(fn => fn(val));
  }
};

// Bootstrap: load state + settings on init
Store.loadState();
Store.loadSettings();
