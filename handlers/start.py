import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.supabase import SupabaseService

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command, optionally with referral param: /start ref_123456789"""

    user = update.effective_user
    supabase = SupabaseService()

    # Extract referral code from deep link param (e.g. ?start=ref_123456789)
    referred_by: str | None = None
    if context.args:
        param = context.args[0]
        if param.startswith("ref_"):
            referrer_id = param[4:]  # strip "ref_"
            if referrer_id and referrer_id != str(user.id):  # can't refer yourself
                referred_by = referrer_id
                logger.info(f"User {user.id} came via referral from {referrer_id}")

    # Upsert user — referred_by saved only on first join
    try:
        await supabase.upsert_user(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name,
            referred_by=referred_by,
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
