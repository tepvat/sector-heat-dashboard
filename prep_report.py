import datetime
import requests
import logging
import os
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates

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
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed for {coin_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in fetch_ohlcv for {coin_id}: {e}")
        logging.error(f"Error type: {type(e)}")
        return None

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
def create_price_chart(symbol, df, vwap, high, low, current_price):
    # Create figure and axis
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot candlesticks
    mpf.plot(df, type='candle', style='charles',
             title=f'{symbol} Price Chart',
             ylabel='Price (USD)',
             ax=ax1,
             volume=False)
    
    # Add VWAP line
    ax1.axhline(y=vwap, color='blue', linestyle='--', label='VWAP')
    
    # Add high/low levels
    ax1.axhline(y=high, color='green', linestyle=':', label='High')
    ax1.axhline(y=low, color='red', linestyle=':', label='Low')
    
    # Add current price
    ax1.axhline(y=current_price, color='purple', linestyle='-', label='Current Price')
    
    # Add legend
    ax1.legend()
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    
    # Plot volume
    ax2.bar(df.index, df['volume'], color='gray', alpha=0.5)
    ax2.set_ylabel('Volume')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the figure
    filename = f'{symbol.lower()}_chart.png'
    plt.savefig(filename)
    plt.close()
    
    return filename

def analyze_token(symbol, df, vwap, high, low, current_price):
    """Analyze token's trading conditions and provide insights"""
    analysis = {
        'trend': '',
        'strength': '',
        'setup': '',
        'suggestion': ''
    }
    
    # Calculate basic metrics
    price_change = ((current_price - df['open'].iloc[0]) / df['open'].iloc[0]) * 100
    volatility = (df['high'].max() - df['low'].min()) / df['low'].min() * 100
    
    # Determine trend
    if current_price > vwap:
        analysis['trend'] = 'BULLISH'
    else:
        analysis['trend'] = 'BEARISH'
    
    # Determine strength
    if abs(price_change) > 5:
        analysis['strength'] = 'STRONG'
    else:
        analysis['strength'] = 'MODERATE'
    
    # Determine setup
    if current_price > high:
        analysis['setup'] = 'BREAKOUT'
    elif current_price < low:
        analysis['setup'] = 'BREAKDOWN'
    else:
        analysis['setup'] = 'RANGE'
    
    # Generate trading suggestion
    if analysis['setup'] == 'BREAKOUT':
        analysis['suggestion'] = f"Consider long positions with stop loss below {low:.2f}"
    elif analysis['setup'] == 'BREAKDOWN':
        analysis['suggestion'] = f"Consider short positions with stop loss above {high:.2f}"
    else:
        analysis['suggestion'] = f"Range trading between {low:.2f} and {high:.2f}"
    
    return analysis

def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC\n"]

    data = get_coin_data(TOKENS)
    vwap_data = {}
    chart_files = []
    
    logging.debug("Starting VWAP calculations for all tokens")
    for token in TOKENS:
        try:
            logging.debug(f"Processing {token}")
            coin_id = SYMBOL_MAP[token]
            
            # Get OHLCV data
            df = fetch_ohlcv(coin_id, days=1)
            if df is None or df.empty:
                continue
                
            # Calculate VWAP
            vwap = calculate_vwap(df)
            vwap_data[token] = vwap
            
            # Get current price and high/low
            current_price = data[token]['price']
            high = data[token]['high']
            low = data[token]['low']
            
            # Create chart
            chart_file = create_price_chart(token, df, vwap, high, low, current_price)
            chart_files.append(chart_file)
            
            # Analyze token
            analysis = analyze_token(token, df, vwap, high, low, current_price)
            
            # Build message
            emoji, percent = get_movement_emoji(current_price, low, high)
            percent_text = f"{percent}%" if percent is not None else "N/A"
            
            lines.append(
                f"*{token}*  {emoji} ({percent_text})\n"
                f"`Asia:`  {low:.1f}–{high:.1f}\n"
                f"`Price:`  ${current_price:.1f}\n"
                f"`VWAP:`  {vwap:.1f}\n"
                f"`Trend:`  {analysis['trend']} ({analysis['strength']})\n"
                f"`Setup:`  {analysis['setup']}\n"
                f"`Suggestion:`  {analysis['suggestion']}\n"
            )
            
        except Exception as e:
            logging.error(f"Error processing {token}: {e}")
            continue
            
    return "\n".join(lines), chart_files

def main():
    from telegram import Bot
    import os

    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHAT = os.environ.get("TELEGRAM_CHAT")
    
    logging.info(f"Starting bot with TOKEN: {TOKEN[:5]}... and CHAT: {CHAT}")
    
    if not TOKEN or not CHAT:
        logging.error("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT environment variables")
        return
        
    try:
        bot = Bot(TOKEN)
        logging.info("Bot initialized successfully")
        
        # Send test message first
        logging.info("Sending test message...")
        bot.send_message(chat_id=CHAT, text="🤖 Bot starting up...")
        logging.info("Test message sent successfully")
        
        text, chart_files = build_message()
        logging.info(f"Message built successfully, length: {len(text)}")
        logging.info(f"Generated {len(chart_files)} chart files")
        
        # Send text message
        logging.info("Attempting to send text message...")
        bot.send_message(chat_id=CHAT, text=text, parse_mode='Markdown')
        logging.info("Text message sent successfully")
        
        # Send charts
        for chart_file in chart_files:
            logging.info(f"Sending chart file: {chart_file}")
            with open(chart_file, 'rb') as f:
                bot.send_photo(chat_id=CHAT, photo=f)
            logging.info(f"Chart {chart_file} sent successfully")
            os.remove(chart_file)  # Clean up
            logging.info(f"Chart file {chart_file} removed")
        
        # Send debug log if it exists
        if os.path.exists(log_file):
            logging.info("Sending debug log...")
            with open(log_file, 'rb') as f:
                bot.send_document(chat_id=CHAT, document=f, caption="VWAP Debug Log")
            logging.info("Debug log sent successfully")
            
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
        logging.error(f"Error type: {type(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
