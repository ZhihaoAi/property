import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";

import { importArtifactTool } from "./artifact_tool_loader.mjs";

const require = createRequire(import.meta.url);
const wealthModel = require("../wealth-model.js");

const googleSheetsMode = process.argv.includes("--gsheets");
const MAIN_SHEET = googleSheetsMode ? "Model" : "财富模型";
const LOOKUPS_SHEET = "Lookups";
const CALC_SHEET = "Calc";
const numbersMode = process.argv.includes("--numbers");
const outputPath = path.resolve(
  googleSheetsMode
    ? "artifacts/wealth-model-gsheets.xlsx"
    : numbersMode
      ? "artifacts/wealth-model-numbers.xlsx"
      : "artifacts/wealth-model.xlsx"
);

const CPF_AGE_BANDS = [
  [35, 0.37, 0.2, 0.17, 0.6217],
  [45, 0.37, 0.2, 0.17, 0.5677],
  [50, 0.37, 0.2, 0.17, 0.5136],
  [55, 0.37, 0.2, 0.17, 0.4055],
  [60, 0.34, 0.18, 0.16, 0.353],
  [65, 0.25, 0.125, 0.125, 0.14],
  [70, 0.165, 0.075, 0.09, 0.0607],
  [999, 0.125, 0.05, 0.075, 0.08],
];

const BSD_TIERS = [
  [0, 180000, 0.01],
  [180000, 180000, 0.02],
  [360000, 640000, 0.03],
  [1000000, 500000, 0.04],
  [1500000, 1500000, 0.05],
  [3000000, 999999999, 0.06],
];

const scenarioBlocks = [
  { startCol: "A", stockCol: "B", oaCol: "C", cashCol: "D", housingOaCol: "E", investableCol: "F", loanCol: "G" },
  { startCol: "I", stockCol: "J", oaCol: "K", cashCol: "L", housingOaCol: "M", investableCol: "N", loanCol: "O" },
  { startCol: "Q", stockCol: "R", oaCol: "S", cashCol: "T", housingOaCol: "U", investableCol: "V", loanCol: "W" },
  { startCol: "Y", stockCol: "Z", oaCol: "AA", cashCol: "AB", housingOaCol: "AC", investableCol: "AD", loanCol: "AE" },
  { startCol: "AG", stockCol: "AH", oaCol: "AI", cashCol: "AJ", housingOaCol: "AK", investableCol: "AL", loanCol: "AM" },
  { startCol: "AO", stockCol: "AP", oaCol: "AQ", cashCol: "AR", housingOaCol: "AS", investableCol: "AT", loanCol: "AU" },
];

const mainCells = {
  maleAge: "B3",
  maleGross: "B4",
  maleBonus: "B5",
  maleInitialOA: "B6",
  femaleAge: "B7",
  femaleGross: "B8",
  femaleBonus: "B9",
  femaleInitialOA: "B10",
  assetsK: "E4",
  livingMonthly: "E5",
  stockAnnualReturn: "E6",
  lakevilleGrowth: "E7",
  lakeGrandeGrowth: "E8",
  rentMonthly: "E9",
  fixedRate: "E10",
  fixedYears: "E11",
  floatRate: "E12",
  simulationYears: "E13",
  loanCap: "E14",
  ltv: "E15",
  absdRate: "E16",
  legalFees: "E17",
  mandatoryCashRate: "E18",
  loanTenorYears: "E19",
  oaInterestRate: "E20",
  cpfOwCeiling: "E21",
};

const calcCells = {
  maleCash: "B1",
  maleOA: "B2",
  femaleCash: "B3",
  femaleOA: "B4",
  combinedCash: "B5",
  combinedOA: "B6",
  initialWealth: "B7",
  simMonths: "B8",
  fixedMonthsUsed: "B9",
  floatStart: "B10",
};

const calcCols = {
  label: "D",
  isRent: "E",
  price: "F",
  growthRate: "G",
  desiredLoan: "H",
  actualLoan: "I",
  loanCapped: "J",
  downPayment: "K",
  downPaymentRatio: "L",
  bsd: "M",
  absd: "N",
  mandatoryCash: "O",
  cpfEligible: "P",
  totalCpfUsed: "Q",
  oaShortfall: "R",
  totalCashUsed: "S",
  totalUpfront: "T",
  initialStock: "U",
  initialOA: "V",
  fixedMortgage: "W",
  balanceAfterFixed: "X",
  floatMortgage: "Y",
  propertyEquity: "Z",
  totalWealth: "AA",
  totalCagr: "AB",
  fixedCashAvg: "AC",
  fixedOaAvg: "AD",
  floatCashAvg: "AE",
  floatOaAvg: "AF",
  avgCashHousing: "AG",
  avgOaHousing: "AH",
  avgInvestableCash: "AI",
  stockFinal: "AJ",
  oaFinal: "AK",
};

const monthlyHeaderRow = 20;
const monthlyStartRow = 21;
const monthlyEndRow = 381;
const helperHeaderRow = 11;
const helperFirstRow = 12;

function escapeSheetName(name) {
  return `'${name.replace(/'/g, "''")}'`;
}

function absoluteCell(cell) {
  const match = /^([A-Z]+)(\d+)$/.exec(cell);
  if (!match) throw new Error(`Invalid cell reference: ${cell}`);
  return `$${match[1]}$${match[2]}`;
}

function ref(sheetName, cell) {
  return `${escapeSheetName(sheetName)}!${absoluteCell(cell)}`;
}

function calcRef(cell) {
  return ref(CALC_SHEET, cell);
}

function mainRef(cell) {
  return ref(MAIN_SHEET, cell);
}

function lookupRef(cell) {
  return ref(LOOKUPS_SHEET, cell);
}

function helperRef(col, row) {
  return calcRef(`${col}${row}`);
}

function scenarioValueRef(col, row) {
  return helperRef(col, row);
}

function loadDashboardData() {
  const src = require("node:fs").readFileSync(path.resolve("data/dashboard_data.js"), "utf8");
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(src, context);
  return context.window.__DASHBOARD_DATA__;
}

