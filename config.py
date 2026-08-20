import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", "0")) if os.getenv("API_ID", "").isdigit() else 0
    API_HASH = os.getenv("API_HASH", "")
    
    # Optional Admin IDs (comma-separated list of integer telegram user IDs)
    _raw_admins = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()] if _raw_admins else []
    
    DATABASE_PATH = os.getenv("DATABASE_PATH", "massreport.db")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not cls.API_ID:
            missing.append("API_ID")
        if not cls.API_HASH:
            missing.append("API_HASH")
        return missing
