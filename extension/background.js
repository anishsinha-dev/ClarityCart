/**
 * ClarityCart — Background Service Worker (Manifest V3)
 *
 * Handles:
 * - Extension lifecycle events
 * - Message routing between popup and content scripts
 * - Context menu integration (future)
 */

// ── Installation ─────────────────────────────────────
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === "install") {
        console.log("[ClarityCart] Extension installed successfully");
    } else if (details.reason === "update") {
        console.log("[ClarityCart] Extension updated to version", chrome.runtime.getManifest().version);
    }
});

// ── Message Handling ─────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "ANALYZE_REQUEST") {
        // Forward analyze request to backend
        handleAnalyzeRequest(message.payload)
            .then(sendResponse)
            .catch((err) => sendResponse({ success: false, error: err.message }));
        return true; // Keep message channel open for async response
    }

    if (message.type === "HEALTH_CHECK") {
        fetch("http://localhost:8000/health")
            .then((r) => r.json())
            .then(sendResponse)
            .catch(() => sendResponse({ status: "offline" }));
        return true;
    }

    if (message.type === "GET_PAGE_PRODUCTS") {
        // Request product data from the active Flipkart tab's content script
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]?.id) {
                chrome.tabs.sendMessage(tabs[0].id, { type: "EXTRACT_PRODUCTS" }, sendResponse);
            } else {
                sendResponse({ products: [] });
            }
        });
        return true;
    }
});

// ── Backend Communication ────────────────────────────
async function handleAnalyzeRequest(payload) {
    try {
        const response = await fetch("http://localhost:8000/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`Backend returned ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error("[ClarityCart] Backend request failed:", error);
        throw error;
    }
}