function buildDefaultScenarioRows() {
  const dashboardData = loadDashboardData();
  const scenario = wealthModel.buildScenario({
    assumptions: wealthModel.DEFAULT_ASSUMPTIONS,
    plans: wealthModel.BASE_PLANS,
    focusProjects: dashboardData.focus_projects,
  });

  return wealthModel.BASE_PLANS.map((plan) => {
    const result = scenario.results.find((item) => item.id === plan.id);
    return {
      label: plan.label,
      projectName: plan.isRent ? "纯租房" : plan.projectName,
      type: plan.isRent ? "rent" : "buy",
      price: result?.transaction?.price || 0,
      sqft: result?.transaction?.sqft || 0,
      fixedCostMonthly: plan.isRent ? 0 : plan.fixedCostMonthly,
    };
  });
}

function buildDefaultScenarioBundle() {
  const dashboardData = loadDashboardData();
  const scenario = wealthModel.buildScenario({
    assumptions: wealthModel.DEFAULT_ASSUMPTIONS,
    plans: wealthModel.BASE_PLANS,
    focusProjects: dashboardData.focus_projects,
  });

  const rows = wealthModel.BASE_PLANS.map((plan) => {
    const result = scenario.results.find((item) => item.id === plan.id);
    return {
      label: plan.label,
      projectName: plan.isRent ? "纯租房" : plan.projectName,
      type: plan.isRent ? "rent" : "buy",
      price: result?.transaction?.price || 0,
      sqft: result?.transaction?.sqft || 0,
      fixedCostMonthly: plan.isRent ? 0 : plan.fixedCostMonthly,
    };
  });

  return { scenario, rows };
}

function nestedAgeBandFormula(ageExpr, valueCol) {
  const bandRefs = CPF_AGE_BANDS.map((_, index) => ({
    age: lookupRef(`A${index + 2}`),
    value: lookupRef(`${valueCol}${index + 2}`),
  }));
  let formula = bandRefs[bandRefs.length - 1].value;
  for (let index = bandRefs.length - 2; index >= 0; index -= 1) {
    formula = `IF(${ageExpr}<=${bandRefs[index].age},${bandRefs[index].value},${formula})`;
  }
  return formula;
}

function totalRateFormula(ageExpr) {
  return nestedAgeBandFormula(ageExpr, "B");
}

function employeeRateFormula(ageExpr) {
  return nestedAgeBandFormula(ageExpr, "C");
}

function oaRatioFormula(ageExpr) {
  return nestedAgeBandFormula(ageExpr, "E");
}

function monthlyEmployeeShareFormula(grossExpr, ageExpr) {
  return `ROUNDDOWN(MIN(${grossExpr},${mainRef(mainCells.cpfOwCeiling)})*${employeeRateFormula(ageExpr)},0)`;
}

function monthlyOaCreditFormula(grossExpr, ageExpr) {
  const total = `ROUND(MIN(${grossExpr},${mainRef(mainCells.cpfOwCeiling)})*${totalRateFormula(ageExpr)},0)`;
  return `ROUND(${total}*${oaRatioFormula(ageExpr)},0)`;
}

function bonusEmployeeShareFormula(grossExpr, bonusExpr, ageExpr) {
  return `ROUNDDOWN((${grossExpr}*${bonusExpr})*${employeeRateFormula(ageExpr)},0)`;
}

function bonusOaCreditFormula(grossExpr, bonusExpr, ageExpr) {
  const bonusTotal = `ROUND((${grossExpr}*${bonusExpr})*${totalRateFormula(ageExpr)},0)`;
  return `ROUND(${bonusTotal}*${oaRatioFormula(ageExpr)},0)`;
}

function cashMonthlyFormula(grossExpr, bonusExpr, ageExpr) {
  return `${grossExpr}-${monthlyEmployeeShareFormula(grossExpr, ageExpr)}+((${grossExpr}*${bonusExpr})-${bonusEmployeeShareFormula(grossExpr, bonusExpr, ageExpr)})/12`;
}

function oaMonthlyFormula(grossExpr, bonusExpr, ageExpr) {
  return `${monthlyOaCreditFormula(grossExpr, ageExpr)}+${bonusOaCreditFormula(grossExpr, bonusExpr, ageExpr)}/12`;
}

function bsdFormula(priceExpr) {
  return `ROUND(
MAX(MIN(${priceExpr}-${lookupRef("G2")},${lookupRef("H2")}),0)*${lookupRef("I2")}+
MAX(MIN(${priceExpr}-${lookupRef("G3")},${lookupRef("H3")}),0)*${lookupRef("I3")}+
MAX(MIN(${priceExpr}-${lookupRef("G4")},${lookupRef("H4")}),0)*${lookupRef("I4")}+
MAX(MIN(${priceExpr}-${lookupRef("G5")},${lookupRef("H5")}),0)*${lookupRef("I5")}+
MAX(MIN(${priceExpr}-${lookupRef("G6")},${lookupRef("H6")}),0)*${lookupRef("I6")}+
MAX(MIN(${priceExpr}-${lookupRef("G7")},${lookupRef("H7")}),0)*${lookupRef("I7")}
,0)`;
}

function mortgagePaymentFormula(principalExpr, annualRateExpr, yearsExpr) {
  const monthsExpr = `((${yearsExpr})*12)`;
  const monthlyRateExpr = `(${annualRateExpr})/12`;
  return `IF(${principalExpr}<=0,0,IF(${yearsExpr}<=0,0,ROUND(IF(${annualRateExpr}=0,${principalExpr}/${monthsExpr},${principalExpr}*${monthlyRateExpr}*(1+${monthlyRateExpr})^${monthsExpr}/(((1+${monthlyRateExpr})^${monthsExpr})-1)),0)))`;
}

function loanBalanceFormula(principalExpr, annualRateExpr, totalYearsExpr, paidYearsExpr) {
  const totalMonthsExpr = `((${totalYearsExpr})*12)`;
  const paidMonthsExpr = `((${paidYearsExpr})*12)`;
  const monthlyRateExpr = `(${annualRateExpr})/12`;
  const paidRatioExpr = `(((${paidYearsExpr})/(${totalYearsExpr})))`;
  return `IF(${principalExpr}<=0,0,IF(${paidYearsExpr}<=0,${principalExpr},IF(${paidYearsExpr}>=${totalYearsExpr},0,IF(${annualRateExpr}=0,${principalExpr}*(1-${paidRatioExpr}),${principalExpr}*(((1+${monthlyRateExpr})^${totalMonthsExpr})-((1+${monthlyRateExpr})^${paidMonthsExpr}))/(((1+${monthlyRateExpr})^${totalMonthsExpr})-1))))))`;
}

