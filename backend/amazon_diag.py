"""
Diagnostic script to dump text nodes from an Amazon product card.
"""
import asyncio, os, json
os.environ['PYTHONIOENCODING'] = 'utf-8'

from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
        )
        page = await context.new_page()
        
        await page.goto("https://www.amazon.in/s?k=earphone+under+1000", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        
        for i in range(2):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(800)
        
        cards = await page.locator("div[data-component-type='s-search-result']").all()
        print(f"Found {len(cards)} cards")
        
        for i, card in enumerate(cards[:2]):
            html = await card.inner_html()
            # print html snippet looking for rating
            print(f"--- Card {i} HTML snippet around star ---")
            lines = html.split('>')
            for j, line in enumerate(lines):
                if 'star' in line or 'rating' in line or 'review' in line.lower() or 'href' in line:
                    print(line + '>')
                    
            print("\nURLs:")
            links = await card.locator("a").all()
            for link in links:
                href = await link.get_attribute("href")
                if href and '/dp/' in href:
                    print(f"Link: {href}")
        
        await browser.close()

asyncio.run(main())
