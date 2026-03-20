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
    await expect(page.locator('#pk_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#overall_cagr_chart .cagr-row').first()).toBeVisible();
    await expect(page.locator('#overall_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#all_source_cagr_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#layout_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#area_proxy_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#overall_projects_table')).toContainText('_transactions.csv');
    await expect(page.locator('#overall_projects_table')).toContainText('SRX last-transacted-prices');
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
    const meta = await page.evaluate(() => window.__DASHBOARD_DATA__.meta);
    await expect(page.locator('#scrape_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#focus_mapping_cards .ai').first()).toBeVisible();
    await expect(page.locator('#scraped_projects_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#scraped_projects_table')).toContainText('已纳入');
    await expect(page.locator('#scraped_projects_table')).toContainText('面积近似PK');
    await expect(page.locator('#scraped_projects_table')).toContainText('SRX last-transacted-prices');
    expect(meta.ura_project_count + meta.srx_project_count).toBe(meta.project_count);
    expect(meta.srx_backup_project_count).toBeGreaterThan(0);
  });

  test('s13 renders URA project browser and local comparison', async ({ page }) => {
    await page.goto('/?tab=s13');
    await expect(page.locator('#ura_project_select')).toBeVisible();
    await expect(page.locator('#ura_project_kpis .kpi').first()).toBeVisible();
    await expect(page.locator('#ura_project_summary')).toContainText('LAKEVILLE');
    await expect(page.locator('#ura_project_compare')).toContainText('成交差值');
    await expect(page.locator('#ura_transactions_table tbody tr').first()).toBeVisible();
    await expect(page.locator('#ura_rental_median_table')).toContainText('2025Q4');
    await expect(page.locator('#ura_rental_contracts_table')).toContainText('2026 Q1');
  });
});