function averageFormula(valueRange, monthRange, lowerExpr, upperExpr) {
  return `IF(OR(${upperExpr}<${lowerExpr},COUNTIFS(${monthRange},">="&${lowerExpr},${monthRange},"<="&${upperExpr})=0),0,SUMIFS(${valueRange},${monthRange},">="&${lowerExpr},${monthRange},"<="&${upperExpr})/COUNTIFS(${monthRange},">="&${lowerExpr},${monthRange},"<="&${upperExpr}))`;
}

function indexedAverageFormula(col, startExpr, endExpr) {
  const range = `${CALC_SHEET}!$${col}$${monthlyStartRow + 1}:$${col}$${monthlyEndRow}`;
  return `IF(OR(${endExpr}<${startExpr},${endExpr}<=0),0,SUM(INDEX(${range},${startExpr}):INDEX(${range},${endExpr}))/((${endExpr})-(${startExpr})+1))`;
}

function sumProductAverageFormula(valueCol, startExpr, endExpr) {
  const monthRange = `${CALC_SHEET}!$A$${monthlyStartRow + 1}:$A$${monthlyEndRow}`;
  const valueRange = `${CALC_SHEET}!$${valueCol}$${monthlyStartRow + 1}:$${valueCol}$${monthlyEndRow}`;
  return `IF(OR(${endExpr}<${startExpr},${endExpr}<=0),0,SUMPRODUCT((${monthRange}>=${startExpr})*(${monthRange}<=${endExpr})*${valueRange})/((${endExpr})-(${startExpr})+1))`;
}

function buildVisibleSheetCacheMap(defaultScenario) {
  const cache = {};
  const resultValueColumns = [
    ["E", (result) => result.loan?.actualLoan || 0],
    ["F", (result) => result.upfront?.totalCashUsed || 0],
    ["G", (result) => result.upfront?.totalCpfUsed || 0],
    ["H", (result) => result.upfront?.oaShortfallToCash || 0],
    ["I", (result) => result.wealth.fixedPhaseCashHousing],
    ["J", (result) => result.wealth.fixedPhaseOAHousing],
    ["K", (result) => result.wealth.floatPhaseCashHousing],
    ["L", (result) => result.wealth.floatPhaseOAHousing],
    ["M", (result) => result.wealth.stockFV],
    ["N", (result) => result.wealth.oaBalance],
    ["O", (result) => result.wealth.propEquity],
    ["P", (result) => result.wealth.totalWealth],
    ["Q", (result) => result.wealth.totalCagr],
  ];
  const chartValueColumns = ["T", "U", "V", "W", "X", "Y"];
  const initialWealth =
    wealthModel.DEFAULT_ASSUMPTIONS.assetsK * 1000 +
    wealthModel.DEFAULT_ASSUMPTIONS.household.male.initialOA +
    wealthModel.DEFAULT_ASSUMPTIONS.household.female.initialOA;
  const simYears = wealthModel.DEFAULT_ASSUMPTIONS.simulationYears;

  defaultScenario.results.forEach((result, index) => {
    const resultRow = 24 + index;
    const breakdownRow = 71 + index;

    resultValueColumns.forEach(([col, getter]) => {
      cache[`${col}${resultRow}`] = getter(result);
    });

    cache[`T${breakdownRow}`] = result.wealth.propEquity;
    cache[`U${breakdownRow}`] = result.wealth.stockFV;
    cache[`V${breakdownRow}`] = result.wealth.oaBalance;
  });

  for (let year = 0; year <= 30; year += 1) {
    const row = 36 + year;
    chartValueColumns.forEach((col, index) => {
      if (year === 0) {
        cache[`${col}${row}`] = initialWealth;
      } else if (year <= simYears) {
        cache[`${col}${row}`] = defaultScenario.results[index].wealth.trajectory[year - 1].totalWealth;
      } else {
        cache[`${col}${row}`] = "";
      }
    });
  }

  return cache;
}

async function postProcessWorkbook(filePath, sheetNames, visibleSheetCacheMap) {
  const cachePath = path.join(os.tmpdir(), `wealth-model-cache-${Date.now()}.json`);
  await fs.writeFile(cachePath, JSON.stringify(visibleSheetCacheMap), "utf8");
  const pythonScript = `
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

file_path = sys.argv[1]
cache_path = sys.argv[2]
sheet_names = set(sys.argv[3:])
ns_uri = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ns = {"x": ns_uri}
ET.register_namespace("x", ns_uri)

with open(cache_path, "r", encoding="utf-8") as fh:
    cache_map = json.load(fh)

with zipfile.ZipFile(file_path, "r") as src:
    workbook_xml = src.read("xl/workbook.xml").decode("utf-8")
    def repl(match):
        prefix, name, suffix = match.groups()
        if name in sheet_names and 'state=' not in suffix:
            suffix = suffix[:-2] + ' state="hidden"' + suffix[-2:]
        return prefix + name + suffix

    workbook_xml = re.sub(r'(<x:sheet name=")([^"]+)(" [^>]+/>)', repl, workbook_xml)
    if "<x:calcPr" in workbook_xml:
        workbook_xml = re.sub(
            r'<x:calcPr[^>]*/>',
            '<x:calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>',
            workbook_xml,
            count=1,
        )
    else:
        workbook_xml = workbook_xml.replace(
            "</x:workbook>",
            '<x:calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/></x:workbook>',
        )

    sheet_xml = src.read("xl/worksheets/sheet1.xml")
    sheet_root = ET.fromstring(sheet_xml)
    for cell_ref, value in cache_map.items():
        cell = sheet_root.find(f".//x:c[@r='{cell_ref}']", ns)
        if cell is None:
            continue
        if value == "":
            cell.set("t", "str")
            text_value = ""
        elif isinstance(value, (int, float)):
            cell.set("t", "n")
            text_value = str(value)
        else:
            cell.set("t", "str")
            text_value = str(value)
        value_node = cell.find("x:v", ns)
        if value_node is None:
            value_node = ET.SubElement(cell, f"{{{ns_uri}}}v")
        value_node.text = text_value

    sheet_xml = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)
    entries = [
        (info, src.read(info.filename))
        for info in src.infolist()
        if info.filename not in {"xl/workbook.xml", "xl/worksheets/sheet1.xml"}
    ]

with zipfile.ZipFile(file_path, "w") as dst:
    for info, data in entries:
        dst.writestr(info, data)
    dst.writestr("xl/workbook.xml", workbook_xml.encode("utf-8"))
    dst.writestr("xl/worksheets/sheet1.xml", sheet_xml)
`;
  try {
    execFileSync("python3", ["-c", pythonScript, filePath, cachePath, ...sheetNames], { stdio: "pipe" });
  } finally {
    await fs.rm(cachePath, { force: true });
  }
}

