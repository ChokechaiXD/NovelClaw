/**
 * tests/test-static-ui.js — static frontend hygiene checks.
 *
 * Keeps generated UI strings aligned with the design system:
 *   - no inline style attributes in public JS
 *   - no inline onclick attributes in public JS
 *   - no blocking alert() calls in public JS
 *   - npm run check runs the recursive JS syntax gate
 */

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PUBLIC_JS = path.join(ROOT, 'public', 'js');
const PACKAGE_JSON = path.join(ROOT, 'package.json');
const SERVER_JS = path.join(ROOT, 'server.js');
const ADMIN_JS = path.join(PUBLIC_JS, 'pages', 'admin.js');

const FORBIDDEN = [
  { label: 'inline style attribute', pattern: 'style="' },
  { label: 'inline onclick attribute', pattern: 'onclick="' },
  { label: 'blocking alert()', pattern: 'alert(' },
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

for (const file of jsFiles) {
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

const pkg = JSON.parse(fs.readFileSync(PACKAGE_JSON, 'utf8'));
const checkScript = pkg.scripts?.check || '';
if (!checkScript.includes('tests/test-js-syntax.js')) {
  fail('npm run check does not run tests/test-js-syntax.js');
}

const adminText = fs.readFileSync(ADMIN_JS, 'utf8');
if (adminText.includes('#admin/novels/')) {
  fail('admin novels edit action must link to #admin/novel-edit/<slug>');
}

const serverText = fs.readFileSync(SERVER_JS, 'utf8');
for (const missingScript of ['glossary.py', 'translate_term.py', 'novelctl.py']) {
  if (serverText.includes(missingScript)) {
    fail(`server.js references removed script ${missingScript}`);
  }
}

if (process.exitCode) {
  process.exit(process.exitCode);
}

console.log(`Static UI checks passed (${jsFiles.length} files)`);
