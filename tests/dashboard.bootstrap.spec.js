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

test('dashboard bootstrap renders wealth and cost tables under a stubbed DOM', async () => {
  const html = fs.readFileSync('./index.html', 'utf8');
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
  const inlineScript = scripts[scripts.length - 1];
  const dashboardData = loadDashboardData();
  const elements = new Map();
  const ids = [
    'c_psf', 'c_tp', 'c_scatter', 'c_upfront', 'c_cashcpf', 'c_m30', 'c_m25', 'c_rate_jump',
    'c_wealth', 'c_breakdown', 'c_flow', 'c_leverage', 'c_loan', 'c_tenure',
    'core_plan_table', 'loan_cap_table', 'cost_alert_text', 'cost_detail_table', 'cost_detail_note',
    'monthly_kpis', 'monthly_detail_table', 'monthly_detail_note', 'wealth_table_card', 'assumptions_box',
    'kpi_wealth', 'ct_wealth', 'ct_breakdown', 'insight_box',
    'i_assets', 'i_male_gross', 'i_male_bonus', 'i_male_oa',
    'i_female_gross', 'i_female_bonus', 'i_female_oa',
    'i_living', 'i_stock', 'i_rate_lv', 'i_rate_lg', 'i_rent', 'i_fixed_rate', 'i_fixed_yrs',
    'i_float_rate', 'i_total_yrs',
    'lv_focus_content', 'lg_focus_content', 'overall_cagr_chart', 'focus_mapping_cards', 'ura_project_summary',
    'ura_project_compare', 'ura_transactions_table', 'ura_rental_median_table', 'ura_rental_contracts_table',
    'overall_projects_table', 'all_source_cagr_table', 'layout_projects_table', 'area_proxy_projects_table',
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
  assert.match(elements.get('wealth_table_card').innerHTML, /起始\$800K/);
  assert.match(elements.get('cost_detail_table').innerHTML, /实际 CPF OA 支出/);
  assert.doesNotMatch(elements.get('assumptions_box').innerHTML, /1997-06-25/);
  assert.equal(elements.get('i_assets').value, 800);
});
