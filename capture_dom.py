"""Capture DOM selectors from CA UCC site at each interaction stage."""
import asyncio, os, json
from playwright.async_api import async_playwright

OUT = os.path.join(os.environ.get('TEMP', '/tmp'), 'dom_capture')
os.makedirs(OUT, exist_ok=True)

async def dump(page, label):
    """Save screenshot + HTML + element inventory."""
    await page.screenshot(path=os.path.join(OUT, f'{label}.png'), full_page=True)
    html = await page.content()
    with open(os.path.join(OUT, f'{label}.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    # Dump interactive elements
    info = await page.evaluate("""() => {
        const els = [];
        document.querySelectorAll('input,select,button,a,[role="button"],[role="row"],[role="link"]').forEach(el => {
            els.push({
                tag: el.tagName,
                type: el.type || '',
                id: el.id || '',
                name: el.name || '',
                className: el.className || '',
                placeholder: el.placeholder || '',
                textContent: el.textContent.trim().substring(0, 80),
                role: el.getAttribute('role') || '',
                href: el.href || '',
                disabled: el.disabled || false,
                visible: el.offsetParent !== null,
                options: el.tagName === 'SELECT' ? Array.from(el.options).map(o => ({value: o.value, text: o.text})) : []
            });
        });
        return els;
    }""")
    with open(os.path.join(OUT, f'{label}_elements.json'), 'w') as f:
        json.dump(info, f, indent=2)
    print(f"[{label}] {len(info)} interactive elements captured")

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        page = await ctx.new_page()

        # Stage 1: Initial load
        print("Stage 1: Loading page...")
        await page.goto('https://bizfileonline.sos.ca.gov/search/ucc', wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)
        await dump(page, '1_initial')

        # Stage 2: Click Advanced
        print("Stage 2: Clicking Advanced...")
        adv = await page.query_selector('button.advanced-search-toggle')
        if adv:
            await adv.click()
            await asyncio.sleep(1)
        await dump(page, '2_advanced')

        # Stage 3: Fill form and search
        print("Stage 3: Filling form...")
        search_input = await page.query_selector('input[placeholder*="Search by name"]')
        if search_input:
            await search_input.fill('Internal Revenue Service')
            print("  Filled search input")

        # Try filling dates
        date_start = await page.query_selector('#field-date-FILING_DATEs')
        date_end = await page.query_selector('#field-date-FILING_DATEe')
        if date_start:
            await date_start.fill('01/18/2026')
            print("  Filled start date")
        else:
            print("  ! No start date field found")
        if date_end:
            await date_end.fill('02/17/2026')
            print("  Filled end date")
        else:
            print("  ! No end date field found")

        # Try selecting Federal Tax Lien
        record_type = await page.query_selector('#field-RECORD_TYPE_ID')
        if record_type:
            await record_type.select_option(label='Federal Tax Lien')
            print("  Selected Federal Tax Lien")
        else:
            print("  ! No record type select found")

        await dump(page, '3_filled')

        # Stage 4: Click Search
        print("Stage 4: Searching...")
        search_btn = await page.query_selector('button.advanced-search-button')
        if search_btn:
            await search_btn.click()
            print("  Clicked search button")
        else:
            print("  ! No search button found")

        # Wait for results
        try:
            # Try multiple selectors for results
            await page.wait_for_selector('.search-results, .results-table, table, .record-row, [class*="result"]', timeout=15000)
            print("  Results selector found!")
        except:
            print("  ! Primary result selector not found, waiting 8s...")
            await asyncio.sleep(8)

        await dump(page, '4_results')

        # Check for error message
        error = await page.query_selector('h3:has-text("more than 1,000")')
        if error:
            print("  WARNING: >1000 results error detected")
        
        # Stage 5: Check what result rows look like
        print("Stage 5: Analyzing results structure...")
        structure = await page.evaluate("""() => {
            const info = { tables: 0, rows: [], links: [], buttons: [] };
            info.tables = document.querySelectorAll('table').length;
            // Look for any repeated row-like structures
            document.querySelectorAll('[class*="row"], [class*="record"], [class*="result"], tr, li').forEach(el => {
                if (el.textContent.includes('Internal Revenue') || el.textContent.includes('Federal Tax')) {
                    info.rows.push({
                        tag: el.tagName,
                        class: el.className,
                        text: el.textContent.trim().substring(0, 120)
                    });
                }
            });
            // Look for clickable detail/history links
            document.querySelectorAll('a, button').forEach(el => {
                const t = el.textContent.trim().toLowerCase();
                if (t.includes('history') || t.includes('detail') || t.includes('view') || t.includes('download')) {
                    info.links.push({ tag: el.tagName, class: el.className, text: el.textContent.trim().substring(0, 60), href: el.href || '' });
                }
            });
            return info;
        }""")
        print(f"  Tables: {structure['tables']}, Result-like rows: {len(structure['rows'])}, Detail links: {len(structure['links'])}")
        with open(os.path.join(OUT, '5_result_structure.json'), 'w') as f:
            json.dump(structure, f, indent=2)

        # If we got results, try clicking the first one
        if structure['rows']:
            print("Stage 6: Clicking first result row...")
            # Try clicking on the first result
            first_row = await page.query_selector('[class*="record"]:has-text("Internal Revenue"), [class*="result"]:has-text("Internal Revenue"), tr:has-text("Internal Revenue")')
            if first_row:
                await first_row.click()
                await asyncio.sleep(2)
                await dump(page, '6_detail')
            else:
                print("  Could not find clickable result row")

        await browser.close()
        print(f"\nAll artifacts saved to: {OUT}")

asyncio.run(main())
