"""
ClarityCart — FastAPI Backend Entry Point.

Endpoints:
    POST /analyze       — Full analysis pipeline
    POST /order         — Order automation
    GET  /health        — Health check
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from scraper.amazon_scraper import scrape_amazon
from scoring.engine import score_products
from llm.explainer import explain_product, check_ollama_health
from sentiment.reddit import analyze_reddit_sentiment
from automation.order import add_to_cart
from config import DEFAULT_PRODUCT_LIMIT, MAX_PRODUCT_LIMIT, PORT, HOST

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("claritycart")


# ── Lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🛒 ClarityCart backend starting...")
    ollama_ok = await check_ollama_health()
    if ollama_ok:
        logger.info("✅ Ollama is available — LLM explanations enabled")
    else:
        logger.warning("⚠ Ollama not available — falling back to rule-based explanations")
    yield
    logger.info("ClarityCart backend shutting down")


# ── App ──────────────────────────────────────────────────
app = FastAPI(
    title="ClarityCart API",
    description="AI-powered Flipkart shopping assistant backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Chrome extension will connect from chrome-extension:// origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ────────────────────────────
class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="Natural language product query")
    product_limit: int = Field(DEFAULT_PRODUCT_LIMIT, ge=5, le=MAX_PRODUCT_LIMIT)
    reddit_check: bool = Field(False, description="Enable Reddit background sentiment check")


class ProductResponse(BaseModel):
    title: str
    price: Optional[float]
    rating: Optional[float]
    review_count: int = 0
    sponsored: bool = False
    url: str = ""
    offers: str = ""
    score: float = 0.0


class AnalyzeResponse(BaseModel):
    success: bool
    query: str
    total_scraped: int
    top_product: Optional[ProductResponse]
    explanation: str
    reddit_sentiment: Optional[dict] = None
    top_5: list[ProductResponse] = []
    error: Optional[str] = None


class OrderRequest(BaseModel):
    product_url: str = Field(..., description="Flipkart product URL")


class OrderResponse(BaseModel):
    status: str
    message: str
    product_url: str = ""
    cart_url: str = ""


# ── Endpoints ────────────────────────────────────────────
@app.get("/health")
async def health_check():
    ollama_ok = await check_ollama_health()
    return {
        "status": "healthy",
        "ollama_available": ollama_ok,
        "version": "1.0.0",
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Full analysis pipeline:
    1. Scrape Amazon for products
    2. Score products deterministically
    3. Generate LLM explanation for the #1 product
    4. Optionally run Reddit sentiment check
    """
    logger.info(f"📦 Analyzing: '{request.query}' (limit={request.product_limit})")

    # Step 1: Scrape
    try:
        products = await scrape_amazon(request.query, request.product_limit)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return AnalyzeResponse(
            success=False,
            query=request.query,
            total_scraped=0,
            top_product=None,
            explanation="",
            error=f"Scraping failed: {str(e)}",
        )

    if not products:
        return AnalyzeResponse(
            success=False,
            query=request.query,
            total_scraped=0,
            top_product=None,
            explanation="",
            error="No products found. Try a different search query.",
        )

    logger.info(f"Scraped {len(products)} products")

    # Step 2: Score
    scored = score_products(products)
    top = scored[0]
    top_5 = scored[:5]

    # Step 3: LLM Explanation (async)
    # Step 4: Reddit Sentiment (async, conditional)
    tasks = [explain_product(top)]
    if request.reddit_check:
        tasks.append(analyze_reddit_sentiment(top["title"]))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    explanation = results[0] if isinstance(results[0], str) else "Explanation unavailable."
    reddit_sentiment = None
    if request.reddit_check and len(results) > 1:
        reddit_sentiment = results[1] if isinstance(results[1], dict) else None

    # Build response
    top_product = ProductResponse(
        title=top["title"],
        price=top.get("price"),
        rating=top.get("rating"),
        review_count=top.get("review_count", 0),
        sponsored=top.get("sponsored", False),
        url=top.get("url", ""),
        offers=top.get("offers", ""),
        score=top.get("score", 0),
    )

    top_5_response = [
        ProductResponse(
            title=p["title"],
            price=p.get("price"),
            rating=p.get("rating"),
            review_count=p.get("review_count", 0),
            sponsored=p.get("sponsored", False),
            url=p.get("url", ""),
            offers=p.get("offers", ""),
            score=p.get("score", 0),
        )
        for p in top_5
    ]

    return AnalyzeResponse(
        success=True,
        query=request.query,
        total_scraped=len(products),
        top_product=top_product,
        explanation=explanation,
        reddit_sentiment=reddit_sentiment,
        top_5=top_5_response,
    )


@app.post("/order", response_model=OrderResponse)
async def order(request: OrderRequest):
    """
    Add product to cart and pause for user confirmation.
    Opens a visible browser window.
    """
    logger.info(f"🛍️ Order automation for: {request.product_url}")
    result = await add_to_cart(request.product_url)
    return OrderResponse(**result)


# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
