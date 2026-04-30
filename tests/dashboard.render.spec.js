const { test, expect } = require('@playwright/test');

test.describe('dashboard render', () => {
  test('s2 renders focus buckets for Lakeville and Lake Grande', async ({ page }) => {
    await page.goto('/?tab=s2');
    await page.waitForFunction(() => !!window.__DASHBOARD_DATA__?.focus_projects?.lakeville);
    await expect(page.locator('#lv_focus_content .ai').first()).toBeVisible();
    await expect(page.locator('#lg_focus_content .ai').first()).toBeVisible();
    await expect(page.locator('#lv_focus_content')).toContainText('2b1b');
    await expect(page.locator('#lg_focus_content')).toContainText('3b2b');
  });

  test('s10 renders PK metrics and local source csv rows', async ({ page }) => {
    await page.goto('/?tab=s10');
    const data = await page.evaluate(() => window.__DASHBOARD_DATA__);
    const nonPropertyProject = data.projects.find(project => project.source_kind !== 'propertyforsale_csv');
    await expect(page.locator('#pk_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#overall_cagr_chart')).toBeVisible();
    await expect(page.locator('#overall_rolling_3y_cagr_chart')).toBeVisible();
    await expect(page.locator('#overall_yoy_chart')).toBeVisible();
    await expect(page.locator('#layout_cagr_chart')).toBeVisible();
    await expect(page.locator('#layout_rolling_3y_cagr_chart')).toBeVisible();
    await expect(page.locator('#layout_yoy_chart')).toBeVisible();
    await expect(page.locator('#area_proxy_cagr_chart')).toBeVisible();
    await expect(page.locator('#area_proxy_rolling_3y_cagr_chart')).toBeVisible();
    await expect(page.locator('#area_proxy_yoy_chart')).toBeVisible();
    await expect(page.locator('#owner_pool_cagr_chart')).toBeVisible();
    await expect(page.locator('#owner_pool_rolling_3y_cagr_chart')).toBeVisible();
    await expect(page.locator('#owner_pool_yoy_chart')).toBeVisible();
    await expect(page.locator('#layout_focus_detail_chart')).toBeVisible();
    await expect(page.locator('#owner_pool_focus_detail_chart')).toBeVisible();
    await expect(page.locator('#layout_focus_metric_toggle')).toContainText('All-time CAGR');
    await expect(page.locator('#layout_focus_metric_toggle')).toContainText('Rolling 3Y CAGR');
    await expect(page.locator('#layout_focus_metric_toggle')).toContainText('YoY');
    await expect(page.locator('#owner_pool_focus_metric_toggle')).toContainText('All-time CAGR');
    await expect(page.locator('#owner_pool_focus_metric_toggle')).toContainText('Rolling 3Y CAGR');
    await expect(page.locator('#owner_pool_focus_metric_toggle')).toContainText('YoY');

    await page.locator('summary:has-text("口径 1 · 全项目汇总")').click();
    await page.locator('summary:has-text("口径 2 · 真实户型映射汇总")').click();
    await page.locator('summary:has-text("口径 3 · 面积代理汇总")').click();
    await page.locator('summary:has-text("口径 4 · 自住口径汇总")').click();
    await expect(page.locator('#overall_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#layout_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#area_proxy_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#owner_pool_projects_table tbody tr').first()).toBeVisible();

    await expect(page.locator('#s10')).toContainText('口径 1 · 全项目');
    await expect(page.locator('#s10')).toContainText('口径 2 · 真实户型映射');
    await expect(page.locator('#s10')).toContainText('口径 3 · 面积代理');
    await expect(page.locator('#s10')).toContainText('口径 4 · 自住口径');
    await expect(page.locator('#s10')).toContainText('全项目 resale-only 聚合线');
    await expect(page.locator('#s10')).toContainText('2b1b 600-699 sqft · 2b2b 700-849 sqft · 3b2b 850-1199 sqft');
    await expect(page.locator('#s10')).toContainText('真实 2b2b -> 真实 2b1b+2b2b -> 面积代理 -> 全项目');
    await expect(page.locator('#s10')).not.toContainText('当前自住池价格位置');
    await expect(page.locator('#s10')).not.toContainText('历史位置');
    await expect(page.locator('#s10 canvas')).toHaveCount(14);
    const defaultVisible = await page.evaluate(() => {
      const chart = Chart.getChart(document.getElementById('overall_cagr_chart'));
      return chart.data.datasets.filter((dataset, index) => chart.isDatasetVisible(index)).map((dataset) => dataset.label).sort();
    });
    expect(defaultVisible).toEqual(['Lake Grande', 'Lakeville']);
    if (nonPropertyProject) {
      await expect(page.locator('#area_proxy_projects_table')).toContainText(nonPropertyProject.name);
    }
    await expect(page.locator('#overall_projects_table tbody tr.focus-row')).toHaveCount(2);
    await expect(page.locator('#area_proxy_projects_table tbody tr.focus-row')).toHaveCount(2);
    await expect(page.locator('#owner_pool_projects_table tbody tr.focus-row')).toHaveCount(2);
    await expect(page.locator('#owner_pool_projects_table')).toContainText('Lakeville');
    await expect(page.locator('#owner_pool_projects_table')).toContainText('Lake Grande');
    await expect(page.locator('#owner_pool_projects_table')).toContainText('YoY');
    await expect(page.locator('#layout_projects_table')).toContainText('Lake Grande');
    await expect(page.locator('#layout_projects_table')).toContainText('映射覆盖率');
  });

  test('s10 focus detail charts keep fixed project colors and metric toggles', async ({ page }) => {
    await page.goto('/?tab=s10');

    const beforeToggle = await page.evaluate(() => {
      const overall = Chart.getChart(document.getElementById('overall_cagr_chart'));
      const layoutDetail = Chart.getChart(document.getElementById('layout_focus_detail_chart'));
      const ownerDetail = Chart.getChart(document.getElementById('owner_pool_focus_detail_chart'));

      return {
        overallColors: Object.fromEntries(
          overall.data.datasets
            .filter((dataset) => dataset.label === 'Lakeville' || dataset.label === 'Lake Grande')
            .map((dataset) => [dataset.label, dataset.borderColor])
        ),
        layoutLabels: layoutDetail.data.datasets.map((dataset) => dataset.label).sort(),
        ownerLabels: ownerDetail.data.datasets.map((dataset) => dataset.label).sort(),
        layoutLakevilleColor: layoutDetail.data.datasets.find((dataset) => dataset.label === 'Lakeville · 主线')?.borderColor,
        ownerLakevilleColor: ownerDetail.data.datasets.find((dataset) => dataset.label === 'Lakeville · 主线')?.borderColor,
        layoutLakeGrandeColor: layoutDetail.data.datasets.find((dataset) => dataset.label === 'Lake Grande · 主线')?.borderColor,
        ownerLakeGrandeColor: ownerDetail.data.datasets.find((dataset) => dataset.label === 'Lake Grande · 主线')?.borderColor,
        layoutSeriesSnapshot: layoutDetail.data.datasets.map((dataset) => ({
          label: dataset.label,
          borderDash: dataset.borderDash,
          data: dataset.data,
        })),
      };
    });

    expect(beforeToggle.layoutLabels).toEqual([
      'Lake Grande · 2b1b',
      'Lake Grande · 2b2b',
      'Lake Grande · 主线',
      'Lakeville · 2b1b',
      'Lakeville · 2b2b',
      'Lakeville · 主线',
    ]);
    expect(beforeToggle.ownerLabels).toEqual(beforeToggle.layoutLabels);
    expect(beforeToggle.layoutLakevilleColor).toBe(beforeToggle.overallColors.Lakeville);
    expect(beforeToggle.ownerLakevilleColor).toBe(beforeToggle.overallColors.Lakeville);
    expect(beforeToggle.layoutLakeGrandeColor).toBe(beforeToggle.overallColors['Lake Grande']);
    expect(beforeToggle.ownerLakeGrandeColor).toBe(beforeToggle.overallColors['Lake Grande']);

    await page.getByRole('button', { name: 'Rolling 3Y CAGR' }).nth(0).click();

    const afterToggle = await page.evaluate(() => {
      const layoutDetail = Chart.getChart(document.getElementById('layout_focus_detail_chart'));
      return layoutDetail.data.datasets.map((dataset) => ({
        label: dataset.label,
        borderDash: dataset.borderDash,
        data: dataset.data,
      }));
    });

    expect(afterToggle.map((dataset) => dataset.label).sort()).toEqual(beforeToggle.layoutLabels);
    expect(afterToggle.map((dataset) => JSON.stringify(dataset.borderDash))).toEqual(
      beforeToggle.layoutSeriesSnapshot.map((dataset) => JSON.stringify(dataset.borderDash))
    );
    expect(afterToggle.map((dataset) => JSON.stringify(dataset.data))).not.toEqual(
      beforeToggle.layoutSeriesSnapshot.map((dataset) => JSON.stringify(dataset.data))
    );
  });

  test('s12 renders scraped project table and PK inclusion status', async ({ page }) => {
    await page.goto('/?tab=s12');
    const data = await page.evaluate(() => window.__DASHBOARD_DATA__);
    const meta = data.meta;
    await expect(page.locator('#scrape_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#focus_mapping_cards .ai').first()).toBeVisible();
    await expect(page.locator('#scraped_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#scraped_projects_table thead')).toContainText('自住PK');
    await expect(page.locator('#scraped_projects_table')).toContainText('已纳入');
    await expect(page.locator('#scraped_projects_table')).toContainText('自住主口径');
    await expect(page.locator('#scraped_projects_table')).toContainText('confidence');
    expect(meta.propertyforsale_project_count + meta.ura_resale_project_count + meta.srx_project_count).toBe(meta.project_count);
    expect(meta.srx_backup_project_count).toBeGreaterThan(0);
    expect(meta.layout_mapping_source).toBe('formal');
  });

  test('s13 renders URA project browser and local comparison', async ({ page }) => {
    await page.goto('/?tab=s13');
    await expect(page.locator('#ura_project_select')).toBeVisible();
    await expect(page.locator('#ura_project_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#ura_project_summary')).toContainText('LAKEVILLE');
    await expect(page.locator('#ura_project_compare')).toContainText('成交差值');
    await expect(page.locator('#ura_transactions_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#ura_transactions_table .exp-btn').first()).toBeVisible();
    await page.locator('#ura_transactions_table .exp-btn').first().click();
    await expect(page.locator('#ura_transactions_table')).toContainText('面积口径');
    await expect(page.locator('#ura_transactions_table')).toContainText('转售');
    await expect(page.locator('#ura_rental_median_table')).toContainText('2025Q4');
    await expect(page.locator('#ura_rental_contracts_table')).toContainText('2026 Q1');
  });

  test('s9 renders long-term rent benchmark with official index note', async ({ page }) => {
    await page.goto('/?tab=s9');
    await expect(page.locator('#c_rent_benchmark')).toBeVisible();
    await expect(page.locator('#rent_benchmark_note')).toContainText(/10Y rolling CAGR|长期锚点/);
  });

  test('s5 renders unified wealth model rows and assumptions', async ({ page }) => {
    await page.goto('/?tab=s5');
    await expect(page.locator('#s5')).not.toContainText('出生日期');
    await expect(page.locator('#s5')).not.toContainText('买房时年龄');
    await expect(page.locator('#assumptions_box')).not.toContainText('1997-06-25');
    await expect(page.locator('#assumptions_box')).not.toContainText('1986-04-22');
    await expect(page.locator('#i_assets')).toHaveValue('800');
    await expect(page.locator('#wealth_table_card')).toContainText('前期 CPF OA 支出');
    await expect(page.locator('#wealth_table_card')).toContainText('OA 不足转现金');
    await expect(page.locator('#wealth_table_card')).toContainText('总财富 CAGR');
    await expect(page.locator('#wealth_table_card')).toContainText('起始$800K');
    await expect(page.locator('#monthly_detail_table')).toContainText('OA(Y1-');
    await expect(page.locator('#cost_detail_table')).toContainText('实际 CPF OA 支出');
  });

  test('decision process tab and section are removed', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: /决策过程/ })).toHaveCount(0);
    await expect(page.locator('#s7')).toHaveCount(0);
  });

  test('s14 renders sensitivity sweep with break-even note', async ({ page }) => {
    await page.goto('/?tab=s14');
    await page.getByRole('button', { name: /🎯 决策/ }).click();
    await expect(page.locator('#decision_sensitivity_chart')).toBeVisible();
    await expect(page.locator('#decision_sensitivity_note')).toContainText(/break-even|更高增长率/);
    await expect(page.locator('#decision_sensitivity_note')).toContainText(/all-in CAGR/);
    await expect(page.locator('#decision_sensitivity_formula')).toContainText(/公式全过程/);
    await expect(page.locator('#decision_sensitivity_formula')).toContainText(/PropertyEquity/);
    const sensitivity = await page.evaluate(() => window.__DASHBOARD_DATA__.sensitivity);
    expect(Array.isArray(sensitivity.points)).toBe(true);
    expect(sensitivity.points.length).toBeGreaterThan(5);
  });

  test('s14 renders rental-yield block with gross-yield chart and fair-price matrix', async ({ page }) => {
    await page.goto('/?tab=s14');
    await page.getByRole('button', { name: /🎯 决策/ }).click();
    await expect(page.locator('#decision_yield_chart')).toBeVisible();
    await expect(page.locator('#decision_fair_price_tables')).toContainText(/Lakeville 2B2B|Lake Grande 2B2B/);
    const dry = await page.evaluate(() => window.__DASHBOARD_DATA__.decision_rental_yield);
    expect(Array.isArray(dry.required_yields)).toBe(true);
    expect(dry.projects.lake_grande['2b2b'].fair_price_matrix.length).toBeGreaterThan(0);
  });

  test('s14 listing valuation form computes percentile band locally', async ({ page }) => {
    await page.goto('/?tab=s14');
    await page.getByRole('button', { name: /🎯 决策/ }).click();
    await expect(page.locator('#decision_listing_project')).toBeVisible();
    await page.selectOption('#decision_listing_project', 'lakegrande');
    await page.fill('#decision_listing_sqft', '775');
    await page.fill('#decision_listing_price', '1480000');
    await expect(page.locator('#decision_listing_result')).toContainText(/Rank:.*P60|Rank:.*P67/);
    await expect(page.locator('#decision_listing_result')).toContainText(/Verdict:.*FAIR-RICH|Verdict:.*RICH|Verdict:.*FAIR-CHEAP/);
    await expect(page.locator('#decision_listing_result')).toContainText(/P50/);
  });

  test('s15 renders lease decay explanation charts and table', async ({ page }) => {
    await page.goto('/?tab=s15');
    await page.getByRole('button', { name: /地契折旧/ }).click();
    await expect(page.locator('#c_lease_bala')).toBeVisible();
    await expect(page.locator('#c_lease_drag')).toBeVisible();
    await expect(page.locator('#lease_decay_table')).toContainText(/Observed all-in CAGR/);
  });
});
