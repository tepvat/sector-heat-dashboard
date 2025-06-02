import yaml, pandas as pd
from data_fetch import get_prices, get_funding, get_tvl

RULES = {
    "price_7d": 0.40,          # +40 % / 7 d → +2 pistettä
    "funding": 0.0012,         # >0.12 %/8h → +2
}

def load_baskets(path="baskets.yml"):
    with open(path) as f:
        return yaml.safe_load(f)

def calc_scores():
    baskets = load_baskets()
    tickers = {t for tok in baskets.values() for t in tok}
    prices_now = get_prices(list(tickers))
    # (tallenna aiemmat hinnat CSV:hen – tässä esimerkki: kaikki +0 p)
    scores = {}
    for name, holdings in baskets.items():
        price_pump    = False     # TODO: vertaile 7 d sitten tallennettuun arvoon
        high_funding  = any(get_funding(t) > RULES["funding"] for t in holdings)
        score = 0
        if price_pump:   score += 2
        if high_funding: score += 2
        # lisää TVL ym.
        scores[name] = score
    return scores
