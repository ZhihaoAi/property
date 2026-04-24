#!/usr/bin/env node
// Runs wealth-model sweepScenarios using current dashboard_data.js as focus input,
// emits a JSON object to stdout with { sensitivity: {...} } suitable for merging
// into dashboard_data.json.

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const require = createRequire(import.meta.url);

const wealth = require(path.join(repoRoot, 'wealth-model.js'));
const dashboardJsPath = path.join(repoRoot, 'data', 'dashboard_data.js');
const ctx = { window: {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(dashboardJsPath, 'utf8'), ctx);
const dashboard = ctx.window.__DASHBOARD_DATA__;
if (!dashboard || !dashboard.focus_projects) {
  console.error('ERR: dashboard_data.js missing focus_projects');
  process.exit(1);
}

const sweep = wealth.sweepScenarios({
  focusProjects: dashboard.focus_projects,
  minRate: -0.02,
  maxRate: 0.06,
  step: 0.005,
});

const planLabels = wealth.BASE_PLANS.map((p) => ({ id: p.id, label: p.label, color: p.color, isRent: !!p.isRent }));

const output = {
  sensitivity: {
    generated_at: new Date().toISOString(),
    assumptions_note: 'Sweep varies lakevilleAnnualGrowth and lakeGrandeAnnualGrowth together. Other DEFAULT_ASSUMPTIONS unchanged. Here r is treated as all-in resale CAGR, so no extra lease-decay factor is applied in the main wealth curve.',
    min_rate: sweep.minRate,
    max_rate: sweep.maxRate,
    step: sweep.step,
    plan_labels: planLabels,
    points: sweep.points,
  },
};

process.stdout.write(JSON.stringify(output, null, 2));
