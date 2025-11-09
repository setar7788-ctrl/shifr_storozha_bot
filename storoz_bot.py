from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random, os
from datetime import datetime, time, timedelta

# Московское время (UTC+3)
moscow_time = datetime.utcnow() + timedelta(hours=3)

TOKEN = os.environ.get("TOKEN")

letters = ['М', 'Г', 'П']

# ---- Функции ----

async def send_cipher(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    letter = random.choice(letters)
    number = random.randint(1, 20)
    await context.bot.send_message(chat_id=chat_id, text=f"🕯️ Шифр Сторожа: {letter}{number}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id=chat_id, text="⏰ Пора сделать дело 🔥")

# команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🔥 Сторож на посту! Я буду присылать напоминания и шифры по расписанию.\n"
        "Команда /new — получить шифр вручную."
    )

    # каждые 30 минут с 8:00 до 22:00 (по Москве)
    for hour in range(5, 20):  # UTC → МСК (+3 часа)
        for minute in (0, 30):
            send_time = time(hour=hour, minute=minute)
            job_queue.run_daily(send_reminder, time=send_time, chat_id=chat_id)

    # шифры в 05, 11, 17, 23 (по МСК → UTC)
    for hour in (2, 8, 14, 20):  # смещение -3
        send_time = time(hour=hour, minute=0)
        job_queue.run_daily(send_cipher, time=send_time, chat_id=chat_id)

# команда /new — выдать шифр по запросу
async def new_cipher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    letter = random.choice(letters)
    number = random.randint(1, 20)
    await update.message.reply_text(f"🕯️ Новый шифр: {letter}{number}")

# ---- Основной блок ----

app = ApplicationBuilder().token(TOKEN).build()
job_queue = app.job_queue

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("new", new_cipher))

app.run_polling()
