import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models import Session
from services.comparison import lookup_and_compare, format_response
from services.social_proof import get_stats
from services.supabase import SupabaseService
from datetime import datetime

logger = logging.getLogger(__name__)

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session) -> None:
    """Show confirmation dialog for extracted data"""

    partial = session.partial
    missing_field = session.next_missing()

    if missing_field:
        # Ask for missing field
        if missing_field == "product":
            msg = "What's the product, please? 🤔\n(Какой товар?)"
            await update.message.reply_text(msg)
        elif missing_field == "price":
            msg = "How much was it? 💰\n(Сколько стоит?)"
            await update.message.reply_text(msg)
        elif missing_field == "source":
            msg = "Where did you spot it? 🏪\n(Где вы видели?)"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏬 Магазин", callback_data="source_magazin")],
                [InlineKeyboardButton("🏢 Базар", callback_data="source_bazar")],
                [InlineKeyboardButton("🛒 Лавка", callback_data="source_lavka")],
                [InlineKeyboardButton("📦 Опт", callback_data="source_altyn_orda")]
            ])
            await update.message.reply_text(msg, reply_markup=keyboard)
            session.missing_field = "source"
            context.user_data["session"] = session
            return
        elif missing_field == "unit":
            msg = "В какой упаковке?"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("кг", callback_data="unit_kg"),
                    InlineKeyboardButton("шт", callback_data="unit_pcs")
                ]
            ])
            await update.message.reply_text(msg, reply_markup=keyboard)
            session.missing_field = "unit"
            context.user_data["session"] = session
            return

        session.missing_field = missing_field
        context.user_data["session"] = session
        return

    # All fields complete - show confirmation
    product_name = partial.get("product", "")
    price = partial.get("price", 0)
    source = partial.get("source")
    source_detail = partial.get("source_detail")

    confirmation_text = f"✅ {product_name.capitalize()}, {price} ₸"
    if source_detail:
        confirmation_text += f" в {source_detail.capitalize()}"
    elif source:
        confirmation_text += f" ({source.capitalize()})"
    confirmation_text += ". Верно?"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton("✏️ Исправить", callback_data="confirm_edit"),
            InlineKeyboardButton("❌ Отмена", callback_data="confirm_cancel")
        ]
    ])

    context.user_data["session"] = session
    await update.message.reply_text(confirmation_text, reply_markup=keyboard)