function buildLookupsSheet(sheet) {
  sheet.getRange("A1:E9").values = [
    ["max_age", "total_rate", "employee_rate", "employer_rate", "oa_ratio"],
    ...CPF_AGE_BANDS,
  ];

  sheet.getRange("G1:I7").values = [
    ["lower_bound", "band_size", "rate"],
    ...BSD_TIERS,
  ];

  sheet.getRange("A1:E1").format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("G1:I1").format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("B2:E9").format.numberFormat = "0.0000";
  sheet.getRange("I2:I7").format.numberFormat = "0.00%";
}

function buildMainSheet(sheet, scenarioRows, options = {}) {
  const { includeCharts = true } = options;
  const defaults = wealthModel.DEFAULT_ASSUMPTIONS;

  sheet.getRange("A1:Q1").merge();
  sheet.getRange("A1").values = [["财富模型 Excel 工作簿"]];
  sheet.getRange("A1").format = {
    fill: "#16314A",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };

  sheet.getRange("A2:Q2").merge();
  sheet.getRange("A2").values = [["黄色单元格可编辑；结果表、图表和隐藏 Calc / Lookups 会自动联动更新。"]];
  sheet.getRange("A2").format = {
    fill: "#EAF2F8",
    font: { color: "#355C7D" },
  };

  sheet.getRange("A3:B11").values = [
    ["男方年龄", defaults.household.male.purchaseAge],
    ["男方税前月工资", defaults.household.male.grossMonthly],
    ["男方年终奖（月）", defaults.household.male.annualBonusMonths],
    ["男方初始 OA", defaults.household.male.initialOA],
    ["女方年龄", defaults.household.female.purchaseAge],
    ["女方税前月工资", defaults.household.female.grossMonthly],
    ["女方年终奖（月）", defaults.household.female.annualBonusMonths],
    ["女方初始 OA", defaults.household.female.initialOA],
    ["", ""],
  ];

  sheet.getRange("D3:E21").values = [
    ["全局输入", "值"],
    ["起始投入资金（K）", defaults.assetsK],
    ["月生活费", defaults.livingMonthly],
    ["股票年化回报", defaults.stockAnnualReturn],
    ["Lakeville 年增值", defaults.lakevilleAnnualGrowth],
    ["Lake Grande 年增值", defaults.lakeGrandeAnnualGrowth],
    ["纯租房月租", defaults.rentMonthly],
    ["固定利率", defaults.fixedRate],
    ["固定期年数", defaults.fixedYears],
    ["浮动利率", defaults.floatRate],
    ["模拟年限", defaults.simulationYears],
    ["贷款上限", defaults.loanCap],
    ["LTV", defaults.ltv],
    ["ABSD", defaults.absdRate],
    ["律师费", defaults.legalFees],
    ["强制现金首付", defaults.mandatoryCashDownPaymentRate],
    ["贷款年限", defaults.loanTenorYears],
    ["OA 利率", defaults.oaInterestRate],
    ["CPF OW Ceiling", defaults.cpfOwCeilingMonthly],
  ];

  sheet.getRange("H3:N9").values = [
    ["方案", "项目", "类型", "价格", "面积 sqft", "固定月成本", "年增值"],
    ...scenarioRows.map((row) => [
      row.label,
      row.projectName,
      row.type,
      row.price,
      row.sqft,
      row.fixedCostMonthly,
      null,
    ]),
  ];

  for (let row = 4; row <= 9; row += 1) {
    const projectCell = `I${row}`;
    const growthCell = `N${row}`;
    if (row === 10) {
      sheet.getRange(growthCell).formulas = [["=0"]];
    } else {
      sheet.getRange(growthCell).formulas = [[`=IF(${projectCell}="Lakeville",$E$7,IF(${projectCell}="Lake Grande",$E$8,0))`]];
    }
  }

  sheet.getRange("H13:K18").values = [
    ["家庭现金流摘要", "男方", "女方", "合计"],
    ["月到手现金", `=${calcRef(calcCells.maleCash)}`, `=${calcRef(calcCells.femaleCash)}`, `=${calcRef(calcCells.combinedCash)}`],
    ["月 OA 入账", `=${calcRef(calcCells.maleOA)}`, `=${calcRef(calcCells.femaleOA)}`, `=${calcRef(calcCells.combinedOA)}`],
    ["起始净资产", "", "", `=${calcRef(calcCells.initialWealth)}`],
    ["模拟总月数", "", "", `=${calcRef(calcCells.simMonths)}`],
    ["固定期覆盖月数", "", "", `=${calcRef(calcCells.fixedMonthsUsed)}`],
  ];

  sheet.getRange("A23:Q23").values = [[
    "方案", "项目", "价格", "面积", "贷款", "前期现金", "前期CPF OA", "OA缺口转现金",
    "月住房现金(Y1-Y固定)", "月住房OA(Y1-Y固定)", "月住房现金(浮动期)", "月住房OA(浮动期)",
    "期末股票", "期末OA", "房产净权益", "总财富", "CAGR",
  ]];

  for (let index = 0; index < scenarioRows.length; index += 1) {
    const row = 24 + index;
    const helperRow = helperFirstRow + index;
    const scenarioRow = 4 + index;
    sheet.getRange(`A${row}:Q${row}`).formulas = [[
      `=H${scenarioRow}`,
      `=I${scenarioRow}`,
      `=K${scenarioRow}`,
      `=L${scenarioRow}`,
      `=${helperRef(calcCols.actualLoan, helperRow)}`,
      `=${helperRef(calcCols.totalCashUsed, helperRow)}`,
      `=${helperRef(calcCols.totalCpfUsed, helperRow)}`,
      `=${helperRef(calcCols.oaShortfall, helperRow)}`,
      `=${helperRef(calcCols.fixedCashAvg, helperRow)}`,
      `=${helperRef(calcCols.fixedOaAvg, helperRow)}`,
      `=${helperRef(calcCols.floatCashAvg, helperRow)}`,
      `=${helperRef(calcCols.floatOaAvg, helperRow)}`,
      `=${helperRef(calcCols.stockFinal, helperRow)}`,
      `=${helperRef(calcCols.oaFinal, helperRow)}`,
      `=${helperRef(calcCols.propertyEquity, helperRow)}`,
      `=${helperRef(calcCols.totalWealth, helperRow)}`,
      `=${helperRef(calcCols.totalCagr, helperRow)}`,
    ]];
  }

  sheet.getRange("S35:Y35").values = [[
    "Year",
    ...scenarioRows.map((row) => row.label),
  ]];

  for (let row = 36; row <= 66; row += 1) {
    const year = row - 36;
    const formulas = [`=${year}`];
    for (let index = 0; index < scenarioRows.length; index += 1) {
      const helperRow = helperFirstRow + index;
      const block = scenarioBlocks[index];
      const yearCell = `$S${row}`;
      const stockRange = `${CALC_SHEET}!$${block.stockCol}$${monthlyStartRow}:$${block.stockCol}$${monthlyEndRow}`;
      const oaRange = `${CALC_SHEET}!$${block.oaCol}$${monthlyStartRow}:$${block.oaCol}$${monthlyEndRow}`;
      const loanRange = `${CALC_SHEET}!$${block.loanCol}$${monthlyStartRow}:$${block.loanCol}$${monthlyEndRow}`;
      const propertyAtYear = `IF(${helperRef(calcCols.isRent, helperRow)}=1,0,${helperRef(calcCols.price, helperRow)}*(1+${helperRef(calcCols.growthRate, helperRow)})^${yearCell}-INDEX(${loanRange},${yearCell}*12+1))`;
      formulas.push(`=IF(${yearCell}=0,${calcRef(calcCells.initialWealth)},IF(${yearCell}>${mainRef(mainCells.simulationYears)},"",INDEX(${stockRange},${yearCell}*12+1)+INDEX(${oaRange},${yearCell}*12+1)+${propertyAtYear}))`);
    }
    sheet.getRange(`S${row}:Y${row}`).formulas = [formulas];
  }

  sheet.getRange("S70:V70").values = [["方案", "房产净权益", "期末股票", "期末OA"]];
  for (let index = 0; index < scenarioRows.length; index += 1) {
    const row = 71 + index;
    const helperRow = helperFirstRow + index;
    const scenarioRow = 4 + index;
    sheet.getRange(`S${row}:V${row}`).formulas = [[
      `=H${scenarioRow}`,
      `=${helperRef(calcCols.propertyEquity, helperRow)}`,
      `=${helperRef(calcCols.stockFinal, helperRow)}`,
      `=${helperRef(calcCols.oaFinal, helperRow)}`,
    ]];
  }

  sheet.getRange("A3:B3").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("D3:E3").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("H3:N3").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("H13:K13").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("A23:Q23").format = { fill: "#16314A", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("S35:Y35").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("S70:V70").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };

  sheet.getRange("B4:B11").format.fill = "#FFF2CC";
  sheet.getRange("E4:E21").format.fill = "#FFF2CC";
  sheet.getRange("K4:M10").format.fill = "#FFF2CC";

  sheet.getRange("B3:B10").format.numberFormat = "0";
  sheet.getRange("B4:B4").format.numberFormat = "$#,##0";
  sheet.getRange("B6:B6").format.numberFormat = "$#,##0";
  sheet.getRange("B8:B8").format.numberFormat = "$#,##0";
  sheet.getRange("B10:B10").format.numberFormat = "$#,##0";
  sheet.getRange("E4:E4").format.numberFormat = "0";
  sheet.getRange("E5:E5").format.numberFormat = "$#,##0";
  sheet.getRange("E6:E8").format.numberFormat = "0.00%";
  sheet.getRange("E9:E9").format.numberFormat = "$#,##0";
  sheet.getRange("E10:E10").format.numberFormat = "0.00%";
  sheet.getRange("E11:E11").format.numberFormat = "0";
  sheet.getRange("E12:E12").format.numberFormat = "0.00%";
  sheet.getRange("E13:E14").format.numberFormat = "0";
  sheet.getRange("E14:E14").format.numberFormat = "$#,##0";
  sheet.getRange("E15:E16").format.numberFormat = "0.00%";
  sheet.getRange("E17:E17").format.numberFormat = "$#,##0";
  sheet.getRange("E18:E18").format.numberFormat = "0.00%";
  sheet.getRange("E19:E19").format.numberFormat = "0";
  sheet.getRange("E20:E20").format.numberFormat = "0.00%";
  sheet.getRange("E21:E21").format.numberFormat = "$#,##0";
  sheet.getRange("N5:N10").format.numberFormat = "0.00%";
  sheet.getRange("A24:P30").format.numberFormat = "$#,##0";
  sheet.getRange("Q24:Q30").format.numberFormat = "0.00%";
  sheet.getRange("T36:Y66").format.numberFormat = "$#,##0";
  sheet.getRange("T71:V76").format.numberFormat = "$#,##0";
  sheet.getRange("I14:K18").format.numberFormat = "$#,##0";

  sheet.getRange("A3:Q30").format.wrapText = true;
  sheet.getRange("H13:K18").format.wrapText = true;
  sheet.getRange("A3:Q30").format.autofitColumns();
  sheet.getRange("H13:K18").format.autofitColumns();
  sheet.getRange("A23:Q30").format.rowHeightPx = 24;
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(2);

  if (includeCharts) {
    const wealthChart = sheet.charts.add("line", sheet.getRange("S35:Y66"));
    wealthChart.setPosition("S3", "AE17");

    const breakdownChart = sheet.charts.add("bar", sheet.getRange("S70:V76"));
    breakdownChart.setPosition("S19", "AE33");
  }
}

