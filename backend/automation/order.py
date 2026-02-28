"""
Order Automation Module — Playwright-based Flipkart ordering.

Safety first:
- Never auto-purchases without user confirmation
- Uses persistent browser session (user stays logged in)
- Pauses before checkout for manual confirmation
"""

import asyncio
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext

from config import BROWSER_USER_AGENT, SCRAPE_TIMEOUT_MS

logger = logging.getLogger(__name__)

# Persistent context directory for maintaining login sessions
SESSION_DIR = "./playwright_session"


async def add_to_cart(product_url: str) -> dict:
    """
    Navigate to a product page and add it to cart.
    
    Returns:
        Dict with status and message.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,  # Show browser so user can see what's happening
            args=["--no-sandbox"],
        )

        # Use persistent context to keep login state
        context = await browser.new_context(
            user_agent=BROWSER_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            storage_state=_get_storage_state(),
        )

        page = await context.new_page()

        try:
            # Navigate to product page
            logger.info(f"Navigating to product: {product_url}")
            await page.goto(product_url, timeout=SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Try to click "Add to Cart" button
            add_btn_selectors = [
                "button._2KpZ6l._2U9uOA._3v1-ww",  # Common Flipkart add-to-cart
                "button:has-text('ADD TO CART')",
                "button:has-text('Add to Cart')",
                "button:has-text('Add to cart')",
                "button._2KpZ6l._2U9uOA",
            ]

            clicked = False
            for selector in add_btn_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    clicked = True
                    logger.info("Clicked 'Add to Cart'")
                    break

            if not clicked:
                # Maybe it's a "BUY NOW" only product
                buy_btn = page.locator("button:has-text('BUY NOW')").first
                if await buy_btn.count() > 0:
                    return {
                        "status": "info",
                        "message": "This product only has 'BUY NOW' option. Please purchase manually.",
                        "product_url": product_url,
                    }
                return {
                    "status": "error",
                    "message": "Could not find 'Add to Cart' button. The page layout may have changed.",
                    "product_url": product_url,
                }

            await page.wait_for_timeout(2000)

            # Navigate to cart
            await page.goto("https://www.flipkart.com/viewcart", timeout=SCRAPE_TIMEOUT_MS)
            await page.wait_for_timeout(2000)

            # Save session state for future use
            storage = await context.storage_state()
            _save_storage_state(storage)

            # PAUSE — Wait for user confirmation
            # The browser stays open for the user to review and manually proceed
            logger.info("Product added to cart. Browser is open for user review.")
            logger.info("⚠ PAUSED — Close the browser window when done or press Ctrl+C to cancel.")

            # Keep browser open for 5 minutes max
            await page.wait_for_timeout(300_000)

            return {
                "status": "success",
                "message": "Product added to cart. Please review and complete purchase in the browser.",
                "cart_url": "https://www.flipkart.com/viewcart",
                "product_url": product_url,
            }

        except Exception as e:
            logger.error(f"Order automation error: {e}")
            return {
                "status": "error",
                "message": f"Error during order automation: {str(e)}",
                "product_url": product_url,
            }
        finally:
            await browser.close()


def _get_storage_state() -> dict | None:
    """Load saved browser session if available."""
    import json
    from pathlib import Path

    state_file = Path(SESSION_DIR) / "state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except Exception:
            return None
    return None


def _save_storage_state(state: dict) -> None:
    """Save browser session for persistence."""
    import json
    from pathlib import Path

    state_dir = Path(SESSION_DIR)
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / "state.json"
    state_file.write_text(json.dumps(state, indent=2))
    logger.info("Browser session saved for future use")
