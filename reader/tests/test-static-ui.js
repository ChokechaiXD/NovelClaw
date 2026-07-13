/**
 * tests/test-static-ui.js — static frontend hygiene checks.
 *
 * Keeps generated UI strings aligned with the design system:
 *   - no inline style attributes in public JS/HTML
 *   - no inline onclick attributes in public JS/HTML
 *   - no blocking alert() calls in public JS
 *   - npm run check runs the recursive JS syntax gate
 */

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PUBLIC_JS = path.join(ROOT, 'public', 'js');
const PUBLIC_HTML = path.join(ROOT, 'public', 'index.html');
const DESIGN_CSS = path.join(ROOT, 'public', 'design-system.css');
const PACKAGE_JSON = path.join(ROOT, 'package.json');
const SERVER_JS = path.join(ROOT, 'server.js');
const API_JS = path.join(PUBLIC_JS, 'api.js');
const APP_JS = path.join(PUBLIC_JS, 'app.js');
const ADMIN_JS = path.join(PUBLIC_JS, 'pages', 'admin.js');
const ADMIN_PAGE_LOADER_JS = path.join(PUBLIC_JS, 'pages', 'admin-page-loader.js');
const ADMIN_TRANSLATE_JS = path.join(PUBLIC_JS, 'pages', 'admin-translate.js');
const ADMIN_TRANSLATE_JOB_JS = path.join(PUBLIC_JS, 'pages', 'admin-translate-job.js');
const HOME_JS = path.join(PUBLIC_JS, 'pages', 'home.js');
const NOVEL_JS = path.join(PUBLIC_JS, 'pages', 'novel.js');
const READER_JS = path.join(PUBLIC_JS, 'pages', 'reader.js');
const PAGES_JS = path.join(PUBLIC_JS, 'pages', 'pages.js');
const STATE_JS = path.join(PUBLIC_JS, 'state.js');

const FORBIDDEN = [
  { label: 'inline style attribute', pattern: 'style="' },
  { label: 'inline onclick attribute', pattern: 'onclick="' },
  { label: 'blocking alert()', pattern: 'alert(' },
  { label: 'untranslated Admin Control Center heading', pattern: 'Admin Control Center</' },
  { label: 'untranslated Translation Cockpit heading', pattern: 'Translation Cockpit</' },
  { label: 'untranslated AI Settings action', pattern: 'AI Settings</span>' },
  { label: 'untranslated Translate Queue action', pattern: 'Translate Queue</span>' },
  { label: 'untranslated Import Novel action', pattern: 'Import Novel</span>' },
  { label: 'untranslated Import Studio heading', pattern: 'Import Studio</' },
  { label: 'untranslated Library Manager action', pattern: 'Library Manager</span>' },
  { label: 'untranslated Local Settings label', pattern: 'Local Settings</' },
  { label: 'untranslated Audit Logs label', pattern: 'Audit Logs</' },
  { label: 'untranslated Settings heading', pattern: '>Settings</' },
  { label: 'untranslated Local tools heading', pattern: '>Local tools</' },
  { label: 'untranslated About heading', pattern: '>About</' },
  { label: 'manual asset version query', pattern: '?_v=' },
];

function walkJs(dir) {
  const files = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...walkJs(full));
    else if (entry.isFile() && entry.name.endsWith('.js')) files.push(full);
  }
  return files;
}

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, '/');
}

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

const jsFiles = walkJs(PUBLIC_JS);
const uiFiles = jsFiles.concat(PUBLIC_HTML);
const htmlText = fs.readFileSync(PUBLIC_HTML, 'utf8');
const cssText = fs.readFileSync(DESIGN_CSS, 'utf8');
const uiText = uiFiles.map(file => fs.readFileSync(file, 'utf8')).join('\n');

for (const file of uiFiles) {
  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split(/\r?\n/);
  for (const rule of FORBIDDEN) {
    lines.forEach((line, idx) => {
      if (line.includes(rule.pattern)) {
        fail(`${rel(file)}:${idx + 1} contains ${rule.label}`);
      }
    });
  }
}

