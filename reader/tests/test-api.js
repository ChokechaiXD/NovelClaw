/**
 * tests/test-api.js — NovelClaw API smoke tests
 *
 * Run: node tests/test-api.js
 * Env:  PORT (default 4173), ADMIN_TOKEN (optional)
 *
 * Tests:
 *   ✓ /api/health reports reader readiness
 *   ✓ static assets support HTTP validation caching
 *   ✓ missing static assets return 404 instead of the SPA shell
 *   ✓ /api/novels returns novels with translatedTitle
 *   ✓ /api/novel/:slug/chapters returns chapter list
 *   ✓ /api/novel/:slug/chapter/:num?lang=th returns Thai
 *   ✓ /api/novel/:slug/chapter/:num?lang=cn returns Chinese
 *   ✓ /api/novel/:slug/glossary/data returns terms (no 500)
 *   ✓ /api/local/llm-config returns provider catalog
 *   ✓ source importer catalog, paste, and local files work end-to-end
 *   ✓ /api/novel/:slug/chapters/search?mode=content finds Chinese terms
 *   ✓ admin save/create temp chapter
 *   ✓ chapters list includes temp chapter after save
 *   ✓ admin delete temp chapter
 *   ✓ chapters list does not include temp chapter after delete
 */

const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const PORT = parseInt(process.env.PORT, 10) || 4173;
const BASE = `http://localhost:${PORT}`;
const TEST_SLUG = 'global-descent';
const TEST_NUM = 9999; // unlikely to exist
const TEST_IMPORT_SLUG = 'api-import-smoke';
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';
const NOVELS_DIR = process.env.NOVELCLAW_ROOT
  ? path.resolve(process.env.NOVELCLAW_ROOT)
  : path.resolve(__dirname, '..', '..', 'novels');
const TEST_CHAPTER_FILE = path.join(NOVELS_DIR, TEST_SLUG, 'chapters', `${TEST_NUM}.th.json`);
const TEST_IMPORT_DIR = path.join(NOVELS_DIR, TEST_IMPORT_SLUG);
const TRACKED_INDEX_FILES = [
  path.join(NOVELS_DIR, TEST_SLUG, 'chapters.json'),
  path.join(NOVELS_DIR, TEST_SLUG, 'chapters', 'index.json'),
];

let passed = 0;
let failed = 0;

