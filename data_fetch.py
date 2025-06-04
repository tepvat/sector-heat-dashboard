# data_fetch.py
# -------------
"""
Kerää:
1. Spot-hinnat CoinGeckosta (prices.csv)
2. Perpetual-futuurien funding-ratet Binancesta + Bybitistä
3. (Optio) TVL-snapshot protokollille DeFiLlamasta (tvl.csv)
"""

import csv
import datetime
import os
import statistics
from pathlib import Path
from typing import Dict, List

import requests
import yaml

# ---------------------------------------------------------------------------
# 0. Korit ja token-listat
# ---------------------------------------------------------------------------
with open("baskets.yml", encoding="utf-8") as fh:
    BASKETS: Dict[str, Dict[str, float]] = yaml.safe_load(fh)

# ---------------------------------------------------------------------------
# 1. Hinnat CoinGeckosta
# ---------------------------------------------------------------------------
CG_ENDPOINT = "https://api.coingecko.com/api/v3/simple/price"


def get_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Palauttaa dictin {'SUI': 1.35, 'SOL': 173.8, …} USD-hinnoilla.
    """
    ids = ",".join(s.lower() for s in symbols)
    url = f"{CG_ENDPOINT}?ids={ids}&vs_currencies=usd"
    r = requests.get(url, timeout=20).json()
    return {k.upper(): r[k.lower()]["usd"] for k in r}


def save_snapshot(prices: Dict[str, float], path: str = "prices.csv") -> None:
    """
    Lisää rivin prices.csv-tiedostoon: päivä + hinnat.
    """
    header = ["date"] + list(prices.keys())
    new_file = not Path(path).exists()

    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(header)
        row = [datetime.date.today().isoformat()] + [prices[k] for k in prices]
        w.writerow(row)


# ---------------------------------------------------------------------------
# 2. Funding-rate pörsseiltä (Binance + Bybit)
# ---------------------------------------------------------------------------
_BINANCE_FR = "https://fapi.binance.com/fapi/v1/fundingRate"          # ?symbol=BTCUSDT
_BYBIT_FR = "https://api.bybit.com/v2/public/funding/prev-funding-rate"
_TIMEOUT = 10


def _binance_funding(symbol: str) -> float:
    params = {"symbol": f"{symbol.upper()}USDT", "limit": 1}
    try:
        r = requests.get(_BINANCE_FR, params=params, timeout=_TIMEOUT).json()
        if isinstance(r, list) and r:
            return float(r[0]["fundingRate"])
    except Exception:
        pass
    return 0.0


def _bybit_funding(symbol: str) -> float:
    params = {"symbol": f"{symbol.upper()}USDT"}
    try:
        r = requests.get(_BYBIT_FR, params=params, timeout=_TIMEOUT).json()
        if r.get("ret_code") == 0:
            return float(r["result"]["funding_rate"])
    except Exception:
        pass
    return 0.0


def get_funding(symbol: str) -> float:
    """
    Keskiarvo Binance + Bybit -funding-rateista.
    Jos molemmat epäonnistuvat → 0.
    """
    rates = [_binance_funding(symbol), _bybit_funding(symbol)]
    rates = [r for r in rates if r != 0.0]
    return statistics.mean(rates) if rates else 0.0


# ---------------------------------------------------------------------------
# 3. (Optio) TVL DeFiLlamasta – käytä jos haluat pisteyttää TVL-kasvun
# ---------------------------------------------------------------------------
_LLAMA_TVL = "https://api.llama.fi/tvl/"  # esim. https://api.llama.fi/tvl/solana


def get_tvl(protocol: str) -> float:
    try:
        r = requests.get(f"{_LLAMA_TVL}{protocol.lower()}", timeout=10).json()
        return float(r)
    except Exception:
        return 0.0


def save_tvl_snapshot(protocols: List[str], path: str = "tvl.csv") -> None:
    """
    Lisää rivin tvl.csv: päivä + TVL-usd per protokolla.
    """
    header = ["date"] + protocols
    new_file = not Path(path).exists()

    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(header)
        row = [datetime.date.today().isoformat()] + [get_tvl(p) for p in protocols]
        w.writerow(row)
