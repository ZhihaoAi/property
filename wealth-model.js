(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.WealthModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const LOAN_TENOR = 30;
  const RESIDENTIAL_BSD_TIERS = [
    [180000, 0.01],
    [180000, 0.02],
    [640000, 0.03],
    [500000, 0.04],
    [1500000, 0.05],
    [Infinity, 0.06],
  ];
  // Bala's Table (SLA): leasehold value as fraction of freehold, by remaining years.
  // Used here purely to compute relative decay between two points in time;
  // absolute scale cancels out in the ratio balaFactor(remAtT) / balaFactor(remAt0).
  const BALA_TABLE = [
    [99, 0.960], [95, 0.946], [90, 0.926], [85, 0.905], [80, 0.884],
    [75, 0.857], [70, 0.830], [65, 0.800], [60, 0.768], [55, 0.733],
    [50, 0.694], [45, 0.653], [40, 0.609], [35, 0.560], [30, 0.508],
    [25, 0.451], [20, 0.389], [15, 0.320], [10, 0.241], [5, 0.147], [0, 0],
  ];

  function balaFactor(remainingYears) {
    if (remainingYears == null) return 1;
    if (remainingYears >= 99) return 0.960;
    if (remainingYears <= 0) return 0;
    for (let i = 0; i < BALA_TABLE.length - 1; i += 1) {
      const [yHi, vHi] = BALA_TABLE[i];
      const [yLo, vLo] = BALA_TABLE[i + 1];
      if (remainingYears <= yHi && remainingYears >= yLo) {
        const t = (remainingYears - yLo) / (yHi - yLo);
        return vLo + t * (vHi - vLo);
      }
    }
    return 1;
  }

  const CPF_AGE_BANDS = [
    { maxAge: 35, totalRate: 0.37, employeeRate: 0.20, employerRate: 0.17, oaRatio: 0.6217 },
    { maxAge: 45, totalRate: 0.37, employeeRate: 0.20, employerRate: 0.17, oaRatio: 0.5677 },
    { maxAge: 50, totalRate: 0.37, employeeRate: 0.20, employerRate: 0.17, oaRatio: 0.5136 },
    { maxAge: 55, totalRate: 0.37, employeeRate: 0.20, employerRate: 0.17, oaRatio: 0.4055 },
    { maxAge: 60, totalRate: 0.34, employeeRate: 0.18, employerRate: 0.16, oaRatio: 0.3530 },
    { maxAge: 65, totalRate: 0.25, employeeRate: 0.125, employerRate: 0.125, oaRatio: 0.14 },
    { maxAge: 70, totalRate: 0.165, employeeRate: 0.075, employerRate: 0.09, oaRatio: 0.0607 },
    { maxAge: Infinity, totalRate: 0.125, employeeRate: 0.05, employerRate: 0.075, oaRatio: 0.08 },
  ];
  const CPF_SPR_GG_RATE_BANDS = {
    spr_gg_year1: [
      { maxAge: 60, totalRate: 0.09, employeeRate: 0.05 },
      { maxAge: Infinity, totalRate: 0.085, employeeRate: 0.05 },
    ],
    spr_gg_year2: [
      { maxAge: 55, totalRate: 0.24, employeeRate: 0.15 },
      { maxAge: 60, totalRate: 0.185, employeeRate: 0.125 },
      { maxAge: 65, totalRate: 0.11, employeeRate: 0.075 },
      { maxAge: Infinity, totalRate: 0.085, employeeRate: 0.05 },
    ],
  };

  const DEFAULT_ASSUMPTIONS = {
    assetsK: 800,
    livingMonthly: 3000,
    stockAnnualReturn: 0.07,
    lakevilleAnnualGrowth: 0.02,
    lakeGrandeAnnualGrowth: 0.02,
    rentMonthly: 4000,
    fixedRate: 0.015,
    fixedYears: 2,
    floatRate: 0.025,
    simulationYears: 5,
    monthlyTaxGiro: 700,
    monthlyRsuAfterTax: 1100,
    customUnitSqft: null,
    customUnitPsf: null,
    loanCap: 1100000,
    ltv: 0.75,
    absdRate: 0.05,
    legalFees: 5000,
    sellerAgentCommissionRate: 0.02,
    gstRate: 0.09,
    sellerLegalFees: 3000,
    includeSellingCosts: true,
    mandatoryCashDownPaymentRate: 0.05,
    loanTenorYears: LOAN_TENOR,
    oaInterestRate: 0.025,
    cpfOwCeilingMonthly: 8000,
    useAverageBonusFlow: true,
    cpfRulesVersion: 'CPF contribution and allocation rates from 1 Jan 2026; male uses default SPR G/G rates in Y1-Y2 then full rates; simplified AW handling without AW ceiling.',
    irasRulesVersion: 'Residential BSD progressive tiers and PR first-home ABSD 5% as at 2026 assumptions.',
    applyLeaseDecay: false,
    household: {
      male: {
        dob: '1997-06-25',
        purchaseAge: 29,
        grossMonthly: 8750,
        annualBonusMonths: 1,
        initialOA: 0,
        cpfProfile: 'spr_gg',
        sprYearAtPurchase: 1,
      },
      female: {
        dob: '1986-04-22',
        purchaseAge: 40,
        grossMonthly: 4000,
        annualBonusMonths: 0,
        initialOA: 8000,
        cpfProfile: 'full',
      },
    },
  };

  const BASE_PLANS = [
    {
      id: 'A',
      name: 'LG 2B1B',
      label: 'A: LG 2B1B',
      projectName: 'Lake Grande',
      projectSlug: 'lakegrande',
      projectKey: 'lakeGrande',
      bucket: '2b1b',
      fixedCostMonthly: 360,
      color: '#55efc4',
      txUrl: 'https://www.99.co/singapore/sale/property/YTYDkuJdgRYTZvgbBgLcf9',
      fallbackTransaction: { price: 1275000, dateLabel: 'Feb2026', sqft: 613 },
      address: '3 Gateway Drive',
      topInfo: '2019（7年）',
      leaseInfo: '~94年',
      leaseRemainingYears: 94,
      mrtInfo: 'Lakeside 7min',
    },
    {
      id: 'B',
      name: 'LV 2B2B',
      label: 'B: LV 2B2B',
      projectName: 'Lakeville',
      projectSlug: 'lakeville',
      projectKey: 'lakeville',
      bucket: '2b2b',
      fixedCostMonthly: 430,
      color: '#74b9ff',
      txUrl: 'https://www.99.co/singapore/sale/property/lakeville-condo-GfhL2qN9siYLyrNcK5nboF',
      fallbackTransaction: { price: 1260000, dateLabel: 'Dec2025', sqft: 731 },
      address: '13 Jurong Lake Link',
      topInfo: '2018（8年）',
      leaseInfo: '~87年',
      leaseRemainingYears: 87,
      mrtInfo: 'Lakeside 10min',
    },
    {
      id: 'C',
      name: 'LG 2B2B',
      label: 'C: LG 2B2B',
      projectName: 'Lake Grande',
      projectSlug: 'lakegrande',
      projectKey: 'lakeGrande',
      bucket: '2b2b',
      fixedCostMonthly: 330,
      color: '#a29bfe',
      txUrl: 'https://www.99.co/singapore/sale/property/lake-grande-condo-GsAGr4gdbQvabXDFoh2pKQ',
      fallbackTransaction: { price: 1514000, dateLabel: 'Feb2026', sqft: 818 },
      address: '3 Gateway Drive',
      topInfo: '2019（7年）',
      leaseInfo: '~94年',
      leaseRemainingYears: 94,
      mrtInfo: 'Lakeside 7min',
    },
    {
      id: 'D',
      name: 'LG 3B2B',
      label: 'D: LG 3B2B',
      projectName: 'Lake Grande',
      projectSlug: 'lakegrande',
      projectKey: 'lakeGrande',
      bucket: '3b2b',
      fixedCostMonthly: 520,
      color: '#fdcb6e',
      txUrl: 'https://www.99.co/singapore/sale/property/lake-grande-condo-HbzY8PZF59oWxMm4YymJgA',
      fallbackTransaction: { price: 1739000, dateLabel: 'Jan2026', sqft: 904 },
      address: '3 Gateway Drive',
      topInfo: '2019（7年）',
      leaseInfo: '~94年',
      leaseRemainingYears: 94,
      mrtInfo: 'Lakeside 7min',
    },
    {
      id: 'E',
      name: 'LV 3B2B',
      label: 'E: LV 3B2B',
      projectName: 'Lakeville',
      projectSlug: 'lakeville',
      projectKey: 'lakeville',
      bucket: '3b2b',
      fixedCostMonthly: 530,
      color: '#81ecec',
      txUrl: 'https://www.99.co/singapore/sale/property/lakeville-condo-GNdReToNjTWUFUbYgTky7y',
      fallbackTransaction: { price: 1795000, dateLabel: 'Aug2025', sqft: 968 },
      address: '13 Jurong Lake Link',
      topInfo: '2018（8年）',
      leaseInfo: '~87年',
      leaseRemainingYears: 87,
      mrtInfo: 'Lakeside 10min',
    },
    {
      id: 'G',
      name: '自定义户型',
      label: 'G: 自定义户型',
      projectName: 'Lake Grande',
      projectSlug: 'lakegrande',
      projectKey: 'lakeGrande',
      bucket: '2b2b',
      isCustomUnit: true,
      customSourcePlanId: 'C',
      fixedCostMonthly: 330,
      color: '#ff7675',
      txUrl: 'https://www.99.co/singapore/sale/property/lake-grande-condo-GsAGr4gdbQvabXDFoh2pKQ',
      fallbackTransaction: { price: 1514000, dateLabel: 'Feb2026', sqft: 818 },
      address: '3 Gateway Drive',
      topInfo: '2019（7年）',
      leaseInfo: '~94年',
      leaseRemainingYears: 94,
      mrtInfo: 'Lakeside 7min',
    },
    {
      id: 'F',
      name: '纯租房',
      label: 'F: 纯租房',
      isRent: true,
      color: '#9e9e9e',
      dash: [6, 4],
    },
  ];

  function roundNearestDollar(value) {
    return Math.round(value);
  }

  function floorDollar(value) {
    return Math.floor(value);
  }

  function round1(value) {
    return Math.round(value * 10) / 10;
  }

  function getCpfAgeBand(age) {
    return CPF_AGE_BANDS.find((band) => age <= band.maxAge) || CPF_AGE_BANDS[CPF_AGE_BANDS.length - 1];
  }

  function getCpfSprRateBand(profile, age) {
    const bands = CPF_SPR_GG_RATE_BANDS[profile];
    return bands?.find((band) => age <= band.maxAge) || null;
  }

  function getCpfContributionProfile(age, cpfProfile = 'full') {
    const ageBand = getCpfAgeBand(age);
    const sprBand = getCpfSprRateBand(cpfProfile, age);
    if (sprBand) {
      return {
        cpfProfile,
        totalRate: sprBand.totalRate,
        employeeRate: sprBand.employeeRate,
        employerRate: sprBand.totalRate - sprBand.employeeRate,
        oaRatio: ageBand.oaRatio,
      };
    }
    return {
      cpfProfile: 'full',
      totalRate: ageBand.totalRate,
      employeeRate: ageBand.employeeRate,
      employerRate: ageBand.employerRate,
      oaRatio: ageBand.oaRatio,
    };
  }

  function resolveCpfProfileForMonth(person, month) {
    if (person?.cpfProfile !== 'spr_gg') return person?.cpfProfile || 'full';
    const startYear = Math.max(Number(person.sprYearAtPurchase || 1), 1);
    const sprYear = startYear + Math.floor((Math.max(month, 1) - 1) / 12);
    if (sprYear <= 1) return 'spr_gg_year1';
    if (sprYear === 2) return 'spr_gg_year2';
    return 'full';
  }

  function getProjectGrowthRate(plan, assumptions) {
    return plan.projectKey === 'lakeville' ? assumptions.lakevilleAnnualGrowth : assumptions.lakeGrandeAnnualGrowth;
  }

  function calcBSD(price) {
    let remaining = price;
    let duty = 0;
    for (const [bandSize, rate] of RESIDENTIAL_BSD_TIERS) {
      if (remaining <= 0) break;
      const taxable = Math.min(remaining, bandSize);
      duty += taxable * rate;
      remaining -= taxable;
    }
    return roundNearestDollar(duty);
  }

  function calcABSD(price, buyerProfile) {
    return roundNearestDollar(price * (buyerProfile?.absdRate || 0));
  }

  function positiveNumberOrNull(value) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : null;
  }

  function resolveFocusBucketTransaction(plan, focusProjects) {
    const rows = focusProjects?.[plan.projectSlug]?.recent_by_bucket?.[plan.bucket] || [];
    const latest = rows[0];
    if (!latest) return null;
    return {
      price: Number(latest.price),
      dateLabel: latest.date_label,
      sqft: Number(latest.sqft),
      psf: latest.psf != null ? Number(latest.psf) : Number(latest.price) / Number(latest.sqft),
      url: plan.txUrl || null,
      source: 'focus_project_latest',
    };
  }

  function resolveFallbackTransaction(plan) {
    const fallback = plan.fallbackTransaction || {};
    const fallbackPrice = Number(fallback.price || 0);
    const fallbackSqft = Number(fallback.sqft || 0);
    return {
      price: fallbackPrice,
      dateLabel: fallback.dateLabel || 'Fallback',
      sqft: fallbackSqft,
      psf: fallbackSqft ? fallbackPrice / fallbackSqft : null,
      url: plan.txUrl || null,
      source: 'fallback',
    };
  }

  function resolveCustomUnitTransaction(plan, focusProjects, assumptions) {
    const sourcePlan = BASE_PLANS.find((candidate) => candidate.id === plan.customSourcePlanId) || plan;
    const source = resolveFocusBucketTransaction(sourcePlan, focusProjects) || resolveFallbackTransaction(sourcePlan);
    const defaultSqft = positiveNumberOrNull(source.sqft) || positiveNumberOrNull(plan.fallbackTransaction?.sqft) || 0;
    const defaultPsf = positiveNumberOrNull(source.price) && defaultSqft
      ? source.price / defaultSqft
      : positiveNumberOrNull(source.psf) || 0;
    const sqft = positiveNumberOrNull(assumptions?.customUnitSqft) || defaultSqft;
    const psf = positiveNumberOrNull(assumptions?.customUnitPsf) || defaultPsf;
    const price = roundNearestDollar(sqft * psf);
    return {
      price,
      dateLabel: source.dateLabel,
      sqft,
      psf,
      url: plan.txUrl || source.url || null,
      source: 'custom_lg_2b2b_latest',
      customBasePrice: source.price,
      customBaseSqft: source.sqft,
      customBasePsf: defaultPsf,
    };
  }

  function resolveLatestTransaction(plan, focusProjects, assumptions = DEFAULT_ASSUMPTIONS) {
    if (!plan || plan.isRent) return null;
    if (plan.isCustomUnit) return resolveCustomUnitTransaction(plan, focusProjects, assumptions);
    return resolveFocusBucketTransaction(plan, focusProjects) || resolveFallbackTransaction(plan);
  }

  function calcLoan(price, ltv, loanCap) {
    const desiredLoan = roundNearestDollar(price * ltv);
    const actualLoan = Math.min(desiredLoan, loanCap);
    const downPayment = price - actualLoan;
    return {
      desiredLoan,
      actualLoan,
      capped: actualLoan < desiredLoan,
      downPayment,
      downPaymentRatio: price > 0 ? downPayment / price : 0,
    };
  }

  function calcCpfForWage({ wage, ageAtPurchase, owCeilingMonthly, isBonus, cpfProfile = 'full' }) {
    const band = getCpfContributionProfile(ageAtPurchase, cpfProfile);
    const contributionBase = isBonus ? wage : Math.min(wage, owCeilingMonthly);
    const totalContribution = roundNearestDollar(contributionBase * band.totalRate);
    const employeeShare = floorDollar(contributionBase * band.employeeRate);
    const employerShare = totalContribution - employeeShare;
    const oaCredit = roundNearestDollar(totalContribution * band.oaRatio);
    return {
      contributionBase,
      totalContribution,
      employeeShare,
      employerShare,
      oaCredit,
      cpfProfile: band.cpfProfile,
      totalRate: band.totalRate,
      employeeRate: band.employeeRate,
      employerRate: band.employerRate,
      oaRatio: band.oaRatio,
    };
  }

  function calcCpfMonthly({ grossMonthly, annualBonusMonths = 0, ageAtPurchase, owCeilingMonthly = DEFAULT_ASSUMPTIONS.cpfOwCeilingMonthly, cpfProfile = 'full' }) {
    const monthly = calcCpfForWage({ wage: grossMonthly, ageAtPurchase, owCeilingMonthly, isBonus: false, cpfProfile });
    const annualBonusGross = grossMonthly * annualBonusMonths;
    const bonus = calcCpfForWage({ wage: annualBonusGross, ageAtPurchase, owCeilingMonthly, isBonus: true, cpfProfile });
    return {
      ageAtPurchase,
      grossMonthly,
      annualBonusMonths,
      cpfProfile: monthly.cpfProfile,
      totalRate: monthly.totalRate,
      employeeRate: monthly.employeeRate,
      employerRate: monthly.employerRate,
      oaRatio: monthly.oaRatio,
      annualBonusGross,
      employeeShareMonthly: monthly.employeeShare,
      employerShareMonthly: monthly.employerShare,
      totalContributionMonthly: monthly.totalContribution,
      oaCreditMonthly: monthly.oaCredit,
      takeHomeMonthly: grossMonthly - monthly.employeeShare,
      employeeShareAnnualBonus: bonus.employeeShare,
      employerShareAnnualBonus: bonus.employerShare,
      totalContributionAnnualBonus: bonus.totalContribution,
      oaCreditAnnualBonus: bonus.oaCredit,
      takeHomeAnnualBonus: annualBonusGross - bonus.employeeShare,
      monthlyCashIncludingBonus: grossMonthly - monthly.employeeShare + (annualBonusGross - bonus.employeeShare) / 12,
      monthlyOAIncludingBonus: monthly.oaCredit + bonus.oaCredit / 12,
    };
  }

  function calcPersonCpfForMonth(person, month, assumptions) {
    return calcCpfMonthly({
      grossMonthly: person.grossMonthly,
      annualBonusMonths: person.annualBonusMonths,
      ageAtPurchase: person.purchaseAge,
      owCeilingMonthly: assumptions.cpfOwCeilingMonthly,
      cpfProfile: resolveCpfProfileForMonth(person, month),
    });
  }

  function calcUpfrontFunding({ price, loan, bsd, absd, legalFees, household, mandatoryCashDownPaymentRate = DEFAULT_ASSUMPTIONS.mandatoryCashDownPaymentRate }) {
    const mandatoryCash = roundNearestDollar(price * mandatoryCashDownPaymentRate);
    const cpfEligible = Math.max(loan.downPayment - mandatoryCash, 0);
    const maleInitialOA = household?.maleInitialOA || 0;
    const femaleInitialOA = household?.femaleInitialOA || 0;
    const totalOAAvailable = maleInitialOA + femaleInitialOA;
    const totalCpfUsed = Math.min(cpfEligible, totalOAAvailable);
    const oaUsedMale = Math.min(maleInitialOA, totalCpfUsed);
    const oaUsedFemale = Math.min(femaleInitialOA, totalCpfUsed - oaUsedMale);
    const oaShortfallToCash = Math.max(cpfEligible - totalCpfUsed, 0);
    const totalCashUsed = mandatoryCash + bsd + absd + legalFees + oaShortfallToCash;
    return {
      bsd,
      absd,
      legalFees,
      mandatoryCash,
      cpfEligible,
      totalCpfUsed,
      oaUsedMale,
      oaUsedFemale,
      oaShortfallToCash,
      totalCashUsed,
      totalUpfront: totalCashUsed + totalCpfUsed,
      totalOAAvailable,
    };
  }

  function mortgagePmt(principal, annualRate, years) {
    if (principal <= 0 || years <= 0) return 0;
    const r = annualRate / 12;
    const n = years * 12;
    if (r === 0) return principal / n;
    const pow = Math.pow(1 + r, n);
    return principal * r * pow / (pow - 1);
  }

  function loanBalance(principal, annualRate, totalYears, paidYears) {
    if (principal <= 0) return 0;
    const r = annualRate / 12;
    const n = totalYears * 12;
    const t = paidYears * 12;
    if (t <= 0) return principal;
    if (t >= n) return 0;
    if (r === 0) return principal * (1 - t / n);
    const pn = Math.pow(1 + r, n);
    const pt = Math.pow(1 + r, t);
    return principal * (pn - pt) / (pn - 1);
  }

  function calcPhaseMonthlyHousing({ loanAmount, fixedRate, floatRate, fixedYears, loanTenorYears, fixedCostMonthly }) {
    const maintenance = fixedCostMonthly || 0;
    const mortgageFixed = roundNearestDollar(mortgagePmt(loanAmount, fixedRate, loanTenorYears));
    const balanceAfterFixed = fixedYears > 0 ? loanBalance(loanAmount, fixedRate, loanTenorYears, fixedYears) : loanAmount;
    const remainingTenor = Math.max(loanTenorYears - fixedYears, 1);
    const mortgageFloat = roundNearestDollar(mortgagePmt(balanceAfterFixed, floatRate, remainingTenor));
    return {
      fixedPhase: {
        mortgage: mortgageFixed,
        maintenance,
        fixedCost: maintenance,
        total: mortgageFixed + maintenance,
      },
      floatPhase: {
        mortgage: mortgageFloat,
        maintenance,
        fixedCost: maintenance,
        total: mortgageFloat + maintenance,
      },
      balanceAfterFixed,
    };
  }

  function calcTotalWealthCagr(totalWealth, initialWealth, years) {
    if (!years || years <= 0 || initialWealth <= 0 || totalWealth <= 0) return null;
    return Math.pow(totalWealth / initialWealth, 1 / years) - 1;
  }

  function calcResidentialSSD(salePrice, holdingYears, marketValue = salePrice) {
    const dutiableValue = Math.max(Number(salePrice) || 0, Number(marketValue) || 0);
    const years = Number(holdingYears);
    if (!dutiableValue || !Number.isFinite(years) || years >= 4) return 0;
    let rate = 0;
    if (years < 1) rate = 0.16;
    else if (years < 2) rate = 0.12;
    else if (years < 3) rate = 0.08;
    else if (years < 4) rate = 0.04;
    return roundNearestDollar(dutiableValue * rate);
  }

  function calcSellingCosts({ salePrice, holdingYears, assumptions = DEFAULT_ASSUMPTIONS, marketValue = salePrice }) {
    if (!assumptions.includeSellingCosts || !salePrice) {
      return {
        agentCommission: 0,
        agentCommissionGst: 0,
        legalFees: 0,
        ssd: 0,
        totalSellingCosts: 0,
      };
    }
    const agentCommission = roundNearestDollar(salePrice * (assumptions.sellerAgentCommissionRate || 0));
    const agentCommissionGst = roundNearestDollar(agentCommission * (assumptions.gstRate || 0));
    const legalFees = roundNearestDollar(assumptions.sellerLegalFees || 0);
    const ssd = calcResidentialSSD(salePrice, holdingYears, marketValue);
    return {
      agentCommission,
      agentCommissionGst,
      legalFees,
      ssd,
      totalSellingCosts: agentCommission + agentCommissionGst + legalFees + ssd,
    };
  }

  function combineHouseholdCpf(assumptions) {
    const months = Math.max(Math.round((assumptions.simulationYears || 1) * 12), 1);
    const monthlySchedule = Array.from({ length: months }, (_, index) => {
      const month = index + 1;
      const male = calcPersonCpfForMonth(assumptions.household.male, month, assumptions);
      const female = calcPersonCpfForMonth(assumptions.household.female, month, assumptions);
      return {
        month,
        male,
        female,
        combinedCash: male.monthlyCashIncludingBonus + female.monthlyCashIncludingBonus,
        combinedOA: male.monthlyOAIncludingBonus + female.monthlyOAIncludingBonus,
      };
    });
    const firstMonth = monthlySchedule[0];
    return {
      male: firstMonth.male,
      female: firstMonth.female,
      combinedCashMonthly: firstMonth.combinedCash,
      combinedOAMonthly: firstMonth.combinedOA,
      monthlySchedule,
    };
  }

  function simulateScenario({
    plan,
    transaction,
    assumptions,
    householdCpf,
    upfront,
    loan,
    propertyGrowthRate,
  }) {
    const months = assumptions.simulationYears * 12;
    const fixedMonths = Math.min(months, assumptions.fixedYears * 12);
    const initialWealth = assumptions.assetsK * 1000 + assumptions.household.male.initialOA + assumptions.household.female.initialOA;
    const initialStock = Math.max(assumptions.assetsK * 1000 - (upfront?.totalCashUsed || 0), 0);
    const initialOA = plan.isRent
      ? assumptions.household.male.initialOA + assumptions.household.female.initialOA
      : Math.max((assumptions.household.male.initialOA + assumptions.household.female.initialOA) - upfront.totalCpfUsed, 0);
    const monthlyStockRate = assumptions.stockAnnualReturn / 12;
    const monthlyOARate = assumptions.oaInterestRate / 12;

    let stockBalance = initialStock;
    let oaBalance = initialOA;
    const housing = plan.isRent
      ? null
      : calcPhaseMonthlyHousing({
          loanAmount: loan.actualLoan,
          fixedRate: assumptions.fixedRate,
          floatRate: assumptions.floatRate,
          fixedYears: assumptions.fixedYears,
          loanTenorYears: assumptions.loanTenorYears,
          fixedCostMonthly: plan.fixedCostMonthly,
        });
    const fixedCashFlows = [];
    const floatCashFlows = [];
    const fixedOAFlows = [];
    const floatOAFlows = [];
    const fixedInvestmentFlows = [];
    const floatInvestmentFlows = [];
    const monthlyFlows = [];
    const trajectory = [];

    for (let month = 1; month <= months; month += 1) {
      const monthCpf = householdCpf.monthlySchedule?.[month - 1] || {
        combinedCash: householdCpf.combinedCashMonthly,
        combinedOA: householdCpf.combinedOAMonthly,
      };
      stockBalance *= 1 + monthlyStockRate;
      oaBalance *= 1 + monthlyOARate;
      oaBalance += monthCpf.combinedOA;

      let housingCash = 0;
      let housingOA = 0;
      let housingMortgageCash = 0;
      let housingMaintenanceCash = 0;
      if (plan.isRent) {
        housingCash = assumptions.rentMonthly;
      } else {
        const phase = month <= fixedMonths ? housing.fixedPhase : housing.floatPhase;
        housingOA = Math.min(oaBalance, phase.mortgage);
        oaBalance -= housingOA;
        housingMaintenanceCash = phase.maintenance;
        housingMortgageCash = phase.mortgage - housingOA;
        housingCash = housingMaintenanceCash + housingMortgageCash;
      }

      const monthlyTaxGiro = assumptions.monthlyTaxGiro || 0;
      const monthlyRsuAfterTax = assumptions.monthlyRsuAfterTax || 0;
      const investableCash = monthCpf.combinedCash + monthlyRsuAfterTax - monthlyTaxGiro - assumptions.livingMonthly - housingCash;
      stockBalance = Math.max(stockBalance + investableCash, 0);
      monthlyFlows.push({
        month,
        cpfCash: monthCpf.combinedCash,
        cpfOA: monthCpf.combinedOA,
        monthlyTaxGiro,
        monthlyRsuAfterTax,
        housingCash,
        housingOA,
        housingMortgageCash,
        housingMaintenanceCash,
        investableCash,
        stockBalance,
        oaBalance,
      });

      const inFixed = month <= fixedMonths;
      if (inFixed) {
        fixedCashFlows.push(housingCash);
        fixedOAFlows.push(housingOA);
        fixedInvestmentFlows.push(investableCash);
      } else {
        floatCashFlows.push(housingCash);
        floatOAFlows.push(housingOA);
        floatInvestmentFlows.push(investableCash);
      }

      if (month % 12 === 0 || month === months) {
        const year = month / 12;
        let leaseAdj = 1;
        if (!plan.isRent && assumptions.applyLeaseDecay && plan.leaseRemainingYears != null) {
          const remNow = plan.leaseRemainingYears;
          const remFuture = plan.leaseRemainingYears - year;
          const base = balaFactor(remNow);
          leaseAdj = base > 0 ? balaFactor(remFuture) / base : 1;
        }
        const futurePrice = plan.isRent
          ? 0
          : transaction.price * Math.pow(1 + propertyGrowthRate, year) * leaseAdj;
        const outstandingLoan = plan.isRent
          ? 0
          : (year <= assumptions.fixedYears
                ? loanBalance(loan.actualLoan, assumptions.fixedRate, assumptions.loanTenorYears, year)
                : loanBalance(
                    housing.balanceAfterFixed,
                    assumptions.floatRate,
                    Math.max(assumptions.loanTenorYears - assumptions.fixedYears, 1),
                    year - assumptions.fixedYears
                  ));
        const sellingCosts = plan.isRent
          ? calcSellingCosts({ salePrice: 0, holdingYears: year, assumptions })
          : calcSellingCosts({ salePrice: futurePrice, holdingYears: year, assumptions });
        const grossPropertyEquity = futurePrice - outstandingLoan;
        const propertyEquity = grossPropertyEquity - sellingCosts.totalSellingCosts;
        trajectory.push({
          year,
          stockBalance,
          oaBalance,
          futurePrice,
          outstandingLoan,
          grossPropertyEquity,
          sellingCosts,
          propertyEquity,
          totalWealth: stockBalance + oaBalance + propertyEquity,
        });
      }
    }

    const finalPoint = trajectory[trajectory.length - 1] || {
      stockBalance,
      oaBalance,
      futurePrice: 0,
      outstandingLoan: 0,
      grossPropertyEquity: 0,
      sellingCosts: calcSellingCosts({ salePrice: 0, holdingYears: 0, assumptions }),
      propertyEquity: 0,
      totalWealth: stockBalance + oaBalance,
    };
    const totalWealth = finalPoint.totalWealth;
    return {
      initialStock,
      initialOA,
      stockFV: finalPoint.stockBalance,
      oaBalance: finalPoint.oaBalance,
      propEquity: finalPoint.propertyEquity,
      grossPropEquity: finalPoint.grossPropertyEquity,
      futurePrice: finalPoint.futurePrice,
      outstandingLoan: finalPoint.outstandingLoan,
      sellingCosts: finalPoint.sellingCosts,
      totalWealth,
      totalCagr: calcTotalWealthCagr(totalWealth, initialWealth, assumptions.simulationYears),
      trajectory,
      monthlyFlows,
      fixedPhaseCashHousing: fixedCashFlows.length ? fixedCashFlows.reduce((sum, value) => sum + value, 0) / fixedCashFlows.length : 0,
      floatPhaseCashHousing: floatCashFlows.length ? floatCashFlows.reduce((sum, value) => sum + value, 0) / floatCashFlows.length : 0,
      fixedPhaseOAHousing: fixedOAFlows.length ? fixedOAFlows.reduce((sum, value) => sum + value, 0) / fixedOAFlows.length : 0,
      floatPhaseOAHousing: floatOAFlows.length ? floatOAFlows.reduce((sum, value) => sum + value, 0) / floatOAFlows.length : 0,
      avgCashHousing: months ? [...fixedCashFlows, ...floatCashFlows].reduce((sum, value) => sum + value, 0) / months : 0,
      avgOAHousing: months ? [...fixedOAFlows, ...floatOAFlows].reduce((sum, value) => sum + value, 0) / months : 0,
      avgInvestableCash: months ? [...fixedInvestmentFlows, ...floatInvestmentFlows].reduce((sum, value) => sum + value, 0) / months : 0,
      housing,
    };
  }

  function buildScenario({ assumptions = DEFAULT_ASSUMPTIONS, plans = BASE_PLANS, focusProjects }) {
    const householdCpf = combineHouseholdCpf(assumptions);
    const buyResults = plans.filter((plan) => !plan.isRent).map((plan) => {
      const transaction = resolveLatestTransaction(plan, focusProjects, assumptions);
      const bsd = calcBSD(transaction.price);
      const absd = calcABSD(transaction.price, { absdRate: assumptions.absdRate });
      const loan = calcLoan(transaction.price, assumptions.ltv, assumptions.loanCap);
      const upfront = calcUpfrontFunding({
        price: transaction.price,
        loan,
        bsd,
        absd,
        legalFees: assumptions.legalFees,
        household: {
          maleInitialOA: assumptions.household.male.initialOA,
          femaleInitialOA: assumptions.household.female.initialOA,
        },
        mandatoryCashDownPaymentRate: assumptions.mandatoryCashDownPaymentRate,
      });
      const propertyGrowthRate = getProjectGrowthRate(plan, assumptions);
      const wealth = simulateScenario({
        plan,
        transaction,
        assumptions,
        householdCpf,
        upfront,
        loan,
        propertyGrowthRate,
      });
      return Object.assign({}, plan, {
        maintenanceMonthly: plan.fixedCostMonthly || 0,
        transaction,
        bsd,
        absd,
        loan,
        upfront,
        sellingCosts: wealth.sellingCosts,
        propertyGrowthRate,
        householdCpf,
        wealth,
      });
    });

    const rentPlan = plans.find((plan) => plan.isRent);
    const rentResult = rentPlan
      ? Object.assign({}, rentPlan, {
          wealth: simulateScenario({
            plan: rentPlan,
            transaction: { price: 0 },
            assumptions,
            householdCpf,
            upfront: null,
            loan: { actualLoan: 0 },
            propertyGrowthRate: 0,
          }),
          householdCpf,
        })
      : null;

    const results = rentResult ? [...buyResults, rentResult] : buyResults;
    return {
      assumptions,
      householdCpf,
      results,
      buyResults,
      rentResult,
    };
  }

  function sweepScenarios({
    focusProjects,
    assumptions = DEFAULT_ASSUMPTIONS,
    plans = BASE_PLANS,
    minRate = -0.02,
    maxRate = 0.06,
    step = 0.005,
  } = {}) {
    const points = [];
    // Inclusive upper bound with tolerance to avoid float drift.
    const steps = Math.round((maxRate - minRate) / step);
    for (let i = 0; i <= steps; i += 1) {
      const rate = +(minRate + i * step).toFixed(6);
      const assumptionsAtRate = {
        ...assumptions,
        lakevilleAnnualGrowth: rate,
        lakeGrandeAnnualGrowth: rate,
      };
      const scenario = buildScenario({ assumptions: assumptionsAtRate, plans, focusProjects });
      const perPlan = {};
      scenario.buyResults.forEach((r) => {
        perPlan[r.id] = {
          totalWealth: r.wealth.totalWealth,
          propEquity: r.wealth.propEquity,
          totalCagr: r.wealth.totalCagr,
          avgCashHousing: r.wealth.avgCashHousing,
          avgOAHousing: r.wealth.avgOAHousing,
          avgInvestableCash: r.wealth.avgInvestableCash,
          totalUpfront: r.upfront ? r.upfront.totalUpfront : null,
        };
      });
      if (scenario.rentResult) {
        perPlan.F = {
          totalWealth: scenario.rentResult.wealth.totalWealth,
          propEquity: 0,
          totalCagr: scenario.rentResult.wealth.totalCagr,
          avgCashHousing: scenario.rentResult.wealth.avgCashHousing,
          avgOAHousing: scenario.rentResult.wealth.avgOAHousing,
          avgInvestableCash: scenario.rentResult.wealth.avgInvestableCash,
          totalUpfront: null,
        };
      }
      points.push({ growthRate: rate, byPlan: perPlan });
    }
    return {
      minRate,
      maxRate,
      step,
      appliesTo: ['lakeville', 'lakeGrande'],
      points,
    };
  }

  return {
    LOAN_TENOR,
    BASE_PLANS,
    DEFAULT_ASSUMPTIONS,
    getCpfAgeBand,
    resolveLatestTransaction,
    calcBSD,
    calcABSD,
    calcLoan,
    calcCpfMonthly,
    calcUpfrontFunding,
    calcResidentialSSD,
    calcSellingCosts,
    calcPhaseMonthlyHousing,
    calcTotalWealthCagr,
    buildScenario,
    sweepScenarios,
    mortgagePmt,
    loanBalance,
    round1,
    balaFactor,
    BALA_TABLE,
  };
});
