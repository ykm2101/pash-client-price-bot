import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from handlers.start import start_command
from handlers.referral import referral_command
from scheduler import create_scheduler
from handlers.text import text_handler
from handlers.voice import voice_handler
from handlers.photo import photo_handler
from handlers.confirm import confirm_callback, location_callback, location_text_handler, location_handler, batch_callback

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def on_startup(application: Application) -> None:
    """Start APScheduler after the asyncio event loop is running."""
    scheduler = create_scheduler(application.bot)
    scheduler.start()
    logger.info("Scheduler started")


def main():
    """Start bot"""

    token = os.getenv("TELEGRAM_BOT_TOKEN_CLIENT")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN_CLIENT not set")
        sys.exit(1)

    app = Application.builder().token(token).post_init(on_startup).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("referral", referral_command))

    # Message handlers
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^source_"))
    app.add_handler(CallbackQueryHandler(location_callback, pattern="^location_"))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^unit_"))
    app.add_handler(CallbackQueryHandler(batch_callback, pattern="^batch_"))

    # Check if running on Railway (has PORT env var)
    port = os.getenv("PORT")

    if port:
        # Production: Use webhook
        port = int(port)
        railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "pash-client-price-bot.up.railway.app")
        webhook_url = f"https://{railway_url}/telegram"
        logger.info(f"Bot starting... webhook mode on port {port}, url={webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/telegram",
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        # Local development: Use polling
        logger.info("Bot starting... polling mode (local)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
