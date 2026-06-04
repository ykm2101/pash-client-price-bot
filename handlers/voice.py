import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from models import Session
from services.gemini import transcribe_and_parse
from handlers.confirm import show_confirmation

logger = logging.getLogger(__name__)

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice message - transcribe and parse"""

    try:
        voice_file = update.message.voice

        # Download voice file
        file = await context.bot.get_file(voice_file.file_id)
        voice_path = f"/tmp/voice_{update.effective_user.id}.ogg"
        await file.download_to_drive(voice_path)

        # Read voice file and transcribe with Gemini
        with open(voice_path, 'rb') as f:
            voice_bytes = f.read()

        # Clean up
        if os.path.exists(voice_path):
            os.remove(voice_path)

        # Transcribe and parse in one call
        parsed = await transcribe_and_parse(voice_bytes)

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
            await update.message.reply_text("Не поняла по голосу 🤔 Попробуй текстом или фото ценника")

    except Exception as e:
        logger.error(f"Error processing voice: {e}")
        await update.message.reply_text("Ошибка с голосом 😞 Повтори, пожалуйста")
