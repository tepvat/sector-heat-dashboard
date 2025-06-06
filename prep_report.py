import datetime, requests

# Mappaukset symboleihin
SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
}

SYMBOL_TO_BINANCE = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT"
}

TOKENS = ["BTC", "ETH", "SOL", "BNB"]

COINGECKO_MARKET_URL = "https://api.coingecko.com/api/v3/coins/markets"

# --- VWAP-laskenta ---
def fetch_ohlcv(symbol='BTCUSDT', interval='15m', limit=96):
    """
    Hakee Binance API:sta OHLCV-datan (default: viimeisen 24h, 15min kynttilät = 96 kpl)
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    ohlcv = []
    for row in data:
        ohlcv.append({
            'high': float(row[2]),
            'low': float(row[3]),
            'close': float(row[4]),
            'volume': float(row[5])
        })
    return ohlcv

def calculate_vwap(ohlcv):
    total_pv = 0
    total_vol = 0
    for k in ohlcv:
        price = (k['high'] + k['low'] + k['close']) / 3
        vol = k['volume']
        total_pv += price * vol
        total_vol += vol
    if total_vol == 0:
        return None
    return total_pv / total_vol

def get_vwap(symbol='BTCUSDT'):
    ohlcv = fetch_ohlcv(symbol, interval='15m', limit=96)  # viimeisen 24h (15m kynttilät)
    return calculate_vwap(ohlcv)

# --- Hinta- ja range-tiedot ---
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

# --- Nuoli & prosenttiluku ---
def get_movement_emoji(current, low, high):
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

# --- Rakennetaan viesti ---
def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC\n"]

    data = get_coin_data(TOKENS)

    # Haetaan VWAPit kaikille tokeneille
    vwap_data = {}
    for token in TOKENS:
        try:
            binance_symbol = SYMBOL_TO_BINANCE[token]
            vwap = get_vwap(binance_symbol)
            vwap_data[token] = vwap
        except Exception as e:
            print(f"VWAP error {token}: {e}")
            vwap_data[token] = None

    for token in TOKENS:
        c = data.get(token)
        if not c or c["price"] is None or c["high"] is None or c["low"] is None:
            lines.append(f"`{token}`  ⚠️ pair missing or API error")
            continue

        emoji, percent = get_movement_emoji(c['price'], c['low'], c['high'])
        percent_text = f"{percent}%" if percent is not None else "N/A"
        vwap = vwap_data[token]
        if vwap is None:
            vwap_str = "N/A"
            vwap_emoji = ""
        else:
            vwap_emoji = "🟢" if c['price'] > vwap else "🔴"
            vwap_str = f"{vwap_emoji} {vwap:.1f}"

        lines.append(
            f"*{token}*  {emoji} ({percent_text})\n"
            f"`Asia:`  {c['low']:.1f}–{c['high']:.1f}\n"
            f"`Price:`  ${c['price']:.1f}\n"
            f"`VWAP:`  {vwap_str}\n"
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
    