# heat_score.py
# -------------
"""
Laskee sektorikohtaiset 'heat score' -pisteet kolmesta tekijästä:

1) 7 vrk hinnan keskimääräinen muutos  (≥ +40 %  → +2 p)
2) Perpetual-futuurien funding-rate    (≥ 0,12 %  → +2 p)
3) 30 vrk TVL-kasvu (DeFiLlama)        (≥ +60 %  → +2 p)

Palauttaa dictin {'AI':0–6, 'RWA':0–6, 'L1':0–6}.
"""

from pathlib import Path
import datetime
import statistics
from typing import Dict, List

import yaml
import pandas as pd

from data_fetch import BASKETS, get_funding  # BASKETS = YAML-korit, get_funding = Binance+Bybit

# -------------------- raja-arvot --------------------
PRICE_THRESHOLD = 0.40    # +40 %
FUNDING_THRESHOLD = 0.0012  # 0,12 % (8 h)
TVL_THRESHOLD = 0.60      # +60 % (30 vrk)

# TVL-mapping: kori → DeFiLlama-protokolla
BASKET_TO_PROTOCOL = {
    "AI": None,           # ei TVL-pisteitä tälle
    "RWA": None,          # -||-
    "L1": "solana",       # esimerkki; muokkaa tarpeen mukaan
}

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "baskets.yml", "r", encoding="utf-8") as fh:
    BASKETS = yaml.safe_load(fh)

# ---------------------------------------------------------------------------
# 1. Apu: prosenttimuutos & turvallinen luku csv:stä
# ---------------------------------------------------------------------------
def _pct_change(new: float, old: float) -> float:
    return (new - old) / old if old else 0.0


def _read_csv(path: str) -> pd.DataFrame | None:
    if Path(path).exists():
        return pd.read_csv(path, parse_dates=["date"]).set_index("date")
    return None


# ---------------------------------------------------------------------------
# 2. Pääfunktio
# ---------------------------------------------------------------------------
def calc_scores() -> Dict[str, int]:
    # ---------------- hinnat ----------------
    price_df = _read_csv("prices.csv")
    price_scores: Dict[str, int] = {b: 0 for b in BASKETS}

    if price_df is not None and len(price_df) >= 8:
        today, week_ago = price_df.iloc[-1], price_df.iloc[-8]
        pct_series = (today - week_ago) / week_ago
        for basket, tokens in BASKETS.items():
            tokens_present = [t for t in tokens if t in pct_series.index]
            if tokens_present:
                avg_change = pct_series[tokens_present].mean()
                if avg_change >= PRICE_THRESHOLD:
                    price_scores[basket] = 2

    # ---------------- funding ----------------
    funding_scores: Dict[str, int] = {}
    for basket, tokens in BASKETS.items():
        high = any(get_funding(tok) >= FUNDING_THRESHOLD for tok in tokens)
        funding_scores[basket] = 2 if high else 0

    # ---------------- TVL ----------------
    tvl_scores: Dict[str, int] = {b: 0 for b in BASKETS}
    tvl_df = _read_csv("tvl.csv")

    if tvl_df is not None and len(tvl_df) >= 31:
        today, month_ago = tvl_df.iloc[-1], tvl_df.iloc[-31]
        tvl_pct = (today - month_ago) / month_ago
        for basket, proto in BASKET_TO_PROTOCOL.items():
            if proto and proto in tvl_pct.index and tvl_pct[proto] >= TVL_THRESHOLD:
                tvl_scores[basket] = 2

    # ---------------- yhdistä ----------------
    final_scores = {
        b: price_scores[b] + funding_scores[b] + tvl_scores[b]
        for b in BASKETS
    }
    return final_scores


# ---------------------------------------------------------------------------
# 3. Debug-ajo: tulosta pistetaulukko terminaaliin
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    s = calc_scores()
    print(f"[{datetime.date.today()}] Current sector scores:", s)
