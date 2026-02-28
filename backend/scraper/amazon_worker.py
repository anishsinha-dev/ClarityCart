"""
Amazon Scraper Worker — Standalone script for subprocess execution.

This script is run as a separate Python process to avoid
Python 3.14 asyncio subprocess compatibility issues on Windows.

Usage:
    python amazon_worker.py <query> <product_limit>

Output:
    JSON array of product dicts to stdout.
"""

import asyncio
import json
import logging
import re
import sys
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser

# Import config — must run from the backend directory
sys.path.insert(0, ".")
from config import (
    AMAZON_SEARCH,
    SCRAPE_TIMEOUT_MS,
    PAGE_LOAD_WAIT_MS,
    SCROLL_PAUSE_MS,
    MAX_SCROLL_ATTEMPTS,
    BROWSER_HEADLESS,
    BROWSER_USER_AGENT,
    MAX_PRODUCT_LIMIT,
)

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("amazon_worker")


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_rating(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_review_count(text: str) -> int:
    if not text:
        return 0
    # Try to extract number before " ratings" or just numeric string
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        if cleaned:
            return int(cleaned)
    except ValueError:
        pass
    return 0


async def _scroll_page(page: Page) -> None:
    for i in range(MAX_SCROLL_ATTEMPTS):
        await page.evaluate("window.scrollBy(0, 800)")
        await page.wait_for_timeout(SCROLL_PAUSE_MS)
        at_bottom = await page.evaluate(
            "(window.innerHeight + window.scrollY) >= document.body.scrollHeight - 200"
        )
        if at_bottom:
            break


async def _close_login_popup(page: Page) -> None:
    # Amazon doesn't usually have a hard login blocker on search pages, but sometimes asks for location
    try:
        location_btn = page.locator("input[data-action-type='DISMISS']").first
        if await location_btn.is_visible(timeout=2000):
            await location_btn.click()
            logger.info("Closed location popup")
    except Exception:
        pass


async def _extract_products_from_page(page: Page) -> list[dict]:
    products = []

    # Amazon search results container
    card_selectors = [
        "div[data-component-type='s-search-result']",
    ]

    cards = []
    for selector in card_selectors:
        cards = await page.locator(selector).all()
        if len(cards) > 2:
            logger.info(f"Found {len(cards)} product cards using selector: {selector}")
            break

    for card in cards:
        try:
            product = {}

            # Title
            title_el = card.locator("h2 a span, a.a-text-normal span, .a-size-medium.a-text-normal, .a-size-base-plus.a-text-normal").first
            title = await title_el.inner_text() if await title_el.count() > 0 else None
            
            product["title"] = title.strip() if title else ""
            if len(product["title"]) < 5:
                continue

            # URL
            url_el = card.locator("h2 a, a.a-link-normal.s-no-outline").first
            href = await url_el.get_attribute("href") if await url_el.count() > 0 else None
            # Fallback for URL if not found
            if not href:
                links = await card.locator("a.a-link-normal").all()
                for link in links:
                    h = await link.get_attribute("href")
                    if h and ("/dp/" in h or "/gp/" in h):
                        href = h
                        break
            
            if href:
                base_url = href.split("?")[0] if "?" in href else href
                product["url"] = f"https://www.amazon.in{base_url}" if base_url.startswith("/") else base_url
            else:
                product["url"] = ""

            # Price
            price_el = card.locator(".a-price-whole").first
            price_text = await price_el.inner_text() if await price_el.count() > 0 else None
            product["price"] = _parse_price(price_text) if price_text else None

            # Skip if no price
            if product["price"] is None:
                continue

            # Rating
            rating_text = None
            # Check aria-label on star icons or their containers
            rating_els = await card.locator("i[class*='a-star-'], a[aria-label*='out of 5 stars'], span[aria-label*='out of 5 stars']").all()
            for el in rating_els:
                aria = await el.get_attribute("aria-label")
                if aria and "out of 5" in aria:
                    rating_text = aria
                    break
                text = await el.text_content()
                if text and "out of 5" in text:
                    rating_text = text
                    break
            
            if not rating_text:
                rating_text = await card.evaluate("""(el) => {
                    const icon = el.querySelector('i.a-icon-star-small, i.a-icon-star');
                    if (icon) {
                        const match = icon.className.match(/a-star-(?:small-)?([0-9-]+)/);
                        if (match) return match[1].replace('-', '.');
                    }
                    const textNode = el.querySelector('span[aria-label*="out of 5 stars"]');
                    if (textNode) return textNode.getAttribute('aria-label');
                    return null;
                }""")
            
            product["rating"] = _parse_rating(rating_text) if rating_text else None

            # Review count
            review_text = None
            review_els = await card.locator("a[aria-label*='ratings'], span[aria-label*='ratings']").all()
            for el in review_els:
                aria = await el.get_attribute("aria-label")
                if aria and "rating" in aria.lower():
                    review_text = aria
                    break
                    
            if not review_text:
                review_el = card.locator(".a-size-base.s-underline-text, span.a-size-base.s-underline-text").first
                review_text = await review_el.inner_text() if await review_el.count() > 0 else None
                
            product["review_count"] = _parse_review_count(review_text) if review_text else 0

            # Sponsored
            sponsored = await card.evaluate("""(el) => {
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while (node = walker.nextNode()) {
                    if (node.nodeValue.trim() === 'Sponsored' || node.nodeValue.trim() === 'Sponsored ') return true;
                }
                return false;
            }""")
            product["sponsored"] = bool(sponsored)

            # Offers / Lightning Deals / Coupons
            offers = []
            coupon_el = card.locator(".s-coupon-highlight-color").first
            if await coupon_el.count() > 0:
                offers.append(await coupon_el.inner_text())
                
            deal_el = card.locator(".a-badge-text").first # e.g. "Limited time deal" or "Great Indian Festival"
            if await deal_el.count() > 0:
                offers.append(await deal_el.inner_text())

            product["offers"] = " | ".join(filter(None, offers))

            products.append(product)

        except Exception as e:
            logger.debug(f"Error extracting product card: {e}")
            continue

    return products


async def _goto_next_page(page: Page) -> bool:
    try:
        next_btn = page.locator("a.s-pagination-next").first
        if await next_btn.count() > 0 and await next_btn.is_visible() and not await next_btn.get_attribute("aria-disabled"):
            await next_btn.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(PAGE_LOAD_WAIT_MS)
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to navigate to next page: {e}")
        return False


async def scrape(query: str, product_limit: int) -> list[dict]:
    product_limit = min(product_limit, MAX_PRODUCT_LIMIT)
    all_products: list[dict] = []
    page_num = 0

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=BROWSER_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        context = await browser.new_context(
            user_agent=BROWSER_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
        )

        page = await context.new_page()

        try:
            search_url = AMAZON_SEARCH.format(query.replace(" ", "+"))
            logger.info(f"Navigating to: {search_url}")
            await page.goto(search_url, timeout=SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(PAGE_LOAD_WAIT_MS)

            await _close_login_popup(page)

            while len(all_products) < product_limit:
                page_num += 1
                logger.info(f"Scraping page {page_num}...")

                await _scroll_page(page)
                page_products = await _extract_products_from_page(page)
                logger.info(f"Page {page_num}: extracted {len(page_products)} products")

                if not page_products:
                    logger.warning(f"No products found on page {page_num}, stopping")
                    break

                all_products.extend(page_products)

                if len(all_products) >= product_limit:
                    break

                has_next = await _goto_next_page(page)
                if not has_next:
                    logger.info("No more pages available")
                    break

        except Exception as e:
            logger.error(f"Scraping error: {e}")
            raise
        finally:
            await browser.close()

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_products: list[dict] = []
    for p in all_products:
        url = p.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_products.append(p)
        elif not url:
            unique_products.append(p)

    return unique_products[:product_limit]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: amazon_worker.py <query> <product_limit>"}))
        sys.exit(1)

    query = sys.argv[1]
    product_limit = int(sys.argv[2])

    try:
        results = asyncio.run(scrape(query, product_limit))
        # Output JSON to stdout
        print(json.dumps(results, ensure_ascii=True))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
