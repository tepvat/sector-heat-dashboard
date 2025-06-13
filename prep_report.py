import datetime
import requests
import logging
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Set the backend to non-interactive 'Agg'
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates
import ta

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
    """Calculate Volume Weighted Average Price"""
    try:
        # Calculate typical price for each period
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Since CoinGecko doesn't provide volume, use constant volume of 1.0
        df['volume'] = 1.0
        
        # Calculate VWAP
        vwap = (df['typical_price'] * df['volume']).sum() / df['volume'].sum()
        
        logging.debug(f"VWAP calculation:")
        logging.debug(f"  Typical price range: {df['typical_price'].min():.2f} - {df['typical_price'].max():.2f}")
        logging.debug(f"  Final VWAP: {vwap:.2f}")
        
        return vwap
    except Exception as e:
        logging.error(f"Error calculating VWAP: {e}")
        return None

def calculate_max_rr(df, entry_price, stop_loss):
    """Calculate the maximum achieved RR after entry price in the given DataFrame."""
    max_price = df['high'].max()
    risk = entry_price - stop_loss
    reward = max_price - entry_price
    rr_max = reward / risk if risk != 0 else 0
    return rr_max, max_price

def create_price_chart(symbol, df, vwap, high, low, current_price, london_rr=None, london_rr_max=None, london_max_price=None, day_rr=None, day_rr_max=None, day_max_price=None):
    """Create price chart with VWAP and levels for Asia session (00-07 UTC) and show RR levels."""
    try:
        # Ensure index is in UTC
        df.index = df.index.tz_localize('UTC')
        
        # Filter data for Asia session (00-07 UTC)
        df_asia = df.between_time('00:00', '07:00')
        if df_asia.empty:
            logging.error(f"No Asia session data available for {symbol}")
            return None
        # Filter data for London session (07:00-15:00 UTC)
        df_london = df.between_time('07:00', '15:00')
        
        # Calculate Asia session high/low
        asia_high = df_asia['high'].max()
        asia_low = df_asia['low'].min()
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot price (Asia session only)
        ax.plot(df_asia.index, df_asia['close'], label='Asia Price', color='blue', linewidth=2)
        # Plot London session price
        if not df_london.empty:
            ax.plot(df_london.index, df_london['close'], label='London Price', color='orange', linewidth=2)
        
        # Plot VWAP (Asia session VWAP)
        ax.axhline(y=vwap, color='magenta', linestyle='--', linewidth=2, label='VWAP')
        
        # Plot Asia session high/low
        ax.axhline(y=asia_high, color='limegreen', linestyle='--', linewidth=2, label='Asia High')
        ax.axhline(y=asia_low, color='orange', linestyle='--', linewidth=2, label='Asia Low')
        
        # Plot full-day high/low (dotted black)
        ax.axhline(y=high, color='black', linestyle=':', linewidth=1.5, label='Full Day High')
        ax.axhline(y=low, color='black', linestyle=':', linewidth=1.5, label='Full Day Low')
        
        # Plot current price
        ax.axhline(y=current_price, color='purple', linestyle='-', linewidth=2, label='Current')
        
        # Plot max RR levels for London and full day
        if london_max_price:
            ax.axhline(y=london_max_price, color='deepskyblue', linestyle='-.', linewidth=2, label='London Max Price')
        if day_max_price:
            ax.axhline(y=day_max_price, color='red', linestyle='-.', linewidth=2, label='Day Max Price')
        
        # Add legend
        ax.legend(loc='upper left', fontsize=10)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M UTC'))
        plt.xticks(rotation=45)
        
        # Set x-axis limits to show only Asia and London session
        start_time = df_asia.index[0].replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = df_london.index[-1].replace(hour=15, minute=0, second=0, microsecond=0) if not df_london.empty else df_asia.index[-1].replace(hour=7, minute=0, second=0, microsecond=0)
        ax.set_xlim(start_time, end_time)
        
        # Add title
        plt.title(f'{symbol} Asia & London Sessions (00-15 UTC)')
        
        # Save the figure
        filename = f'{symbol.lower()}_chart.png'
        plt.savefig(filename, bbox_inches='tight')
        plt.close()
        
        logging.debug(f"Chart created: {filename}")
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

def get_bias_emoji(bias):
    return "🟢" if bias == "bullish" else "🔴"

def get_setup_quality(score):
    try:
        num = int(score.split('/')[0])
        if num >= 8:
            return "🟢"
        elif num >= 5:
            return "🟡"
        else:
            return "🔴"
    except:
        return "⚪️"

