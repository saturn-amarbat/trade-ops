# Trade Ops

[![Language](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](#)
[![Status](https://img.shields.io/badge/status-active-success?style=flat-square)](#)

Automated US stock momentum scanner and bull flag detector with real-time Discord alerts. Built around the Ross Cameron small-cap trading methodology — scans for technical patterns, fires alerts instantly, and persists trade data to SQLite for backreview.

---

## 🧠 Technical Highlights (For Recruiters)

| Concept | Implementation |
|---|---|
| **Real-time Data Pipeline** | Continuously polls stock price/volume data and evaluates pattern conditions |
| **Pattern Detection** | Bull flag detection logic: identifies consolidation after sharp momentum moves |
| **Discord Bot Integration** | Posts formatted live alerts to a Discord channel via webhook/bot API |
| **SQLite Persistence** | Stores scan results, alerts, and ticker history for review and backtesting |
| **Automation** | Fully headless — runs as a background process with no manual intervention |

> **Skills:** Python, Discord API, SQLite, Real-time Automation, Financial Data Processing, Pattern Detection

---

## ⚙️ How It Works

1. **Scanner** polls market data for a universe of small-cap US stocks
2. **Pattern Engine** evaluates each ticker for bull flag conditions (sharp move up → tight consolidation)
3. **Alert System** fires a Discord message with ticker, price, volume, and pattern details when triggered
4. **Database** logs every scan result and alert to SQLite for post-session review

---

## 🚀 Setup

```bash
git clone https://github.com/saturn-amarbat/trade-ops.git
cd trade-ops
pip install -r requirements.txt
```

Create a `.env` file with your credentials:

```env
DISCORD_WEBHOOK_URL=your_discord_webhook_url
DATA_API_KEY=your_market_data_api_key
```

Run the scanner:

```bash
python main.py
```

---

## 📁 Project Structure

```
trade-ops/
├── main.py          # Entry point, scanner loop
├── scanner.py       # Market data fetching and filtering
├── patterns.py      # Bull flag and momentum pattern logic
├── alerts.py        # Discord alert formatting and delivery
├── db.py            # SQLite schema and persistence layer
└── requirements.txt
```

---

## 📜 License

MIT
