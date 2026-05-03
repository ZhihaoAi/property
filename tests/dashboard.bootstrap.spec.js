const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const wealthModel = require('../wealth-model.js');

function loadDashboardData() {
  const src = fs.readFileSync('./data/dashboard_data.js', 'utf8');
  const ctx = { window: {} };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx.window.__DASHBOARD_DATA__;
}

function buildElement(id) {
  return {
    id,
    value: '',
    innerHTML: '',
    textContent: '',
    style: {},
    checked: false,
    options: [],
    classList: { add() {}, remove() {} },
    addEventListener() {},
    appendChild(node) {
      this.options.push(node);
      return node;
    },
    remove() {},
    click() {},
    getContext() {
      return {};
    },
    querySelector() {
      return buildElement(id + ':qs');
    },
    querySelectorAll() {
      return [];
    },
    setAttribute() {},
    getAttribute() {
      return null;
    },
  };
}

function runDashboardInlineScript({ search = '?tab=s5', dashboardData = loadDashboardData(), initialValues = {} } = {}) {
  const html = fs.readFileSync('./index.html', 'utf8');
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
  const inlineScript = scripts[scripts.length - 1];
  const elements = new Map();
  const getElement = (id) => {
    if (!elements.has(id)) {
      const element = buildElement(id);
      if (Object.prototype.hasOwnProperty.call(initialValues, id)) element.value = initialValues[id];
      elements.set(id, element);
    }
    return elements.get(id);
  };
  const inputIds = [
    'i_assets', 'i_male_gross', 'i_male_bonus', 'i_male_oa',
    'i_female_gross', 'i_female_bonus', 'i_female_oa',
    'i_living', 'i_stock', 'i_rate_lv', 'i_rate_lg', 'i_rent', 'i_fixed_rate', 'i_fixed_yrs',
    'i_float_rate', 'i_total_yrs',
  ];
  const document = {
    getElementById: getElement,
    querySelectorAll(selector) {
      return selector === '.inputs input' ? inputIds.map(getElement) : [];
    },
    querySelector() {
      return buildElement('query');
    },
    createElement(tag) {
      return buildElement(tag);
    },
  };

  function ChartMock() {
    return { destroy() {} };
  }
  ChartMock.register = () => {};
  ChartMock.defaults = { color: '', borderColor: '', font: {}, plugins: { datalabels: {} } };

  const context = {
    window: {
      WealthModel: wealthModel,
      __DASHBOARD_DATA__: dashboardData,
      location: { protocol: 'file:', search },
    },
    document,
    console,
    Chart: ChartMock,
    ChartDataLabels: {},
    fetch: async () => ({ ok: true, json: async () => dashboardData }),
    setTimeout,
    clearTimeout,
    Promise,
    URL,
    URLSearchParams,
  };

  Object.assign(context.window, {
    document,
    console,
    Chart: ChartMock,
    ChartDataLabels: {},
    fetch: context.fetch,
    setTimeout,
    clearTimeout,
    URLSearchParams,
  });

  vm.createContext(context);
  vm.runInContext(inlineScript, context);
  return { context, elements };
}

