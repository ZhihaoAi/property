const test = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const vm = require('node:vm');

function loadDashboardData() {
  const src = fs.readFileSync('./data/dashboard_data.js', 'utf8');
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(src, context);
  return context.window.__DASHBOARD_DATA__;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ',') {
      row.push(field);
      field = '';
    } else if (char === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else if (char !== '\r') {
      field += char;
    }
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }

  const [header, ...body] = rows;
  return body
    .filter((values) => values.length === header.length)
    .map((values) => Object.fromEntries(header.map((key, index) => [key, values[index]])));
}

function loadLayoutMap(projectSlug) {
  return parseCsv(fs.readFileSync(`./data/layout_mapping/${projectSlug}_transaction_layout_map.csv`, 'utf8'));
}

function countRootTransactionProjects() {
  return fs.readdirSync('./data')
    .filter((filename) => filename.endsWith('_transactions.csv'))
    .length;
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

test('Lake Grande 2b1b bucket excludes 517 sqft one-bedroom transactions', () => {
  const data = loadDashboardData();
  const lakeGrande = data.focus_projects.lakegrande;
  const recent2b1b = lakeGrande.recent_by_bucket['2b1b'];
  const recentSmall = lakeGrande.recent_by_bucket.small;

  assert.ok(recent2b1b.every((row) => row.sqft >= 600), 'LG 2b1b should not include sub-600 sqft rows');
  assert.equal(recent2b1b[0].date_label, 'Feb 2026');
  assert.equal(recent2b1b[0].sqft, 613);
  assert.equal(recent2b1b[0].price, 1275000);
  assert.ok(
    recentSmall.some((row) => row.date_label === 'Mar 2026' && row.sqft === 516 && row.price === 923000),
    'Mar 2026 516 sqft transaction should be classified as small/1BR',
  );
});

test('developer brochure evidence covers Lakeville and Lake Grande layout gaps', () => {
  const lakevilleRows = loadLayoutMap('lakeville');
  const lakeGrandeRows = loadLayoutMap('lakegrande');
  const lakevilleBySqft = new Map(lakevilleRows.map((row) => [`${row.sqft}:${row.date}`, row]));
  const lakeGrandeBySqft = new Map(lakeGrandeRows.map((row) => [`${row.sqft}:${row.date}`, row]));
  const lakeGrandeUnresolved = lakeGrandeRows.filter((row) => row.mapping_status !== 'matched');

  const lakeville1140 = lakevilleBySqft.get('1140:Jan2026');
  const lakeville1302 = lakevilleBySqft.get('1302:Dec2025');
  assert.equal(lakeville1140.mapping_status, 'matched');
  assert.match(lakeville1140.evidence_kinds, /developer_brochure/);
  assert.equal(lakeville1302.mapping_status, 'matched');
  assert.match(lakeville1302.evidence_kinds, /developer_brochure/);

  const lakeGrande742 = lakeGrandeBySqft.get('742:Jul2025');
  assert.equal(lakeGrande742.mapping_status, 'matched');
  assert.equal(lakeGrande742.resolved_layout, '2b1b');
  assert.match(lakeGrande742.evidence_kinds, /developer_brochure|developer_floor_plan/);

  const lakeGrande721 = lakeGrandeBySqft.get('721:Dec2025');
  assert.equal(lakeGrande721.mapping_status, 'ambiguous');
  assert.match(lakeGrande721.layout_options, /2b1b/);
  assert.match(lakeGrande721.layout_options, /2b2b/);
  assert.match(lakeGrande721.evidence_notes, /B3a/);

  assert.deepEqual(
    lakeGrandeUnresolved.map((row) => Number(row.sqft)).sort((a, b) => a - b),
    [
      ...Array(18).fill(721),
      1011,
    ],
    'Lake Grande should leave 721 sqft ambiguous because that area can be both B1P/B1aP and B3/B3a; 1011 sqft remains the other unresolved size',
  );
  assert.ok(lakeGrandeUnresolved.every((row) => row.mapping_status === 'ambiguous'));
});

test('Lake Grande exposes B3/B3a 721 sqft as a target-area focus line without forcing the formal bucket', () => {
  const data = loadDashboardData();
  const lakeGrande = data.focus_projects.lakegrande;
  const b3a = lakeGrande.watched_layout_metrics.b3_b3a_721;

  assert.ok(b3a);
  assert.equal(b3a.key, 'b3_b3a_721');
  assert.equal(b3a.label, 'B3/B3a 721sqft');
  assert.equal(b3a.source_label, 'TYPE B3/B3a · 67 sqm | 721 sqft');
  assert.equal(b3a.sqft, 721);
  assert.equal(b3a.target_area_proxy, true);
  assert.ok(b3a.current);
  assert.ok(b3a.count > 0);
  assert.match(b3a.mapping_note, /same-size variants/);
});

test('Lake Grande exposes 721 sqft sensitivity lines without changing true 2b1b and 2b2b buckets', () => {
  const data = loadDashboardData();
  const lakeGrande = data.focus_projects.lakegrande;
  const b3a = lakeGrande.watched_layout_metrics.b3_b3a_721;
  const sensitivity = lakeGrande.layout_sensitivity_metrics;
  const as2b1b = sensitivity.lg_721_as_2b1b;
  const as2b2b = sensitivity.lg_721_as_2b2b;

  assert.equal(lakeGrande.type_breakout['2b1b'].count, 28);
  assert.equal(lakeGrande.type_breakout['2b2b'].count, 53);
  assert.equal(b3a.count, 18);

  assert.equal(as2b1b.label, '2b1b + 721全归2b1b');
  assert.equal(as2b1b.base_bucket, '2b1b');
  assert.equal(as2b1b.assumed_bucket, '2b1b');
  assert.equal(as2b1b.count, lakeGrande.type_breakout['2b1b'].count + b3a.count);
  assert.ok(as2b1b.recent_12m_count > lakeGrande.type_breakout['2b1b'].recent_12m_count);
  assert.ok(as2b1b.recent_12m_count <= lakeGrande.type_breakout['2b1b'].recent_12m_count + b3a.count);
  assert.match(as2b1b.mapping_note, /Treats every 721 sqft/);
  assert.equal(as2b1b.chart_style.pointStyle, 'crossRot');

  assert.equal(as2b2b.label, '2b2b + 721全归2b2b');
  assert.equal(as2b2b.base_bucket, '2b2b');
  assert.equal(as2b2b.assumed_bucket, '2b2b');
  assert.equal(as2b2b.count, lakeGrande.type_breakout['2b2b'].count + b3a.count);
  assert.ok(as2b2b.recent_12m_count > lakeGrande.type_breakout['2b2b'].recent_12m_count);
  assert.ok(as2b2b.recent_12m_count <= lakeGrande.type_breakout['2b2b'].recent_12m_count + b3a.count);
  assert.match(as2b2b.mapping_note, /Treats every 721 sqft/);
  assert.equal(as2b2b.chart_style.pointStyle, 'rectRounded');
});

test('layout mapping builder --all discovers every root transaction project without writing outputs', () => {
  const expectedCount = countRootTransactionProjects();
  const output = execFileSync('python3', ['scripts/build_layout_mappings.py', '--all', '--dry-run'], {
    encoding: 'utf8',
  });

  assert.match(output, new RegExp(`selected_projects=${expectedCount}`));
  const referenceProjects = Number(output.match(/reference_projects=(\d+)/)?.[1] || 0);
  const unmappedProjects = Number(output.match(/unmapped_projects=(\d+)/)?.[1] || 0);
  assert.equal(referenceProjects + unmappedProjects, expectedCount);
  assert.ok(referenceProjects > 2, 'auto-seeded brochure references should cover more than the original two focus projects');
  assert.match(output, /lakeville/);
  assert.match(output, /lakegrande/);
});

test('layout source manifest tracks source status for every transaction project', () => {
  const expectedCount = countRootTransactionProjects();
  const manifestRows = parseCsv(fs.readFileSync('./data/poc_layout/layout_source_manifest.csv', 'utf8'));

  assert.equal(manifestRows.length, expectedCount);
  assert.ok(manifestRows.every((row) => row.project_slug && row.project_name));
  assert.ok(manifestRows.every((row) => row.source_type && row.source_status));
  assert.ok(manifestRows.some((row) => row.project_slug === 'sol_acres' && row.source_status === 'parsed'));
  assert.ok(manifestRows.some((row) => row.project_slug === 'lakeville'));
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

test('dashboard payload reports formal mapping coverage rollout metadata', () => {
  const data = loadDashboardData();
  const focusProjectSlugs = Object.keys(data.focus_projects).sort();

  assert.deepEqual(focusProjectSlugs, ['lakegrande', 'lakeville']);
  assert.equal(typeof data.meta.layout_mapping_project_count, 'number');
  assert.equal(typeof data.meta.layout_mapping_complete, 'boolean');
  assert.equal(data.meta.layout_mapping_min_coverage_pct, 95);
  assert.ok(data.meta.layout_mapping_project_count >= 2);
  assert.equal(data.meta.layout_mapping_project_count, data.meta.layout_mapping_coverage.length);
  assert.ok(data.meta.layout_mapping_coverage.every((item) => typeof item.coverage_pct === 'number'));
});

test('rolling 3Y CAGR series compares current TTM PSF with the TTM PSF 36 months earlier', () => {
  const data = loadDashboardData();
  const metric = data.focus_projects.lakeville.owner_pool_filled;
  const monthKey = findRolling3yMonth(metric);

  assert.ok(monthKey, 'expected Lakeville owner-pool metric to have at least one rolling 3Y month');
  assert.ok(metric.rolling_3y_cagr_monthly, 'missing rolling_3y_cagr_monthly series');
  assert.equal(metric.rolling_3y_cagr_monthly[monthKey], computeRolling3yCagr(metric, monthKey));
});

test('recent 24-month transaction count is split into current and previous TTM windows', () => {
  const data = loadDashboardData();
  const lakeville = data.layout_comparison_projects.find((project) => project.slug === 'lakeville');
  const lakeGrande = data.layout_comparison_projects.find((project) => project.slug === 'lakegrande');

  assert.equal(lakeville.recent_12m_count, 19);
  assert.equal(lakeville.previous_12m_count, 9);
  assert.equal(lakeville.recent_24m_count, lakeville.recent_12m_count + lakeville.previous_12m_count);
  assert.equal(lakeville.owner_pool_direct.recent_12m_count, 19);
  assert.equal(lakeville.owner_pool_direct.previous_12m_count, 9);
  assert.equal(lakeville.type_breakout['2b1b'].recent_12m_count, 5);
  assert.equal(lakeville.type_breakout['2b1b'].previous_12m_count, 3);
  assert.equal(lakeville.type_breakout['2b2b'].recent_12m_count, 14);
  assert.equal(lakeville.type_breakout['2b2b'].previous_12m_count, 7);

  assert.equal(lakeGrande.recent_12m_count, 18);
  assert.equal(lakeGrande.previous_12m_count, 16);
  assert.equal(lakeGrande.recent_24m_count, lakeGrande.recent_12m_count + lakeGrande.previous_12m_count);
  assert.equal(lakeGrande.owner_pool_direct.recent_12m_count, 18);
  assert.equal(lakeGrande.owner_pool_direct.previous_12m_count, 16);
});
