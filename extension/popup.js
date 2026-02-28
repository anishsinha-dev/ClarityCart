/**
 * ClarityCart — Popup Script
 *
 * Handles:
 * - Backend health checking
 * - Sending analysis requests
 * - Rendering results
 * - Order automation trigger
 */

const API_BASE = "http://localhost:8000";

// ── DOM Elements ─────────────────────────────────────
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const queryInput = document.getElementById("queryInput");
const limitSelect = document.getElementById("limitSelect");
const redditToggle = document.getElementById("redditToggle");
const analyzeBtn = document.getElementById("analyzeBtn");
const loadingSection = document.getElementById("loadingSection");
const loadingText = document.getElementById("loadingText");
const resultsSection = document.getElementById("resultsSection");
const errorSection = document.getElementById("errorSection");
const errorText = document.getElementById("errorText");
const retryBtn = document.getElementById("retryBtn");
const resetBtn = document.getElementById("resetBtn");
const buyBtn = document.getElementById("buyBtn");

// Loading steps
const stepScrape = document.getElementById("stepScrape");
const stepScore = document.getElementById("stepScore");
const stepExplain = document.getElementById("stepExplain");
const stepReddit = document.getElementById("stepReddit");

// Result elements
const productTitle = document.getElementById("productTitle");
const productPrice = document.getElementById("productPrice");
const productRating = document.getElementById("productRating");
const productReviews = document.getElementById("productReviews");
const productScore = document.getElementById("productScore");
const productOffers = document.getElementById("productOffers");
const offersRow = document.getElementById("offersRow");
const sponsoredBadge = document.getElementById("sponsoredBadge");
const explanationText = document.getElementById("explanationText");
const reviewSummaryText = document.getElementById("reviewSummaryText");
const viewOnAmazon = document.getElementById("viewOnFlipkart"); // The HTML id is still viewOnFlipkart, we just updated the visible text there, but let's change the JS variable for consistency/correctness. Wait, if I change the JS variable I have to change it below. No, I'll keep the JS variable name the same for simplicity unless I want to change both. Let's change the JS variable name to `viewOnAmazon` AND update the `getElementById` to `viewOnAmazon`. I will also need to update the HTML ID.
const sentimentCard = document.getElementById("sentimentCard");
const sentimentBadge = document.getElementById("sentimentBadge");
const sentimentCount = document.getElementById("sentimentCount");
const praiseList = document.getElementById("praiseList");
const complaintList = document.getElementById("complaintList");

const webSentimentCard = document.getElementById("webSentimentCard");
const webSentimentBadge = document.getElementById("webSentimentBadge");
const webSentimentCount = document.getElementById("webSentimentCount");
const webPraiseList = document.getElementById("webPraiseList");
const webComplaintList = document.getElementById("webComplaintList");

const top5List = document.getElementById("top5List");

// State
let currentProductUrl = "";

// ── Health Check ─────────────────────────────────────
async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
    const data = await resp.json();

    const dot = statusDot.querySelector(".dot");
    dot.className = "dot online";
    statusText.textContent = data.ollama_available ? "Ready (LLM ✓)" : "Ready (no LLM)";
    analyzeBtn.disabled = false;
  } catch {
    const dot = statusDot.querySelector(".dot");
    dot.className = "dot offline";
    statusText.textContent = "Backend offline";
    analyzeBtn.disabled = true;
  }
}

// ── Loading Steps Animation ──────────────────────────
function setStep(stepEl, state) {
  stepEl.className = `step ${state}`;
}

function showLoading(withReddit) {
  loadingSection.style.display = "flex";
  resultsSection.style.display = "none";
  errorSection.style.display = "none";

  setStep(stepScrape, "active");
  setStep(stepScore, "");
  setStep(stepExplain, "");
  stepReddit.style.display = withReddit ? "flex" : "none";
  if (withReddit) setStep(stepReddit, "");
}

function advanceStep(current, next) {
  setStep(current, "done");
  if (next) setStep(next, "active");
}

