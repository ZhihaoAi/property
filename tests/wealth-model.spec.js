const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const {
  BASE_PLANS,
  DEFAULT_ASSUMPTIONS,
  resolveLatestTransaction,
  calcBSD,
  calcABSD,
  calcLoan,
  calcCpfMonthly,
  calcUpfrontFunding,
  buildScenario,
  calcResidentialSSD,
} = require('../wealth-model.js');

function loadDashboardData() {
  const src = fs.readFileSync('./data/dashboard_data.js', 'utf8');
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(src, context);
  return context.window.__DASHBOARD_DATA__;
}

test('resolveLatestTransaction uses latest focus bucket transaction for each plan', () => {
  const data = loadDashboardData();
  const planC = BASE_PLANS.find(plan => plan.id === 'C');
  const planE = BASE_PLANS.find(plan => plan.id === 'E');

  const txC = resolveLatestTransaction(planC, data.focus_projects);
  const txE = resolveLatestTransaction(planE, data.focus_projects);

  assert.equal(txC.price, 1480000);
  assert.equal(txC.dateLabel, 'Mar 2026');
  assert.equal(txC.sqft, 775);

  assert.equal(txE.price, 1900000);
  assert.equal(txE.dateLabel, 'Mar 2026');
  assert.equal(txE.sqft, 990);
});

test('custom unit defaults to latest LG 2B2B sqft and psf and can be overridden', () => {
  const data = loadDashboardData();
  const planG = BASE_PLANS.find(plan => plan.id === 'G');

  const defaultTx = resolveLatestTransaction(planG, data.focus_projects, DEFAULT_ASSUMPTIONS);
  const customTx = resolveLatestTransaction(planG, data.focus_projects, {
    ...DEFAULT_ASSUMPTIONS,
    customUnitSqft: 800,
    customUnitPsf: 2000,
  });

  assert.equal(planG.label, 'G: 自定义户型');
  assert.equal(defaultTx.price, 1480000);
  assert.equal(defaultTx.dateLabel, 'Mar 2026');
  assert.equal(defaultTx.sqft, 775);
  assert.equal(Math.round(defaultTx.psf), Math.round(1480000 / 775));
  assert.equal(defaultTx.source, 'custom_lg_2b2b_latest');

  assert.equal(customTx.price, 1600000);
  assert.equal(customTx.sqft, 800);
  assert.equal(customTx.psf, 2000);
});

test('calcBSD and calcABSD match current scenario expectations for latest LG 2B2B transaction', () => {
  const price = 1480000;

  assert.equal(calcBSD(price), 43800);
  assert.equal(calcABSD(price, { absdRate: 0.05 }), 74000);
});

test('calcLoan enforces LTV and bank cap', () => {
  const loan = calcLoan(1480000, 0.75, 1100000);

  assert.equal(loan.desiredLoan, 1110000);
  assert.equal(loan.actualLoan, 1100000);
  assert.equal(loan.capped, true);
  assert.equal(loan.downPayment, 380000);
});

test('calcCpfMonthly uses age band allocation and contribution caps', () => {
  const male = calcCpfMonthly({
    grossMonthly: 8750,
    annualBonusMonths: 1,
    ageAtPurchase: 29,
  });
  const female = calcCpfMonthly({
    grossMonthly: 4000,
    annualBonusMonths: 0,
    ageAtPurchase: 40,
  });

  assert.equal(male.employeeShareMonthly, 1600);
  assert.equal(male.employerShareMonthly, 1360);
  assert.equal(male.oaCreditMonthly, 1840);
  assert.equal(male.takeHomeMonthly, 7150);
  assert.equal(male.oaCreditAnnualBonus, 2013);

  assert.equal(female.employeeShareMonthly, 800);
  assert.equal(female.employerShareMonthly, 680);
  assert.equal(female.oaCreditMonthly, 840);
  assert.equal(female.takeHomeMonthly, 3200);
});

