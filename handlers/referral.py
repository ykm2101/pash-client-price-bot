import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.supabase import SupabaseService
from services.referral import generate_referral_link, get_referral_stats

logger = logging.getLogger(__name__)


REFERRAL_TEXT = {
    "ru": (
        "🔗 *Твоя личная ссылка:*\n"
        "`{link}`\n\n"
        "👥 Пришло по твоей ссылке: *{count}* чел.\n"
        "🛒 Сделали заказ: *{converted}*\n\n"
        "Поделись с друзьями —\n"
        "пусть тоже сэкономят на фруктах 🌱"
    ),
    "kz": (
        "🔗 *Жеке сілтемең:*\n"
        "`{link}`\n\n"
        "👥 Сілтемең арқылы келді: *{count}* адам\n"
        "🛒 Тапсырыс берді: *{converted}*\n\n"
        "Достарыңмен бөліс —\n"
        "олар да жемістерде үнемдесін 🌱"
    ),
    "en": (
        "🔗 *Your personal link:*\n"
        "`{link}`\n\n"
        "👥 Joined via your link: *{count}* people\n"
        "🛒 Placed an order: *{converted}*\n\n"
        "Share with friends —\n"
        "let them save on fruits too 🌱"
    ),
}


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /referral command — show personal referral link and stats."""

    user = update.effective_user
    supabase = SupabaseService()

    # Get user language
    user_data = await supabase.get_user(user.id)
    lang = (user_data or {}).get("language", "ru")
    if lang not in REFERRAL_TEXT:
        lang = "ru"

    link = generate_referral_link(user.id)
    stats = await get_referral_stats(user.id, supabase)

    text = REFERRAL_TEXT[lang].format(
        link=link,
        count=stats["count"],
        converted=stats["converted"],
    )

    await update.message.reply_text(text, parse_mode="Markdown")