async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation buttons"""

    query = update.callback_query
    await query.answer()

    session = context.user_data.get("session")
    if not session:
        await query.edit_message_text("Сессия истекла, повтори с начала")
        return

    if query.data == "confirm_cancel":
        context.user_data.pop("session", None)
        await query.edit_message_text("❌ Отменили")
        return

    if query.data == "confirm_edit":
        await query.edit_message_text("✏️ Напиши исправленные данные")
        session.missing_field = None
        context.user_data["session"] = session
        return

    if query.data == "confirm_yes":
        # Lookup and compare
        await process_comparison(update, context, session)
        context.user_data.pop("session", None)
        return

    # Source selection
    if query.data.startswith("source_"):
        source_map = {
            "source_magazin": "magazin",
            "source_bazar": "bazar",
            "source_lavka": "lavka",
            "source_altyn_orda": "altyn_orda"
        }
        source = source_map.get(query.data)
        if source:
            session.partial["source"] = source
            session.missing_field = None
            context.user_data["session"] = session
            await query.answer()
            partial = session.partial
            # Check if more fields missing - if yes, show next question
            next_missing = session.next_missing()
            if next_missing:
                # Re-check confirmation to ask for next missing field
                if next_missing == "product":
                    await context.bot.send_message(chat_id=query.from_user.id, text="А что за товар? 🤔")
                elif next_missing == "price":
                    await context.bot.send_message(chat_id=query.from_user.id, text="А сколько стоит? 💰")
                elif next_missing == "unit":
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("кг", callback_data="unit_kg"),
                            InlineKeyboardButton("шт", callback_data="unit_pcs")
                        ]
                    ])
                    await context.bot.send_message(chat_id=query.from_user.id, text="В какой упаковке?", reply_markup=keyboard)
                session.missing_field = next_missing
                context.user_data["session"] = session
            else:
                # All fields complete - show confirmation
                confirmation_text = f"✅ {partial.get('product', '').capitalize()}, {partial.get('price', 0)} ₸"
                if partial.get("source_detail"):
                    confirmation_text += f" в {partial.get('source_detail').capitalize()}"
                elif partial.get("source"):
                    confirmation_text += f" ({partial.get('source').capitalize()})"
                confirmation_text += ". Верно?"
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
                        InlineKeyboardButton("✏️ Исправить", callback_data="confirm_edit"),
                        InlineKeyboardButton("❌ Отмена", callback_data="confirm_cancel")
                    ]
                ])
                await context.bot.send_message(chat_id=query.from_user.id, text=confirmation_text, reply_markup=keyboard)
            return

    # Unit selection
    if query.data in ["unit_kg", "unit_pcs"]:
        unit = "кг" if query.data == "unit_kg" else "шт"
        session.partial["unit"] = unit
        session.missing_field = None
        context.user_data["session"] = session
        await query.answer()
        partial = session.partial
        # Check if more fields missing
        next_missing = session.next_missing()
        if next_missing:
            if next_missing == "product":
                await context.bot.send_message(chat_id=query.from_user.id, text="А что за товар? 🤔")
            elif next_missing == "price":
                await context.bot.send_message(chat_id=query.from_user.id, text="А сколько стоит? 💰")
            elif next_missing == "source":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏬 Магазин", callback_data="source_magazin")],
                    [InlineKeyboardButton("🏢 Базар", callback_data="source_bazar")],
                    [InlineKeyboardButton("🛒 Лавка", callback_data="source_lavka")],
                    [InlineKeyboardButton("📦 Опт", callback_data="source_altyn_orda")]
                ])
                await context.bot.send_message(chat_id=query.from_user.id, text="Где ты видел(а)? 🏪", reply_markup=keyboard)
            session.missing_field = next_missing
            context.user_data["session"] = session
        else:
            # All fields complete - show confirmation
            confirmation_text = f"✅ {partial.get('product', '').capitalize()}, {partial.get('price', 0)} ₸"
            if partial.get("source_detail"):
                confirmation_text += f" в {partial.get('source_detail').capitalize()}"
            elif partial.get("source"):
                confirmation_text += f" ({partial.get('source').capitalize()})"
            confirmation_text += ". Верно?"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
                    InlineKeyboardButton("✏️ Исправить", callback_data="confirm_edit"),
                    InlineKeyboardButton("❌ Отмена", callback_data="confirm_cancel")
                ]
            ])
            await context.bot.send_message(chat_id=query.from_user.id, text=confirmation_text, reply_markup=keyboard)
        return

async def process_comparison(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session) -> None:
    """Main comparison logic"""

    user = update.effective_user
    partial = session.partial

    supabase = SupabaseService()

    try:
        # Get user's district if not set
        user_data = await supabase.get_user(user.id)
        district = partial.get("district") or (user_data.get("district") if user_data else None)

        # Lookup and compare
        result = await lookup_and_compare(
            product_name=partial.get("product", ""),
            submitted_price=partial.get("price", 0),
            source=partial.get("source"),
            source_detail=partial.get("source_detail"),
            district=district,
            supabase_service=supabase
        )

        # Get social proof count
        social_proof_count = 0
        if result.has_pash_offer and result.product_id:
            social_proof_count = await get_stats(result.product_id, district, supabase)

        # Format response
        text, keyboard = format_response(result, social_proof_count)

        # Send response
        await context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard["inline_keyboard"])
        )

        # Insert into price_queries
        query_data = {
            "telegram_id": user.id,
            "product_id": result.product_id,
            "product_name_raw": result.product_name_raw,
            "submitted_price": result.submitted_price,
            "submitted_source": result.submitted_source,
            "submitted_source_detail": result.submitted_source_detail,
            "pash_price": result.pash_price,
            "savings_pct": result.savings_pct,
            "has_pash_offer": result.has_pash_offer,
            "district": result.district,
            "created_at": datetime.utcnow().isoformat()
        }

        await supabase.insert_query(query_data)

        # Always ask for district if not extracted from message
        # (allow user to specify different district each time)
        if not partial.get("district"):
            logger.info(f"Asking for district for user {user.id}")
            await ask_for_district(update, context, user.id, supabase)
        else:
            logger.info(f"District extracted from message for user {user.id}: {partial.get('district')}")

    except Exception as e:
        logger.error(f"Error in comparison: {e}")
        await context.bot.send_message(
            chat_id=user.id,
            text="Ошибка при обработке 😞 Повтори, пожалуйста"
        )

async def ask_for_district(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, supabase: SupabaseService) -> None:
    """Ask user for district if not set"""

    message = "Which district was it in? 📍\n(В каком районе эта цена?)"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Share location", callback_data="location_share")],
        [InlineKeyboardButton("✏️ Type district", callback_data="location_text")],
        [InlineKeyboardButton("⏭ Skip", callback_data="location_skip")]
    ])

    await context.bot.send_message(chat_id=user_id, text=message, reply_markup=keyboard)

async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle location selection"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    supabase = SupabaseService()

    if query.data == "location_skip":
        context.user_data.pop("awaiting_location", None)
        context.user_data.pop("awaiting_district_text", None)
        await context.bot.send_message(chat_id=query.from_user.id, text="No worries! 👍\n(Спасибо за информацию!)")
        return

    if query.data == "location_text":
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="Type the district name, please 📍\n(Напишите название района)"
        )
        context.user_data["awaiting_district_text"] = True
        return

    if query.data == "location_share":
        context.user_data["awaiting_location"] = True
        # Send keyboard with location sharing button
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Share my location", request_location=True)]],
            one_time_keyboard=True
        )
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="Please share your location 📍\n(Пожалуйста, отправьте вашу локацию)",
            reply_markup=keyboard
        )
        return

async def location_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle district text input"""

    if not context.user_data.get("awaiting_district_text"):
        return

    supabase = SupabaseService()
    user_id = update.effective_user.id
    text = update.message.text

    # Normalize district
    normalized = await supabase.normalize_district(text)
    district = normalized or text

    # Update user
    await supabase.update_user_district(user_id, district)

    context.user_data.pop("awaiting_district_text", None)
    await update.message.reply_text(f"Cheers! 🙏 Got it: {district}\n(Спасибо! Записала район: {district})")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle location sharing"""

    if not context.user_data.get("awaiting_location"):
        return

    location = update.message.location
    supabase = SupabaseService()

    # Find nearest district
    district = await supabase.find_district_by_coords(location.latitude, location.longitude)

    if not district:
        await update.message.reply_text("Couldn't pinpoint the district 🤔 Type it manually, please\n(Не смогла определить район. Напишите вручную)")
        context.user_data["awaiting_district_text"] = True
        return

    # Update user
    await supabase.update_user_district(update.effective_user.id, district, (location.latitude, location.longitude))

    context.user_data.pop("awaiting_location", None)
    await update.message.reply_text(f"Cheers! 🙏 Got it: {district}\n(Спасибо! Записала район: {district})")
