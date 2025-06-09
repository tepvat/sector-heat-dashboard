import datetime
import requests
import logging
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Set the backend to non-interactive 'Agg'
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
        logging.StreamHandler()
    ]
)

# Mappaukset
SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
}
TOKENS = ["BTC", "ETH", "SOL", "BNB"]
COINGECKO_MARKET_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_OHLC_URL = "https://api.coingecko.com/api/v3/coins/{id}/ohlc"

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
            return None
            
        data = resp.json()
        logging.debug(f"Received {len(data)} rows of data")
        
        if not data:
            logging.error(f"No data received for {coin_id}")
            return None
            
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

def calculate_vwap(df):
    if df is None or df.empty:
        logging.error("Empty OHLCV data")
        return None
        
    logging.debug(f"Calculating VWAP for {len(df)} rows")
    total_pv = 0
    total_vol = 0
    
    for i, row in df.iterrows():
        try:
            price = (row['high'] + row['low'] + row['close']) / 3
            vol = 1.0  # Using constant volume since CoinGecko doesn't provide it
            total_pv += price * vol
            total_vol += vol
            
            if i < 3:
                logging.debug(f"Row {i} calculation:")
                logging.debug(f"  Price: {price:.2f} = ({row['high']:.2f} + {row['low']:.2f} + {row['close']:.2f}) / 3")
                logging.debug(f"  Volume: {vol:.2f}")
                logging.debug(f"  Price * Volume: {price * vol:.2f}")
                
        except Exception as e:
            logging.error(f"Error calculating VWAP for row {i}: {e}")
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

def create_price_chart(symbol, df, vwap, high, low, current_price):
    try:
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
        
        # Plot volume (using constant volume)
        ax2.bar(df.index, [1.0] * len(df), color='gray', alpha=0.5)
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
    except Exception as e:
        logging.error(f"Error creating chart for {symbol}: {e}")
        return None

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
            if chart_file:
                chart_files.append(chart_file)
            
            # Build message
            emoji, percent = get_movement_emoji(current_price, low, high)
            percent_text = f"{percent}%" if percent is not None else "N/A"
            
            lines.append(
                f"*{token}*  {emoji} ({percent_text})\n"
                f"`Asia:`  {low:.1f}–{high:.1f}\n"
                f"`Price:`  ${current_price:.1f}\n"
                f"`VWAP:`  {vwap:.1f}\n"
            )
            
        except Exception as e:
            logging.error(f"Error processing {token}: {e}")
            continue
            
    return "\n".join(lines), chart_files

def main():
    from telegram import Bot
    from telegram.error import TelegramError
    import os
    import sys
    import asyncio

    # Print all environment variables (except token)
    print("Environment variables:")
    for key, value in os.environ.items():
        if key != "TELEGRAM_TOKEN":
            print(f"{key}: {value}")

    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHAT = os.environ.get("TELEGRAM_CHAT")
    
    print(f"\nToken exists: {bool(TOKEN)}")
    print(f"Chat ID exists: {bool(CHAT)}")
    
    if not TOKEN or not CHAT:
        print("ERROR: Missing TELEGRAM_TOKEN or TELEGRAM_CHAT")
        sys.exit(1)
        
    async def test_coin_data():
        try:
            print("\nInitializing bot...")
            bot = Bot(token=TOKEN)
            
            # Test with just BTC
            test_token = "BTC"
            print(f"\nTesting with {test_token}...")
            
            # Get OHLCV data
            df = fetch_ohlcv(SYMBOL_MAP[test_token], days=1)
            if df is None or df.empty:
                print("Failed to fetch OHLCV data")
                return
                
            print(f"Received {len(df)} rows of data")
            print(f"First row: {df.iloc[0]}")
            
            # Calculate VWAP
            vwap = calculate_vwap(df)
            if vwap is None:
                print("Failed to calculate VWAP")
                return
                
            print(f"VWAP: {vwap:.2f}")
            
            # Get current price data
            data = get_coin_data([test_token])
            if not data:
                print("Failed to get current price data")
                return
                
            current_price = data[test_token]['price']
            high = data[test_token]['high']
            low = data[test_token]['low']
            
            # Send results to Telegram
            message = (
                f"*Test Results for {test_token}*\n\n"
                f"Current Price: ${current_price:.2f}\n"
                f"24h High: ${high:.2f}\n"
                f"24h Low: ${low:.2f}\n"
                f"VWAP: ${vwap:.2f}\n"
            )
            
            await bot.send_message(
                chat_id=CHAT,
                text=message,
                parse_mode='Markdown'
            )
            print("Results sent to Telegram")
            
        except TelegramError as e:
            print(f"\nTELEGRAM ERROR: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            sys.exit(1)
        except Exception as e:
            print(f"\nUNEXPECTED ERROR: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            sys.exit(1)

    # Run the async function
    asyncio.run(test_coin_data())

if __name__ == "__main__":
    main()
