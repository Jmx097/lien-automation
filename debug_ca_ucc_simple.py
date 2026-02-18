
import asyncio
from playwright.async_api import async_playwright

async def main():
    print("Launching browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        print("Navigating to https://bizfileonline.sos.ca.gov/search/ucc ...")
        
        try:
            await page.goto("https://bizfileonline.sos.ca.gov/search/ucc", timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            # Screenshot after load
            await page.screenshot(path="debug_initial.png")
            print("Saved debug_initial.png")
            
            # Check for title
            title = await page.title()
            print(f"Page title: {title}")

            # Try to find the label
            label_text = "Search by name or file number"
            try:
                await page.get_by_label(label_text).wait_for(timeout=5000)
                print(f"SUCCESS: Found label '{label_text}'")
            except Exception as e:
                print(f"FAIL: Could not find label '{label_text}'")
                
                # Dump actual labels
                labels = await page.evaluate("() => Array.from(document.querySelectorAll('label')).map(l => l.innerText)")
                print(f"Labels on page: {labels}")
                
                # Dump text content
                text = await page.inner_text("body")
                print(f"Body text start: {text[:200]}")
                
                await page.screenshot(path="debug_fail.png")
                print("Saved debug_fail.png")

        except Exception as e:
            print(f"Critical error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