for (const removedSurface of ['data-page="profile"', 'id="page-profile"', 'id="page-ranking"', 'id="profile-avatar"']) {
  if (htmlText.includes(removedSurface)) {
    fail(`index.html still exposes removed local-only surface ${removedSurface}`);
  }
}
if (!htmlText.includes('data-page="settings"') || !htmlText.includes('aria-label="ตั้งค่า"')) {
  fail('index.html mobile navigation must expose local settings');
}

for (const deadSelector of ['.c-hero', '.c-update', '.c-popular', '.c-ranking', '.c-profile', '.c-avatar', '--c-hero', '.c-table-wrap td::before']) {
  if (cssText.includes(deadSelector)) {
    fail(`design-system.css still ships unused selector/token ${deadSelector}`);
  }
}

const generatedCssClasses = new Set([
  'c-admin-edit__status--error',
  'c-admin-edit__status--muted',
  'c-admin-edit__status--success',
  'c-glossary-admin__status--error',
  'c-glossary-admin__status--success',
  'c-icon--md',
  'c-toast--error',
  'c-toast--success',
  'c-toast--warning',
  ...Array.from({ length: 11 }, (_, index) => `u-progress-w-${index * 10}`),
]);
const cssClasses = [...cssText.matchAll(/\.([A-Za-z_][A-Za-z0-9_-]*)/g)]
  .map(match => match[1]);
const orphanCssClasses = [...new Set(cssClasses)]
  .filter(className => !uiText.includes(className) && !generatedCssClasses.has(className));
if (orphanCssClasses.length) {
  fail(`design-system.css has orphan class selectors: ${orphanCssClasses.join(', ')}`);
}

if (!cssText.includes('.c-table-wrap { overflow-x: auto; }')) {
  fail('design-system.css must keep semantic tables scrollable on narrow screens');
}

const homeText = fs.readFileSync(HOME_JS, 'utf8');
for (const fakeHomeSection of ['c-hero', 'c-update', 'c-popular', 'ยอดนิยมประจำสัปดาห์']) {
  if (homeText.includes(fakeHomeSection)) {
    fail(`home.js still renders duplicate/fake discovery section ${fakeHomeSection}`);
  }
}
if (!homeText.includes('Ui.novelCard')) {
  fail('home.js must reuse the canonical novel card instead of maintaining another card implementation');
}

const readerText = fs.readFileSync(READER_JS, 'utf8');
for (const eagerModelSurface of ['reader-model-select', 'reader-model-list', 'Api.getLlmConfig', 'Api.saveLlmConfig']) {
  if (readerText.includes(eagerModelSurface)) {
    fail(`reader.js must not load or edit provider config while reading: ${eagerModelSurface}`);
  }
}

const novelText = fs.readFileSync(NOVEL_JS, 'utf8');
if (!novelText.includes('continueNum') || !novelText.includes('อ่านต่อตอนที่')) {
  fail('novel.js primary action must resume the last-read chapter');
}

const pagesText = fs.readFileSync(PAGES_JS, 'utf8');
for (const removedPage of ['const RankingPage', 'const ProfilePage']) {
  if (pagesText.includes(removedPage)) {
    fail(`pages.js still ships unused page ${removedPage}`);
  }
}

const stateText = fs.readFileSync(STATE_JS, 'utf8');
if (stateText.includes('_PROFILE_KEY') || stateText.includes('chokechai@gmail.com')) {
  fail('state.js must not ship a fake local profile or personal email');
}

const pkg = JSON.parse(fs.readFileSync(PACKAGE_JSON, 'utf8'));
const checkScript = pkg.scripts?.check || '';
if (!checkScript.includes('tests/test-js-syntax.js')) {
  fail('npm run check does not run tests/test-js-syntax.js');
}

const adminText = fs.readFileSync(ADMIN_JS, 'utf8');
if (adminText.includes('#admin/novels/')) {
  fail('admin novels edit action must link to #admin/novel-edit/<slug>');
}

const appText = fs.readFileSync(APP_JS, 'utf8');
for (const routeOnlyAsset of [
  'admin-page-loader.js',
  'admin-ui.js',
  'admin-format.js',
  'admin-translate-model.js',
  'admin-glossary-model.js',
  'admin-import-model.js',
]) {
  if (appText.includes(routeOnlyAsset)) {
    fail(`app.js must not eagerly load admin route dependency ${routeOnlyAsset}`);
  }
}
if (!appText.includes("'/js/pages/admin.js'")) {
  fail('app.js must lazy-load the admin route registry');
}
if (fs.existsSync(ADMIN_PAGE_LOADER_JS)) {
  fail('single-use admin-page-loader.js must be folded into the admin route registry');
}

