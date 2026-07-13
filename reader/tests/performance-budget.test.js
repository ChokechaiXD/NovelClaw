const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { gzipSync } = require('node:zlib');

const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');
const KIB = 1024;

// Baseline 2026-07-13; each ceiling leaves roughly 10-20% for normal iteration.
const BUDGET = {
  initialRaw: 300 * KIB,
  initialGzip: 64 * KIB,
  initialJsRaw: 145 * KIB,
  initialJsGzip: 38 * KIB,
  initialCssRaw: 140 * KIB,
  initialCssGzip: 23 * KIB,
  lazyJsRaw: 245 * KIB,
  lazyJsGzip: 60 * KIB,
  lazyChunkRaw: 60 * KIB,
  lazyChunkGzip: 12 * KIB,
  staticRaw: 540 * KIB,
  staticGzip: 122 * KIB,
};

function listFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const absolute = path.join(dir, entry.name);
    return entry.isDirectory() ? listFiles(absolute) : [absolute];
  });
}

function assetPathFromUrl(url) {
  const pathname = String(url || '').split(/[?#]/, 1)[0];
  assert.match(pathname, /^\/[a-z0-9_./-]+$/i, `Initial asset must be a local path: ${url}`);
  const absolute = path.resolve(PUBLIC_DIR, `.${pathname}`);
  assert.ok(absolute.startsWith(`${PUBLIC_DIR}${path.sep}`), `Initial asset escapes public/: ${url}`);
  assert.ok(fs.existsSync(absolute), `Initial asset is missing: ${url}`);
  return absolute;
}

function initialAssetPaths() {
  const indexPath = path.join(PUBLIC_DIR, 'index.html');
  const html = fs.readFileSync(indexPath, 'utf8');
  const attribute = (tag, name) => tag.match(new RegExp(`\\b${name}=["']([^"']+)["']`, 'i'))?.[1] || '';
  const styles = [...html.matchAll(/<link\b[^>]*>/gi)]
    .map(match => match[0])
    .filter(tag => attribute(tag, 'rel').split(/\s+/).includes('stylesheet'))
    .map(tag => assetPathFromUrl(attribute(tag, 'href')));
  const scripts = [...html.matchAll(/<script\b[^>]*>/gi)]
    .map(match => attribute(match[0], 'src'))
    .filter(Boolean)
    .map(assetPathFromUrl);
  return [...new Set([indexPath, ...styles, ...scripts])];
}

function measure(files) {
  return files.reduce((total, file) => {
    const content = fs.readFileSync(file);
    total.raw += content.length;
    total.gzip += gzipSync(content).length;
    return total;
  }, { raw: 0, gzip: 0 });
}

function formatBytes(bytes) {
  return `${(bytes / KIB).toFixed(1)} KiB`;
}

function assertWithin(actual, maximum, label) {
  assert.ok(
    actual <= maximum,
    `${label} is ${formatBytes(actual)}, over the ${formatBytes(maximum)} budget by ${formatBytes(actual - maximum)}`,
  );
}

const allFiles = listFiles(PUBLIC_DIR);
const initialFiles = initialAssetPaths();
const initialScripts = initialFiles.filter(file => file.endsWith('.js'));
const initialStyles = initialFiles.filter(file => file.endsWith('.css'));
const initialScriptSet = new Set(initialScripts);
const lazyScripts = allFiles.filter(file => file.endsWith('.js') && !initialScriptSet.has(file));

test('initial reader assets stay within raw and gzip budgets', () => {
  const initial = measure(initialFiles);
  const scripts = measure(initialScripts);
  const styles = measure(initialStyles);

  console.log(
    `[performance] initial=${formatBytes(initial.raw)} raw/${formatBytes(initial.gzip)} gzip; `
    + `js=${formatBytes(scripts.raw)} raw/${formatBytes(scripts.gzip)} gzip; `
    + `css=${formatBytes(styles.raw)} raw/${formatBytes(styles.gzip)} gzip`,
  );

  assertWithin(initial.raw, BUDGET.initialRaw, 'Initial payload (raw)');
  assertWithin(initial.gzip, BUDGET.initialGzip, 'Initial payload (gzip)');
  assertWithin(scripts.raw, BUDGET.initialJsRaw, 'Initial JavaScript (raw)');
  assertWithin(scripts.gzip, BUDGET.initialJsGzip, 'Initial JavaScript (gzip)');
  assertWithin(styles.raw, BUDGET.initialCssRaw, 'Initial CSS (raw)');
  assertWithin(styles.gzip, BUDGET.initialCssGzip, 'Initial CSS (gzip)');
});

test('lazy reader chunks stay separate and within budgets', () => {
  assert.ok(lazyScripts.length > 0, 'Expected admin route JavaScript to remain lazy-loaded');
  assert.equal(
    initialScripts.some(file => path.basename(file).startsWith('admin')),
    false,
    'Admin route chunks must not be loaded by index.html',
  );
  const lazy = measure(lazyScripts);
  const largest = lazyScripts
    .map(file => ({ file, ...measure([file]) }))
    .sort((a, b) => b.gzip - a.gzip)[0];

  console.log(
    `[performance] lazy-js=${formatBytes(lazy.raw)} raw/${formatBytes(lazy.gzip)} gzip; `
    + `largest=${path.relative(PUBLIC_DIR, largest.file)} ${formatBytes(largest.raw)} raw/${formatBytes(largest.gzip)} gzip`,
  );

  assertWithin(lazy.raw, BUDGET.lazyJsRaw, 'Lazy JavaScript total (raw)');
  assertWithin(lazy.gzip, BUDGET.lazyJsGzip, 'Lazy JavaScript total (gzip)');
  for (const file of lazyScripts) {
    const size = measure([file]);
    const name = path.relative(PUBLIC_DIR, file);
    assertWithin(size.raw, BUDGET.lazyChunkRaw, `Lazy chunk ${name} (raw)`);
    assertWithin(size.gzip, BUDGET.lazyChunkGzip, `Lazy chunk ${name} (gzip)`);
  }
});

test('all reader static assets stay within the resource envelope', () => {
  const total = measure(allFiles);
  console.log(`[performance] static-total=${formatBytes(total.raw)} raw/${formatBytes(total.gzip)} gzip`);

  assertWithin(total.raw, BUDGET.staticRaw, 'All static assets (raw)');
  assertWithin(total.gzip, BUDGET.staticGzip, 'All static assets (gzip)');
});
