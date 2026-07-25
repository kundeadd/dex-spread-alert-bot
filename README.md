# dex-spread-alert-bot

Telegram bot that tracks price spread between DEX and MEXC Futures. Sends alert when spread opens, replies when it closes.

## What it does

Pulls prices for 1000+ tokens from MEXC Futures and compares with DEX prices via CoinGecko. When spread is big enough — sends Telegram notification with market data. When spread converges — replies to the original alert.

## Alert includes

- Spread % and direction (LONG/SHORT)
- DEX vs MEXC price
- Market Cap, Volume, Funding Rate
- Open Interest, Max Position Size
- Order book depth (Bid/Ask in USD)

## Stack

- Python, requests
- MEXC API + CoinGecko API
- Telegram Bot API

## Run

```bash
pip install requests
python bot.py
```

## Config (bot.py)

```python
SPREAD_THRESHOLD = 5.0    # alert when spread > 5%
SPREAD_MAX = 25.0         # ignore if spread > 25% (bad token match)
MIN_MARKET_CAP = 5000000  # skip tokens under $5M mcap
CHECK_INTERVAL = 120      # check every 2 minutes
```
