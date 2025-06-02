import requests, time

CG_ENDPOINT = "https://api.coingecko.com/api/v3/simple/price"

def get_prices(symbols: list[str]) -> dict[str, float]:
    ids = ",".join(symbols).lower()
    url = f"{CG_ENDPOINT}?ids={ids}&vs_currencies=usd"
    r = requests.get(url, timeout=10).json()
    return {k.upper(): v["usd"] for k, v in r.items()}

# TODO: funding & TVL – placeholder funkat
def get_funding(symbol): return 0.001  # dummy
def get_tvl(protocol):   return 1_000_000