test('dashboard bootstrap renders wealth and cost tables under a stubbed DOM', async () => {
  const html = fs.readFileSync('./index.html', 'utf8');
  assert.match(html, /<details class="card collapsible-card" style="margin-top:20px" id="assumptions_card">/);
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
  const inlineScript = scripts[scripts.length - 1];
  const dashboardData = loadDashboardData();
  const elements = new Map();
  const ids = [
    'c_psf', 'c_tp', 'c_scatter', 'c_upfront', 'c_cashcpf', 'c_m30', 'c_m25', 'c_rate_jump',
    'c_wealth', 'c_breakdown', 'c_flow', 'c_leverage', 'c_loan', 'c_tenure',
    'core_plan_table', 'loan_cap_table', 'cost_alert_text', 'cost_detail_table', 'cost_detail_note',
    'monthly_kpis', 'monthly_detail_table', 'monthly_detail_note', 'wealth_table_card', 'lg_2b2b_explain', 'assumptions_box',
    'kpi_wealth', 'ct_wealth', 'ct_breakdown', 'insight_box',
    'i_assets', 'i_male_gross', 'i_male_bonus', 'i_male_oa',
    'i_female_gross', 'i_female_bonus', 'i_female_oa',
    'i_living', 'i_stock', 'i_rate_lv', 'i_rate_lg', 'i_rent', 'i_fixed_rate', 'i_fixed_yrs',
    'i_float_rate', 'i_total_yrs',
    'lv_focus_content', 'lg_focus_content', 'focus_mapping_cards', 'ura_project_summary',
    'ura_project_compare', 'ura_transactions_table', 'ura_rental_median_table', 'ura_rental_contracts_table',
    'overall_cagr_chart', 'overall_yoy_chart', 'layout_cagr_chart', 'layout_yoy_chart',
    'area_proxy_cagr_chart', 'area_proxy_yoy_chart', 'owner_pool_cagr_chart', 'owner_pool_yoy_chart',
    'overall_projects_table', 'layout_projects_table', 'area_proxy_projects_table', 'owner_pool_projects_table',
    'scrape_kpis', 'scraped_projects_table', 'ura_project_select', 'ura_project_kpis', 'rental_summary_table',
    'c_rent_2b1b', 'c_rent_2b2b', 'c_rent_3b2b', 'c_rent_yield', 'rental_yield_table', 'mrt_table',
  ];
  ids.forEach((id) => elements.set(id, buildElement(id)));

  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, buildElement(id));
      return elements.get(id);
    },
    querySelectorAll(selector) {
      if (selector === '.inputs input') {
        return [
          'i_assets', 'i_male_gross', 'i_male_bonus', 'i_male_oa',
          'i_female_gross', 'i_female_bonus', 'i_female_oa',
          'i_living', 'i_stock', 'i_rate_lv', 'i_rate_lg', 'i_rent', 'i_fixed_rate', 'i_fixed_yrs',
          'i_float_rate', 'i_total_yrs',
        ].map((id) => elements.get(id));
      }
      return [];
    },
    querySelector() {
      return buildElement('query');
    },
    createElement(tag) {
      return buildElement(tag);
    },
  };

  function ChartMock() {
    return { destroy() {} };
  }
  ChartMock.register = () => {};
  ChartMock.defaults = { color: '', borderColor: '', font: {}, plugins: { datalabels: {} } };

  const context = {
    window: {
      WealthModel: wealthModel,
      __DASHBOARD_DATA__: dashboardData,
      location: { protocol: 'file:', search: '?tab=s5' },
    },
    document,
    console,
    Chart: ChartMock,
    ChartDataLabels: {},
    fetch: async () => ({ ok: true, json: async () => dashboardData }),
    setTimeout,
    clearTimeout,
    Promise,
    URL,
    URLSearchParams,
  };

  Object.assign(context.window, {
    document,
    console,
    Chart: ChartMock,
    ChartDataLabels: {},
    fetch: context.fetch,
    setTimeout,
    clearTimeout,
    URLSearchParams,
  });

  vm.createContext(context);
  vm.runInContext(inlineScript, context);
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert.match(elements.get('wealth_table_card').innerHTML, /总财富 CAGR/);
  assert.match(elements.get('wealth_table_card').innerHTML, /起始80万/);
  assert.match(elements.get('wealth_table_card').innerHTML, /前期总资金支出/);
  assert.match(elements.get('wealth_table_card').innerHTML, /class="metric-sub"[^>]*><td>现金支出/);
  assert.match(elements.get('wealth_table_card').innerHTML, /class="metric-sub"[^>]*><td>CPF OA 支出/);
  assert.match(elements.get('wealth_table_card').innerHTML, /class="metric-sub2"[^>]*><td>其中 OA 不足转现金/);
  assert.match(elements.get('lg_2b2b_explain').innerHTML, /LG 2B2B/);
  assert.match(elements.get('assumptions_box').innerHTML, /月均现金\(含年终奖摊销\)/);
  assert.match(elements.get('assumptions_box').innerHTML, /Y1 男方月均现金 \$9043 = 薪资到手 \$8350 \+ 奖金摊销 \$693/);
  assert.match(elements.get('cost_detail_table').innerHTML, /实际 CPF OA 支出/);
  assert.doesNotMatch(elements.get('assumptions_box').innerHTML, /1997-06-25/);
  assert.equal(elements.get('i_assets').value, 800);
});

test('listing valuation preserves explicit zero local CAGR', async () => {
  const dashboardData = {
    ...loadDashboardData(),
    listing_valuation: {
      default_window_months: 24,
      projects: {
        lakegrande: {
          latest_date: 'Mar2026',
          latest_date_label: 'Mar 2026',
          buckets: {
            '2b2b': {
              local_cagr: 0,
              transactions: [
                { date: 'Mar2025', sqft: 775, psf: 1000, price: 775000 },
              ],
            },
          },
        },
      },
    },
  };
  const { elements } = runDashboardInlineScript({
    search: '?tab=s14',
    dashboardData,
    initialValues: {
      decision_listing_sqft: '775',
      decision_listing_price: '775000',
      decision_listing_window: '24',
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert.match(elements.get('decision_listing_result').innerHTML, /Time-adjust:\s+0\.00% local CAGR/);
  assert.match(elements.get('decision_listing_result').innerHTML, /P50 : \$1,000/);
});
