/**
 * tests/test-api.js — NovelClaw API smoke tests
 *
 * Run: node tests/test-api.js
 * Env:  PORT (default 4173)
 *
 * Tests:
 *   ✓ /api/novels returns novels with translatedTitle
 *   ✓ /api/novel/:slug/chapters returns chapter list
 *   ✓ /api/novel/:slug/chapter/:num?lang=th returns Thai
 *   ✓ /api/novel/:slug/chapter/:num?lang=cn returns Chinese
 *   ✓ /api/novel/:slug/glossary/data returns terms (no 500)
 *   ✓ /api/novel/:slug/chapters/search?mode=content finds Chinese terms
 *   ✓ admin save/create temp chapter
 *   ✓ chapters list includes temp chapter after save
 *   ✓ admin delete temp chapter
 *   ✓ chapters list does not include temp chapter after delete
 */

const http = require('node:http');
const PORT = parseInt(process.env.PORT, 10) || 4173;
const BASE = `http://localhost:${PORT}`;
const TEST_SLUG = 'global-descent';
const TEST_NUM = 9999; // unlikely to exist

let passed = 0;
let failed = 0;

function request(method, urlPath, body) {
  return new Promise((resolve) => {
    const url = new URL(urlPath, BASE);
    const opts = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {},
      timeout: 10_000,
    };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
    }
    const req = http.request(opts, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        let parsed = null;
        try { parsed = JSON.parse(data); } catch {}
        resolve({ status: res.statusCode, body: parsed, raw: data });
      });
    });
    req.on('error', (err) => resolve({ status: 0, body: null, raw: err.message }));
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

function test(name, fn) {
  return fn().then((ok) => {
    if (ok) {
      console.log(`  ✓ ${name}`);
      passed++;
    } else {
      console.log(`  ✗ ${name}`);
      failed++;
    }
  }).catch((err) => {
    console.log(`  ✗ ${name}: ${err.message}`);
    failed++;
  });
}

async function get(url) { return request('GET', url); }
async function post(url, body) { return request('POST', url, body); }

async function main() {
  console.log(`NovelClaw API Smoke Tests — ${BASE}\n`);

  // ── Test 1: Novel listing ─────────────────────────────────────────
  await test('/api/novels returns novels', async () => {
    const res = await get('/api/novels');
    if (res.status !== 200) return false;
    if (!Array.isArray(res.body)) return false;
    if (res.body.length === 0) return false;
    const n = res.body[0];
    return n.slug && n.translatedTitle && n.chapterCount > 0;
  });

  // ── Test 2: Chapter list ──────────────────────────────────────────
  await test('/api/novel/:slug/chapters', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapters`);
    if (res.status !== 200) return false;
    const chs = res.body?.chapters;
    if (!Array.isArray(chs) || chs.length === 0) return false;
    const first = chs[0];
    return first.num === 1 && first.title && first.hasTh !== undefined;
  });

  // ── Test 3: Thai chapter ──────────────────────────────────────────
  await test('/api/novel/.../chapter/1?lang=th', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapter/1?lang=th`);
    if (res.status !== 200) return false;
    return Array.isArray(res.body?.paragraphs) && res.body.paragraphs.length > 0
      && res.body.isTranslated === true
      && res.body.lang === 'th';
  });

  // ── Test 4: Chinese chapter ───────────────────────────────────────
  await test('/api/novel/.../chapter/1?lang=cn', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapter/1?lang=cn`);
    if (res.status !== 200) return false;
    return Array.isArray(res.body?.paragraphs) && res.body.paragraphs.length > 0
      && res.body.isTranslated === false
      && res.body.lang === 'cn';
  });

  // ── Test 5: Glossary ──────────────────────────────────────────────
  await test('/api/novel/.../glossary/data', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/glossary/data`);
    if (res.status !== 200) return false;
    return Array.isArray(res.body?.terms) && res.body.terms.length > 0;
  });

  // ── Test 6: Content search (Chinese term) ─────────────────────────
  await test('/api/novel/.../search?q=曹星&mode=content', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapters/search?q=%E6%9B%B9%E6%98%9F&mode=content&limit=2`);
    if (res.status !== 200) return false;
    return Array.isArray(res.body) && res.body.length > 0;
  });

  // ── Test 7: Admin save temp chapter ───────────────────────────────
  let tempSaved = false;
  await test('POST save temp chapter 9999', async () => {
    const payload = {
      title: `ตอนที่ ${TEST_NUM} (test)`,
      blocks: [
        { type: 'narration', text: 'นี่คือตอนทดสอบ' },
        { type: 'narration', text: 'บรรทัดที่สอง' },
        { type: 'end', text: '(จบบท)' },
      ],
      lang: 'th',
    };
    const res = await post(`/api/novel/${TEST_SLUG}/chapter/${TEST_NUM}/save`, payload);
    tempSaved = res.status === 200;
    return res.status === 200;
  });

  // ── Test 8: Chapters includes temp after save ─────────────────────
  await test('chapters list includes 9999 after save', async () => {
    if (!tempSaved) return false; // skip if save failed
    const res = await get(`/api/novel/${TEST_SLUG}/chapters`);
    if (res.status !== 200) return false;
    return res.body.chapters.some(c => c.num === TEST_NUM);
  });

  // ── Test 9: Admin delete temp chapter ─────────────────────────────
  let tempDeleted = false;
  await test('POST delete temp chapter 9999', async () => {
    if (!tempSaved) return false;
    const res = await post(`/api/novel/${TEST_SLUG}/chapter/${TEST_NUM}/delete`);
    tempDeleted = res.status === 200;
    return res.status === 200;
  });

  // ── Test 10: Chapters excludes temp after delete ──────────────────
  await test('chapters list excludes 9999 after delete', async () => {
    if (!tempDeleted) return false;
    const res = await get(`/api/novel/${TEST_SLUG}/chapters`);
    if (res.status !== 200) return false;
    return !res.body.chapters.some(c => c.num === TEST_NUM);
  });

  // ── Summary ───────────────────────────────────────────────────────
  console.log(`\n${'━'.repeat(40)}`);
  console.log(`  ${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
