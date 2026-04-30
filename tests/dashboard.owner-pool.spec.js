const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function loadDashboardData() {
  const src = fs.readFileSync('./data/dashboard_data.js', 'utf8');
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(src, context);
  return context.window.__DASHBOARD_DATA__;
}

function addMonths(monthKey, offset) {
  const [year, month] = monthKey.split('-').map(Number);
  const total = year * 12 + (month - 1) + offset;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, '0')}`;
}

function findRolling3yMonth(metric) {
  return Object.keys(metric.ttm_monthly || {}).sort().find((monthKey) => {
    const current = metric.ttm_monthly[monthKey]?.median_psf;
    const prior = metric.ttm_monthly[addMonths(monthKey, -36)]?.median_psf;
    return current > 0 && prior > 0;
  });
}

function computeRolling3yCagr(metric, monthKey) {
  const current = metric.ttm_monthly[monthKey].median_psf;
  const prior = metric.ttm_monthly[addMonths(monthKey, -36)].median_psf;
  return Math.round((Math.pow(current / prior, 1 / 3) - 1) * 10000) / 100;
}

test('focus projects expose owner-pool metrics and confidence metadata', () => {
  const data = loadDashboardData();
  const project = data.focus_projects.lakeville;
  const lakeGrande = data.focus_projects.lakegrande;

  assert.ok(project.owner_pool_direct);
  assert.ok(project.owner_pool_filled);
  assert.ok(project.type_breakout);
  assert.ok(project.type_breakout['2b1b']);
  assert.ok(project.type_breakout['2b2b']);
  assert.ok(project.overall_reference);
  assert.ok(project.data_confidence);
  assert.equal(typeof project.data_confidence.coverage_pct, 'number');
  assert.equal(typeof project.data_confidence.recent_24m_count, 'number');
  assert.match(project.owner_pool_filled.provenance, /^(direct_2b2b|direct_owner_pool|area_proxy|overall_fallback)$/);
  assert.ok(project.owner_pool_filled.current);
  assert.equal(typeof project.owner_pool_filled.current_yoy, 'number');
  assert.equal(typeof project.owner_pool_filled.lifetime_cagr, 'number');
  assert.ok(project.owner_pool_filled.cagr_monthly);
  assert.ok(project.owner_pool_filled.rolling_3y_cagr_monthly);
  assert.ok(project.owner_pool_filled.yoy_monthly);
  assert.equal(project.owner_pool_filled.current_yoy, project.owner_pool_filled.yoy_monthly[Object.keys(project.owner_pool_filled.yoy_monthly).sort().at(-1)]);
  assert.equal(project.owner_pool_filled.all_time_cagr, project.owner_pool_filled.cagr_monthly[Object.keys(project.owner_pool_filled.cagr_monthly).sort().at(-1)]);

  [project, lakeGrande].forEach((focusProject) => {
    assert.ok(focusProject);
    assert.match(focusProject.slug, /^(lakeville|lakegrande)$/);
    assert.equal(typeof focusProject.name, 'string');
    ['2b1b', '2b2b'].forEach((bucket) => {
      const metric = focusProject.type_breakout[bucket];
      assert.ok(metric, `${focusProject.slug} missing ${bucket}`);
      assert.ok(metric.cagr_monthly, `${focusProject.slug} ${bucket} missing cagr_monthly`);
      assert.ok(metric.rolling_3y_cagr_monthly, `${focusProject.slug} ${bucket} missing rolling_3y_cagr_monthly`);
      assert.ok(metric.yoy_monthly, `${focusProject.slug} ${bucket} missing yoy_monthly`);
      assert.ok(metric.current, `${focusProject.slug} ${bucket} missing current metric`);
    });
  });
});

test('dashboard payload exposes four PK lenses with unified all-time CAGR, rolling 3Y CAGR, and YoY fields', () => {
  const data = loadDashboardData();
  const firstOwnerPool = data.comparison_projects[0];
  const firstOverall = data.overall_comparison_projects[0];
  const firstAreaProxy = data.area_proxy_comparison_projects[0];
  const firstLayout = data.layout_comparison_projects[0];

  assert.ok(Array.isArray(data.comparison_projects));
  assert.ok(Array.isArray(data.overall_comparison_projects));
  assert.ok(Array.isArray(data.area_proxy_comparison_projects));
  assert.ok(Array.isArray(data.layout_comparison_projects));

  assert.ok(firstOwnerPool.owner_pool_filled);
  assert.equal(typeof firstOwnerPool.all_time_cagr, 'number');
  assert.equal(typeof firstOwnerPool.current_yoy, 'number');
  assert.equal(typeof firstOwnerPool.current_psf, 'number');
  assert.equal(typeof firstOwnerPool.sample_count, 'number');
  assert.ok(firstOwnerPool.cagr_monthly);
  assert.ok(firstOwnerPool.rolling_3y_cagr_monthly);
  assert.ok(firstOwnerPool.yoy_monthly);

  assert.equal(typeof firstOverall.all_time_cagr, 'number');
  assert.equal(typeof firstOverall.current_yoy, 'number');
  assert.equal(typeof firstOverall.current_psf, 'number');
  assert.equal(typeof firstOverall.sample_count, 'number');
  assert.ok(firstOverall.cagr_monthly);
  assert.ok(firstOverall.rolling_3y_cagr_monthly);
  assert.ok(firstOverall.yoy_monthly);

  assert.equal(typeof firstAreaProxy.all_time_cagr, 'number');
  assert.equal(typeof firstAreaProxy.current_yoy, 'number');
  assert.equal(typeof firstAreaProxy.current_psf, 'number');
  assert.equal(typeof firstAreaProxy.sample_count, 'number');
  assert.ok(firstAreaProxy.cagr_monthly);
  assert.ok(firstAreaProxy.rolling_3y_cagr_monthly);
  assert.ok(firstAreaProxy.yoy_monthly);

  assert.equal(typeof firstLayout.all_time_cagr, 'number');
  assert.equal(typeof firstLayout.current_yoy, 'number');
  assert.equal(typeof firstLayout.current_psf, 'number');
  assert.equal(typeof firstLayout.sample_count, 'number');
  assert.ok(firstLayout.cagr_monthly);
  assert.ok(firstLayout.rolling_3y_cagr_monthly);
  assert.ok(firstLayout.yoy_monthly);

  assert.equal(data.meta.pk_project_count, data.comparison_projects.length);
  assert.equal(data.meta.area_proxy_comparison_project_count, data.area_proxy_comparison_projects.length);
  assert.ok(data.comparison_projects.some((project) => project.slug === 'lakeville'));
  assert.ok(data.comparison_projects.some((project) => project.slug === 'lakegrande'));
});

test('rolling 3Y CAGR series compares current TTM PSF with the TTM PSF 36 months earlier', () => {
  const data = loadDashboardData();
  const metric = data.focus_projects.lakeville.owner_pool_filled;
  const monthKey = findRolling3yMonth(metric);

  assert.ok(monthKey, 'expected Lakeville owner-pool metric to have at least one rolling 3Y month');
  assert.ok(metric.rolling_3y_cagr_monthly, 'missing rolling_3y_cagr_monthly series');
  assert.equal(metric.rolling_3y_cagr_monthly[monthKey], computeRolling3yCagr(metric, monthKey));
});
