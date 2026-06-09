import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN_CLIENT = os.getenv("TELEGRAM_BOT_TOKEN_CLIENT")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

BOT_USERNAME = os.getenv("BOT_USERNAME", "pash_client_price_bot")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@pash_channel")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "@pash_club")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "@yoridosu")

if not all([TELEGRAM_BOT_TOKEN_CLIENT, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY]):
    raise ValueError("Missing required environment variables in .env")
