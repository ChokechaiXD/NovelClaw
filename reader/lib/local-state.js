const fs = require('node:fs/promises');
const path = require('node:path');

const { writeJsonAtomic } = require('./atomic-write');

const DEFAULT_LOCAL_STATE_PATH = path.resolve(__dirname, '../local_state.json');

function isLocalStateObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

async function readLocalState(filePath = DEFAULT_LOCAL_STATE_PATH) {
  try {
    const state = JSON.parse(await fs.readFile(filePath, 'utf8'));
    return isLocalStateObject(state) ? state : {};
  } catch (err) {
    if (err.code === 'ENOENT' || err instanceof SyntaxError) return {};
    throw err;
  }
}

async function saveLocalState(state, filePath = DEFAULT_LOCAL_STATE_PATH) {
  if (!isLocalStateObject(state)) {
    const err = new TypeError('Local state must be a JSON object');
    err.status = 400;
    err.code = 'INVALID_LOCAL_STATE';
    throw err;
  }
  await writeJsonAtomic(filePath, state);
}

module.exports = {
  DEFAULT_LOCAL_STATE_PATH,
  isLocalStateObject,
  readLocalState,
  saveLocalState,
};