def calculate_technical_indicators(df):
    """Calculate technical indicators for strategy analysis"""
    try:
        # EMA
        df['EMA20'] = ta.trend.ema_indicator(df['close'], window=20)
        df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)
        
        # RSI
        df['RSI'] = ta.momentum.rsi(df['close'], window=14)
        
        # MACD
        macd = ta.trend.MACD(df['close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_hist'] = macd.macd_diff()
        
        return df
    except Exception as e:
        logging.error(f"Error calculating technical indicators: {e}")
        return None

def analyze_trading_strategy(df, current_price, high, low):
    """Analyze trading strategy based on price action and indicators"""
    try:
        # Calculate range
        daily_range = high - low
        range_percent = (daily_range / low) * 100
        
        # Calculate price position in range
        price_position = (current_price - low) / daily_range * 100
        
        # Determine if range trading or breakout strategy
        if range_percent < 3:  # Tight range
            strategy = "Range Trading"
            entry_type = "Range Reversal"
        else:
            strategy = "Breakout Trading"
            entry_type = "Breakout Confirmation"
        
        # Analyze indicators
        last_row = df.iloc[-1]
        indicator_signals = []
        
        # EMA analysis
        if current_price > last_row['EMA20'] and last_row['EMA20'] > last_row['EMA50']:
            indicator_signals.append("EMA: Bullish")
        elif current_price < last_row['EMA20'] and last_row['EMA20'] < last_row['EMA50']:
            indicator_signals.append("EMA: Bearish")
            
        # RSI analysis
        if last_row['RSI'] > 70:
            indicator_signals.append("RSI: Overbought")
        elif last_row['RSI'] < 30:
            indicator_signals.append("RSI: Oversold")
            
        # MACD analysis
        if last_row['MACD'] > last_row['MACD_signal']:
            indicator_signals.append("MACD: Bullish")
        else:
            indicator_signals.append("MACD: Bearish")
            
        # Calculate potential stop loss and take profit levels
        if strategy == "Range Trading":
            stop_loss = low * 0.995  # 0.5% below range low
            take_profit = high * 1.01  # 1% above range high
        else:  # Breakout Trading
            stop_loss = current_price * 0.98  # 2% below current price
            take_profit = current_price * 1.04  # 4% above current price
            
        risk = current_price - stop_loss
        reward = take_profit - current_price
        risk_reward_ratio = reward / risk if risk != 0 else 0
        
        return {
            'strategy': strategy,
            'entry_type': entry_type,
            'range_percent': range_percent,
            'price_position': price_position,
            'indicator_signals': indicator_signals,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward_ratio': risk_reward_ratio
        }
    except Exception as e:
        logging.error(f"Error analyzing trading strategy: {e}")
        return None

def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC\n"]
    error_lines = []

    data = get_coin_data(TOKENS)
    vwap_data = {}
    chart_files = []
    
    logging.debug("Starting analysis for all tokens")
    for token in TOKENS:
        try:
            print(f"[DEBUG] Processing {token}")
            logging.debug(f"Processing {token}")
            coin_id = SYMBOL_MAP[token]
            
            # Get OHLCV data
            df = fetch_ohlcv(coin_id, days=1)
            if df is None or df.empty:
                msg = f"{token}: No OHLCV data"
                print(f"[DEBUG] {msg}")
                logging.error(msg)
                error_lines.append(msg)
                continue
            print(f"[DEBUG] OHLCV data shape for {token}: {df.shape}")
            
            # Calculate VWAP
            vwap = calculate_vwap(df)
            if vwap is None:
                msg = f"{token}: VWAP calculation failed"
                print(f"[DEBUG] {msg}")
                logging.error(msg)
                error_lines.append(msg)
                continue
            print(f"[DEBUG] VWAP for {token}: {vwap}")
            vwap_data[token] = vwap
            
            # Calculate technical indicators
            df = calculate_technical_indicators(df)
            if df is None:
                msg = f"{token}: Technical indicators calculation failed"
                print(f"[DEBUG] {msg}")
                logging.error(msg)
                error_lines.append(msg)
                continue
            print(f"[DEBUG] Technical indicators calculated for {token}")
            
            # Get current price and high/low
            current_price = data[token]['price']
            high = data[token]['high']
            low = data[token]['low']
            print(f"[DEBUG] Price for {token}: {current_price}, High: {high}, Low: {low}")
            
            # Analyze trading strategy
            strategy_analysis = analyze_trading_strategy(df, current_price, high, low)
            if strategy_analysis is None:
                msg = f"{token}: Trading strategy analysis failed"
                print(f"[DEBUG] {msg}")
                logging.error(msg)
                error_lines.append(msg)
                continue
            print(f"[DEBUG] Trading strategy analysis for {token}: {strategy_analysis}")
            
            # --- RR Analysis ---
            # Entry price: Asia session close (07:00 UTC)
            df.index = df.index.tz_localize('UTC')
            asia_close_time = df[df.index.indexer_between_time('07:00', '07:00')].index
            if not asia_close_time.empty:
                entry_price = df.loc[asia_close_time[0], 'close']
            else:
                entry_price = current_price
            stop_loss = strategy_analysis['stop_loss']
            # London session RR
            df_london = df.between_time('07:00', '15:00')
            london_rr_max, london_max_price = calculate_max_rr(df_london, entry_price, stop_loss) if not df_london.empty else (None, None)
            # Full day RR
            day_rr_max, day_max_price = calculate_max_rr(df, entry_price, stop_loss)
            # Perinteinen RR (nykyisillä take profit/stop loss -ehdoilla)
            rr = strategy_analysis['risk_reward_ratio']
            print(f"[DEBUG] RR for {token}: {rr}, London max: {london_rr_max}, Day max: {day_rr_max}")
            
            # Create chart with RR markers
            chart_file = create_price_chart(
                token, df, vwap, high, low, current_price,
                london_rr=rr, london_rr_max=london_rr_max, london_max_price=london_max_price,
                day_rr=rr, day_rr_max=day_rr_max, day_max_price=day_max_price
            )
            if chart_file:
                print(f"[DEBUG] Chart created for {token}: {chart_file}")
                chart_files.append(chart_file)
            else:
                msg = f"{token}: Chart creation failed"
                print(f"[DEBUG] {msg}")
                error_lines.append(msg)
            
            # Build message
            emoji, percent = get_movement_emoji(current_price, low, high)
            percent_text = f"{percent}%" if percent is not None else "N/A"
            
            # Add bias and setup score
            bias = "bullish" if current_price > vwap else "bearish"
            bias_emoji = get_bias_emoji(bias)
            
            # Calculate setup score based on strategy analysis
            setup_score = "6/10"  # Default score
            if strategy_analysis['risk_reward_ratio'] >= 2:
                if len(strategy_analysis['indicator_signals']) >= 2:
                    setup_score = "9/10"
                else:
                    setup_score = "8/10"
            elif strategy_analysis['risk_reward_ratio'] >= 1.5:
                setup_score = "7/10"
                
            setup_emoji = get_setup_quality(setup_score)
            
            # RR-analyysit viestiin
            lines.append(
                f"*{token}*  {emoji} ({percent_text})\n"
                f"`Asia:`  {low:.1f}–{high:.1f} ({strategy_analysis['range_percent']:.1f}%)\n"
                f"`Price:`  ${current_price:.1f}\n"
                f"`VWAP:`  {vwap:.1f}\n"
                f"`Strategy:`  {strategy_analysis['strategy']}\n"
                f"`Entry:`  {strategy_analysis['entry_type']}\n"
                f"`Signals:`  {', '.join(strategy_analysis['indicator_signals'])}\n"
                f"`Stop:`  ${strategy_analysis['stop_loss']:.1f}\n"
                f"`Target:`  ${strategy_analysis['take_profit']:.1f}\n"
                f"`R/R:`  {rr:.2f} (London max: {london_rr_max:.2f} | Day max: {day_rr_max:.2f})\n"
                f"`Setup:`  {setup_emoji} {setup_score}\n"
            )
            print(f"[DEBUG] Finished processing {token}")
        except Exception as e:
            msg = f"{token}: Exception: {e}"
            print(f"[DEBUG] {msg}")
            logging.error(msg)
            error_lines.append(msg)
            continue
    # Jos ei yhtään tokenia onnistunut, lisätään virheet viestiin
    if len(lines) == 1 and error_lines:
        lines.append("\n*Errors:*")
        lines.extend(error_lines)
    return "\n".join(lines), chart_files

def main():
    from telegram import Bot
    from telegram.error import TelegramError
    import os
    import sys
    import asyncio

    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHAT = os.environ.get("TELEGRAM_CHAT")
    
    print("Checking environment variables...")
    if not TOKEN:
        print("ERROR: TELEGRAM_TOKEN is not set")
        sys.exit(1)
    if not CHAT:
        print("ERROR: TELEGRAM_CHAT is not set")
        sys.exit(1)
    print("Environment variables are set")
    
    async def send_report():
        try:
            print("Initializing Telegram bot...")
            bot = Bot(token=TOKEN)
            
            print("Building message...")
            message, chart_files = build_message()
            if not message:
                print("ERROR: Failed to build message")
                sys.exit(1)
            print(f"Message built, length: {len(message)}")
            print(f"Number of charts: {len(chart_files)}")
            
            print("Sending text message...")
            # Send text message
            await bot.send_message(
                chat_id=CHAT,
                text=message,
                parse_mode='Markdown'
            )
            print("Text message sent successfully")
            
            # Send charts
            for chart_file in chart_files:
                if os.path.exists(chart_file):
                    print(f"Sending chart: {chart_file}")
                    with open(chart_file, 'rb') as f:
                        await bot.send_photo(
                            chat_id=CHAT,
                            photo=f
                        )
                    print(f"Chart {chart_file} sent successfully")
                    os.remove(chart_file)  # Clean up after sending
                else:
                    print(f"Warning: Chart file {chart_file} not found")
            
        except TelegramError as e:
            print(f"Telegram error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)

    print("Starting async execution...")
    asyncio.run(send_report())
    print("Async execution completed")

if __name__ == "__main__":
    main()