// ── Analyze ──────────────────────────────────────────
async function analyze() {
  const query = queryInput.value.trim();
  if (!query) {
    queryInput.focus();
    return;
  }

  const limit = parseInt(limitSelect.value, 10);
  const withReddit = redditToggle.checked;

  analyzeBtn.disabled = true;
  showLoading(withReddit);

  // Simulate step progression
  const stepTimers = [];
  stepTimers.push(setTimeout(() => {
    loadingText.textContent = "Scraping Amazon products...";
    advanceStep(stepScrape, stepScore);
  }, 5000));

  stepTimers.push(setTimeout(() => {
    loadingText.textContent = "Scoring and ranking products...";
    advanceStep(stepScore, stepExplain);
  }, 8000));

  if (withReddit) {
    stepTimers.push(setTimeout(() => {
      loadingText.textContent = "Running background checks...";
      advanceStep(stepExplain, stepReddit);
    }, 12000));
  }

  try {
    const resp = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        product_limit: limit,
        reddit_check: withReddit,
      }),
    });

    stepTimers.forEach(clearTimeout);

    if (!resp.ok) {
      throw new Error(`Server error: ${resp.status}`);
    }

    const data = await resp.json();

    if (!data.success) {
      showError(data.error || "Analysis failed. Try a different query.");
      return;
    }

    renderResults(data);
  } catch (err) {
    stepTimers.forEach(clearTimeout);
    showError(`Connection failed: ${err.message}. Is the backend running?`);
  } finally {
    analyzeBtn.disabled = false;
  }
}

// ── Render Results ───────────────────────────────────
function renderResults(data) {
  loadingSection.style.display = "none";
  errorSection.style.display = "none";
  resultsSection.style.display = "flex";

  const top = data.top_product;
  if (!top) {
    showError("No products found.");
    return;
  }

  // Top product card
  productTitle.textContent = top.title;
  productPrice.textContent = top.price ? `₹${top.price.toLocaleString("en-IN")}` : "N/A";
  productRating.textContent = top.rating ? `${top.rating} ★` : "N/A";
  productReviews.textContent = top.review_count ? top.review_count.toLocaleString("en-IN") : "0";
  productScore.textContent = (top.score * 100).toFixed(1) + "%";

  // Offers
  if (top.offers && top.offers.trim()) {
    offersRow.style.display = "flex";
    productOffers.textContent = top.offers;
  } else {
    offersRow.style.display = "none";
  }

  // Sponsored
  sponsoredBadge.style.display = top.sponsored ? "block" : "none";

  // Explanation
  explanationText.innerHTML = (data.explanation || "Explanation unavailable.").replace(/\n/g, '<br/>');

  // Review Summary
  if (data.review_summary) {
    reviewSummaryText.innerHTML = data.review_summary.replace(/\n/g, '<br/>');
    reviewSummaryText.parentElement.style.display = "block";
  } else {
    reviewSummaryText.parentElement.style.display = "none";
  }

  // Amazon link
  currentProductUrl = top.url || "";
  viewOnAmazon.href = currentProductUrl;
  viewOnAmazon.style.display = currentProductUrl ? "flex" : "none";

  // Reddit sentiment
  if (data.reddit_sentiment && data.reddit_sentiment.overall_sentiment !== "Unknown") {
    renderSentiment(data.reddit_sentiment);
    sentimentCard.style.display = "block";
  } else {
    sentimentCard.style.display = "none";
  }

  // Web sentiment
  if (data.web_sentiment && data.web_sentiment.overall_sentiment !== "Unknown") {
    renderWebSentiment(data.web_sentiment);
    webSentimentCard.style.display = "block";
  } else {
    webSentimentCard.style.display = "none";
  }

  // Top 5
  renderTop5(data.top_5 || []);

  // Save last query
  chrome.storage?.local?.set({ lastQuery: queryInput.value, lastLimit: limitSelect.value });
}

function renderSentiment(sentiment) {
  const overall = sentiment.overall_sentiment || "Unknown";
  sentimentBadge.textContent = overall;
  sentimentBadge.className = `sentiment-badge ${overall.toLowerCase()}`;
  sentimentCount.textContent = `Based on ${sentiment.post_count || 0} Reddit posts`;

  // Praise
  praiseList.innerHTML = "";
  (sentiment.common_praise || []).forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    praiseList.appendChild(li);
  });
  if (!sentiment.common_praise?.length) {
    praiseList.innerHTML = "<li>No specific praise found</li>";
  }

  // Complaints
  complaintList.innerHTML = "";
  (sentiment.common_complaints || []).forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    complaintList.appendChild(li);
  });
  if (!sentiment.common_complaints?.length) {
    complaintList.innerHTML = "<li>No specific complaints found</li>";
  }
}

