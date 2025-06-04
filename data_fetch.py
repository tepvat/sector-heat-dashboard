import requests, csv, datetime, os, yaml

CG_ENDPOINT = "https://api.coingecko.com/api/v3/simple/price"
BASKETS = yaml.safe_load(open("baskets.yml"))

def get_prices(symbols: list[str]) -> dict[str, float]:
    ids = ",".join(symbols).lower()
    url = f"{CG_ENDPOINT}?ids={ids}&vs_currencies=usd"
    r = requests.get(url, timeout=10).json()
    return {k.upper(): r[k.lower()]["usd"] for k in r}

def save_snapshot(prices: dict[str, float], path="prices.csv"):
    header = ["date"] + list(prices.keys())
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(header)
        row = [datetime.date.today().isoformat()] + [prices[k] for k in prices]
        w.writerow(row)