test('male default CPF schedule uses first-year SPR G/G then second-year SPR then full rates', () => {
  const data = loadDashboardData();
  const scenario = buildScenario({
    assumptions: DEFAULT_ASSUMPTIONS,
    plans: BASE_PLANS,
    focusProjects: data.focus_projects,
  });

  const y1 = scenario.householdCpf.monthlySchedule[0].male;
  const y2 = scenario.householdCpf.monthlySchedule[12].male;
  const y3 = scenario.householdCpf.monthlySchedule[24].male;

  assert.equal(y1.employeeShareMonthly, 400);
  assert.equal(y1.employerShareMonthly, 320);
  assert.equal(y1.oaCreditMonthly, 448);
  assert.equal(Math.round(y1.monthlyCashIncludingBonus), 9043);
  assert.equal(Math.round(y1.monthlyOAIncludingBonus), 489);

  assert.equal(y2.employeeShareMonthly, 1200);
  assert.equal(y2.employerShareMonthly, 720);
  assert.equal(y2.oaCreditMonthly, 1194);
  assert.equal(Math.round(y2.monthlyCashIncludingBonus), 8170);
  assert.equal(Math.round(y2.monthlyOAIncludingBonus), 1303);

  assert.equal(y3.employeeShareMonthly, 1600);
  assert.equal(y3.employerShareMonthly, 1360);
  assert.equal(y3.oaCreditMonthly, 1840);
  assert.equal(Math.round(y3.monthlyCashIncludingBonus), 7733);
  assert.equal(Math.round(y3.monthlyOAIncludingBonus), 2008);
});

test('default female initial OA is 8000 and offsets LG 2B2B CPF-eligible down payment', () => {
  const data = loadDashboardData();
  const scenario = buildScenario({
    assumptions: DEFAULT_ASSUMPTIONS,
    plans: BASE_PLANS,
    focusProjects: data.focus_projects,
  });
  const result = scenario.buyResults.find(plan => plan.id === 'C');

  assert.equal(DEFAULT_ASSUMPTIONS.household.female.initialOA, 8000);
  assert.equal(result.transaction.price, 1480000);
  assert.equal(result.loan.actualLoan, 1100000);
  assert.equal(result.loan.downPayment, 380000);
  assert.equal(result.upfront.bsd, 43800);
  assert.equal(result.upfront.absd, 74000);
  assert.equal(result.upfront.legalFees, 5000);
  assert.equal(result.upfront.mandatoryCash, 74000);
  assert.equal(result.upfront.cpfEligible, 306000);
  assert.equal(result.upfront.totalCpfUsed, 8000);
  assert.equal(result.upfront.oaUsedFemale, 8000);
  assert.equal(result.upfront.oaShortfallToCash, 298000);
  assert.equal(result.upfront.totalCashUsed, 494800);
  assert.equal(result.upfront.totalUpfront, 502800);
});

test('default property equity deducts seller commission GST legal fees and SSD when selling at simulation end', () => {
  const data = loadDashboardData();
  const scenario = buildScenario({
    assumptions: DEFAULT_ASSUMPTIONS,
    plans: BASE_PLANS,
    focusProjects: data.focus_projects,
  });
  const result = scenario.buyResults.find(plan => plan.id === 'C');
  const finalPoint = result.wealth.trajectory[result.wealth.trajectory.length - 1];

  assert.equal(result.sellingCosts.ssd, 0);
  assert.equal(calcResidentialSSD(1000000, 0.5), 160000);
  assert.equal(calcResidentialSSD(1000000, 1.5), 120000);
  assert.equal(calcResidentialSSD(1000000, 2.5), 80000);
  assert.equal(calcResidentialSSD(1000000, 3.5), 40000);
  assert.equal(calcResidentialSSD(1000000, 4), 0);

  const expectedCommission = Math.round(finalPoint.futurePrice * 0.02);
  const expectedGst = Math.round(expectedCommission * 0.09);
  assert.equal(result.sellingCosts.agentCommission, expectedCommission);
  assert.equal(result.sellingCosts.agentCommissionGst, expectedGst);
  assert.equal(result.sellingCosts.legalFees, 3000);
  assert.equal(result.wealth.propEquity, result.wealth.grossPropEquity - result.sellingCosts.totalSellingCosts);
  assert.equal(result.wealth.totalWealth, result.wealth.stockFV + result.wealth.oaBalance + result.wealth.propEquity);
});

