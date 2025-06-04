import os, telegram, time
from heat_score import calc_scores
from data_fetch import get_prices, save_snapshot, BASKETS
all_tokens = {t for tokens in BASKETS.values() for t in tokens}
save_snapshot(get_prices(list(all_tokens)))


TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT"]
bot = telegram.Bot(TOKEN)

def main():
    scores = calc_scores()
    messages = []
    for k,v in scores.items():
        if v >= 4:
            messages.append(f"🚨 {k}-kori kuumenee (score {v}/5) – hyvä aika keventää!")
    if messages:
        bot.send_message(chat_id=CHAT, text="\n".join(messages))

if __name__ == "__main__":
    main()
    # testiviesti, jotta näet toimiiko yhteys
    bot.send_message(chat_id=CHAT,
                     text="✅ alert_bot.py suoritti testiajon.")


