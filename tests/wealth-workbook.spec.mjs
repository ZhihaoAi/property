import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const bundledNode = path.join(
  os.homedir(),
  ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
);
const artifactToolUrl = pathToFileURL(
  path.join(
    os.homedir(),
    ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs"
  )
).href;
const workbookPath = path.join(repoRoot, "artifacts", "wealth-model.xlsx");
const gsheetsWorkbookPath = path.join(repoRoot, "artifacts", "wealth-model-gsheets.xlsx");
const wealthModel = require("../wealth-model.js");

async function importWorkbook(filePath) {
  const { FileBlob, SpreadsheetFile } = await import(artifactToolUrl);
  const blob = await FileBlob.load(filePath);
  return SpreadsheetFile.importXlsx(blob);
}

function loadDashboardData() {
  const src = fs.readFileSync(path.join(repoRoot, "data/dashboard_data.js"), "utf8");
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(src, context);
  return context.window.__DASHBOARD_DATA__;
}

function buildDefaultScenario() {
  const dashboardData = loadDashboardData();
  return wealthModel.buildScenario({
    assumptions: wealthModel.DEFAULT_ASSUMPTIONS,
    plans: wealthModel.BASE_PLANS,
    focusProjects: dashboardData.focus_projects,
  });
}

test("wealth workbook builder exports workbook with visible and support sheets", async () => {
  fs.rmSync(workbookPath, { force: true });

  execFileSync(bundledNode, ["scripts/build_wealth_model_workbook.mjs"], {
    cwd: repoRoot,
    stdio: "pipe",
  });

  assert.equal(fs.existsSync(workbookPath), true);

  const workbook = await importWorkbook(workbookPath);
  const sheetSummary = await workbook.inspect({
    kind: "sheet",
    include: "id,name",
    maxChars: 2000,
  });

  assert.match(sheetSummary.ndjson, /财富模型/);
  assert.match(sheetSummary.ndjson, /Lookups/);
  assert.match(sheetSummary.ndjson, /Calc/);

  const workbookXml = execFileSync("python3", ["-c", `
import zipfile
from pathlib import Path
path = Path(${JSON.stringify(workbookPath)})
with zipfile.ZipFile(path) as zf:
    print(zf.read("xl/workbook.xml").decode("utf-8"))
`], { encoding: "utf8" });
  assert.match(workbookXml, /name="Lookups"[^>]*state="hidden"/);
  assert.match(workbookXml, /name="Calc"[^>]*state="hidden"/);
});

test("wealth workbook default results match wealth-model output on key metrics", async () => {
  execFileSync(bundledNode, ["scripts/build_wealth_model_workbook.mjs"], {
    cwd: repoRoot,
    stdio: "pipe",
  });

  const workbook = await importWorkbook(workbookPath);
  const sheet = workbook.worksheets.getItem("财富模型");
  const resultTable = sheet.getRange("A23:Q29").values;
  const expected = buildDefaultScenario().results;

  assert.equal(resultTable[0][0], "方案");
  assert.equal(resultTable[0][15], "总财富");
  assert.equal(resultTable[0][16], "CAGR");

  expected.forEach((scenario, index) => {
    const row = resultTable[index + 1];
    assert.equal(row[0], scenario.label);
    assert.equal(row[1], scenario.projectName || "纯租房");
    assert.equal(row[2], scenario.transaction?.price || 0);
    assert.equal(row[3], scenario.transaction?.sqft || 0);
    assert.equal(row[4], scenario.loan?.actualLoan || 0);
    assert.equal(row[5], scenario.upfront?.totalCashUsed || 0);
    assert.equal(row[6], scenario.upfront?.totalCpfUsed || 0);
    assert.equal(row[7], scenario.upfront?.oaShortfallToCash || 0);
    assert.equal(row[8], scenario.wealth.fixedPhaseCashHousing);
    assert.equal(row[9], scenario.wealth.fixedPhaseOAHousing);
    assert.equal(row[10], scenario.wealth.floatPhaseCashHousing);
    assert.equal(row[11], scenario.wealth.floatPhaseOAHousing);
    assert.equal(row[12], scenario.wealth.stockFV);
    assert.equal(row[13], scenario.wealth.oaBalance);
    assert.equal(row[14], scenario.wealth.propEquity);
    assert.equal(row[15], scenario.wealth.totalWealth);
    assert.equal(row[16], scenario.wealth.totalCagr);
  });
});

test("google sheets workbook uses ASCII sheet tabs for formula compatibility", () => {
  fs.rmSync(gsheetsWorkbookPath, { force: true });

  execFileSync(bundledNode, ["scripts/build_wealth_model_workbook.mjs", "--gsheets"], {
    cwd: repoRoot,
    stdio: "pipe",
  });

  assert.equal(fs.existsSync(gsheetsWorkbookPath), true);

  const workbookInfo = execFileSync("python3", ["-c", `
import json
import re
import zipfile
from pathlib import Path
path = Path(${JSON.stringify(gsheetsWorkbookPath)})
with zipfile.ZipFile(path) as zf:
    workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
    sheet1_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    sheet3_xml = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
    print(json.dumps({
        "workbook": workbook_xml,
        "has_chinese_formula_ref_sheet1": "'财富模型'!" in sheet1_xml,
        "has_chinese_formula_ref_sheet3": "'财富模型'!" in sheet3_xml,
    }))
`], { encoding: "utf8" });

  const parsed = JSON.parse(workbookInfo);
  assert.match(parsed.workbook, /name="Model"/);
  assert.doesNotMatch(parsed.workbook, /name="财富模型"/);
  assert.equal(parsed.has_chinese_formula_ref_sheet1, false);
  assert.equal(parsed.has_chinese_formula_ref_sheet3, false);
});
