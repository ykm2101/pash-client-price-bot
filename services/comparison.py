import logging
from typing import Optional
from models import ComparisonResult
from services.supabase import SupabaseService

logger = logging.getLogger(__name__)

PRODUCT_EMOJIS = {
    'банан': '🍌', 'яблоко': '🍎', 'авокадо': '🥑', 'апельсин': '🍊',
    'огурец': '🥒', 'помидор': '🍅', 'виноград': '🍇', 'лимон': '🍋',
    'лук': '🧅', 'картошка': '🥔', 'персик': '🍑', 'киви': '🥝',
    'клубника': '🍓', 'помидоры': '🍅', 'огурцы': '🥒', 'яблоки': '🍎'
}

def get_product_emoji(product_name: str) -> str:
    """Get emoji for product"""
    product_lower = product_name.lower()
    for key, emoji in PRODUCT_EMOJIS.items():
        if key in product_lower:
            return emoji
    return '🥬'

def format_number(num: float) -> str:
    """Format number with spaces: 2970 -> '2 970'"""
    return f"{int(num):,}".replace(',', ' ')

async def lookup_and_compare(
    product_name: str,
    submitted_price: float,
    source: Optional[str],
    source_detail: Optional[str],
    district: Optional[str],
    supabase_service: SupabaseService
) -> ComparisonResult:
    """
    Lookup product in Supabase and compare with submitted price
    Returns ComparisonResult with all data for formatting
    """

    # Lookup product
    product = await supabase_service.lookup_product(product_name)

    if not product:
        # Product not found
        return ComparisonResult(
            product_id=None,
            product_name=product_name,
            product_name_raw=product_name,
            submitted_price=submitted_price,
            submitted_source=source,
            submitted_source_detail=source_detail,
            pash_price=None,
            savings_abs=None,
            savings_pct=None,
            has_pash_offer=False,
            container_info=None,
            district=district
        )

    # Product found - check if PÄSH has this item in their catalog (our_price must be set)
    pash_price = product.get("our_price")

    if not pash_price:
        # Product exists but PÄSH doesn't sell it yet
        return ComparisonResult(
            product_id=product.get("id"),
            product_name=product.get("name", product_name),
            product_name_raw=product_name,
            submitted_price=submitted_price,
            submitted_source=source,
            submitted_source_detail=source_detail,
            pash_price=None,
            savings_abs=None,
            savings_pct=None,
            has_pash_offer=False,
            container_info=None,
            district=district
        )

    # PÄSH has the product - calculate comparison
    savings_abs = submitted_price - pash_price
    savings_pct = ((submitted_price - pash_price) / submitted_price * 100) if submitted_price > 0 else None

    return ComparisonResult(
        product_id=product.get("id"),
        product_name=product.get("name", product_name),
        product_name_raw=product_name,
        submitted_price=submitted_price,
        submitted_source=source,
        submitted_source_detail=source_detail,
        pash_price=pash_price,
        savings_abs=savings_abs,
        savings_pct=savings_pct,
        has_pash_offer=True,
        container_info=product.get("container_weights"),
        district=district
    )

def format_response(result: ComparisonResult, social_proof_count: int) -> tuple[str, dict]:
    """
    Format response text and inline keyboard
    Returns (text, reply_markup dict)
    """

    emoji = get_product_emoji(result.product_name)

    if not result.has_pash_offer:
        # Product not found
        text = f"{emoji} {result.product_name} пока не возим — но скоро! 👀\nСледи за обновлениями\n"
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Подписаться на новинки", "url": "https://t.me/pash_kz"}]
            ]
        }
        return text, keyboard

    # Product found - show comparison
    source_text = ""
    if result.submitted_source_detail:
        source_text = result.submitted_source_detail.capitalize()
    elif result.submitted_source:
        source_text = result.submitted_source.capitalize()
    else:
        source_text = "Магазин"

    text = f"{emoji} {result.product_name}\n"
    text += f"{source_text}: {format_number(result.submitted_price)} ₸/кг\n"
    text += f"PÄSH: {format_number(result.pash_price)} ₸/кг\n\n"

    # Only show savings if both prices are valid
    if result.savings_abs is not None and result.savings_pct is not None:
        text += f"💰 Экономия: {format_number(result.savings_abs)} ₸/кг ({int(result.savings_pct)}%)\n\n"

    # Social proof
    if social_proof_count >= 5:
        district_text = f" в {result.district}" if result.district else ""
        text += f"👥 {social_proof_count} человек{district_text} проверяли на этой неделе\n"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🛒 Заказать", "url": "https://pash.kz"},
                {"text": "🗺 Карта цен", "url": "https://pash.kz/map"}
            ]
        ]
    }

    return text, keyboard
