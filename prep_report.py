import datetime
import requests

# Mappaukset
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
    # Using the exact same URL format as the working curl command
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    print(f"\n[DEBUG] Fetching OHLCV for {symbol}")
    print(f"[DEBUG] Full URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }
        print("[DEBUG] Making request...")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"[DEBUG] Status code: {resp.status_code}")
        print(f"[DEBUG] Response headers: {dict(resp.headers)}")
        
        if resp.status_code != 200:
            print(f"[ERROR] Bad status code: {resp.status_code}")
            print(f"[ERROR] Response text: {resp.text}")
            return []
            
        print("[DEBUG] Parsing JSON response...")
        data = resp.json()
        print(f"[DEBUG] Received {len(data)} rows of data")
        
        if not data:
            print(f"[ERROR] No data received for {symbol}")
            return []
            
        print(f"[DEBUG] First row raw data: {data[0]}")
        
        ohlcv = []
        for i, row in enumerate(data):
            try:
                # Binance API returns: [timestamp, open, high, low, close, volume, ...]
                parsed_row = {
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': float(row[5])
                }
                ohlcv.append(parsed_row)
                if i < 2:  # Print first two parsed rows
                    print(f"[DEBUG] Parsed row {i}: {parsed_row}")
            except (IndexError, ValueError) as e:
                print(f"[ERROR] Failed to parse row {i}: {row}")
                print(f"[ERROR] Error: {e}")
                continue
                
        print(f"[DEBUG] Successfully parsed {len(ohlcv)} rows")
        return ohlcv
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed for {symbol}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error in fetch_ohlcv for {symbol}: {e}")
        print(f"[ERROR] Error type: {type(e)}")
        return []

def calculate_vwap(ohlcv):
    if not ohlcv:
        print("[ERROR] Empty OHLCV data")
        return None
        
    print(f"[DEBUG] Calculating VWAP for {len(ohlcv)} rows")
    total_pv = 0
    total_vol = 0
    
    for i, k in enumerate(ohlcv):
        try:
            price = (k['high'] + k['low'] + k['close']) / 3
            vol = k['volume']
            total_pv += price * vol
            total_vol += vol
            
            if i < 3:  # Print first 3 calculations
                print(f"[DEBUG] Row {i} calculation:")
                print(f"  Price: {price:.2f} = ({k['high']:.2f} + {k['low']:.2f} + {k['close']:.2f}) / 3")
                print(f"  Volume: {vol:.2f}")
                print(f"  Price * Volume: {price * vol:.2f}")
                
        except KeyError as e:
            print(f"[ERROR] Missing key in data: {e}")
            print(f"[ERROR] Data: {k}")
            continue
            
    if total_vol == 0:
        print("[ERROR] Total volume is 0")
        return None
        
    vwap = total_pv / total_vol
    print(f"[DEBUG] Final VWAP calculation:")
    print(f"  Total price * volume: {total_pv:.2f}")
    print(f"  Total volume: {total_vol:.2f}")
    print(f"  VWAP: {vwap:.2f}")
    return vwap

def get_vwap(symbol='BTCUSDT'):
    print(f"\n[DEBUG] Getting VWAP for {symbol}")
    ohlcv = fetch_ohlcv(symbol, interval='15m', limit=96)
    
    if not ohlcv:
        print(f"[ERROR] No OHLCV data available for {symbol}")
        return None
        
    vwap = calculate_vwap(ohlcv)
    if vwap is None:
        print(f"[ERROR] Could not calculate VWAP for {symbol}")
    else:
        print(f"[SUCCESS] VWAP for {symbol}: {vwap:.2f}")
    return vwap

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
        return "⚪️", None
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
    vwap_data = {}
    
    print("\n[DEBUG] Starting VWAP calculations for all tokens")
    for token in TOKENS:
        try:
            binance_symbol = SYMBOL_TO_BINANCE[token]
            print(f"\n[DEBUG] Processing VWAP for {token} ({binance_symbol})")
            vwap = get_vwap(binance_symbol)
            vwap_data[token] = vwap
        except Exception as e:
            print(f"[ERROR] VWAP error for {token}: {e}")
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
