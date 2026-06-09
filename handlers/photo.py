import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from models import Session
from services.gemini import parse_photo
from handlers.confirm import show_confirmation
from config import BOT_USERNAME, ADMIN_TELEGRAM_ID

logger = logging.getLogger(__name__)

GROUP_TRIGGER_WORDS = ['качество', 'свежесть', 'свежее', 'испорченный', 'плохой']
GROUP_NEGATIVE_WORDS = ['испорченный', 'плохой']


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo — single price tag or receipt with multiple items."""

    # Group mode: respond only if mentioned in caption or negative trigger
    if update.message.chat.type in ['group', 'supergroup']:
        caption = update.message.caption or ''
        bot_mentioned = f'@{BOT_USERNAME}' in caption
        triggered = any(w in caption.lower() for w in GROUP_TRIGGER_WORDS)

        if not bot_mentioned and not triggered:
            return

        if any(w in caption.lower() for w in GROUP_NEGATIVE_WORDS):
            await update.message.reply_text(
                "Сожалеем что так получилось 🙏\n"
                "Разберёмся и вернёмся с ответом.\n"
                f"{ADMIN_TELEGRAM_ID} уже в курсе.\n"
                "Напиши подробнее — поможет решить быстрее."
            )
            return

    try:
        photo_file = update.message.photo[-1]

        # Download photo
        file = await context.bot.get_file(photo_file.file_id)
        photo_path = f"/tmp/photo_{update.effective_user.id}.jpg"
        await file.download_to_drive(photo_path)

        with open(photo_path, 'rb') as f:
            photo_bytes = f.read()

        if os.path.exists(photo_path):
            os.remove(photo_path)

        # Parse photo
        parsed = await parse_photo(photo_bytes)

        if not parsed.items:
            await update.message.reply_text(
                "Couldn't read the price tag 🤔\n(Не разобрала ценник — попробуй получше или напиши текстом)"
            )
            return

        # Multiple items → batch mode (receipt)
        if len(parsed.items) > 1:
            await handle_receipt(update, context, parsed)
            return

        # Single item → standard flow
        session = Session()
        session.items = parsed.items
        session.language = parsed.language

        item = parsed.items[0]
        session.partial = {
            "product": item.product,
            "price": item.price,
            "unit": item.unit,
            "source": parsed.source or item.source,
            "source_detail": parsed.source_detail or item.source_detail,
            "district": None
        }

        context.user_data["session"] = session
        await show_confirmation(update, context, session)

    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await update.message.reply_text(
            "Photo error 😞 Try again please\n(Ошибка с фото — повтори, пожалуйста)"
        )


async def handle_receipt(update, context, parsed) -> None:
    """Handle receipt photo with multiple items."""
    from services.batch_processor import format_batch_confirmation

    # Store batch
    context.user_data["batch"] = {
        "items": parsed.items,
        "source": parsed.source,
        "source_detail": parsed.source_detail,
    }
    context.user_data.pop("session", None)

    confirmation_text = format_batch_confirmation(parsed.items, parsed.source, parsed.source_detail)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Верно", callback_data="batch_confirm"),
            InlineKeyboardButton("✏️ Исправить", callback_data="batch_edit"),
            InlineKeyboardButton("❌ Отмена", callback_data="batch_cancel")
        ]
    ])
    await update.message.reply_text(confirmation_text, reply_markup=keyboard)
