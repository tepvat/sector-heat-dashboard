# prep_report.py -------------------------------------------------------------
"""
London-session ‘Prep’ – lähetetään Telegramiin klo 06:25 UTC.
Sisältää Asia-rangen (00-07 UTC), eilisen VWAP:n ja funding-raten.
"""
import os, datetime, requests, statistics, telegram
from data_fetch import get_funding          # funktio on jo projektissasi

TOKENS = ["BTC", "ETH", "SOL", "BNB"]       # lisää alttisi tarvittaessa

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_VWAP   = "https://api.binance.com/api/v3/avgPrice"

def asia_range(symbol: str) -> tuple[float, float]:
    """High & Low väliltä 00:00–07:00 UTC (15 min kynttilöillä)."""
    now = datetime.datetime.utcnow()
    end   = int(now.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
    start = end - 7*60*60*1000        # 7 h taaksepäin
    url   = f"{BINANCE_KLINES}?symbol={symbol}USDT&interval=15m&startTime={start}&endTime={end}"
    ohlc  = requests.get(url, timeout=10).json()
    highs = [float(c[2]) for c in ohlc]
    lows  = [float(c[3]) for c in ohlc]
    return max(highs), min(lows)

def vwap_prev_day(symbol: str) -> float:
    """Binance API antaa ‘avgPrice’ (≈ ed. 5 min). Hyvä proxy VWAP-tasolle."""
    d = requests.get(f"{BINANCE_VWAP}?symbol={symbol}USDT", timeout=10).json()
    return float(d["price"])

def build_message() -> str:
    today = datetime.date.today().isoformat()
    lines = [f"*London prep*  {today} 06:30 UTC"]
    for t in TOKENS:
        hi, lo = asia_range(t)
        vwap   = vwap_prev_day(t)
        fund   = get_funding(t) * 100
        lines.append(
            f"`{t}`  Asia {lo:.1f}–{hi:.1f} · VWAP {vwap:.1f} · Funding {fund:.2f}%"
        )
    return "\n".join(lines)

def main() -> None:
    TOKEN = os.environ["TELEGRAM_TOKEN"]
    CHAT  = os.environ["TELEGRAM_CHAT"]
    telegram.Bot(TOKEN).send_message(
        chat_id=CHAT,
        text=build_message(),
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    main()
