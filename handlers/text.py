import logging
from telegram import Update
from telegram.ext import ContextTypes
from models import Session
from services.gemini import parse_free_text
from handlers.confirm import show_confirmation
from router import route

logger = logging.getLogger(__name__)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input - parse and show confirmation"""

    user = update.effective_user
    text = update.message.text

    # Check if user is correcting a batch
    if context.user_data.get("awaiting_batch_edit"):
        context.user_data.pop("awaiting_batch_edit", None)
        context.user_data.pop("batch", None)
        parsed = await parse_free_text(text)
        if parsed.items and len(parsed.items) > 1:
            await handle_batch_input(update, context, parsed)
        elif parsed.items:
            session = Session()
            session.items = parsed.items
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
        else:
            await update.message.reply_text("Не поняла 🤔 Попробуй ещё раз")
        return

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

    # Check router first (static responses, no Gemini needed)
    routed = route(text)
    if routed:
        await update.message.reply_text(routed, parse_mode="Markdown")
        return

    # Parse text with Gemini
    parsed = await parse_free_text(text)

    if not parsed.items:
        await update.message.reply_text("Не поняла 🤔 Повтори, пожалуйста? Например: 'банан 920 магнум'")
        return

    # Multiple items → batch mode
    if len(parsed.items) > 1:
        await handle_batch_input(update, context, parsed)
        return

    # Single item → standard flow
    session = Session()
    session.items = parsed.items
    session.source = parsed.source
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


async def handle_batch_input(update, context, parsed) -> None:
    """Handle multiple items — show list confirmation."""
    from services.batch_processor import format_batch_confirmation
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    # Store batch in user_data
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
