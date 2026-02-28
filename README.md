# 🛒 ClarityCart — AI-Powered Flipkart Shopping Assistant

> Find the **single best product** on Flipkart using deterministic scoring, local AI explanations, and Reddit sentiment analysis. Runs **100% locally** with zero paid APIs.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Search** | Natural language input — just type what you want |
| 📄 **Multi-Page Scraping** | Scrapes across multiple Flipkart pages (not just page 1) |
| ⚡ **Deterministic Scoring** | Weighted formula: rating × reviews × price × offers × organic bonus |
| 🏷️ **Sponsored Penalization** | Automatically detects and penalizes sponsored listings |
| 🤖 **AI Explanation** | Local LLM explains "Why this product?" in 3 bullet points |
| 📊 **Reddit Sentiment** | Background check using real Reddit posts + comments |
| 🛍️ **Order Automation** | One-click add-to-cart with safety confirmation |
| 🔒 **100% Local** | Everything runs on your machine. No data leaves your system |

---

## 🏗️ Architecture

```
Chrome Extension (Popup UI)
        │  POST /analyze
        ▼
FastAPI Backend (localhost:8000)
        │
        ├── Playwright Scraper  →  Flipkart
        ├── Scoring Engine      →  Deterministic ranking
        ├── LLM Explainer       →  Ollama (local)
        ├── Reddit Sentiment    →  Reddit public API
        └── Order Automation    →  Playwright (visible browser)
```

---

## 📁 Project Structure

```
ClarityCart/
├── backend/
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # All configuration constants
│   ├── requirements.txt            # Python dependencies
│   ├── scraper/
│   │   └── flipkart_scraper.py     # Playwright multi-page scraper
│   ├── scoring/
│   │   └── engine.py               # Deterministic scoring engine
│   ├── llm/
│   │   └── explainer.py            # Ollama LLM integration
│   ├── sentiment/
│   │   └── reddit.py               # Reddit sentiment module
│   └── automation/
│       └── order.py                # Order automation module
├── extension/
│   ├── manifest.json               # Chrome Manifest V3
│   ├── popup.html                  # Extension popup UI
│   ├── popup.css                   # Dark-mode premium styling
│   ├── popup.js                    # Popup logic
│   ├── background.js               # Service worker
│   ├── content.js                  # Flipkart content script
│   └── icons/                      # Extension icons
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Google Chrome
- [Ollama](https://ollama.com/download) (optional — fallback works without it)

### 1. Install Ollama & Pull Model
```powershell
# Download Ollama from https://ollama.com/download
# Then pull a lightweight model:
ollama pull phi3:mini
```

### 2. Set Up Backend
```powershell
cd d:\Code\ClarityCart\backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Start Backend Server
```powershell
cd d:\Code\ClarityCart\backend
.\venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Load Chrome Extension
1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select `d:\Code\ClarityCart\extension\`

### 5. Use It!
1. Click the **ClarityCart** icon in your Chrome toolbar
2. Type: `"best wireless earbuds under 2000"`
3. Set product limit (default: 30)
4. Click **Analyze Products**
5. View the top-ranked product with AI explanation

---

## 🧮 Scoring Formula

```
score = (rating_normalized × 0.35)
      + (log(review_count) × 0.25)
      + (price_relative_score × 0.20)
      + (offer_bonus × 0.10)
      + (non_sponsored_bonus × 0.10)
```

- **Rating**: Normalized to [0, 1] from 5-star scale
- **Reviews**: Log-scaled to prevent domination by outliers
- **Price**: Inverted — cheaper = higher score (within search results)
- **Offers**: Binary bonus for products with active offers
- **Non-Sponsored**: Organic listings get a 10% bonus

---

## 💻 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | i5 10th Gen | Same |
| GPU | GTX 1650 (4GB) | Same |
| RAM | 8 GB | 16 GB |
| Ollama Model | `tinyllama` (1.1B) | `phi3:mini` (3.8B) |

### Ollama Optimization for GTX 1650
```powershell
$env:OLLAMA_NUM_THREADS = "6"
$env:OLLAMA_GPU_LAYERS = "35"
ollama serve
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Backend + Ollama status |
| `/analyze` | POST | Full analysis pipeline |
| `/order` | POST | Add product to cart |

### POST /analyze
```json
{
  "query": "best gaming mouse under 1500",
  "product_limit": 30,
  "reddit_check": true
}
```

---

## 🔒 Safety & Privacy

- **No paid APIs** — Everything runs locally
- **No data collection** — Your searches stay on your machine
- **Order safety** — Never auto-purchases. Always pauses for confirmation
- **Persistent login** — Flipkart session saved locally for convenience

---

## License

MIT
