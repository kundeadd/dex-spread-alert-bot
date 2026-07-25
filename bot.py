import requests
import time

TELEGRAM_TOKEN = "8828726811:AAGB_bDvE2aIB8kSrXtV-Qn-6GSIuFr2Hcg"
CHAT_ID = "443138329"
SPREAD_THRESHOLD = 5.0
SPREAD_MAX = 25.0
CONVERGE_THRESHOLD = 1.0
CHECK_INTERVAL = 120
MIN_MARKET_CAP = 5000000

def send_telegram(msg, reply_to=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    r = requests.post(url, json=payload)
    data = r.json()
    if data.get("ok"):
        return data["result"]["message_id"]
    return None

def get_coingecko_ids():
    print("Loading CoinGecko list...")
    r = requests.get("https://api.coingecko.com/api/v3/coins/list", timeout=15)
    result = {}
    for c in r.json():
        sym = c["symbol"].upper()
        if sym not in result:
            result[sym] = c["id"]
    print(f"Loaded {len(result)} coins")
    return result

def get_mexc_tickers():
    r = requests.get("https://contract.mexc.com/api/v1/contract/ticker", timeout=10)
    tickers = {}
    for item in r.json()["data"]:
        symbol = item["symbol"]
        tickers[symbol] = {
            "price": float(item["lastPrice"]),
            "volume24h": float(item.get("amount24", 0) or 0),
            "funding_rate": float(item.get("fundingRate", 0) or 0),
            "hold_vol": float(item.get("holdVol", 0) or 0),
        }
    return tickers

def get_mexc_detail(symbol, price, hold_vol):
    bid_usd, ask_usd, max_vol_usd, oi_usd = 0, 0, 0, 0
    try:
        r1 = requests.get(f"https://contract.mexc.com/api/v1/contract/depth/{symbol}?limit=20", timeout=5)
        depth = r1.json().get("data", {})
        bids = depth.get("bids", [])
        asks = depth.get("asks", [])

        r2 = requests.get(f"https://contract.mexc.com/api/v1/contract/detail?symbol={symbol}", timeout=5)
        d = r2.json().get("data", {})
        csize = float(d.get("contractSize", 1) or 1)
        max_vol = float(d.get("maxVol", 0) or 0)

        bid_usd = sum(float(b[1]) * csize * price for b in bids)
        ask_usd = sum(float(a[1]) * csize * price for a in asks)
        max_vol_usd = max_vol * csize * price
        oi_usd = hold_vol * csize * price
    except Exception as e:
        print(f"Detail error: {e}")
    return bid_usd, ask_usd, max_vol_usd, oi_usd

def get_coingecko_prices(ids):
    chunks = [ids[i:i+250] for i in range(0, len(ids), 250)]
    result = {}
    for chunk in chunks:
        ids_str = ",".join(chunk)
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true",
            timeout=15
        )
        result.update(r.json())
        time.sleep(1)
    return result

def fmt_usd(val):
    if not val:
        return "N/A"
    if val >= 1_000_000_000:
        return f"${val/1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val/1_000:.0f}K"
    return f"${val:.0f}"

def main():
    print("Bot started.")
    send_telegram(f"🤖 <b>DEX/MEXC Spread Alert Bot started</b>\nThreshold: {SPREAD_THRESHOLD}% | Max: {SPREAD_MAX}%")

    cg_ids = get_coingecko_ids()
    active_alerts = {}

    while True:
        try:
            print("Checking...")
            mexc_tickers = get_mexc_tickers()

            token_to_cgid = {}
            for symbol in mexc_tickers:
                token = symbol.replace("_USDT", "").replace("USDT", "")
                if token in cg_ids:
                    token_to_cgid[token] = cg_ids[token]

            cgid_list = list(set(token_to_cgid.values()))
            print(f"Fetching {len(cgid_list)} tokens...")
            cg_prices = get_coingecko_prices(cgid_list)

            for symbol, ticker in mexc_tickers.items():
                mexc_price = ticker["price"]
                if mexc_price <= 0:
                    continue

                token = symbol.replace("_USDT", "").replace("USDT", "")
                cgid = token_to_cgid.get(token)
                if not cgid:
                    continue

                cg_data = cg_prices.get(cgid, {})
                cg_price = cg_data.get("usd")
                if not cg_price:
                    continue

                market_cap = cg_data.get("usd_market_cap", 0) or 0
                if market_cap < MIN_MARKET_CAP:
                    continue

                spread = ((cg_price - mexc_price) / mexc_price) * 100
                abs_spread = abs(spread)

                if abs_spread > SPREAD_MAX:
                    continue

                if abs_spread >= SPREAD_THRESHOLD and symbol not in active_alerts:
                    direction = "🟢 LONG" if spread > 0 else "🔴 SHORT"
                    funding = ticker["funding_rate"] * 100
                    vol_dex = cg_data.get("usd_24h_vol", 0) or 0

                    bid_usd, ask_usd, max_vol_usd, oi_usd = get_mexc_detail(symbol, mexc_price, ticker["hold_vol"])

                    msg = (
                        f"<b>🚨 DEX/MEXC Spread Alert</b>\n\n"
                        f"{direction} <b>#{token}</b>  Spread: <b>{spread:.2f}%</b>\n\n"
                        f"💎 Price DEX:  <b>${cg_price:.6f}</b>\n"
                        f"📊 Price MEXC: <b>${mexc_price:.6f}</b>\n\n"
                        f"💰 Funding Rate: <b>{funding:.4f}%</b>\n"
                        f"📈 Market Cap: <b>{fmt_usd(market_cap)}</b>\n"
                        f"📊 Vol DEX/MEXC: <b>{fmt_usd(vol_dex)}</b> / <b>{fmt_usd(ticker['volume24h'])}</b>\n"
                        f"📦 Open Interest: <b>{fmt_usd(oi_usd)}</b>\n"
                        f"🔒 Max Position: <b>{fmt_usd(max_vol_usd)}</b>\n"
                        f"📉 Depth Bid/Ask: <b>{fmt_usd(bid_usd)}</b> / <b>{fmt_usd(ask_usd)}</b>\n\n"
                        f"<a href='https://www.coingecko.com/en/coins/{cgid}'>CoinGecko</a> | "
                        f"<a href='https://www.mexc.com/futures/{token}_USDT'>MEXC</a>"
                    )
                    msg_id = send_telegram(msg)
                    if msg_id:
                        active_alerts[symbol] = {"message_id": msg_id, "spread": spread}
                        print(f"Alert: {token} | {spread:.2f}%")

                elif symbol in active_alerts and abs_spread <= CONVERGE_THRESHOLD:
                    orig = active_alerts[symbol]
                    msg = (
                        f"✅ <b>#{token} Spread Converged</b>\n\n"
                        f"Initial spread: <b>{orig['spread']:.2f}%</b>\n"
                        f"Current spread: <b>{spread:.2f}%</b>\n\n"
                        f"💎 Price DEX:  <b>${cg_price:.6f}</b>\n"
                        f"📊 Price MEXC: <b>${mexc_price:.6f}</b>"
                    )
                    send_telegram(msg, reply_to=orig["message_id"])
                    del active_alerts[symbol]
                    print(f"Converged: {token} | {spread:.2f}%")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
