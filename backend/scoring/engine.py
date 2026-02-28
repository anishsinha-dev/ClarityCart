"""
Deterministic Product Scoring Engine.

Scores products using a weighted formula — NO LLM involved.

Formula:
    score = (rating_norm * 0.35) +
            (review_norm * 0.25) +
            (price_norm * 0.20) +
            (offer_bonus * 0.10) +
            (non_sponsored_bonus * 0.10)

All values are normalized to [0, 1] before weighting.
"""

import math
import logging
from typing import Optional

from config import (
    WEIGHT_RATING,
    WEIGHT_REVIEWS,
    WEIGHT_PRICE,
    WEIGHT_OFFERS,
    WEIGHT_NON_SPONSORED,
)

logger = logging.getLogger(__name__)


def _normalize_rating(rating: Optional[float]) -> float:
    """Normalize rating from [0, 5] to [0, 1]."""
    if rating is None or rating <= 0:
        return 0.0
    return min(rating / 5.0, 1.0)


def _normalize_reviews(review_count: int, max_reviews: int) -> float:
    """Normalize review count using log scale relative to max in dataset."""
    if review_count <= 0:
        return 0.0
    if max_reviews <= 0:
        return 0.0
    # Log scale normalization prevents review-count domination
    return min(math.log(review_count + 1) / math.log(max_reviews + 1), 1.0)


def _normalize_price(price: Optional[float], min_price: float, max_price: float) -> float:
    """
    Normalize price — lower is better.
    Returns 1.0 for the cheapest product, 0.0 for the most expensive.
    """
    if price is None or price <= 0:
        return 0.0
    if max_price == min_price:
        return 1.0  # All same price
    # Invert: cheaper = higher score
    return 1.0 - ((price - min_price) / (max_price - min_price))


def _offer_bonus(offers: str) -> float:
    """Return 1.0 if product has offers, 0.0 otherwise."""
    if offers and offers.strip():
        return 1.0
    return 0.0


def _non_sponsored_bonus(sponsored: bool) -> float:
    """Return 1.0 for organic listings, 0.0 for sponsored."""
    return 0.0 if sponsored else 1.0


def score_products(products: list[dict]) -> list[dict]:
    """
    Score and rank a list of products.
    
    Each product dict should have:
        title, price, rating, review_count, sponsored, url, offers
    
    Returns the same list with 'score' field added, sorted descending by score.
    """
    if not products:
        return []

    # Compute dataset-wide stats for normalization
    prices = [p["price"] for p in products if p.get("price") and p["price"] > 0]
    reviews = [p.get("review_count", 0) for p in products]

    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    max_reviews = max(reviews) if reviews else 0

    scored = []
    for product in products:
        rating_norm = _normalize_rating(product.get("rating"))
        review_norm = _normalize_reviews(product.get("review_count", 0), max_reviews)
        price_norm = _normalize_price(product.get("price"), min_price, max_price)
        offer_val = _offer_bonus(product.get("offers", ""))
        non_sponsored_val = _non_sponsored_bonus(product.get("sponsored", False))

        score = (
            (rating_norm * WEIGHT_RATING) +
            (review_norm * WEIGHT_REVIEWS) +
            (price_norm * WEIGHT_PRICE) +
            (offer_val * WEIGHT_OFFERS) +
            (non_sponsored_val * WEIGHT_NON_SPONSORED)
        )

        product["score"] = round(score, 4)

        # Add breakdown for debugging/display
        product["_score_breakdown"] = {
            "rating_contribution": round(rating_norm * WEIGHT_RATING, 4),
            "review_contribution": round(review_norm * WEIGHT_REVIEWS, 4),
            "price_contribution": round(price_norm * WEIGHT_PRICE, 4),
            "offer_contribution": round(offer_val * WEIGHT_OFFERS, 4),
            "non_sponsored_contribution": round(non_sponsored_val * WEIGHT_NON_SPONSORED, 4),
        }

        scored.append(product)

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"Scored {len(scored)} products. Top score: {scored[0]['score'] if scored else 'N/A'}")
    return scored
