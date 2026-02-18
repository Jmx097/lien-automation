"""
Debug: click first row, wait for panel, dump HTML to panel_dump.html
"""
import asyncio
import re
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await ctx.new_page()

        print("Navigating...")
        await page.goto("https://bizfileonline.sos.ca.gov/search/ucc")
        await page.wait_for_load_state("networkidle")

        await page.get_by_role("textbox", name="Search by name or file number").fill("Internal Revenue Service")
        await page.get_by_role("button", name=re.compile(r"Advanced", re.I)).click()
        await page.locator("#field-RECORD_TYPE_ID").wait_for(state="visible")
        await page.locator("#field-RECORD_TYPE_ID").select_option(label="Federal Tax Lien")
        await page.locator("#field-date-FILING_DATEs").fill("01/20/2026")
        await page.locator("#field-date-FILING_DATEe").fill("01/25/2026")
        await page.locator("#field-date-FILING_DATEe").press("Tab")
        await page.get_by_role("button", name="Search").click()
        await page.wait_for_load_state("networkidle")
        print("Search done. Clicking first row...")

        # Click first data row
        rows = page.locator("table tbody tr")
        count = await rows.count()
        print(f"Found {count} rows")

        # Click first row with enough cells
        for i in range(min(count, 5)):
            row = rows.nth(i)
            cells = row.locator("td")
            nc = await cells.count()
            print(f"Row {i}: {nc} cells")
            if nc >= 7:
                file_num = (await cells.nth(2).text_content() or "").strip()
                print(f"Clicking row {i}, file_number={file_num}")
                await cells.first.click()
                await page.wait_for_timeout(3000)
                break

        # Dump full page HTML
        html = await page.content()
        with open("panel_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Saved panel_dump.html ({len(html)} bytes)")

        # Also take screenshot
        await page.screenshot(path="panel_screenshot.png", full_page=False)
        print("Saved panel_screenshot.png")

        await browser.close()

asyncio.run(main())
