/**
 * DEMO.JS — Pipeline Orchestration Harness
 * Executes end-to-end cycle:
 * 1. Pillar 1: Python Scraper & Diagram Dissector
 * 2. Pillar 2: TypeScript Pragmatic Content Compiler
 * 3. Pillar 3: JavaScript Revenue-Weighted Telemetry Optimization Engine
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const BASE_DIR = __dirname;
const DISSECTOR_PATH = path.join(BASE_DIR, 'services', 'scraper', 'dissector.py');
const FACTORY_PATH = path.join(BASE_DIR, 'services', 'compiler', 'factory.ts');
const { processTelemetryFeedback } = require(path.join(BASE_DIR, 'services', 'analytics', 'feedback.js'));

function runFullPipeline() {
  console.log(`\n===============================================================`);
  console.log(`🔥 ANARCHI-TECHNOLOGIES DUAL-ENGINE PROGRAMMATIC BLOG PIPELINE`);
  console.log(`   Host: Intel N150 (4GB RAM) | Node: local-fiber-pipe`);
  console.log(`===============================================================\n`);

  // Step 1: Dissector (Python)
  console.log(`>>> STEP 1: Running Python Stream Dissector & SHA-256 Diagram Isolation...`);
  try {
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const pyOutput = execSync(`${pythonCmd} "${DISSECTOR_PATH}"`, { encoding: 'utf-8' });
    console.log(pyOutput.trim());
  } catch (err) {
    console.error('❌ Step 1 (Dissector) failed:', err.message);
  }

  // Step 2: Content Compiler (TypeScript)
  console.log(`\n>>> STEP 2: Running TypeScript Content Compiler & WSRS / Affiliate Router...`);
  try {
    const tsOutput = execSync(`npx tsx "${FACTORY_PATH}"`, { encoding: 'utf-8' });
    console.log(tsOutput.trim());
  } catch (err) {
    console.error('❌ Step 2 (Compiler) failed:', err.message);
  }

  // Step 3: Telemetry Feedback Engine (JavaScript)
  console.log(`\n>>> STEP 3: Ingesting Telemetry & Executing Revenue Matrix Rules...`);
  const telemetryFile = path.join(BASE_DIR, 'data', 'config', 'telemetry_sample.json');
  if (fs.existsSync(telemetryFile)) {
    const telemetryData = JSON.parse(fs.readFileSync(telemetryFile, 'utf-8'));
    processTelemetryFeedback(telemetryData);
  } else {
    console.warn('⚠️ Telemetry sample file not found, skipping Step 3 execution.');
  }

  console.log(`\n===============================================================`);
  console.log(`✅ PIPELINE CYCLE COMPLETE. All data buffers and posts updated.`);
  console.log(`===============================================================\n`);
}

if (require.main === module) {
  runFullPipeline();
}

module.exports = { runFullPipeline };
