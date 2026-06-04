import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.supabase import SupabaseService

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""

    user = update.effective_user
    chat = update.effective_chat

    supabase = SupabaseService()

    # Upsert user
    try:
        await supabase.upsert_user(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name
        )
    except Exception as e:
        logger.error(f"Error upserting user {user.id}: {e}")

    message = (
        "Hello there! 👋 I'm Mani-Penny, your AI assistant.\n\n"
        "Send me a price from any shop — via text, voice, or photo.\n"
        "I'll tell you how much you can save at PÄSH 🥑\n\n"
        "Привет! 👋 Я Мани-Пенни, ваш ИИ ассистент.\n\n"
        "Отправьте цену из магазина — текстом, голосом или фото.\n"
        "Скажу, насколько дешевле у PÄSH 🥑"
    )

    await update.message.reply_text(message)
