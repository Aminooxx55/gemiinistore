import os
from dotenv import load_dotenv

load_dotenv()

# Core
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "myshopbot")

# Crypto addresses
USDT_TRC20_ADDRESS: str = os.getenv("USDT_TRC20_ADDRESS", "")
USDT_BEP20_ADDRESS: str = os.getenv("USDT_BEP20_ADDRESS", "")
BINANCE_PAY_ID: str = os.getenv("BINANCE_PAY_ID", "")

# Referral
REFERRAL_REWARD: float = float(os.getenv("REFERRAL_REWARD", "0.50"))

# Membership thresholds (total spent USD)
SILVER_THRESHOLD: float = float(os.getenv("SILVER_THRESHOLD", "50"))
GOLD_THRESHOLD: float = float(os.getenv("GOLD_THRESHOLD", "200"))
DIAMOND_THRESHOLD: float = float(os.getenv("DIAMOND_THRESHOLD", "500"))

# DB path
DB_PATH: str = "shop.db"

# Channel membership check
REQUIRED_CHANNEL: str = os.getenv("REQUIRED_CHANNEL", "@grokkkmet")
STRICT_CHANNEL_CHECK: bool = os.getenv("STRICT_CHANNEL_CHECK", "True").lower() == "true"

# Recurring Message Sender
RECURRING_CHAT: str = os.getenv("RECURRING_CHAT", "")
RECURRING_MESSAGE: str = os.getenv("RECURRING_MESSAGE", "")
RECURRING_INTERVAL: int = int(os.getenv("RECURRING_INTERVAL", "300"))

# Loyalty Cashback (default 5%)
CASHBACK_PERCENT: float = float(os.getenv("CASHBACK_PERCENT", "0.05"))

# Spin Cooldown (default 24h = 86400 seconds)
SPIN_COOLDOWN: int = int(os.getenv("SPIN_COOLDOWN", "86400"))




def get_membership(total_spent: float) -> str:
    if total_spent >= DIAMOND_THRESHOLD:
        return "💎 Diamond"
    elif total_spent >= GOLD_THRESHOLD:
        return "🥇 Gold"
    elif total_spent >= SILVER_THRESHOLD:
        return "🥈 Silver"
    return "🥉 Bronze"
