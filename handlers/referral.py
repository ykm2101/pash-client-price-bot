import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.supabase import SupabaseService
from services.referral import generate_referral_link, get_referral_stats

logger = logging.getLogger(__name__)


# Message 1: shareable invite (for forwarding to friends)
INVITE_TEXT = {
    "ru": (
        "Теперь тоже можешь экономить на фруктах 🌱\n\n"
        "Проверь цену из любого магазина —\n"
        "PÄSH привозит свежие фрукты и овощи дешевле.\n\n"
        "👉 {link}"
    ),
    "kz": (
        "Енді сен де жемістерде үнемдей аласың 🌱\n\n"
        "Кез келген дүкеннен бағаны тексер —\n"
        "PÄSH арзанырақ жеткізеді.\n\n"
        "👉 {link}"
    ),
    "en": (
        "Save on fruits & veggies too 🌱\n\n"
        "Check any store price —\n"
        "PÄSH delivers fresh produce for less.\n\n"
        "👉 {link}"
    ),
}

# Message 2: personal stats (for the user only)
STATS_TEXT = {
    "ru": (
        "📊 *Твоя статистика:*\n"
        "👥 Пришло по ссылке: *{count}* чел.\n"
        "🛒 Сделали заказ: *{converted}*"
    ),
    "kz": (
        "📊 *Статистикаң:*\n"
        "👥 Сілтемең арқылы келді: *{count}* адам\n"
        "🛒 Тапсырыс берді: *{converted}*"
    ),
    "en": (
        "📊 *Your stats:*\n"
        "👥 Joined via your link: *{count}* people\n"
        "🛒 Placed an order: *{converted}*"
    ),
}


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /referral — send two messages: shareable invite + personal stats."""

    user = update.effective_user
    supabase = SupabaseService()

    user_data = await supabase.get_user(user.id)
    lang = (user_data or {}).get("language", "ru")
    if lang not in INVITE_TEXT:
        lang = "ru"

    link = generate_referral_link(user.id)
    stats = await get_referral_stats(user.id, supabase)

    # Message 1: shareable (plain text, easy to forward)
    invite = INVITE_TEXT[lang].format(link=link)
    await update.message.reply_text(invite)

    # Message 2: personal stats
    stats_msg = STATS_TEXT[lang].format(
        count=stats["count"],
        converted=stats["converted"],
    )
    await update.message.reply_text(stats_msg, parse_mode="Markdown")
