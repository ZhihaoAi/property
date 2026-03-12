#!/usr/bin/env python3
"""Take screenshots of the property dashboard page."""
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        
        try:
            # 1. Load page - 小区PK tab is default active
            page.goto("http://localhost:8765/index.html", wait_until="networkidle", timeout=15000)
            time.sleep(1)
            page.screenshot(path="screenshot_1_initial.png", full_page=False)
            print("Screenshot 1: Initial page saved")
            
            # 2. Scroll to CAGR chart and screenshot
            cagr_card = page.locator("#c_all_cagr").locator("..")
            cagr_card.scroll_into_view_if_needed()
            time.sleep(0.5)
            page.screenshot(path="screenshot_2_cagr_chart.png", full_page=False)
            print("Screenshot 2: CAGR chart area saved")
            
            # 3. Scroll to Hillview/Dairy Farm chart
            d23_card = page.locator("#c_d23_psf").locator("..")
            d23_card.scroll_into_view_if_needed()
            time.sleep(0.5)
            page.screenshot(path="screenshot_3_hillview_chart.png", full_page=False)
            print("Screenshot 3: Hillview/Dairy Farm chart saved")
            
            # 4. Click 地铁距离 tab
            page.click("button.tab:has-text('地铁距离')")
            time.sleep(1)  # Wait for map to init
            page.screenshot(path="screenshot_4_mrt_section.png", full_page=False)
            print("Screenshot 4: MRT section saved")
            
            # Full page for MRT to capture map + table
            page.screenshot(path="screenshot_4_mrt_full.png", full_page=True)
            print("Screenshot 4 (full): MRT full page saved")
            
        finally:
            browser.close()
    print("Done.")

if __name__ == "__main__":
    main()