test('LG 2B2B monthly housing cost separates mortgage cash, CPF OA, and MCST maintenance', () => {
  const data = loadDashboardData();
  const scenario = buildScenario({
    assumptions: DEFAULT_ASSUMPTIONS,
    plans: BASE_PLANS,
    focusProjects: data.focus_projects,
  });
  const result = scenario.buyResults.find(plan => plan.id === 'C');
  const firstMonth = result.wealth.monthlyFlows[0];

  assert.equal(result.fixedCostMonthly, 330);
  assert.equal(result.maintenanceMonthly, 330);
  assert.equal(result.wealth.housing.fixedPhase.maintenance, 330);
  assert.equal(result.wealth.housing.fixedPhase.total, result.wealth.housing.fixedPhase.mortgage + 330);
  assert.equal(firstMonth.housingMaintenanceCash, 330);
  assert.equal(firstMonth.housingMortgageCash + firstMonth.housingOA, result.wealth.housing.fixedPhase.mortgage);
  assert.equal(firstMonth.housingCash, firstMonth.housingMortgageCash + firstMonth.housingMaintenanceCash);
});

test('monthly investable cash includes tax GIRO and after-tax RSU cashflow', () => {
  const data = loadDashboardData();
  const scenario = buildScenario({
    assumptions: DEFAULT_ASSUMPTIONS,
    plans: BASE_PLANS,
    focusProjects: data.focus_projects,
  });
  const result = scenario.buyResults.find(plan => plan.id === 'C');
  const firstMonth = result.wealth.monthlyFlows[0];

  assert.equal(DEFAULT_ASSUMPTIONS.simulationYears, 5);
  assert.equal(DEFAULT_ASSUMPTIONS.monthlyTaxGiro, 700);
  assert.equal(DEFAULT_ASSUMPTIONS.monthlyRsuAfterTax, 1100);
  assert.equal(firstMonth.monthlyTaxGiro, 700);
  assert.equal(firstMonth.monthlyRsuAfterTax, 1100);
  assert.equal(
    firstMonth.investableCash,
    firstMonth.cpfCash + firstMonth.monthlyRsuAfterTax - firstMonth.monthlyTaxGiro - DEFAULT_ASSUMPTIONS.livingMonthly - firstMonth.housingCash
  );
});

test('calcUpfrontFunding converts CPF shortfall into cash when OA is zero', () => {
  const data = loadDashboardData();
  const planC = BASE_PLANS.find(plan => plan.id === 'C');
  const txC = resolveLatestTransaction(planC, data.focus_projects);
  const loan = calcLoan(txC.price, DEFAULT_ASSUMPTIONS.ltv, DEFAULT_ASSUMPTIONS.loanCap);
  const bsd = calcBSD(txC.price);
  const absd = calcABSD(txC.price, { absdRate: DEFAULT_ASSUMPTIONS.absdRate });

  const funding = calcUpfrontFunding({
    price: txC.price,
    loan,
    bsd,
    absd,
    legalFees: DEFAULT_ASSUMPTIONS.legalFees,
    household: {
      maleInitialOA: 0,
      femaleInitialOA: 0,
    },
  });

  assert.equal(funding.totalCpfUsed, 0);
  assert.equal(funding.oaShortfallToCash, funding.cpfEligible);
  assert.equal(funding.totalCashUsed, funding.mandatoryCash + funding.bsd + funding.absd + funding.legalFees + funding.cpfEligible);
});
