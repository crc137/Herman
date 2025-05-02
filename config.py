import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API credentials
API_ID = os.getenv("API_ID")  # Replace with your actual API ID
API_HASH = os.getenv("API_HASH")  # Replace with your actual API hash

# Group and user IDs
TARGET_GROUP = int(os.getenv("TARGET_GROUP"))  # Group to add users to
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Admin user ID to receive reports
# ВАЖНО: ID администратора должен взаимодействовать с ботом перед запуском
# Бот должен иметь возможность найти администратора через поиск или общий чат
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # Channel to monitor for CAS bans

# Source groups to monitor (initially just one group)
SOURCE_GROUPS = [int(id.strip()) for id in os.getenv("SOURCE_GROUPS").split(",")]

# API endpoint for CAS check
CAS_API_URL = os.getenv("CAS_API_URL")

# Database configuration
# SQLite configuration (fallback)
DB_FILE = os.getenv("DB_FILE", "users_database.db")

# PostgreSQL configuration
USE_POSTGRES = os.getenv("USE_POSTGRES", "True").lower() in ("true", "1", "t")
POSTGRES_DSN = os.getenv("POSTGRES_DSN") 