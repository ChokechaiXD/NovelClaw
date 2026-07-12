const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const launcher = fs.readFileSync(path.join(__dirname, '..', '..', 'run.bat'), 'utf8');

assert.match(launcher, /set "HOST=0\.0\.0\.0"/i, 'launcher must bind the reader to LAN by default');
assert.match(launcher, /set "TRUSTED_LAN=true"/i, 'launcher must enable the documented trusted-LAN mode');
assert.match(launcher, /\/api\/health/i, 'launcher must wait for the health endpoint');
assert.match(launcher, /SERVER_PID/i, 'launcher must track the process it starts');
assert.match(launcher, /NOVELCLAW_RUN_OPEN/i, 'launcher must support disabling browser auto-open');
assert.doesNotMatch(launcher, /taskkill\s+\/F\s+\/IM\s+node\.exe/i, 'launcher must never kill unrelated Node processes');

console.log('Launcher checks passed');
