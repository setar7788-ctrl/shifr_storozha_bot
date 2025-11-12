from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random, os, threading
from datetime import datetime, time, timedelta
from flask import Flask

# Московское время (UTC+3)
moscow_time = datetime.utcnow() + timedelta(hours=3)

# Токен бота берётся из переменной окружения (Bothost / Fly.io)
TOKEN = os.environ.get("TOKEN") or os.environ.get("BOT_TOKEN")

# Набор возможных букв для шифра
letters = ['М', 'Г', 'П']

# ---- Функции ----

async def send_cipher(context: ContextTypes.DEFAULT_TYPE):
    """Отправка случайного шифра"""
    chat_id = context.job.chat_id
    letter = random.choice(letters)
    number = random.randint(1, 20)
    await context.bot.send_message(chat_id=chat_id, text=f"🕯️ Шифр Сторожа: {letter}{number}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Напоминание"""
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id=chat_id, text="⏰ Пора сделать дело 🔥")

# ---- Команды ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🔥 Сторож на посту! Я буду присылать напоминания и шифры по расписанию.\n"
        "Команда /new — получить шифр вручную."
    )

    job_queue = context.application.job_queue

    # Каждые 10 минут с 8:00 до 22:00 (по Москве)
    for hour in range(2, 20):  # UTC → МСК (+3)
        for minute in (0, 10):
            send_time = time(hour=hour, minute=minute)
            job_queue.run_daily(send_reminder, time=send_time, chat_id=chat_id)

    # Шифры в 05, 11, 17, 23 (по МСК → UTC)
    for hour in (2, 8, 14, 20):
        send_time = time(hour=hour, minute=0)
        job_queue.run_daily(send_cipher, time=send_time, chat_id=chat_id)

async def new_cipher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /new — выдать шифр вручную"""
    letter = random.choice(letters)
    number = random.randint(1, 20)
    await update.message.reply_text(f"🕯️ Новый шифр: {letter}{number}")

# ---- Основной блок ----

def start_bot():
    """Инициализация Telegram-бота"""
    if not TOKEN:
        print("❌ Ошибка: переменная TOKEN не найдена! Убедись, что она задана в Bothost.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_cipher))

    print("✅ Telegram bot started and polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# ---- Flask для проверки на сервере ----

server = Flask(__name__)

@server.route("/")
def home():
    return "✅ Shifr Storozha bot is running!"

# ---- Точка входа ----

if __name__ == "__main__":
    # Бот запускаем в отдельном потоке
    threading.Thread(target=start_bot, daemon=True).start()

    # Flask-сервер работает в основном потоке
    PORT = int(os.environ.get("PORT", 5000))
    server.run(host="0.0.0.0", port=PORT)

