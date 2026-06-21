/**
 * lib/brackets.js — Language bracket configuration.
 *
 * Single source of truth: config/brackets.json.
 * This module loads and normalizes for JS usage (camelCase keys).
 */
const fsSync = require('node:fs');
const path = require('node:path');

const raw = JSON.parse(
  fsSync.readFileSync(path.join(__dirname, '../config/brackets.json'), 'utf8')
);

// Normalize snake_case -> camelCase for JS.
const BRACKETS = {};
for (const lang of Object.keys(raw)) {
  const b = raw[lang];
  BRACKETS[lang] = {
    dialogueOpen: b.dialogue_open,
    dialogueClose: b.dialogue_close,
    systemOpen: b.system_open,
    systemClose: b.system_close,
    gameOpen: b.game_open,
    gameClose: b.game_close,
    endMarker: b.end_marker,
  };
}

const LANGUAGE_ALIASES = {
  zh: 'cn',
  cn: 'cn',
  ja: 'jp',
  jp: 'jp',
  ko: 'kr',
  kr: 'kr',
  en: 'en',
  th: 'th',
};

function normalizeLanguageKey(lang, fallback = 'cn') {
  const key = String(lang || '').trim().toLowerCase();
  if (!key) return fallback;
  return LANGUAGE_ALIASES[key] || key;
}

function resolveProfileLang(chapterOrOptions = {}) {
  const n = normalizeLanguageKey(
    chapterOrOptions.profile_lang || chapterOrOptions.output_lang || chapterOrOptions.lang || 'cn'
  );
  return BRACKETS[n] ? n : 'cn';
}

function getBracketProfile(chapterOrOptions = {}) {
  return BRACKETS[resolveProfileLang(chapterOrOptions)] || BRACKETS.cn;
}

module.exports = {
  BRACKETS,
  LANGUAGE_ALIASES,
  normalizeLanguageKey,
  resolveProfileLang,
  getBracketProfile,
};
