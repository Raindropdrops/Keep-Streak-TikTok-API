# TikTok Streak Bot Configuration v2.0
# Created by: Duc Anh
#
# All sensitive values are loaded from environment variables.
# Copy .env.example to .env and fill in your values.

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# TikTok URLs
# =============================================================================
TIKTOK_BASE_URL = "https://www.tiktok.com"
TIKTOK_MESSAGES_URL = "https://www.tiktok.com/messages"
TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"

# =============================================================================
# API Settings
# =============================================================================
APP_NAME = os.getenv("APP_NAME", "TikTok Streak API")
APP_VERSION = "2.0.0"
APP_ENV = os.getenv("APP_ENV", "development")
API_KEY = os.getenv("API_KEY", "")

# =============================================================================
# Message Settings
# =============================================================================
STREAK_MESSAGE = os.getenv("STREAK_MESSAGE", "🔥 Streak! 🔥")

# =============================================================================
# Schedule Settings
# =============================================================================
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:00")
SCHEDULE_INTERVAL_MINUTES = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "1380"))  # 23 hours

# =============================================================================
# Reliability Settings (inspired by TiktokStreakSaver)
# =============================================================================
MAX_RETRIES_PER_CONTACT = int(os.getenv("MAX_RETRIES_PER_CONTACT", "4"))
SEND_FLOW_MAX_SECONDS = int(os.getenv("SEND_FLOW_MAX_SECONDS", "1200"))
SKIP_UNREACHABLE = os.getenv("SKIP_UNREACHABLE", "true").lower() == "true"
DAILY_COOLDOWN = os.getenv("DAILY_COOLDOWN", "true").lower() == "true"
NETWORK_CHECK = os.getenv("NETWORK_CHECK", "true").lower() == "true"

# =============================================================================
# Telegram Notification Settings
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
TELEGRAM_LOG_ENABLED = os.getenv("TELEGRAM_LOG_ENABLED", "true").lower() == "true"

# Minimum log level to send to Telegram (INFO, WARNING, ERROR)
_log_level = os.getenv("TELEGRAM_LOG_LEVEL", "WARNING").upper()
TELEGRAM_LOG_LEVEL = getattr(logging, _log_level, logging.WARNING)

# =============================================================================
# File Paths
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")
CONTACTS_FILE = os.path.join(BASE_DIR, "contacts.json")
RUN_HISTORY_FILE = os.path.join(BASE_DIR, "run_history.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Create logs directory if it doesn't exist
os.makedirs(LOGS_DIR, exist_ok=True)

# =============================================================================
# Browser Settings
# =============================================================================
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"

# Modern Chrome User-Agent (updated 2026)
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Wait times (in seconds)
PAGE_LOAD_WAIT = int(os.getenv("PAGE_LOAD_WAIT", "5"))
ELEMENT_WAIT = int(os.getenv("ELEMENT_WAIT", "3"))
MESSAGE_SEND_DELAY = int(os.getenv("MESSAGE_SEND_DELAY", "2"))

# =============================================================================
# Server Settings
# =============================================================================
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# =============================================================================
# Logging Settings
# =============================================================================
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
