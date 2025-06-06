import datetime, requests

SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
}

TOKENS = ["BTC", "ETH", "SOL", "BNB"]

COINGECKO_MARKET_URL = "https://api.coingecko.com/api/v3/coins/markets"

def get_coin_data(tokens):
    ids = ','.join(SYMBOL_MAP[token] for token in tokens)
    params = {
        "vs_currency": "usd",
        "ids": ids,
        "order": "market_cap_desc",
        "per_page": len(tokens),
        "page": 1,
        "sparkline": False
    }
    try:
        response = requests.get(COINGECKO_MARKET_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Palautetaan dictionary: {symbol: {price, high, low}}
        result = {}
        for coin in data:
            symbol = [k for k, v in SYMBOL_MAP.items() if v == coin["id"]][0]
            result[symbol] = {
                "price": coin.get("current_price"),
                "high": coin.get("high_24h"),
                "low": coin.get("low_24h")
            }
        return result
    except Exception as e:
        print(f"CoinGecko API error: {e}")
        return {}

def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC"]

    data = get_coin_data(TOKENS)

    for token in TOKENS:
        c = data.get(token)
        if not c or c["price"] is None or c["high"] is None or c["low"] is None:
            lines.append(f"`{token}`  ⚠️ pair missing or API error")
            continue

        lines.append(
            f"`{token}`  Asia {c['low']:.1f}–{c['high']:.1f} · VWAP N/A · Price ${c['price']:.1f}"
        )

    return "\n".join(lines)

def main():
    from telegram import Bot
    import os

    TOKEN = os.environ["TELEGRAM_TOKEN"]
    CHAT  = os.environ["TELEGRAM_CHAT"]
    bot   = Bot(TOKEN)

    text = build_message()
    bot.send_message(chat_id=CHAT, text=text, parse_mode='Markdown')

if __name__ == "__main__":
    main()
