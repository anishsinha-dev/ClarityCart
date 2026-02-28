"""
Amazon Scraper — Subprocess-based wrapper.

Runs the scraper in a separate Python process to avoid
Python 3.14 asyncio subprocess compatibility issues with
uvicorn on Windows.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys

from config import MAX_PRODUCT_LIMIT

logger = logging.getLogger(__name__)

# Path to the worker script
_WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "amazon_worker.py")

# Path to the Python executable in the venv
_PYTHON_EXE = sys.executable


async def scrape_amazon(query: str, product_limit: int = 30) -> list[dict]:
    """
    Main entry point for scraping Amazon products.

    Runs the scraper as a separate Python process using subprocess
    to avoid Python 3.14 asyncio event loop compatibility issues.

    Args:
        query: Search term (natural language)
        product_limit: Maximum products to collect

    Returns:
        List of product dicts with keys:
        title, price, rating, review_count, sponsored, url, offers
    """
    product_limit = min(product_limit, MAX_PRODUCT_LIMIT)

    logger.info(f"Starting scraper subprocess for: '{query}' (limit={product_limit})")

    # Run the worker script as a separate process
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _run_worker_subprocess,
        query,
        product_limit,
    )

    return result


def _run_worker_subprocess(query: str, product_limit: int) -> list[dict]:
    """Run the scraper worker as a subprocess and parse its JSON output."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        proc = subprocess.run(
            [_PYTHON_EXE, _WORKER_SCRIPT, query, str(product_limit)],
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout
            cwd=backend_dir,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Scraper timed out after 3 minutes")
    except Exception as e:
        raise RuntimeError(f"Failed to start scraper process: {e}")

    # Log stderr (contains scraper progress logs)
    if proc.stderr:
        for line in proc.stderr.strip().split("\n"):
            if line.strip():
                logger.info(f"[worker] {line.strip()}")

    if proc.returncode != 0:
        error_msg = proc.stderr.strip().split("\n")[-1] if proc.stderr else "Unknown error"
        raise RuntimeError(f"Scraper process failed (exit {proc.returncode}): {error_msg}")

    # Parse stdout as JSON
    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("Scraper process produced no output")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from scraper: {e}")

    # Check for error response
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"Scraper error: {data['error']}")

    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected scraper output type: {type(data)}")

    logger.info(f"Scraper subprocess returned {len(data)} products")
    return data
