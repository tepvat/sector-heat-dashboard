# alert_bot.py
# ------------
import os
import telegram
from heat_score import calc_scores
from data_fetch import (
    get_prices,
    save_snapshot,
    save_tvl_snapshot,
    BASKETS,
)

# ---------------------------------------------------------------------------
# 0. Päivän snapshotit (hinnat & TVL)
# ---------------------------------------------------------------------------
all_tokens = {tok for tok_list in BASKETS.values() for tok in tok_list}
save_snapshot(get_prices(list(all_tokens)))

# TVL-ketjut (valitse oman korijakosi mukaan; voit poistaa kutsun, jos et
# pisteytä TVL:ää):
CHAIN_PROTOCOLS = ["solana", "near", "avalanche", "sui"]
save_tvl_snapshot(CHAIN_PROTOCOLS)

# ---------------------------------------------------------------------------
# 1. Telegram-yhteys
# ---------------------------------------------------------------------------
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT"]
bot   = telegram.Bot(TOKEN)

# ---------------------------------------------------------------------------
# 2. Hälytyslogiikka
# ---------------------------------------------------------------------------
def main() -> None:
    scores = calc_scores()
    print("Scores:", scores)                     # näkyy Actions-lokeissa

    messages = []
    for basket, score in scores.items():
        if score >= 4:  # raja hälytykselle
            messages.append(
                f"🔥 {basket}-kori kuumenee (score {score}/6) – hyvä aika arvioida kevennystä!"
            )

    if messages:
        bot.send_message(chat_id=CHAT, text="\n".join(messages))

# ---------------------------------------------------------------------------
# 3. Suorita skripti
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
    # debug-viesti, jotta näet yhteyden aina toimivan
    bot.send_message(chat_id=CHAT, text="✅ alert_bot.py suoritti testiajon.")
