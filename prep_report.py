import datetime, requests

SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
}

COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_VWAP = "https://api.binance.com/api/v3/vwap"

TOKENS = ["BTC", "ETH", "SOL", "BNB"]

def get_prices_coingecko(tokens):
    ids = ','.join(SYMBOL_MAP[token] for token in tokens)
    params = {"ids": ids, "vs_currencies": "usd"}
    try:
        response = requests.get(COINGECKO_API, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return {}

def asia_range(symbol: str) -> tuple[float | None, float | None]:
    pair = f"{symbol}USDT"
    url = f"{BINANCE_KLINES}?symbol={pair}&interval=15m&limit=28"
    try:
        data = requests.get(url, timeout=10).json()
        if not isinstance(data, list):
            return None, None
        highs = [float(c[2]) for c in data]
        lows = [float(c[3]) for c in data]
        return max(highs), min(lows)
    except Exception:
        return None, None

def vwap_prev_day(symbol: str) -> float | None:
    pair = f"{symbol}USDT"
    try:
        d = requests.get(f"{BINANCE_VWAP}?symbol={pair}", timeout=10).json()
        return float(d["price"])
    except Exception:
        return None

def get_funding(symbol: str) -> float | None:
    return None

def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC"]

    prices = get_prices_coingecko(TOKENS)

    for token in TOKENS:
        hi, lo = asia_range(token)
        vwap = vwap_prev_day(token)
        fund = get_funding(token)
        
        token_id = SYMBOL_MAP[token]
        price = prices.get(token_id, {}).get('usd')

        if price is None or hi is None or lo is None or vwap is None:
            lines.append(f"`{token}`  ⚠️ pair missing or API error")
            continue

        lines.append(
            f"`{token}`  Asia {lo:.1f}–{hi:.1f} · VWAP {vwap:.1f} · Price ${price:.1f}"
        )

    return "\n".join(lines)

def main():
    from telegram import Bot
    import os

    TOKEN = os.environ["TELEGRAM_TOKEN"]
    CHAT  = os.environ["TELEGRAM_CHAT"]
    bot   = Bot(TOKEN)

    text = build_message()
    bot.send_message(chat_id=CHAT, text=text)

if __name__ == "__main__":
    main()
