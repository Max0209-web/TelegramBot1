import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()]
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "bot.db")
BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBot")

PLANS = {
    "7":         {"days": 7,   "stars": 50,  "usdt": 0.5,  "label": "7 дней — 50⭐"},
    "30":        {"days": 30,  "stars": 150, "usdt": 1.5,  "label": "30 дней — 150⭐"},
    "90":        {"days": 90,  "stars": 300, "usdt": 3.0,  "label": "90 дней — 300⭐"},
    "180":       {"days": 180, "stars": 450, "usdt": 4.5,  "label": "180 дней — 450⭐"},
    "360":       {"days": 360, "stars": 600, "usdt": 6.0,  "label": "360 дней — 600⭐"},
    "unlimited": {"days": 0,   "stars": 999, "usdt": 9.99, "label": "♾ Безлимит — 999⭐"},
}

INITIAL_PROMO_CODES = [
    "DEJA2026A", "DEJA2026B", "DEJA2026C", "DEJA2026D", "DEJA2026E",
    "FREEWK001", "FREEWK002", "FREEWK003", "FREEWK004", "FREEWK005",
]
