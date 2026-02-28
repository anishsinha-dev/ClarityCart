"""
ClarityCart Configuration
"""

# Server
HOST = "0.0.0.0"
PORT = 8000

# Scraper
AMAZON_BASE = "https://www.amazon.in"
AMAZON_SEARCH = f"{AMAZON_BASE}/s?k={{}}"
DEFAULT_PRODUCT_LIMIT = 30
MAX_PRODUCT_LIMIT = 100
SCRAPE_TIMEOUT_MS = 60_000
PAGE_LOAD_WAIT_MS = 3000
SCROLL_PAUSE_MS = 1000
MAX_SCROLL_ATTEMPTS = 15

# Scoring weights
WEIGHT_RATING = 0.35
WEIGHT_REVIEWS = 0.25
WEIGHT_PRICE = 0.20
WEIGHT_OFFERS = 0.10
WEIGHT_NON_SPONSORED = 0.10

# LLM
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:latest"
OLLAMA_TIMEOUT = 120
LLM_MAX_PRODUCTS = 5

# Reddit
REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
REDDIT_MAX_POSTS = 10
REDDIT_MAX_COMMENTS = 30
REDDIT_USER_AGENT = "ClarityCart/1.0 (Educational Research Bot)"

# Playwright
BROWSER_HEADLESS = True
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
