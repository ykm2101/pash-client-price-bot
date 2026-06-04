# Pash Client Price Bot 🥑

Telegram bot for comparing prices at PÄSH.

## Deploy на Railway 🚀

### Шаги деплоя:

1. **Создай аккаунт на Railway:**
   - Перейди на https://railway.app
   - Зарегистрируйся через GitHub

2. **Создай новый проект:**
   - Нажми "New Project"
   - Выбери "Deploy from GitHub"
   - Выбери этот репозиторий

3. **Установи переменные окружения:**
   На странице переменных добавь:
   ```
   TELEGRAM_BOT_TOKEN_CLIENT = [твой токен бота]
   GEMINI_API_KEY = [твой Gemini API ключ]
   SUPABASE_URL = https://nzskcvwghqadvobjrppf.supabase.co
   SUPABASE_ANON_KEY = [твой Supabase анон ключ]
   ```

4. **Запусти деплой:**
   - Railway автоматически начнет деплой
   - Проверь логи в разделе "Deployments"

5. **Убедись что бот работает:**
   - Отправь `/start` в Telegram боту
   - Проверь логи в Railway

## Локальная разработка

```bash
# Установи зависимости
pip install -r requirements.txt

# Создай .env файл (скопируй из .env.example)
cp .env.example .env

# Запусти бота
python main.py
```

## Структура проекта

```
├── main.py              # Точка входа
├── config.py            # Конфигурация
├── models.py            # Модели данных
├── sources.py           # Маппинг источников
├── prompts.py           # Промпты Gemini
├── requirements.txt     # Зависимости
├── handlers/            # Обработчики команд
└── services/            # Сервисы (Supabase, Gemini)
```

## Telegram бот: @pash_client_price_bot

Публичный бот для сравнения цен на фрукты и овощи в Алматы.