function buildCalcSheet(sheet, scenarioRows) {
  sheet.getRange("A1:B10").values = [
    ["male_cash", null],
    ["male_oa", null],
    ["female_cash", null],
    ["female_oa", null],
    ["combined_cash", null],
    ["combined_oa", null],
    ["initial_wealth", null],
    ["sim_months", null],
    ["fixed_months_used", null],
    ["float_start", null],
  ];

  sheet.getRange("C1").formulas = [[`=${totalRateFormula(mainRef(mainCells.maleAge))}`]];
  sheet.getRange("D1").formulas = [[`=${employeeRateFormula(mainRef(mainCells.maleAge))}`]];
  sheet.getRange("E1").formulas = [[`=${oaRatioFormula(mainRef(mainCells.maleAge))}`]];
  sheet.getRange("C2").formulas = [[`=${totalRateFormula(mainRef(mainCells.femaleAge))}`]];
  sheet.getRange("D2").formulas = [[`=${employeeRateFormula(mainRef(mainCells.femaleAge))}`]];
  sheet.getRange("E2").formulas = [[`=${oaRatioFormula(mainRef(mainCells.femaleAge))}`]];

  sheet.getRange("B1").formulas = [[`=${mainRef(mainCells.maleGross)}-ROUNDDOWN(MIN(${mainRef(mainCells.maleGross)},${mainRef(mainCells.cpfOwCeiling)})*${calcRef("D1")},0)+((${mainRef(mainCells.maleGross)}*${mainRef(mainCells.maleBonus)})-ROUNDDOWN((${mainRef(mainCells.maleGross)}*${mainRef(mainCells.maleBonus)})*${calcRef("D1")},0))/12`]];
  sheet.getRange("B2").formulas = [[`=ROUND(ROUND(MIN(${mainRef(mainCells.maleGross)},${mainRef(mainCells.cpfOwCeiling)})*${calcRef("C1")},0)*${calcRef("E1")},0)+ROUND(ROUND((${mainRef(mainCells.maleGross)}*${mainRef(mainCells.maleBonus)})*${calcRef("C1")},0)*${calcRef("E1")},0)/12`]];
  sheet.getRange("B3").formulas = [[`=${mainRef(mainCells.femaleGross)}-ROUNDDOWN(MIN(${mainRef(mainCells.femaleGross)},${mainRef(mainCells.cpfOwCeiling)})*${calcRef("D2")},0)+((${mainRef(mainCells.femaleGross)}*${mainRef(mainCells.femaleBonus)})-ROUNDDOWN((${mainRef(mainCells.femaleGross)}*${mainRef(mainCells.femaleBonus)})*${calcRef("D2")},0))/12`]];
  sheet.getRange("B4").formulas = [[`=ROUND(ROUND(MIN(${mainRef(mainCells.femaleGross)},${mainRef(mainCells.cpfOwCeiling)})*${calcRef("C2")},0)*${calcRef("E2")},0)+ROUND(ROUND((${mainRef(mainCells.femaleGross)}*${mainRef(mainCells.femaleBonus)})*${calcRef("C2")},0)*${calcRef("E2")},0)/12`]];
  sheet.getRange("B5").formulas = [[`=${calcRef(calcCells.maleCash)}+${calcRef(calcCells.femaleCash)}`]];
  sheet.getRange("B6").formulas = [[`=${calcRef(calcCells.maleOA)}+${calcRef(calcCells.femaleOA)}`]];
  sheet.getRange("B7").formulas = [[`=${mainRef(mainCells.assetsK)}*1000+${mainRef(mainCells.maleInitialOA)}+${mainRef(mainCells.femaleInitialOA)}`]];
  sheet.getRange("B8").formulas = [[`=${mainRef(mainCells.simulationYears)}*12`]];
  sheet.getRange("B9").formulas = [[`=MIN(${mainRef(mainCells.simulationYears)}*12,${mainRef(mainCells.fixedYears)}*12)`]];
  sheet.getRange("B10").formulas = [[`=${mainRef(mainCells.fixedYears)}*12+1`]];

  sheet.getRange(`D${helperHeaderRow}:AK${helperHeaderRow}`).values = [[
    "label", "is_rent", "price", "growth_rate", "desired_loan", "actual_loan", "loan_capped",
    "down_payment", "down_payment_ratio", "bsd", "absd", "mandatory_cash", "cpf_eligible",
    "total_cpf_used", "oa_shortfall_cash", "total_cash_used", "total_upfront", "initial_stock",
    "initial_oa", "fixed_mortgage", "balance_after_fixed", "float_mortgage", "property_equity",
    "total_wealth", "total_cagr", "fixed_cash_avg", "fixed_oa_avg", "float_cash_avg", "float_oa_avg",
    "avg_cash_housing", "avg_oa_housing", "avg_investable_cash", "stock_final", "oa_final",
  ]];

  for (let index = 0; index < scenarioRows.length; index += 1) {
    const helperRow = helperFirstRow + index;
    const mainRow = 4 + index;
    const block = scenarioBlocks[index];
    const monthRange = `${CALC_SHEET}!$${block.startCol}$${monthlyStartRow + 1}:$${block.startCol}$${monthlyEndRow}`;
    const cashRange = `${CALC_SHEET}!$${block.cashCol}$${monthlyStartRow + 1}:$${block.cashCol}$${monthlyEndRow}`;
    const housingOaRange = `${CALC_SHEET}!$${block.housingOaCol}$${monthlyStartRow + 1}:$${block.housingOaCol}$${monthlyEndRow}`;
    const investableRange = `${CALC_SHEET}!$${block.investableCol}$${monthlyStartRow + 1}:$${block.investableCol}$${monthlyEndRow}`;
    const stockRange = `${CALC_SHEET}!$${block.stockCol}$${monthlyStartRow}:$${block.stockCol}$${monthlyEndRow}`;
    const oaRange = `${CALC_SHEET}!$${block.oaCol}$${monthlyStartRow}:$${block.oaCol}$${monthlyEndRow}`;

    sheet.getRange(`D${helperRow}:AK${helperRow}`).formulas = [[
      `=${mainRef(`H${mainRow}`)}`,
      `=--(${mainRef(`J${mainRow}`)}="rent")`,
      `=${mainRef(`K${mainRow}`)}`,
      `=${mainRef(`N${mainRow}`)}`,
      `=ROUND(${scenarioValueRef(calcCols.price, helperRow)}*${mainRef(mainCells.ltv)},0)`,
      `=MIN(${scenarioValueRef(calcCols.desiredLoan, helperRow)},${mainRef(mainCells.loanCap)})`,
      `=--(${scenarioValueRef(calcCols.actualLoan, helperRow)}<${scenarioValueRef(calcCols.desiredLoan, helperRow)})`,
      `=MAX(${scenarioValueRef(calcCols.price, helperRow)}-${scenarioValueRef(calcCols.actualLoan, helperRow)},0)`,
      `=IF(${scenarioValueRef(calcCols.price, helperRow)}=0,0,${scenarioValueRef(calcCols.downPayment, helperRow)}/${scenarioValueRef(calcCols.price, helperRow)})`,
      `=${bsdFormula(scenarioValueRef(calcCols.price, helperRow))}`,
      `=ROUND(${scenarioValueRef(calcCols.price, helperRow)}*${mainRef(mainCells.absdRate)},0)`,
      `=ROUND(${scenarioValueRef(calcCols.price, helperRow)}*${mainRef(mainCells.mandatoryCashRate)},0)`,
      `=MAX(${scenarioValueRef(calcCols.downPayment, helperRow)}-${scenarioValueRef(calcCols.mandatoryCash, helperRow)},0)`,
      `=MIN(${scenarioValueRef(calcCols.cpfEligible, helperRow)},${mainRef(mainCells.maleInitialOA)}+${mainRef(mainCells.femaleInitialOA)})`,
      `=MAX(${scenarioValueRef(calcCols.cpfEligible, helperRow)}-${scenarioValueRef(calcCols.totalCpfUsed, helperRow)},0)`,
      `=${scenarioValueRef(calcCols.mandatoryCash, helperRow)}+${scenarioValueRef(calcCols.bsd, helperRow)}+${scenarioValueRef(calcCols.absd, helperRow)}+${mainRef(mainCells.legalFees)}+${scenarioValueRef(calcCols.oaShortfall, helperRow)}`,
      `=${scenarioValueRef(calcCols.totalCashUsed, helperRow)}+${scenarioValueRef(calcCols.totalCpfUsed, helperRow)}`,
      `=MAX(${mainRef(mainCells.assetsK)}*1000-${scenarioValueRef(calcCols.totalCashUsed, helperRow)},0)`,
      `=IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,${mainRef(mainCells.maleInitialOA)}+${mainRef(mainCells.femaleInitialOA)},MAX(${mainRef(mainCells.maleInitialOA)}+${mainRef(mainCells.femaleInitialOA)}-${scenarioValueRef(calcCols.totalCpfUsed, helperRow)},0))`,
      `=IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,${mortgagePaymentFormula(scenarioValueRef(calcCols.actualLoan, helperRow), mainRef(mainCells.fixedRate), mainRef(mainCells.loanTenorYears))})`,
      `=IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,${loanBalanceFormula(scenarioValueRef(calcCols.actualLoan, helperRow), mainRef(mainCells.fixedRate), mainRef(mainCells.loanTenorYears), mainRef(mainCells.fixedYears))})`,
      `=IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,${mortgagePaymentFormula(scenarioValueRef(calcCols.balanceAfterFixed, helperRow), mainRef(mainCells.floatRate), `MAX(${mainRef(mainCells.loanTenorYears)}-${mainRef(mainCells.fixedYears)},1)`)})`,
      `=IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,${scenarioValueRef(calcCols.price, helperRow)}*(1+${scenarioValueRef(calcCols.growthRate, helperRow)})^${mainRef(mainCells.simulationYears)}-IF(${mainRef(mainCells.simulationYears)}<=${mainRef(mainCells.fixedYears)},${loanBalanceFormula(scenarioValueRef(calcCols.actualLoan, helperRow), mainRef(mainCells.fixedRate), mainRef(mainCells.loanTenorYears), mainRef(mainCells.simulationYears))},${loanBalanceFormula(scenarioValueRef(calcCols.balanceAfterFixed, helperRow), mainRef(mainCells.floatRate), `MAX(${mainRef(mainCells.loanTenorYears)}-${mainRef(mainCells.fixedYears)},1)`, `${mainRef(mainCells.simulationYears)}-${mainRef(mainCells.fixedYears)}`)}))`,
      `=${scenarioValueRef(calcCols.stockFinal, helperRow)}+${scenarioValueRef(calcCols.oaFinal, helperRow)}+${scenarioValueRef(calcCols.propertyEquity, helperRow)}`,
      `=IF(OR(${calcRef(calcCells.initialWealth)}<=0,${scenarioValueRef(calcCols.totalWealth, helperRow)}<=0,${mainRef(mainCells.simulationYears)}<=0),"",(${scenarioValueRef(calcCols.totalWealth, helperRow)}/${calcRef(calcCells.initialWealth)})^(1/${mainRef(mainCells.simulationYears)})-1)`,
      `=${sumProductAverageFormula(block.cashCol, "1", calcRef(calcCells.fixedMonthsUsed))}`,
      `=${sumProductAverageFormula(block.housingOaCol, "1", calcRef(calcCells.fixedMonthsUsed))}`,
      `=${sumProductAverageFormula(block.cashCol, calcRef(calcCells.floatStart), calcRef(calcCells.simMonths))}`,
      `=${sumProductAverageFormula(block.housingOaCol, calcRef(calcCells.floatStart), calcRef(calcCells.simMonths))}`,
      `=${sumProductAverageFormula(block.cashCol, "1", calcRef(calcCells.simMonths))}`,
      `=${sumProductAverageFormula(block.housingOaCol, "1", calcRef(calcCells.simMonths))}`,
      `=${sumProductAverageFormula(block.investableCol, "1", calcRef(calcCells.simMonths))}`,
      `=INDEX(${stockRange},${calcRef(calcCells.simMonths)}+1)`,
      `=INDEX(${oaRange},${calcRef(calcCells.simMonths)}+1)`,
    ]];
  }

  for (let index = 0; index < scenarioRows.length; index += 1) {
    const helperRow = helperFirstRow + index;
    const mainRow = 4 + index;
    const block = scenarioBlocks[index];

    sheet.getRange(`${block.startCol}${monthlyHeaderRow}:${block.loanCol}${monthlyHeaderRow}`).values = [[
      `${scenarioRows[index].label} month`,
      "stock",
      "oa",
      "housing_cash",
      "housing_oa",
      "investable_cash",
      "loan_balance",
    ]];

    const monthValues = [];
    const stockFormulas = [];
    const oaFormulas = [];
    const cashFormulas = [];
    const housingOaFormulas = [];
    const investableFormulas = [];
    const loanFormulas = [];

    for (let offset = 0; offset <= 360; offset += 1) {
      const row = monthlyStartRow + offset;
      monthValues.push([offset]);

      if (offset === 0) {
        stockFormulas.push([`=${scenarioValueRef(calcCols.initialStock, helperRow)}`]);
        oaFormulas.push([`=${scenarioValueRef(calcCols.initialOA, helperRow)}`]);
        cashFormulas.push([0]);
        housingOaFormulas.push([0]);
        investableFormulas.push([0]);
        loanFormulas.push([`=${scenarioValueRef(calcCols.actualLoan, helperRow)}`]);
        continue;
      }

      const prevRow = row - 1;
      const monthCell = `${CALC_SHEET}!$${block.startCol}$${row}`;
      const stockCellPrev = `${CALC_SHEET}!$${block.stockCol}$${prevRow}`;
      const oaCellPrev = `${CALC_SHEET}!$${block.oaCol}$${prevRow}`;
      const loanPrevCell = `${CALC_SHEET}!$${block.loanCol}$${prevRow}`;
      const currentMortgage = `IF(${monthCell}<=${mainRef(mainCells.fixedYears)}*12,${scenarioValueRef(calcCols.fixedMortgage, helperRow)},${scenarioValueRef(calcCols.floatMortgage, helperRow)})`;
      const oaAvailable = `${oaCellPrev}*(1+${mainRef(mainCells.oaInterestRate)}/12)+${calcRef(calcCells.combinedOA)}`;
      const currentRate = `IF(${monthCell}<=${mainRef(mainCells.fixedYears)}*12,${mainRef(mainCells.fixedRate)},${mainRef(mainCells.floatRate)})`;
      const housingOaFormula = `IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,MIN(${oaAvailable},${currentMortgage}))`;
      const housingCashFormula = `IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,${mainRef(mainCells.rentMonthly)},${mainRef(`M${mainRow}`)}+${currentMortgage}-(${housingOaFormula}))`;
      const investableFormula = `${calcRef(calcCells.combinedCash)}-${mainRef(mainCells.livingMonthly)}-(${housingCashFormula})`;
      const nextLoanBalance = `${loanPrevCell}*(1+${currentRate}/12)-IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,${currentMortgage})`;

      stockFormulas.push([`=IF(${monthCell}>${calcRef(calcCells.simMonths)},"",MAX(${stockCellPrev}*(1+${mainRef(mainCells.stockAnnualReturn)}/12)+(${investableFormula}),0))`]);
      oaFormulas.push([`=IF(${monthCell}>${calcRef(calcCells.simMonths)},"",MAX(${oaAvailable}-(${housingOaFormula}),0))`]);
      housingOaFormulas.push([`=IF(${monthCell}>${calcRef(calcCells.simMonths)},"",${housingOaFormula})`]);
      cashFormulas.push([`=IF(${monthCell}>${calcRef(calcCells.simMonths)},"",${housingCashFormula})`]);
      investableFormulas.push([`=IF(${monthCell}>${calcRef(calcCells.simMonths)},"",${investableFormula})`]);
      loanFormulas.push([`=IF(${monthCell}>${calcRef(calcCells.simMonths)},"",IF(${scenarioValueRef(calcCols.isRent, helperRow)}=1,0,MAX(${nextLoanBalance},0)))`]);
    }

    sheet.getRange(`${block.startCol}${monthlyStartRow}:${block.startCol}${monthlyEndRow}`).values = monthValues;
    sheet.getRange(`${block.stockCol}${monthlyStartRow}:${block.stockCol}${monthlyEndRow}`).formulas = stockFormulas;
    sheet.getRange(`${block.oaCol}${monthlyStartRow}:${block.oaCol}${monthlyEndRow}`).formulas = oaFormulas;
    sheet.getRange(`${block.cashCol}${monthlyStartRow}:${block.cashCol}${monthlyEndRow}`).formulas = cashFormulas;
    sheet.getRange(`${block.housingOaCol}${monthlyStartRow}:${block.housingOaCol}${monthlyEndRow}`).formulas = housingOaFormulas;
    sheet.getRange(`${block.investableCol}${monthlyStartRow}:${block.investableCol}${monthlyEndRow}`).formulas = investableFormulas;
    sheet.getRange(`${block.loanCol}${monthlyStartRow}:${block.loanCol}${monthlyEndRow}`).formulas = loanFormulas;
  }

  sheet.getRange("A1:AK17").format.wrapText = true;
  sheet.getRange("A1:AK17").format.autofitColumns();
  sheet.getRange(`D${helperHeaderRow}:AK${helperFirstRow + scenarioRows.length - 1}`).format.numberFormat = "0.00";
  sheet.getRange(`M${helperFirstRow}:AK${helperFirstRow + scenarioRows.length - 1}`).format.numberFormat = "$#,##0";
  sheet.getRange(`AB${helperFirstRow}:AB${helperFirstRow + scenarioRows.length - 1}`).format.numberFormat = "0.00%";
}

async function main() {
  const { SpreadsheetFile, Workbook } = await importArtifactTool();
  const workbook = Workbook.create();
  const mainSheet = workbook.worksheets.add(MAIN_SHEET);
  const lookupsSheet = workbook.worksheets.add(LOOKUPS_SHEET);
  const calcSheet = workbook.worksheets.add(CALC_SHEET);
  const { scenario, rows: scenarioRows } = buildDefaultScenarioBundle();

  buildLookupsSheet(lookupsSheet);
  buildCalcSheet(calcSheet, scenarioRows);
  buildMainSheet(mainSheet, scenarioRows, { includeCharts: !(numbersMode || googleSheetsMode) });

  if (!(numbersMode || googleSheetsMode)) {
    lookupsSheet.visibility = "hidden";
    calcSheet.visibility = "hidden";
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  await postProcessWorkbook(
    outputPath,
    numbersMode || googleSheetsMode ? [] : [LOOKUPS_SHEET, CALC_SHEET],
    buildVisibleSheetCacheMap(scenario)
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
