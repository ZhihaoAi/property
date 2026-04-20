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

test('focus projects expose owner-pool metrics and confidence metadata', () => {
  const data = loadDashboardData();
  const project = data.focus_projects.lakeville;

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
  assert.ok(project.owner_pool_filled.yoy_monthly);
  assert.equal(project.owner_pool_filled.current_yoy, project.owner_pool_filled.yoy_monthly[Object.keys(project.owner_pool_filled.yoy_monthly).sort().at(-1)]);
  assert.equal(project.owner_pool_filled.all_time_cagr, project.owner_pool_filled.cagr_monthly[Object.keys(project.owner_pool_filled.cagr_monthly).sort().at(-1)]);
});

test('dashboard payload exposes four PK lenses with unified all-time CAGR and YoY fields', () => {
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
  assert.ok(firstOwnerPool.yoy_monthly);

  assert.equal(typeof firstOverall.all_time_cagr, 'number');
  assert.equal(typeof firstOverall.current_yoy, 'number');
  assert.equal(typeof firstOverall.current_psf, 'number');
  assert.equal(typeof firstOverall.sample_count, 'number');
  assert.ok(firstOverall.cagr_monthly);
  assert.ok(firstOverall.yoy_monthly);

  assert.equal(typeof firstAreaProxy.all_time_cagr, 'number');
  assert.equal(typeof firstAreaProxy.current_yoy, 'number');
  assert.equal(typeof firstAreaProxy.current_psf, 'number');
  assert.equal(typeof firstAreaProxy.sample_count, 'number');
  assert.ok(firstAreaProxy.cagr_monthly);
  assert.ok(firstAreaProxy.yoy_monthly);

  assert.equal(typeof firstLayout.all_time_cagr, 'number');
  assert.equal(typeof firstLayout.current_yoy, 'number');
  assert.equal(typeof firstLayout.current_psf, 'number');
  assert.equal(typeof firstLayout.sample_count, 'number');
  assert.ok(firstLayout.cagr_monthly);
  assert.ok(firstLayout.yoy_monthly);

  assert.equal(data.meta.pk_project_count, data.comparison_projects.length);
  assert.equal(data.meta.area_proxy_comparison_project_count, data.area_proxy_comparison_projects.length);
  assert.ok(data.comparison_projects.some((project) => project.slug === 'lakeville'));
  assert.ok(data.comparison_projects.some((project) => project.slug === 'lakegrande'));
});
