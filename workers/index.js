const path = require('path');
const { ensureDir, WORKER_DIR } = require('./shared/store');

ensureDir(path.join(WORKER_DIR, 'research'));
ensureDir(path.join(WORKER_DIR, 'outreach'));
ensureDir(path.join(WORKER_DIR, 'crawler'));
ensureDir(path.join(WORKER_DIR, 'compiler'));

const workers = [
  'research-bot',
  'outreach-bot',
  'crawler-bot',
  'compiler-bot',
];

console.log('[WORKERS] Starting orchestrator...');

for (const workerName of workers) {
  const workerPath = path.join(__dirname, `${workerName}.js`);
  console.log(`[WORKERS] Launching ${workerName}`);
  require(workerPath);
}

console.log('[WORKERS] All workers have been scheduled and their output is stored under data/workers');
