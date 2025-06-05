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


SYMBOL_MAP = {
    "TAO": None,        # ei spot-paria → käytä CoinGeckoa
    "FET": "FETUSDT",   # on spotissa
    # …
}

def asia_range(symbol: str) -> tuple[float | None, float | None]:
    pair = SYMBOL_MAP.get(symbol, f"{symbol}USDT")
    if pair is None:                      # ei Binance-spottiparia
        return None, None

    # ⬇️⟵  NÄMÄ PUUTTUIVAT
    now   = datetime.datetime.utcnow()
    end   = int(now.replace(minute=0, second=0, microsecond=0).timestamp()*1000)
    start = end - 7*60*60*1000            # 7 h taaksepäin
    # -----------------------------------

    url = (f"{BINANCE_KLINES}?symbol={pair}"
           f"&interval=15m&startTime={start}&endTime={end}")
    data = requests.get(url, timeout=10).json()
    if not isinstance(data, list):        # API-virhe => dict
        return None, None

    highs = [float(c[2]) for c in data]
    lows  = [float(c[3]) for c in data]
    return max(highs), min(lows)

def vwap_prev_day(symbol: str):
    pair = SYMBOL_MAP.get(symbol, f"{symbol}USDT")
    if pair is None:
        # CoinGecko fallback
        cg = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": symbol.lower(), "vs_currencies": "usd"}
        ).json()
        return cg[symbol.lower()]["usd"]
    try:
        d = requests.get(f"{BINANCE_VWAP}?symbol={pair}", timeout=10).json()
        return float(d["price"])
    except Exception:
        return None

def build_message() -> str:
    today  = datetime.date.today().isoformat()
    lines  = [f"*London prep*  {today} 06:30 UTC"]

    for t in TOKENS:
        hi, lo = asia_range(t)
        vwap   = vwap_prev_day(t)
        fund   = get_funding(t)

        # --- DEBUG / virhetulostus ------------------------------
        if None in (hi, lo):
            lines.append(f"`{t}`  ⚠️ pair missing or API error")
            continue
        if vwap is None:
            lines.append(f"`{t}`  ⚠️ VWAP missing")
            continue
        if fund is None:
            lines.append(f"`{t}`  ⚠️ funding missing")
            continue
        # --------------------------------------------------------

        lines.append(
            f"`{t}`  Asia {lo:.1f}–{hi:.1f} · VWAP {vwap:.1f} · Funding {fund*100:.2f}%"
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
