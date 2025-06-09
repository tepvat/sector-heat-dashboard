import datetime
import requests
import logging
import os

# Set up logging
log_file = 'vwap_debug.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also print to console
    ]
)

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
COINGECKO_OHLC_URL = "https://api.coingecko.com/api/v3/coins/{id}/ohlc"

# --- VWAP-laskenta ---
def fetch_ohlcv(coin_id, days=1):
    url = COINGECKO_OHLC_URL.format(id=coin_id)
    params = {'vs_currency': 'usd', 'days': days}
    logging.debug(f"Fetching OHLCV for {coin_id}")
    logging.debug(f"URL: {url}")
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        logging.debug(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            logging.error(f"Bad status code: {resp.status_code}")
            logging.error(f"Response: {resp.text}")
            return []
            
        data = resp.json()
        logging.debug(f"Received {len(data)} rows of data")
        
        if not data:
            logging.error(f"No data received for {coin_id}")
            return []
            
        logging.debug(f"First row raw data: {data[0]}")
        
        ohlcv = []
        for i, row in enumerate(data):
            try:
                # CoinGecko returns: [timestamp, open, high, low, close]
                ohlcv.append({
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': 1.0  # CoinGecko doesn't provide volume in OHLC endpoint
                })
                if i < 2:
                    logging.debug(f"Parsed row {i}: {ohlcv[-1]}")
            except (IndexError, ValueError) as e:
                logging.error(f"Failed to parse row {i}: {row}")
                logging.error(f"Error: {e}")
                continue
                
        logging.debug(f"Successfully parsed {len(ohlcv)} rows")
        return ohlcv
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed for {coin_id}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in fetch_ohlcv for {coin_id}: {e}")
        logging.error(f"Error type: {type(e)}")
        return []

def calculate_vwap(ohlcv):
    if not ohlcv:
        logging.error("Empty OHLCV data")
        return None
        
    logging.debug(f"Calculating VWAP for {len(ohlcv)} rows")
    total_pv = 0
    total_vol = 0
    
    for i, k in enumerate(ohlcv):
        try:
            price = (k['high'] + k['low'] + k['close']) / 3
            vol = k['volume']
            total_pv += price * vol
            total_vol += vol
            
            if i < 3:
                logging.debug(f"Row {i} calculation:")
                logging.debug(f"  Price: {price:.2f} = ({k['high']:.2f} + {k['low']:.2f} + {k['close']:.2f}) / 3")
                logging.debug(f"  Volume: {vol:.2f}")
                logging.debug(f"  Price * Volume: {price * vol:.2f}")
                
        except KeyError as e:
            logging.error(f"Missing key in data: {e}")
            logging.error(f"Data: {k}")
            continue
            
    if total_vol == 0:
        logging.error("Total volume is 0")
        return None
        
    vwap = total_pv / total_vol
    logging.debug("Final VWAP calculation:")
    logging.debug(f"  Total price * volume: {total_pv:.2f}")
    logging.debug(f"  Total volume: {total_vol:.2f}")
    logging.debug(f"  VWAP: {vwap:.2f}")
    return vwap

def get_vwap(symbol):
    coin_id = SYMBOL_MAP[symbol]
    logging.debug(f"Getting VWAP for {symbol} ({coin_id})")
    ohlcv = fetch_ohlcv(coin_id, days=1)
    
    if not ohlcv:
        logging.error(f"No OHLCV data available for {symbol}")
        return None
        
    vwap = calculate_vwap(ohlcv)
    if vwap is None:
        logging.error(f"Could not calculate VWAP for {symbol}")
    else:
        logging.info(f"VWAP for {symbol}: {vwap:.2f}")
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
        logging.error(f"CoinGecko API error: {e}")
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
    
    logging.debug("Starting VWAP calculations for all tokens")
    for token in TOKENS:
        try:
            logging.debug(f"Processing VWAP for {token}")
            vwap = get_vwap(token)
            vwap_data[token] = vwap
        except Exception as e:
            logging.error(f"VWAP error for {token}: {e}")
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
    
    # Send debug log to Telegram if it exists
    if os.path.exists(log_file):
        with open(log_file, 'rb') as f:
            bot.send_document(chat_id=CHAT, document=f, caption="VWAP Debug Log")

if __name__ == "__main__":
    main()
