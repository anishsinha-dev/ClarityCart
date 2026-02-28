"""
Web Search Sentiment Analysis Module.

Uses duckduckgo-search to find web reviews and discussions about a product,
and runs lightweight sentiment analysis using TextBlob.
"""

import logging
from typing import Optional
from textblob import TextBlob
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def _clean_text(text: str) -> str:
    """Clean basic text."""
    import re
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\w\s.,!?'-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _analyze_sentiment(text: str) -> float:
    """Return sentiment polarity in [-1.0, 1.0] using TextBlob."""
    if not text:
        return 0.0
    blob = TextBlob(text)
    return blob.sentiment.polarity

def _classify_sentiment(score: float) -> str:
    if score > 0.1:
        return "Positive"
    elif score < -0.1:
        return "Negative"
    return "Mixed"

def _extract_themes(texts: list[str], category: str) -> list[str]:
    """Extract common keywords from texts."""
    stop_words = {
        "the", "is", "it", "in", "to", "and", "a", "of", "for", "on",
        "with", "this", "that", "was", "are", "be", "have", "has", "had",
        "not", "but", "from", "they", "you", "we", "can", "an", "will",
        "my", "one", "all", "would", "there", "their", "been", "if", "more",
        "when", "so", "very", "just", "about", "than", "its", "also", "after",
        "do", "did", "no", "get", "got", "like", "really", "much", "even",
        "out", "up", "what", "which", "some", "me", "i", "im", "review",
        "reviews", "product", "good", "bad", "buy", "buying"
    }

    word_freq = {}
    for text in texts:
        words = _clean_text(text.lower()).split()
        for word in words:
            if len(word) > 3 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:5]]

async def analyze_web_sentiment(product_name: str) -> Optional[dict]:
    """
    Search the web via DuckDuckGo for reviews/discussions and analyze sentiment.
    """
    search_query = " ".join(product_name.split()[:5]) + " review"
    
    try:
        logger.info(f"Running Web Search background check for: {search_query}")
        
        # duckduckgo-search is synchronous, so we run it in a thread pool if needed,
        # but for simplicity in FastAPI we can just run it
        # Try to get 10 results
        results = []
        with DDGS() as ddgs:
            # We use text() instead of news() to get blog reviews, forums, etc.
            for r in ddgs.text(search_query, max_results=10):
                if r.get('body') or r.get('title'):
                    results.append(r)
        
        if not results:
            return _empty_result("No web results found")

        all_texts = []
        positive_texts = []
        negative_texts = []
        sample_posts = []

        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("href", "")
            
            full_text = f"{title}. {body}".strip()
            if not full_text:
                continue

            all_texts.append(full_text)
            sentiment = _analyze_sentiment(full_text)

            if sentiment > 0.1:
                positive_texts.append(full_text)
            elif sentiment < -0.1:
                negative_texts.append(full_text)

            # Format similar to Reddit results for the UI
            sample_posts.append({
                "title": title[:100],
                "subreddit": url.split("/")[2] if "//" in url else url[:30], # Extract domain
                "score": 0, # N/A for web
                "sentiment": _classify_sentiment(sentiment),
                "url": url,
            })

        if all_texts:
            avg_sentiment = sum(_analyze_sentiment(t) for t in all_texts) / len(all_texts)
        else:
            avg_sentiment = 0.0

        return {
            "overall_sentiment": _classify_sentiment(avg_sentiment),
            "sentiment_score": round(avg_sentiment, 3),
            "common_praise": _extract_themes(positive_texts, "praise"),
            "common_complaints": _extract_themes(negative_texts, "complaints"),
            "post_count": len(sample_posts),
            "sample_posts": sample_posts[:5],
        }

    except Exception as e:
        logger.error(f"Web sentiment error: {e}")
        return _empty_result(str(e))

def _empty_result(reason: str) -> dict:
    return {
        "overall_sentiment": "Unknown",
        "sentiment_score": 0.0,
        "common_praise": [],
        "common_complaints": [],
        "post_count": 0,
        "sample_posts": [],
        "note": reason,
    }
