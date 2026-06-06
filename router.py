"""
Simple pattern router — handles common questions before Gemini.
Returns response text or None (if should go to Gemini).
"""
from typing import Optional

HELP_PATTERNS = [
    "что умеешь", "что ты умеешь", "что можешь", "помощь", "help",
    "как пользоваться", "как работаешь", "инструкция", "команды",
    "что делаешь", "для чего ты", "как ты работаешь"
]

PVZ_PATTERNS = [
    "где забрать", "адрес", "пвз", "самовывоз", "пункт выдачи",
    "где находитесь", "как забрать", "pickup", "pvz", "где вы"
]

CATALOG_PATTERNS = [
    "что есть", "что возите", "ваши товары", "каталог", "прайс",
    "ассортимент", "список товаров", "что продаёте", "что продаете"
]

GREETING_PATTERNS = [
    "привет", "салем", "hello", "hi", "здравствуй", "добрый день",
    "доброе утро", "добрый вечер", "хай", "хэй"
]


HELP_TEXT = """Вот что я умею! 🎩

📸 *Отправь фото* — ценника или чека
🎤 *Запиши голос* — скажи цену и товар
💬 *Напиши текст* — "банан 900 магнум"

Можно сразу несколько товаров:
"авокадо 1630, банан 897, помидор 650 магнум"

Я сравню с ценами PÄSH и покажу экономию 💰

Команды:
/start — начать заново
/help — эта справка"""

GREETING_TEXT = """Hello! 👋 I'm Mani-Penny.

Отправьте цену из магазина — текстом, голосом или фото.
Скажу насколько дешевле у PÄSH 🥑"""


def route(text: str) -> Optional[str]:
    """
    Check if text matches a known pattern.
    Returns response string or None (pass to Gemini).
    """
    text_lower = text.lower().strip()

    # Greeting
    if any(p in text_lower for p in GREETING_PATTERNS):
        return GREETING_TEXT

    # Help
    if any(p in text_lower for p in HELP_PATTERNS):
        return HELP_TEXT

    # PVZ — will be expanded later with actual addresses
    if any(p in text_lower for p in PVZ_PATTERNS):
        return (
            "📍 Наши пункты выдачи в Алматы:\n"
            "Актуальный список на pash.kz/pvz\n\n"
            "Или нажмите 👉 [Карта ПВЗ](https://pash.kz/pvz)"
        )

    # Catalog
    if any(p in text_lower for p in CATALOG_PATTERNS):
        return (
            "🥑 Везём свежие фрукты и овощи из Казахстана и Центральной Азии.\n\n"
            "Актуальный каталог на pash.kz\n"
            "Просто отправьте название товара — сравню цену! 💰"
        )

    return None  # Pass to Gemini
