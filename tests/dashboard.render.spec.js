const { test, expect } = require('@playwright/test');

test.describe('dashboard render', () => {
  test('s2 renders focus buckets for Lakeville and Lake Grande', async ({ page }) => {
    await page.goto('/?tab=s2');
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
    await expect(page.locator('#overall_cagr_chart .cagr-row').first()).toBeVisible();
    
    await expect(page.locator('#cumulative_cagr_chart')).toBeVisible();
    await expect(page.locator('#yoy_return_chart')).toBeVisible();
    await expect(page.locator('#typed_bucket_cagr_chart')).toBeVisible();
    
    await page.locator('summary', { hasText: '口径 1 · 全部主源整体 CAGR 汇总' }).click();
    await page.locator('summary', { hasText: '附加 · propertyforsale resale 主源 CAGR 汇总' }).click();
    await expect(page.locator('#overall_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#all_source_cagr_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#layout_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#area_proxy_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#overall_projects_table')).toContainText('_transactions.csv');
    if (nonPropertyProject) {
      await expect(page.locator('#overall_projects_table')).toContainText(nonPropertyProject.source);
      await expect(page.locator('#overall_projects_table')).toContainText(nonPropertyProject.name);
    }
    await expect(page.locator('#overall_projects_table')).toContainText('Lakeville');
    await expect(page.locator('#layout_projects_table')).toContainText('Lake Grande');
    await expect(page.locator('#layout_projects_table')).toContainText('2b1b');
    await expect(page.locator('#area_proxy_projects_table')).toContainText('600-699 sqft');
    await expect(page.locator('#area_proxy_projects_table')).toContainText('Lakeville');
    await expect(page.locator('#area_proxy_projects_table')).toContainText('Hundred Trees');
    await expect(page.locator('#area_proxy_projects_table tbody tr').first()).toContainText('笔');
  });

  test('s12 renders scraped project table and PK inclusion status', async ({ page }) => {
    await page.goto('/?tab=s12');
    const data = await page.evaluate(() => window.__DASHBOARD_DATA__);
    const meta = data.meta;
    const fallbackProject = data.projects.find(project => (
      project.source_kind !== 'propertyforsale_csv' && project.overall_pk_included
    ));
    await expect(page.locator('#scrape_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#focus_mapping_cards .ai').first()).toBeVisible();
    await expect(page.locator('#scraped_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#scraped_projects_table thead')).toContainText('口径1 PK');
    await expect(page.locator('#scraped_projects_table')).toContainText('已纳入');
    await expect(page.locator('#scraped_projects_table')).toContainText('面积近似PK');
    if (fallbackProject) {
      await expect(page.locator('#scraped_projects_table')).toContainText(fallbackProject.source);
      const fallbackRow = page.locator('#scraped_projects_table tbody tr', { hasText: fallbackProject.name });
      await expect(fallbackRow.locator('td').nth(8)).toHaveText('已纳入');
    }
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
});