function request(method, urlPath, body, headers = {}) {
  return new Promise((resolve) => {
    const url = new URL(urlPath, BASE);
    const opts = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: { ...headers },
      timeout: 10_000,
    };
    if (ADMIN_TOKEN) {
      opts.headers.Authorization = `Bearer ${ADMIN_TOKEN}`;
    }
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
    }
    const req = http.request(opts, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        let parsed = null;
        try { parsed = JSON.parse(data); } catch {}
        resolve({ status: res.statusCode, body: parsed, raw: data, headers: res.headers });
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

async function get(url, headers) { return request('GET', url, null, headers); }
async function post(url, body) { return request('POST', url, body); }

async function snapshotFile(filePath) {
  try {
    return { filePath, contents: await fs.readFile(filePath) };
  } catch (error) {
    if (error.code === 'ENOENT') return { filePath, contents: null };
    throw error;
  }
}

async function restoreFile(snapshot) {
  if (snapshot.contents === null) {
    await fs.rm(snapshot.filePath, { force: true });
    return;
  }
  await fs.writeFile(snapshot.filePath, snapshot.contents);
}

async function main() {
  console.log(`NovelClaw API Smoke Tests — ${BASE}\n`);
  const preflight = await get('/');
  if (preflight.status === 0) {
    console.error(`Reader server is not reachable at ${BASE}. Start it first with: npm --prefix reader start`);
    console.error(`Connection error: ${preflight.raw}`);
    process.exit(1);
  }

  const indexSnapshots = await Promise.all(TRACKED_INDEX_FILES.map(snapshotFile));
  try {

  // ── Test 1: Health ────────────────────────────────────────────────
  await test('/api/health reports reader readiness', async () => {
    const res = await get('/api/health');
    return res.status === 200
      && res.body?.ok === true
      && res.body?.service === 'novelclaw-reader';
  });

  await test('static assets support HTTP validation caching', async () => {
    const first = await get('/design-system.css');
    const etag = first.headers?.etag;
    if (first.status !== 200 || !etag) return false;

    const second = await get('/design-system.css', { 'If-None-Match': etag });
    return second.status === 304 && second.raw === '';
  });

  await test('missing static assets return 404 instead of the SPA shell', async () => {
    const res = await get('/js/pages/does-not-exist.js');
    return res.status === 404
      && !res.raw.includes('<!doctype html>')
      && res.headers['cache-control'] === 'no-store';
  });

  // ── Test 2: Novel listing ─────────────────────────────────────────
  await test('/api/novels returns novels', async () => {
    const res = await get('/api/novels');
    if (res.status !== 200) return false;
    if (!Array.isArray(res.body)) return false;
    if (res.body.length === 0) return false;
    const n = res.body[0];
    return n.slug && 'translatedTitle' in n && n.chapterCount > 0;
  });

  // ── Test 2: Chapter list ──────────────────────────────────────────
  await test('/api/novel/:slug/chapters', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapters`);
    if (res.status !== 200) return false;
    const chs = res.body?.chapters;
    if (!Array.isArray(chs) || chs.length === 0) return false;
    const first = chs[0];
    return first.num === 1
      && first.title
      && first.hasTh !== undefined
      && first.workflowStatus === undefined
      && first.workflowReasons === undefined;
  });

  await test('/api/novel/:slug/chapters?withQuality=1 includes workflow detail', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapters?withQuality=1`);
    const first = res.body?.chapters?.[0];
    return res.status === 200
      && first?.workflowStatus
      && Array.isArray(first.workflowReasons)
      && res.body?.workflowSummary?.translated >= 1;
  });

  await test('basic chapter list supports HTTP revalidation', async () => {
    const first = await get(`/api/novel/${TEST_SLUG}/chapters`);
    const etag = first.headers?.etag;
    if (first.status !== 200 || !etag || first.headers['cache-control'] !== 'private, no-cache') return false;
    const second = await get(`/api/novel/${TEST_SLUG}/chapters`, { 'If-None-Match': etag });
    return second.status === 304 && second.raw === '';
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

  // ── Test 6: Local LLM config catalog ──────────────────────────────
  await test('/api/local/llm-config returns providers', async () => {
    const res = await get('/api/local/llm-config');
    if (res.status !== 200) return false;
    const providers = res.body?.providers;
    if (!Array.isArray(providers)) return false;
    const openrouter = providers.find(p => p.id === 'openrouter');
    const openmodel = providers.find(p => p.id === 'openmodel');
    return openrouter
      && openmodel
      && Array.isArray(openrouter.models)
      && openrouter.models.length > 0
      && Array.isArray(openmodel.models)
      && openmodel.models.some(m => m.id === 'deepseek-v4-flash')
      && res.body.default_provider;
  });

  await test('/api/import/sites returns active adapters', async () => {
    const res = await get('/api/import/sites');
    return res.status === 200
      && res.body?.ok === true
      && res.body?.data?.sites?.some(site => site.id === '69shu');
  });

  await test('manual paste import writes a source chapter', async () => {
    const res = await post('/api/import/paste', {
      slug: TEST_IMPORT_SLUG,
      title: 'API Import Smoke',
      sourceLang: 'en',
      content: 'Chapter 1\n\nA deterministic local import paragraph.',
    });
    if (res.status !== 200 || res.body?.data?.imported !== 1) return false;

    const health = await get(`/api/import/health?slug=${TEST_IMPORT_SLUG}`);
    return health.status === 200
      && health.body?.data?.sourceFileCount === 1;
  });

  await test('local JSON file import writes normalized source chapters', async () => {
    const document = JSON.stringify({
      title: 'API File Import',
      chapters: [
        { num: 2, title: 'Chapter 2 - File', paragraphs: ['A local JSON paragraph.', 'A second paragraph.'] },
      ],
    });
    const res = await post('/api/import/file', {
      slug: TEST_IMPORT_SLUG,
      title: 'API Import Smoke',
      sourceLang: 'en',
      filename: 'fixture.json',
      dataBase64: Buffer.from(document, 'utf8').toString('base64'),
    });
    if (res.status !== 200
      || res.body?.data?.format !== 'json'
      || res.body?.data?.encoding !== 'utf-8'
      || res.body?.data?.imported !== 1) return false;

    const health = await get(`/api/import/health?slug=${TEST_IMPORT_SLUG}`);
    return health.status === 200
      && health.body?.data?.sourceFileCount === 2;
  });

  await test('glossary save preserves document metadata', async () => {
    const glossaryPath = path.join(TEST_IMPORT_DIR, 'glossary', 'glossary.json');
    await fs.mkdir(path.dirname(glossaryPath), { recursive: true });
    await fs.writeFile(glossaryPath, JSON.stringify({
      version: 3,
      review: { owner: 'api-smoke' },
      terms: [{ source: 'Old', thai: 'เก่า' }],
    }), 'utf8');
    const terms = [{ source: 'Mana Core', thai: 'แก่นมานา', verified: true }];
    const snapshot = await get(`/api/novel/${TEST_IMPORT_SLUG}/glossary/data`);
    const res = await post(`/api/novel/${TEST_IMPORT_SLUG}/glossary/save`, {
      terms,
      revision: snapshot.body?.revision,
    });
    if (res.status !== 200) return false;

    const stored = JSON.parse(await fs.readFile(glossaryPath, 'utf8'));
    return stored.version === 3
      && stored.review?.owner === 'api-smoke'
      && stored.terms?.[0]?.source === 'Mana Core';
  });

  await test('stale glossary save returns conflict without losing new terms', async () => {
    const glossaryPath = path.join(TEST_IMPORT_DIR, 'glossary', 'glossary.json');
    const snapshot = await get(`/api/novel/${TEST_IMPORT_SLUG}/glossary/data`);
    const current = JSON.parse(await fs.readFile(glossaryPath, 'utf8'));
    current.terms.push({ source: 'Fresh Discovery', thai: 'คำใหม่', verified: false });
    await fs.writeFile(glossaryPath, JSON.stringify(current), 'utf8');

    const res = await post(`/api/novel/${TEST_IMPORT_SLUG}/glossary/save`, {
      terms: snapshot.body.terms,
      revision: snapshot.body.revision,
    });
    const stored = JSON.parse(await fs.readFile(glossaryPath, 'utf8'));
    return res.status === 409
      && stored.terms.some(term => term.source === 'Fresh Discovery');
  });

  // ── Test 7: Content search (Chinese term) ─────────────────────────
  await test('/api/novel/.../search?q=曹星&mode=content', async () => {
    const res = await get(`/api/novel/${TEST_SLUG}/chapters/search?q=%E6%9B%B9%E6%98%9F&mode=content&limit=2`);
    if (res.status !== 200) return false;
    return Array.isArray(res.body) && res.body.length > 0;
  });

  // ── Test 8: Admin save temp chapter ───────────────────────────────
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

  // ── Test 9: Chapters includes temp after save ─────────────────────
  await test('chapters list includes 9999 after save', async () => {
    if (!tempSaved) return false; // skip if save failed
    const res = await get(`/api/novel/${TEST_SLUG}/chapters`);
    if (res.status !== 200) return false;
    return res.body.chapters.some(c => c.num === TEST_NUM);
  });

  // ── Test 10: Admin delete temp chapter ────────────────────────────
  let tempDeleted = false;
  await test('POST delete temp chapter 9999', async () => {
    if (!tempSaved) return false;
    const res = await post(`/api/novel/${TEST_SLUG}/chapter/${TEST_NUM}/delete`);
    tempDeleted = res.status === 200;
    return res.status === 200;
  });

  // ── Test 11: Chapters excludes temp after delete ──────────────────
  await test('chapters list excludes 9999 after delete', async () => {
    if (!tempDeleted) return false;
    const res = await get(`/api/novel/${TEST_SLUG}/chapters`);
    if (res.status !== 200) return false;
    return !res.body.chapters.some(c => c.num === TEST_NUM);
  });

  } finally {
    await fs.rm(TEST_CHAPTER_FILE, { force: true });
    await fs.rm(TEST_IMPORT_DIR, { recursive: true, force: true });
    await Promise.all(indexSnapshots.map(restoreFile));
    await post('/api/invalidate-cache', {});
  }

  // ── Summary ───────────────────────────────────────────────────────
  console.log(`\n${'━'.repeat(40)}`);
  console.log(`  ${passed} passed, ${failed} failed`);
  process.exitCode = failed > 0 ? 1 : 0;
}

main().catch((err) => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
