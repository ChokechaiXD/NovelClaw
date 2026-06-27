/**
 * tests/test-static-ui.js — static frontend hygiene checks.
 *
 * Keeps generated UI strings aligned with the design system:
 *   - no inline style attributes in public JS
 *   - no inline onclick attributes in public JS
 *   - no blocking alert() calls in public JS
 *   - npm run check covers every public/js file
 */

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PUBLIC_JS = path.join(ROOT, 'public', 'js');
const PACKAGE_JSON = path.join(ROOT, 'package.json');

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
for (const file of jsFiles) {
  const normalized = rel(file);
  if (!checkScript.includes(normalized)) {
    fail(`npm run check does not cover ${normalized}`);
  }
}

if (process.exitCode) {
  process.exit(process.exitCode);
}

console.log(`Static UI checks passed (${jsFiles.length} files)`);
