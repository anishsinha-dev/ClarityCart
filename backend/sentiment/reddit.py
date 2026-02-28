"""
Reddit Sentiment Analysis Module.

Searches Reddit for product mentions, scrapes posts/comments,
and runs lightweight sentiment analysis using TextBlob.

No paid APIs — uses Reddit's public JSON endpoints.
"""

import logging
import re
from typing import Optional

import httpx
from textblob import TextBlob

from config import (
    REDDIT_SEARCH_URL,
    REDDIT_MAX_POSTS,
    REDDIT_MAX_COMMENTS,
    REDDIT_USER_AGENT,
)

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    """Remove URLs, special chars, and excessive whitespace."""
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
    """Classify a polarity score into a label."""
    if score > 0.1:
        return "Positive"
    elif score < -0.1:
        return "Negative"
    return "Mixed"


def _extract_themes(texts: list[str], category: str) -> list[str]:
    """
    Extract common praise or complaint keywords from a list of texts.
    Uses simple frequency-based extraction.
    """
    # Common filler words to exclude
    stop_words = {
        "the", "is", "it", "in", "to", "and", "a", "of", "for", "on",
        "with", "this", "that", "was", "are", "be", "have", "has", "had",
        "not", "but", "from", "they", "you", "we", "can", "an", "will",
        "my", "one", "all", "would", "there", "their", "been", "if", "more",
        "when", "so", "very", "just", "about", "than", "its", "also", "after",
        "do", "did", "no", "get", "got", "like", "really", "much", "even",
        "out", "up", "what", "which", "some", "me", "i", "im",
    }

    word_freq: dict[str, int] = {}
    for text in texts:
        words = _clean_text(text.lower()).split()
        for word in words:
            if len(word) > 3 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

    # Get top frequent words
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:5]]


async def analyze_reddit_sentiment(product_name: str) -> Optional[dict]:
    """
    Search Reddit for a product and analyze sentiment.
    
    Args:
        product_name: Product title (will be truncated for search).
    
    Returns:
        Dict with:
            overall_sentiment: "Positive" | "Mixed" | "Negative"
            sentiment_score: float [-1, 1]
            common_praise: list[str]
            common_complaints: list[str]
            post_count: int
            sample_posts: list[dict]
        Or None if Reddit search fails.
    """
    # Truncate product name for better search results
    search_query = " ".join(product_name.split()[:6])

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Search Reddit
            headers = {"User-Agent": REDDIT_USER_AGENT}
            params = {
                "q": search_query,
                "sort": "relevance",
                "limit": REDDIT_MAX_POSTS,
                "type": "link",
            }

            resp = await client.get(
                REDDIT_SEARCH_URL,
                headers=headers,
                params=params,
            )

            if resp.status_code == 429:
                logger.warning("Reddit rate-limited, skipping sentiment analysis")
                return _empty_result("Rate limited by Reddit")

            resp.raise_for_status()
            data = resp.json()

            posts = data.get("data", {}).get("children", [])
            if not posts:
                logger.info(f"No Reddit posts found for: {search_query}")
                return _empty_result("No Reddit posts found")

            # Process posts
            all_texts: list[str] = []
            positive_texts: list[str] = []
            negative_texts: list[str] = []
            sample_posts: list[dict] = []

            for post_wrapper in posts[:REDDIT_MAX_POSTS]:
                post = post_wrapper.get("data", {})
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                full_text = f"{title} {selftext}".strip()

                if not full_text:
                    continue

                all_texts.append(full_text)
                sentiment = _analyze_sentiment(full_text)

                if sentiment > 0.1:
                    positive_texts.append(full_text)
                elif sentiment < -0.1:
                    negative_texts.append(full_text)

                sample_posts.append({
                    "title": title[:120],
                    "subreddit": post.get("subreddit", ""),
                    "score": post.get("score", 0),
                    "sentiment": _classify_sentiment(sentiment),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                })

            # Also try to fetch comments from top posts
            comment_texts = await _fetch_top_comments(client, posts[:3], headers)
            all_texts.extend(comment_texts)

            for ct in comment_texts:
                s = _analyze_sentiment(ct)
                if s > 0.1:
                    positive_texts.append(ct)
                elif s < -0.1:
                    negative_texts.append(ct)

            # Overall sentiment
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

    except httpx.HTTPStatusError as e:
        logger.error(f"Reddit HTTP error: {e.response.status_code}")
        return _empty_result(f"Reddit returned {e.response.status_code}")
    except Exception as e:
        logger.error(f"Reddit sentiment error: {e}")
        return _empty_result(str(e))


async def _fetch_top_comments(
    client: httpx.AsyncClient,
    posts: list[dict],
    headers: dict,
) -> list[str]:
    """Fetch top comments from a few posts for deeper sentiment."""
    comments: list[str] = []
    count = 0

    for post_wrapper in posts:
        if count >= REDDIT_MAX_COMMENTS:
            break

        post = post_wrapper.get("data", {})
        permalink = post.get("permalink", "")
        if not permalink:
            continue

        try:
            url = f"https://www.reddit.com{permalink}.json"
            resp = await client.get(url, headers=headers, params={"limit": 10})
            if resp.status_code != 200:
                continue

            data = resp.json()
            if len(data) < 2:
                continue

            comment_listing = data[1].get("data", {}).get("children", [])
            for comment_wrapper in comment_listing:
                comment_data = comment_wrapper.get("data", {})
                body = comment_data.get("body", "")
                if body and len(body) > 20:
                    comments.append(_clean_text(body[:500]))
                    count += 1
                    if count >= REDDIT_MAX_COMMENTS:
                        break

        except Exception as e:
            logger.debug(f"Error fetching comments: {e}")
            continue

    return comments


def _empty_result(reason: str) -> dict:
    """Return an empty sentiment result with a note."""
    return {
        "overall_sentiment": "Unknown",
        "sentiment_score": 0.0,
        "common_praise": [],
        "common_complaints": [],
        "post_count": 0,
        "sample_posts": [],
        "note": reason,
    }
