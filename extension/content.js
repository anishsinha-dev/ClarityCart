/**
 * ClarityCart — Content Script (injected on Flipkart pages)
 *
 * Capabilities:
 * - Extract product data from the current Flipkart page DOM
 * - Respond to messages from popup/background scripts
 * - Highlight recommended product on the page
 */

(() => {
    "use strict";

    // ── Message Listener ───────────────────────────────
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === "EXTRACT_PRODUCTS") {
            const products = extractProductsFromDOM();
            sendResponse({ products });
            return true;
        }

        if (message.type === "HIGHLIGHT_PRODUCT") {
            highlightProduct(message.productUrl);
            sendResponse({ success: true });
            return true;
        }
    });

    // ── DOM Product Extraction ─────────────────────────
    function extractProductsFromDOM() {
        const products = [];

        // Try multiple selectors for product cards
        const cardSelectors = [
            "div[data-id]",
            "div._1AtVbE",
            "div._4ddWXP",
            "div._2kHMtA",
            "a.CGtC98",
        ];

        let cards = [];
        for (const selector of cardSelectors) {
            cards = document.querySelectorAll(selector);
            if (cards.length > 2) break;
        }

        cards.forEach((card) => {
            try {
                const product = {};

                // Title
                const titleEl = card.querySelector("a.IRpwTa, a.s1Q9rs, div._4rR01T, a.WKTcLC, a[title]");
                if (titleEl) {
                    product.title = titleEl.getAttribute("title") || titleEl.textContent?.trim() || "";
                }
                if (!product.title) return;

                // URL
                const linkEl = card.querySelector("a[href*='/p/'], a[href*='pid=']");
                if (linkEl) {
                    const href = linkEl.getAttribute("href");
                    product.url = href?.startsWith("/") ? `https://www.flipkart.com${href}` : href || "";
                } else if (titleEl?.href) {
                    product.url = titleEl.href;
                } else {
                    product.url = "";
                }

                // Price
                const priceEl = card.querySelector("div._30jeq3, div._25b18c, div._1_WHN1");
                if (priceEl) {
                    const priceText = priceEl.textContent?.replace(/[^\d.]/g, "").replace(/,/g, "") || "";
                    product.price = parseFloat(priceText) || null;
                }

                // Rating
                const ratingEl = card.querySelector("div._3LWZlK, span._1lRcqv, div.XQDdHH");
                if (ratingEl) {
                    const ratingText = ratingEl.textContent?.trim() || "";
                    const match = ratingText.match(/(\d+\.?\d*)/);
                    product.rating = match ? parseFloat(match[1]) : null;
                }

                // Review count
                const reviewEl = card.querySelector("span._2_R_DZ, span._13vcmD");
                if (reviewEl) {
                    const reviewText = reviewEl.textContent || "";
                    const match = reviewText.match(/([\d,]+)/);
                    product.review_count = match ? parseInt(match[1].replace(/,/g, ""), 10) : 0;
                } else {
                    product.review_count = 0;
                }

                // Sponsored
                const sponsoredEl = card.querySelector(
                    "div._3wiB3O, span[class*='sponsored'], div.siBJMo"
                );
                product.sponsored = !!sponsoredEl;

                // Offers
                const offerEl = card.querySelector("div._3Ay6Sb, li._1QoClr, span._3j9-Vb, div.UkUFwK");
                product.offers = offerEl?.textContent?.trim() || "";

                if (product.title && product.price) {
                    products.push(product);
                }
            } catch {
                // Skip malformed cards
            }
        });

        return products;
    }

    // ── Highlight Product on Page ──────────────────────
    function highlightProduct(productUrl) {
        if (!productUrl) return;

        // Find the product link on the page
        const links = document.querySelectorAll(`a[href*="${new URL(productUrl).pathname}"]`);
        links.forEach((link) => {
            const card = link.closest("div[data-id], div._1AtVbE, div._4ddWXP, div._2kHMtA");
            if (card) {
                card.style.outline = "3px solid #7C3AED";
                card.style.outlineOffset = "2px";
                card.style.borderRadius = "8px";
                card.style.transition = "outline 0.3s ease";
                card.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
    }

    // ── Init ───────────────────────────────────────────
    console.log("[ClarityCart] Content script loaded on Flipkart");
})();
