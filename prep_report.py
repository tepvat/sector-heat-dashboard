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

def get_movement_emoji(current, low, high):
    # Suhde low–high välillä
    try:
        ratio = (current - low) / (high - low)
    except ZeroDivisionError:
        return "⚪️", None  # Ei tietoa
    percent = int(ratio * 100)
    if ratio >= 0.8:
        emoji = "🟢⬆️"
    elif ratio <= 0.2:
        emoji = "🔴⬇️"
    else:
        emoji = "🟡"
    return emoji, percent

def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC\n"]

    data = get_coin_data(TOKENS)

    for token in TOKENS:
        c = data.get(token)
        if not c or c["price"] is None or c["high"] is None or c["low"] is None:
            lines.append(f"`{token}`  ⚠️ pair missing or API error")
            continue

        emoji, percent = get_movement_emoji(c['price'], c['low'], c['high'])
        percent_text = f"{percent}%" if percent is not None else "N/A"

        lines.append(
            f"*{token}*  {emoji} ({percent_text})\n"
            f"`Asia:`  {c['low']:.1f}–{c['high']:.1f}\n"
            f"`Price:`  ${c['price']:.1f}\n"
            f"`VWAP:`  N/A\n"
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
