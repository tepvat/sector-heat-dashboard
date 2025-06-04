# heat_score.py
# -------------
"""
Laskee AI-, RWA- ja L1-korien 'heat score'-pisteet.

Pisteytys v1:
+2 pistettä, jos korin tokenien keskimääräinen hinta on noussut
   vähintään +40 % viimeisten 7 päivän aikana (verrattuna 8 päivää sitten
   kirjattuihin hintoihin prices.csv-tiedostossa).

Future: lisää funding- ja TVL-pisteet.
"""

import yaml
import pandas as pd
from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------------
# 1. Lataa korit
# ---------------------------------------------------------------------------
BASKETS: Dict[str, dict]

with open("baskets.yml", "r", encoding="utf-8") as fh:
    BASKETS = yaml.safe_load(fh)

# ---------------------------------------------------------------------------
# 2. Pääfunktio
# ---------------------------------------------------------------------------
def calc_scores(csv_path: str = "prices.csv") -> Dict[str, int]:
    """
    Lukee prices.csv, laskee 7 d prosentti­muutoksen ja palauttaa
    dictin { 'AI': 0/2, 'RWA': 0/2, 'L1': 0/2 }.
    """
    # --- varmista, että historiaa on tarpeeksi ---
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return {basket: 0 for basket in BASKETS}

    df = pd.read_csv(csv_file, parse_dates=["date"]).set_index("date")

    if len(df) < 8:            # alle 8 riviä = ei 7 pv vertailua
        return {basket: 0 for basket in BASKETS}

    today_prices    = df.iloc[-1]
    week_ago_prices = df.iloc[-8]

    pct_change = (today_prices - week_ago_prices) / week_ago_prices

    scores: Dict[str, int] = {}
    for basket, tokens in BASKETS.items():
        # Nouda vain ne token-sarakkeet, jotka löytyvät csv:stä
        present = [t for t in tokens if t in pct_change]
        if not present:
            scores[basket] = 0
            continue

        basket_change = pct_change[present].mean()

        score = 2 if basket_change >= 0.40 else 0
        # Tulevaisuudessa lisää funding-/TVL-pisteet tähän

        scores[basket] = score

    return scores

# ---------------------------------------------------------------------------
# 3. Suorita skripti paikallisesti
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    s = calc_scores()
    print("Current sector scores:", s)
