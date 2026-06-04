import logging
from telegram import Update
from telegram.ext import ContextTypes
from models import Session
from services.gemini import parse_free_text
from handlers.confirm import show_confirmation

logger = logging.getLogger(__name__)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input - parse and show confirmation"""

    user = update.effective_user
    text = update.message.text

    # Check if user is answering district question
    if context.user_data.get("awaiting_district_text"):
        from services.supabase import SupabaseService
        supabase = SupabaseService()
        normalized = await supabase.normalize_district(text)
        district = normalized or text
        await supabase.update_user_district(user.id, district)
        context.user_data.pop("awaiting_district_text", None)
        await update.message.reply_text(f"Cheers! 🙏 Got it: {district}\n(Спасибо! Записала район: {district})")
        return

    # Check if user is responding to missing field question
    session = context.user_data.get("session")

    if session and session.missing_field:
        # User is answering a specific question
        await handle_missing_field_response(update, context, session, text)
        return

    # Parse text with Gemini
    parsed = await parse_free_text(text)

    # Store in session
    session = Session()
    session.items = parsed.items
    session.source = parsed.source
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
        await update.message.reply_text("Не поняла 🤔 Повтори, пожалуйста? Например: 'банан 920 магнум'")

async def handle_missing_field_response(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session, text: str) -> None:
    """Handle response to a specific missing field question"""

    user_id = update.effective_user.id
    missing_field = session.missing_field

    if missing_field == "product":
        session.partial["product"] = text
    elif missing_field == "price":
        try:
            price = float(text.replace(",", ".").strip())
            session.partial["price"] = price
        except ValueError:
            await update.message.reply_text("А это число? 🤔 Повтори цену")
            return
    elif missing_field == "district":
        # Try to normalize district
        from services.supabase import SupabaseService
        supabase = SupabaseService()
        normalized = await supabase.normalize_district(text)
        if normalized:
            session.partial["district"] = normalized
        else:
            session.partial["district"] = text
    elif missing_field == "source":
        session.partial["source"] = text

    session.missing_field = None

    # Show confirmation
    await show_confirmation(update, context, session)