for (const accessibleShellMarkup of [
  'id="theme-toggle-new"',
  'role="switch"',
  'aria-checked="false"',
  'id="drawer-sidebar" role="dialog"',
  'aria-modal="true"',
  'aria-hidden="true"',
  'id="toast-container" class="c-toast-container" role="status"',
]) {
  if (!htmlText.includes(accessibleShellMarkup)) {
    fail(`index.html must expose accessible shell markup: ${accessibleShellMarkup}`);
  }
}
for (const accessibleShellBehavior of [
  "'aria-checked'",
  "e.key === 'Escape'",
  "e.key !== 'Tab'",
  'drawerReturnFocus',
  "removeAttribute('aria-current')",
  "setAttribute('aria-current', 'page')",
]) {
  if (!appText.includes(accessibleShellBehavior)) {
    fail(`app.js must preserve accessible drawer/theme behavior: ${accessibleShellBehavior}`);
  }
}
if (!cssText.includes('@media (prefers-reduced-motion: reduce)')) {
  fail('design-system.css must respect reduced-motion preferences');
}
if (cssText.includes('.c-toggle__knob')) {
  fail('design-system.css must not keep the obsolete duplicate toggle implementation');
}

const adminTranslateText = fs.readFileSync(ADMIN_TRANSLATE_JS, 'utf8');
if (adminTranslateText.includes('includeChapters: true')) {
  fail('admin translate table must use chapter workflowSourceIssues instead of refetching import health chapters');
}
if (!adminTranslateText.includes('withQuality: true, fresh: true')) {
  fail('admin translate table must fetch fresh chapter workflow state');
}
if (!adminTranslateText.includes('translate-job-retry')) {
  fail('admin translate tracker must expose retry for failed run chapters');
}
if (!adminTranslateText.includes('translate-job-meta')) {
  fail('admin translate tracker must render selected run metadata');
}

const adminTranslateJobText = fs.readFileSync(ADMIN_TRANSLATE_JOB_JS, 'utf8');
if (!adminTranslateJobText.includes('retryPlan') || !adminTranslateJobText.includes('Retry failed')) {
  fail('admin translate job panel must render retryPlan status');
}
if (!adminTranslateJobText.includes('retry of:') || !adminTranslateJobText.includes('workers:')) {
  fail('admin translate job panel must show run model/provider/workers metadata');
}

const apiText = fs.readFileSync(API_JS, 'utf8');
if (!apiText.includes('!options.fresh && cached')) {
  fail('Api.getChapters must let workflow pages bypass cached chapter lists');
}
if (!apiText.includes('retryTranslateRun')) {
  fail('Api must expose retryTranslateRun for failed translate runs');
}

const serverText = fs.readFileSync(SERVER_JS, 'utf8');
if (!serverText.includes("require('compression')") || !serverText.includes('app.use(compression(')) {
  fail('server.js must enable response compression middleware');
}
if (!serverText.includes("require('./lib/atomic-write')") || !serverText.includes('await writeJsonAtomic(translateRunPath(bucket, run.runId)')) {
  fail('server.js must persist translate run JSON atomically');
}
if (!serverText.includes('function findActiveTranslateRun') || !serverText.includes('TRANSLATE_RUN_ACTIVE')) {
  fail('server.js must block overlapping active translate runs for the same novel');
}
if (!serverText.includes("args.push('--sequential')")) {
  fail('server.js must pass --sequential when translate worker count is one');
}
if (!serverText.includes("adminPost('/api/translate/runs/:runId/retry'") || !serverText.includes('NO_RETRYABLE_CHAPTERS')) {
  fail('server.js must expose a retry endpoint for failed translate run chapters');
}
for (const missingScript of ['glossary.py', 'translate_term.py', 'novelctl.py']) {
  if (serverText.includes(missingScript)) {
    fail(`server.js references removed script ${missingScript}`);
  }
}

if (process.exitCode) {
  process.exit(process.exitCode);
}

console.log(`Static UI checks passed (${jsFiles.length} files)`);
