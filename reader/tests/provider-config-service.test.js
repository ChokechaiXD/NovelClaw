const assert = require('node:assert/strict');
const { readProviderConfig } = require('../lib/provider-config-service');

async function main() {
  const config = await readProviderConfig();

  assert.equal(typeof config.active, 'string');
  assert.ok(Array.isArray(config.providers));
  assert.ok(config.providers.some(provider => provider.name === 'openrouter'));
  assert.ok(config.providers.every(provider => Array.isArray(provider.models)));

  console.log('Provider config service checks passed');
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
