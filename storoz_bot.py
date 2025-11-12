import os
import random
import threading
from datetime import time, timedelta, datetime

from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# --- Настройки / защита от пустого токена ---
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("ENV переменная TOKEN не задана. "
                       "Задайте TOKEN в Bothost → Переменные окружения.")

# Если вдруг сервер/контейнер в UTC — так считаем московское смещение
MSK_OFFSET = timedelta(hours=3)

LETTERS = ["М", "Г", "П"]

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 Сторож на посту! Я буду присылать напоминания и шифры по расписанию.\n"
        "Команда /new — получить шифр вручную."
    )

    chat_id = update.effective_chat.id
    jq = context.application.job_queue

    # Напоминания каждые 10 минут с 08:00 до 22:00 МСК (переводим в UTC)
    for msk_hour in range(8, 22 + 1):  # 8..22 включительно
        utc_hour = (datetime(2000,1,1,msk_hour) - MSK_OFFSET).hour
        for minute in (0, 10):
            jq.run_daily(
                send_reminder,
                time=time(hour=utc_hour, minute=minute),
                chat_id=chat_id,
                name=f"rem_{chat_id}_{utc_hour:02d}_{minute:02d}"
            )

    # Шифры в 05:00, 11:00, 17:00, 23:00 МСК
    for msk_hour in (5, 11, 17, 23):
        utc_hour = (datetime(2000,1,1,msk_hour) - MSK_OFFSET).hour
        jq.run_daily(
            send_cipher,
            time=time(hour=utc_hour, minute=0),
            chat_id=chat_id,
            name=f"cipher_{chat_id}_{utc_hour:02d}_00"
        )

async def new_cipher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    letter = random.choice(LETTERS)
    number = random.randint(1, 20)
    await update.message.reply_text(f"🕯️ Новый шифр: {letter}{number}")

# ---------- Джобы ----------
async def send_cipher(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    letter = random.choice(LETTERS)
    number = random.randint(1, 20)
    await context.bot.send_message(chat_id=chat_id, text=f"🕯️ Шифр Сторожа: {letter}{number}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id=chat_id, text="⏰ Пора сделать дело 🔥")

# ---------- Flask (не обязателен на Bothost, но мешать не будет) ----------
server = Flask(__name__)

@server.route("/")
def home():
    return "✅ Shifr Storozha bot is running."

def run_flask():
    # Bothost не требует web-порта для polling, но держать health-ok не мешает
    server.run(host="0.0.0.0", port=8080)

# ---------- Запуск PTB ----------
def start_bot():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_cipher))

    print("✅ Telegram bot started. Using polling...")
    # run_polling автоматически снимет webhook, если он вдруг был
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == "__main__":
    # Поднимем Flask в фоне (не критично)
    threading.Thread(target=run_flask, daemon=True).start()
    # Бот — в основном потоке
    start_bot()
