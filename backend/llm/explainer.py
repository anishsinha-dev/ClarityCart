import json
import logging
import httpx
from textblob import TextBlob
from typing import Tuple

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)

EXPLAIN_PROMPT_TEMPLATE = """You are an expert, highly intelligent shopping assistant.
A user asked for the following: "{user_query}"

Below are the top 5 products retrieved for this query. Your job is to:
1. Identify the SINGLE BEST product out of these 5 that perfectly matches the user's specific request (e.g. if they asked for a "laptop for video editing", pick the one with the best dedicated GPU; if they asked for "good selfie camera", pick the phone known for high MP front camera).
2. Provide exactly 3 short bullet points explaining WHY it fits their EXACT request. Mention specific features referenced in their prompt whenever possible.
3. Provide a 1-2 sentence "Review Summary" inferring the general consensus about this product based on its rating and review count.

Products:
{products_text}

Respond ONLY with valid JSON using this exact schema, and absolutely nothing else (no markdown blocks, no intro text):
{{
  "best_index": <integer from 0 to 4>,
  "explanation": "• point 1\\n• point 2\\n• point 3",
  "review_summary": "A short summary of what reviews indicate."
}}"""


async def explain_and_select_product(user_query: str, top_5_products: list[dict]) -> Tuple[int, str, str]:
    """
    Use local LLM to select the best product from the top 5 based on the user's prompt,
    and generate a tailored explanation and review summary.
    
    Returns:
        (best_index, explanation, review_summary)
    """
    products_text = ""
    for idx, p in enumerate(top_5_products):
        products_text += f"[{idx}] {p.get('title', 'Unknown')}\n"
        products_text += f"    Price: ₹{p.get('price', 'N/A')} | Rating: {p.get('rating', 'N/A')}/5 "
        products_text += f"({p.get('review_count', 0)} reviews)\n"
        if p.get('offers'):
            products_text += f"    Offers: {p.get('offers')}\n"
        products_text += "\n"

    prompt = EXPLAIN_PROMPT_TEMPLATE.format(
        user_query=user_query,
        products_text=products_text.strip()
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
                        "temperature": 0.2, # Low temperature for more deterministic JSON
                        "top_p": 0.9,
                        "num_predict": 300,
                        "num_ctx": 4096,
                    },
                    "format": "json" # Ollama JSON mode
                },
            )
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "").strip()

            try:
                result = json.loads(response_text)
                best_index = int(result.get("best_index", 0))
                explanation = result.get("explanation", "").strip()
                review_summary = result.get("review_summary", "").strip()
                
                # Bounds check
                if best_index < 0 or best_index >= len(top_5_products):
                    best_index = 0
                
                if explanation and review_summary:
                    logger.info(f"LLM expertly selected index {best_index} for query '{user_query}'")
                    return best_index, explanation, review_summary
                
            except json.JSONDecodeError:
                logger.error(f"LLM returned invalid JSON: {response_text}")
                pass

    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama. Is it running? (ollama serve)")
    except Exception as e:
        logger.error(f"LLM explanation error: {e}")

    # Fallback if LLM fails
    return 0, _fallback_explanation(top_5_products[0], user_query), _fallback_review_summary(top_5_products[0])


def _fallback_explanation(product: dict, query: str) -> str:
    """Generate a rule-based explanation when LLM is unavailable."""
    lines = []
    lines.append(f"• Selected based on overall deterministic scoring for '{query}'.")
    
    price = product.get("price")
    offers = product.get("offers", "")
    if price and offers:
        lines.append(f"• Priced at ₹{price:,.0f} with active offers — strong value.")
    elif price:
        lines.append(f"• Priced at ₹{price:,.0f} — competitive in its category.")

    if product.get("rating") and product.get("rating") >= 4.0:
        lines.append(f"• Highly rated at {product.get('rating')}/5 stars.")
    else:
        lines.append("• Represents the best balanced choice in the top results.")

    return "\n".join(lines[:3])


def _fallback_review_summary(product: dict) -> str:
    rating = product.get("rating")
    reviews = product.get("review_count", 0)
    
    if rating and rating >= 4.5 and reviews > 500:
        return "Reviews overwhelmingly praise this product for its top-tier quality and reliability."
    elif rating and rating >= 4.0:
        return "Generally positive reviews, indicating good satisfaction among most buyers."
    elif rating and reviews > 0:
        return "Reviews indicate a mixed but generally acceptable reception."
    return "Not enough detailed review data available to form a strong consensus."


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
