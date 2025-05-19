import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, List


env_path = Path(__file__).resolve().parent.parent.parent / ".env"

if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded .env file from: {env_path}")
else:
    print(f".env file not found at: {env_path}")

class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_DEFAULT_TELEGRAM_TOKEN")
    if TELEGRAM_BOT_TOKEN == "YOUR_DEFAULT_TELEGRAM_TOKEN":
        print("Warning: TELEGRAM_BOT_TOKEN is not set in .env")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@host:port/db")
    if DATABASE_URL == "postgresql://user:pass@host:port/db":
        print("Warning: DATABASE_URL is not set in .env")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "YOUR_DEFAULT_OPENAI_KEY")
    if OPENAI_API_KEY == "YOUR_DEFAULT_OPENAI_KEY":
        print("Warning: OPENAI_API_KEY is not set in .env")

    YOOKASSA_SHOP_ID: Optional[str] = os.getenv("YOOKASSA_SHOP_ID")
    YOOKASSA_SECRET_KEY: Optional[str] = os.getenv("YOOKASSA_SECRET_KEY")

    ADMIN_IDS_STR: str = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS: List[int] = []
    if ADMIN_IDS_STR:
        try:
            ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',')]
            print(f"Loaded ADMIN_IDS: {ADMIN_IDS} from string: '{ADMIN_IDS_STR}'")
        except ValueError:
            print(f"Warning: ADMIN_IDS in .env ('{ADMIN_IDS_STR}') contains non-integer values")
            ADMIN_IDS = []
    else:
        print("Warning: ADMIN_IDS is not set in .env")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    deep_seek_api_key: str = os.getenv("DEEP_SEEK_API_KEY", "YOUR_DEEP_SEEK_API_KEY_HERE")

    # Telegram Payment Provider Token (from BotFather, for YooKassa)
    TELEGRAM_PAYMENT_PROVIDER_TOKEN: Optional[str] = os.getenv("TELEGRAM_PAYMENT_PROVIDER_TOKEN")
    if not TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        print("Warning: TELEGRAM_PAYMENT_PROVIDER_TOKEN is not set in .env. Payments will not work.")

    TRIAL_PERIOD_DAYS: int = 7

settings = Settings()

def is_admin(user_id: int, db_user) -> bool:
    from app.core.config import settings
    from app.db.models import UserRole
    return (user_id in settings.ADMIN_IDS) or (db_user and getattr(db_user, 'role', None) == UserRole.ADMIN)
