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
from llm.explainer import explain_and_select_product, check_ollama_health
from sentiment.reddit import analyze_reddit_sentiment
from sentiment.web import analyze_web_sentiment
from automation.order import add_to_cart
from config import DEFAULT_PRODUCT_LIMIT, MAX_PRODUCT_LIMIT, PORT, HOST


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("claritycart")



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



app = FastAPI(
    title="ClarityCart API",
    description="AI-powered Flipkart shopping assistant backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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
    review_summary: str = ""
    reddit_sentiment: Optional[dict] = None
    web_sentiment: Optional[dict] = None
    top_5: list[ProductResponse] = []
    error: Optional[str] = None


class OrderRequest(BaseModel):
    product_url: str = Field(..., description="Flipkart product URL")


class OrderResponse(BaseModel):
    status: str
    message: str
    product_url: str = ""
    cart_url: str = ""



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
            review_summary="",
            error=f"Scraping failed: {str(e)}",
        )

    if not products:
        return AnalyzeResponse(
            success=False,
            query=request.query,
            total_scraped=0,
            top_product=None,
            explanation="",
            review_summary="",
            error="No products found. Try a different search query.",
        )

    logger.info(f"Scraped {len(products)} products")

    # Step 2: Score
    scored = score_products(products)
    top = scored[0]
    top_5 = scored[:5]

    # Step 3: LLM Explanation & Selection (async)
    # Step 4: Reddit & Web Sentiment (async, conditional)
    tasks = [explain_and_select_product(request.query, top_5)]
    
    if request.reddit_check:
        tasks.append(analyze_reddit_sentiment(top_5[0]["title"])) # Use top scored default for sentiment search while LLM thinks
        tasks.append(analyze_web_sentiment(top_5[0]["title"]))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)

    best_index = 0
    explanation = "Explanation unavailable."
    review_summary = ""
    reddit_sentiment = None
    web_sentiment = None

    llm_res = results[0]
    if not isinstance(llm_res, Exception) and len(llm_res) == 3:
        best_index, explanation, review_summary = llm_res
    else:
        logger.error(f"LLM task failed or returned unexpected format: {llm_res}")

    if request.reddit_check and len(results) > 2:
        reddit_sentiment = results[1] if isinstance(results[1], dict) else None
        web_sentiment = results[2] if isinstance(results[2], dict) else None

    # Re-assign top based on LLM's selection
    top = top_5[best_index] if best_index < len(top_5) else top_5[0]

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
        review_summary=review_summary,
        reddit_sentiment=reddit_sentiment,
        web_sentiment=web_sentiment,
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



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
