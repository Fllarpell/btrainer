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
        except ValueError:
            print(f"Warning: ADMIN_IDS in .env ('{ADMIN_IDS_STR}') contains non-integer values")
            ADMIN_IDS = []
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

settings = Settings()