function renderWebSentiment(sentiment) {
  const overall = sentiment.overall_sentiment || "Unknown";
  webSentimentBadge.textContent = overall;
  webSentimentBadge.className = `sentiment-badge ${overall.toLowerCase()}`;
  webSentimentCount.textContent = `Based on web reviews / articles`;

  // Praise
  webPraiseList.innerHTML = "";
  (sentiment.common_praise || []).forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    webPraiseList.appendChild(li);
  });
  if (!sentiment.common_praise?.length) {
    webPraiseList.innerHTML = "<li>No specific praise found</li>";
  }

  // Complaints
  webComplaintList.innerHTML = "";
  (sentiment.common_complaints || []).forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    webComplaintList.appendChild(li);
  });
  if (!sentiment.common_complaints?.length) {
    webComplaintList.innerHTML = "<li>No specific complaints found</li>";
  }
}

function renderTop5(products) {
  top5List.innerHTML = "";

  products.forEach((p, idx) => {
    const item = document.createElement("a");
    item.className = "top5-item";
    item.href = p.url || "#";
    item.target = "_blank";
    item.rel = "noopener";

    item.innerHTML = `
      <div class="top5-rank ${idx === 0 ? 'rank-1' : ''}">${idx + 1}</div>
      <div class="top5-info">
        <div class="top5-name">${escapeHtml(p.title)}</div>
        <div class="top5-meta">
          <span>₹${p.price ? p.price.toLocaleString("en-IN") : "N/A"}</span>
          <span>${p.rating ? p.rating + " ★" : "N/A"}</span>
          <span>${p.review_count ? p.review_count.toLocaleString("en-IN") + " reviews" : ""}</span>
        </div>
      </div>
      <div class="top5-score">${(p.score * 100).toFixed(1)}%</div>
    `;

    top5List.appendChild(item);
  });
}

// ── Order Automation ─────────────────────────────────
async function triggerOrder() {
  if (!currentProductUrl) {
    alert("No product URL available.");
    return;
  }

  const confirmed = confirm(
    "This will open a browser window, navigate to the product page, and add it to your cart.\n\n" +
    "You will need to be logged into Amazon.\n\n" +
    "Continue?"
  );

  if (!confirmed) return;

  buyBtn.textContent = "⏳ Adding to cart...";
  buyBtn.disabled = true;

  try {
    const resp = await fetch(`${API_BASE}/order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_url: currentProductUrl }),
    });

    const data = await resp.json();

    if (data.status === "success") {
      buyBtn.textContent = "✅ Added to cart!";
    } else {
      buyBtn.textContent = "❌ " + (data.message || "Failed");
    }
  } catch (err) {
    buyBtn.textContent = "❌ Error";
    console.error("Order error:", err);
  }

  setTimeout(() => {
    buyBtn.textContent = "🛒 Add to Cart";
    buyBtn.disabled = false;
  }, 3000);
}

// ── Error / Reset ────────────────────────────────────
function showError(message) {
  loadingSection.style.display = "none";
  resultsSection.style.display = "none";
  errorSection.style.display = "flex";
  errorText.textContent = message;
  analyzeBtn.disabled = false;
}

function resetUI() {
  resultsSection.style.display = "none";
  errorSection.style.display = "none";
  loadingSection.style.display = "none";
  queryInput.value = "";
  queryInput.focus();
}

// ── Utility ──────────────────────────────────────────
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ── Event Listeners ──────────────────────────────────
analyzeBtn.addEventListener("click", analyze);
retryBtn.addEventListener("click", () => {
  errorSection.style.display = "none";
  queryInput.focus();
});
resetBtn.addEventListener("click", resetUI);
buyBtn.addEventListener("click", triggerOrder);

queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !analyzeBtn.disabled) {
    analyze();
  }
});

// Enable/disable button based on input
queryInput.addEventListener("input", () => {
  const dot = statusDot.querySelector(".dot");
  if (dot.classList.contains("online")) {
    analyzeBtn.disabled = !queryInput.value.trim();
  }
});

// ── Init ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  queryInput.focus();

  // Restore last query
  chrome.storage?.local?.get(["lastQuery", "lastLimit"], (data) => {
    if (data?.lastQuery) queryInput.value = data.lastQuery;
    if (data?.lastLimit) limitSelect.value = data.lastLimit;
  });
});
