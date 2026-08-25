const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT_DIR = path.resolve(__dirname, '../..');
const DATA_DIR = path.join(ROOT_DIR, 'data');
const WORKER_DIR = path.join(DATA_DIR, 'workers');

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
  return dirPath;
}

function readJson(filePath, fallback = null) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    const raw = fs.readFileSync(filePath, 'utf8');
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    console.warn(`[STORE] Failed to parse ${filePath}: ${error.message}`);
    return fallback;
  }
}

function writeJson(filePath, value) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), 'utf8');
  return value;
}

function listJsonFiles(dirPath) {
  ensureDir(dirPath);
  return fs.readdirSync(dirPath)
    .filter((entry) => entry.endsWith('.json'))
    .sort();
}

function queueTask(workerName, taskType, payload = {}) {
  const queueFile = path.join(WORKER_DIR, 'queue.json');
  const queue = readJson(queueFile, { tasks: [] });
  const task = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    workerName,
    taskType,
    status: 'queued',
    createdAt: new Date().toISOString(),
    payload,
  };

  queue.tasks.push(task);
  writeJson(queueFile, queue);
  return task;
}

function getQueue() {
  return readJson(path.join(WORKER_DIR, 'queue.json'), { tasks: [] });
}

function markTaskDone(taskId, result = {}) {
  const queueFile = path.join(WORKER_DIR, 'queue.json');
  const queue = readJson(queueFile, { tasks: [] });
  queue.tasks = (queue.tasks || []).map((task) => {
    if (task.id !== taskId) return task;
    return { ...task, status: 'done', completedAt: new Date().toISOString(), result };
  });
  writeJson(queueFile, queue);
  return queue;
}

function persistArtifact(category, fileName, payload) {
  const outDir = path.join(WORKER_DIR, category);
  ensureDir(outDir);
  const targetPath = path.join(outDir, fileName);
  writeJson(targetPath, payload);
  return targetPath;
}

function serialiseHash(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex');
}

module.exports = {
  ROOT_DIR,
  DATA_DIR,
  WORKER_DIR,
  ensureDir,
  readJson,
  writeJson,
  listJsonFiles,
  queueTask,
  getQueue,
  markTaskDone,
  persistArtifact,
  serialiseHash,
};
