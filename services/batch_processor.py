import logging
from typing import List, Optional
from models import PriceEntry, ComparisonResult
from services.comparison import lookup_and_compare, format_number, get_product_emoji
from services.social_proof import get_stats
from services.supabase import SupabaseService
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

logger = logging.getLogger(__name__)


async def process_batch(
    items: List[PriceEntry],
    source: Optional[str],
    source_detail: Optional[str],
    district: Optional[str],
    user_id: int,
    supabase: SupabaseService
) -> tuple[str, dict]:
    """
    Process multiple price entries at once.
    Returns (formatted_text, keyboard)
    """

    results = []
    for item in items:
        result = await lookup_and_compare(
            product_name=item.product,
            submitted_price=item.price,
            source=source or item.source,
            source_detail=source_detail or item.source_detail,
            district=district,
            supabase_service=supabase
        )
        results.append(result)

    text = await format_batch_response(results, district, user_id, supabase)

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🛒 Заказать", "url": "https://pash.kz"},
                {"text": "🗺 Карта цен", "url": "https://pash.kz/map"}
            ]
        ]
    }

    return text, keyboard


async def format_batch_response(
    results: List[ComparisonResult],
    district: Optional[str],
    user_id: int,
    supabase: SupabaseService
) -> str:
    """Format multiple comparison results into one message."""

    found = [r for r in results if r.has_pash_offer]
    not_found = [r for r in results if not r.has_pash_offer]

    total_savings = sum(r.savings_abs for r in found if r.savings_abs) if found else 0

    lines = []

    # Items that PÄSH sells
    for result in found:
        emoji = get_product_emoji(result.product_name)

        source_text = ""
        if result.submitted_source_detail:
            source_text = result.submitted_source_detail.capitalize()
        elif result.submitted_source:
            source_text = result.submitted_source.capitalize()
        else:
            source_text = "Магазин"

        lines.append(f"{emoji} *{result.product_name.capitalize()}*")
        lines.append(f"{source_text}: {format_number(result.submitted_price)} ₸/кг")
        lines.append(f"PÄSH: {format_number(result.pash_price)} ₸/кг")

        if result.savings_abs and result.savings_pct:
            lines.append(f"💰 Экономия: {format_number(result.savings_abs)} ₸ ({int(result.savings_pct)}%)")

        # Container info
        if result.container_info and result.pash_price:
            for container_type, weight_kg in result.container_info.items():
                total_price = result.pash_price * weight_kg
                lines.append(f"📦 {container_type.capitalize()} {weight_kg} кг — {format_number(total_price)} ₸")

        # Social proof
        if result.product_id:
            count = await supabase.get_social_proof(result.product_id, district)
            if count >= 5:
                district_text = f" в {district}" if district else ""
                lines.append(f"👥 {count} человек{district_text} проверяли на этой неделе")

        lines.append("")  # blank line between items

    # Items PÄSH doesn't sell
    if not_found:
        not_found_names = ", ".join(r.product_name for r in not_found)
        lines.append(f"👀 Пока не возим: {not_found_names} — но скоро!")
        lines.append("")

    # Total savings
    if total_savings > 0 and len(found) > 1:
        lines.append(f"✨ *Итого экономия: {format_number(total_savings)} ₸*")

    return "\n".join(lines).strip()


async def save_batch(
    results: List[ComparisonResult],
    user_id: int,
    district: Optional[str],
    supabase: SupabaseService
) -> None:
    """Save all price queries to Supabase."""
    for result in results:
        try:
            await supabase.insert_query({
                "telegram_id": user_id,
                "product_id": result.product_id,
                "product_name_raw": result.product_name_raw,
                "submitted_price": result.submitted_price,
                "submitted_source": result.submitted_source,
                "submitted_source_detail": result.submitted_source_detail,
                "pash_price": result.pash_price,
                "savings_pct": result.savings_pct,
                "has_pash_offer": result.has_pash_offer,
                "district": district,
                "created_at": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error saving batch item {result.product_name_raw}: {e}")


def format_batch_confirmation(items: List[PriceEntry], source: Optional[str], source_detail: Optional[str]) -> str:
    """Format confirmation message for multiple items."""

    source_text = ""
    if source_detail:
        source_text = f" в {source_detail.capitalize()}"
    elif source:
        source_text = f" ({source.capitalize()})"

    lines = [f"Нашла {len(items)} товара{source_text}:\n"]
    for i, item in enumerate(items, 1):
        emoji = get_product_emoji(item.product)
        lines.append(f"{i}. {emoji} {item.product.capitalize()} — {format_number(item.price)} ₸")

    lines.append("\nВсё верно?")
    return "\n".join(lines)


def format_batch_editable(items: List[PriceEntry], source: Optional[str], source_detail: Optional[str]) -> str:
    """Format items as editable text for user to correct."""

    # Source suffix
    source_suffix = ""
    if source_detail:
        source_suffix = f" {source_detail}"
    elif source:
        source_suffix = f" {source}"

    lines = []
    for item in items:
        lines.append(f"{item.product} {int(item.price)}{source_suffix}")

    return "\n".join(lines)
