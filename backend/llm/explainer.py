"""
LLM Explainer — Generates "Why this product?" explanations using local Ollama.

Only called for the TOP-RANKED product after deterministic scoring.
Never used for re-scoring or re-ranking.
"""

import logging
import httpx

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)

EXPLAIN_PROMPT_TEMPLATE = """You are a smart shopping assistant. Based on the product data below, explain in exactly 3 concise bullet points why this product is the best pick. Be factual. Reference the rating, number of reviews, price, and value. Do NOT re-rank or re-score. Keep it simple — the user is non-technical.

Product:
- Title: {title}
- Price: ₹{price}
- Rating: {rating}/5
- Reviews: {review_count}
- Offers: {offers}
- Sponsored: {sponsored}

Respond ONLY with 3 bullet points. No intro sentence. No markdown headers."""


async def explain_product(product: dict) -> str:
    """
    Generate a 3-bullet explanation for why this product is the top pick.
    
    Args:
        product: The top-scoring product dict.
        
    Returns:
        String with 3 bullet points, or a fallback message if LLM fails.
    """
    prompt = EXPLAIN_PROMPT_TEMPLATE.format(
        title=product.get("title", "Unknown"),
        price=product.get("price", "N/A"),
        rating=product.get("rating", "N/A"),
        review_count=product.get("review_count", 0),
        offers=product.get("offers", "None"),
        sponsored="Yes" if product.get("sponsored") else "No",
    )

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 200,
                        "num_ctx": 2048,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            explanation = data.get("response", "").strip()

            if explanation:
                logger.info("LLM explanation generated successfully")
                return explanation
            else:
                logger.warning("LLM returned empty response")
                return _fallback_explanation(product)

    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama. Is it running? (ollama serve)")
        return _fallback_explanation(product)
    except Exception as e:
        logger.error(f"LLM explanation error: {e}")
        return _fallback_explanation(product)


def _fallback_explanation(product: dict) -> str:
    """Generate a rule-based explanation when LLM is unavailable."""
    lines = []

    rating = product.get("rating")
    if rating and rating >= 4.0:
        lines.append(f"• Highly rated at {rating}/5 stars by verified buyers.")
    elif rating:
        lines.append(f"• Rated {rating}/5 stars — decent for its price range.")
    else:
        lines.append("• Rating data unavailable, but selected on overall value.")

    review_count = product.get("review_count", 0)
    if review_count > 1000:
        lines.append(f"• Backed by {review_count:,} reviews — a popular, well-tested choice.")
    elif review_count > 100:
        lines.append(f"• Has {review_count:,} reviews — enough social proof for confidence.")
    else:
        lines.append("• Fewer reviews, but scored well on price-to-quality ratio.")

    price = product.get("price")
    offers = product.get("offers", "")
    if price and offers:
        lines.append(f"• Priced at ₹{price:,.0f} with active offers — strong value for money.")
    elif price:
        lines.append(f"• Priced at ₹{price:,.0f} — competitive in its category.")
    else:
        lines.append("• Good overall value relative to alternatives analyzed.")

    return "\n".join(lines)


async def check_ollama_health() -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if any(OLLAMA_MODEL in m for m in models):
                    return True
                logger.warning(f"Model {OLLAMA_MODEL} not found. Available: {models}")
            return False
    except Exception:
        return False
