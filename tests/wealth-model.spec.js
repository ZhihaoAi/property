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

  assert.equal(txC.price, 1513888);
  assert.equal(txC.dateLabel, 'Feb 2026');
  assert.equal(txC.sqft, 818);

  assert.equal(txE.price, 1795000);
  assert.equal(txE.dateLabel, 'Aug 2025');
  assert.equal(txE.sqft, 968);
});

test('calcBSD and calcABSD match current scenario expectations for latest LG 2B2B transaction', () => {
  const price = 1513888;

  assert.equal(calcBSD(price), 45294);
  assert.equal(calcABSD(price, { absdRate: 0.05 }), 75694);
});

test('calcLoan enforces LTV and bank cap', () => {
  const loan = calcLoan(1513888, 0.75, 1100000);

  assert.equal(loan.desiredLoan, 1135416);
  assert.equal(loan.actualLoan, 1100000);
  assert.equal(loan.capped, true);
  assert.equal(loan.downPayment, 413888);
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
