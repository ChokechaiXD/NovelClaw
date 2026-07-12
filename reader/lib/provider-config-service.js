const path = require('node:path');
const { spawn } = require('node:child_process');

const ROOT_DIR = path.join(__dirname, '..', '..');
const PROVIDER_CONFIG_TTL_MS = 5 * 1000;
const providerConfigCache = { time: 0, data: null, inFlight: null };

function sanitizeOutput(s) {
  if (!s) return '';
  const cleaned = String(s).replace(/[^\x09\x0A\x0D\x20-\x7E\u0E00-\u0E7F\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]/g, '');
  return cleaned.length > 2000 ? cleaned.slice(0, 2000) + '...[truncated]' : cleaned;
}

function getPythonCommand() {
  return process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
}

function runProviderConfigScript(code, input = null) {
  return new Promise((resolve, reject) => {
    const child = spawn(getPythonCommand(), ['-c', code], {
      cwd: ROOT_DIR,
      windowsHide: true,
      timeout: 15_000,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
    child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(sanitizeOutput(stderr || stdout) || `Python exited ${code}`));
        return;
      }
      resolve(stdout);
    });
    if (input !== null) child.stdin.write(input);
    child.stdin.end();
  });
}

async function readProviderConfig(options = {}) {
  const refreshModels = options.refreshModels === true;
  const now = Date.now();
  if (!refreshModels && providerConfigCache.data && now - providerConfigCache.time < PROVIDER_CONFIG_TTL_MS) {
    return providerConfigCache.data;
  }
  if (!refreshModels && providerConfigCache.inFlight) return providerConfigCache.inFlight;

  const load = (async () => {
    const stdout = await runProviderConfigScript(`
import sys; sys.path.insert(0, 'tools')
from llm_router.config_providers import get_provider_config
from llm_router.config_admin import get_providers_list
import json
refresh = ${refreshModels ? 'True' : 'False'}
cfg = get_provider_config()
plist = get_providers_list(refresh=refresh)
print(json.dumps({
  "active": cfg.get("active", ""),
  "default_model": cfg.get("default_model", ""),
  "discovery_model": cfg.get("discovery_model", ""),
  "providers": plist,
  "profiles": cfg.get("profiles", []),
}, ensure_ascii=False))
    `);
    const data = JSON.parse(stdout.trim());
    if (!refreshModels || data.providers?.some(provider => provider.model_source === 'live')) {
      providerConfigCache.time = Date.now();
      providerConfigCache.data = data;
      providerConfigCache.inFlight = null;
    }
    return data;
  })().catch((err) => {
    if (!refreshModels) providerConfigCache.inFlight = null;
    throw err;
  });

  if (refreshModels) return load;
  providerConfigCache.inFlight = load;
  return providerConfigCache.inFlight;
}

function invalidateProviderConfig() {
  providerConfigCache.time = 0;
  providerConfigCache.data = null;
  providerConfigCache.inFlight = null;
}

async function saveProviderConfig(payload) {
  await runProviderConfigScript(`
import json, sys
sys.path.insert(0, 'tools')
from llm_router.config_admin import save_provider_config
payload = json.load(sys.stdin)
saved = save_provider_config(**payload)
if not saved:
    raise SystemExit(2)
print(json.dumps({"saved": True}))
  `, JSON.stringify(payload));
  invalidateProviderConfig();
  return true;
}

module.exports = {
  readProviderConfig,
  saveProviderConfig,
};
