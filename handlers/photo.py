import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from models import Session
from services.gemini import parse_photo
from handlers.confirm import show_confirmation

logger = logging.getLogger(__name__)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo - extract price tag info"""

    try:
        photo_file = update.message.photo[-1]  # Get highest resolution

        # Download photo
        file = await context.bot.get_file(photo_file.file_id)
        photo_path = f"/tmp/photo_{update.effective_user.id}.jpg"
        await file.download_to_drive(photo_path)

        # Extract text from photo with Gemini
        with open(photo_path, 'rb') as f:
            photo_bytes = f.read()

        # Clean up
        if os.path.exists(photo_path):
            os.remove(photo_path)

        # Parse photo
        parsed = await parse_photo(photo_bytes)

        # Store in session
        session = Session()
        session.items = parsed.items
        session.language = parsed.language

        if parsed.items:
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

            # Show confirmation
            await show_confirmation(update, context, session)
        else:
            await update.message.reply_text("Не разобрала ценник 🤔 Попробуй получше или напиши текстом")

    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await update.message.reply_text("Ошибка с фото 😞 Повтори, пожалуйста")
