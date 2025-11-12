from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random, os, threading
from datetime import datetime, time, timedelta
from flask import Flask

# ---- Настройки ----

# Токен бота из переменных окружения
TOKEN = os.environ.get("TOKEN") or os.environ.get("BOT_TOKEN")

# Массив букв для шифров
LETTERS = ['М', 'Г', 'П']

# ---- Функции ----

def is_moscow_daytime() -> bool:
    """Проверяем, сейчас 8:00–22:00 по Москве"""
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    return 8 <= now_msk.hour < 22

async def send_cipher(context: ContextTypes.DEFAULT_TYPE):
    """Отправка случайного шифра по расписанию"""
    chat_id = context.job.chat_id
    letter = random.choice(LETTERS)
    number = random.randint(1, 20)
    msg = f"🕯️ Шифр Сторожа: {letter}{number}"
    print(f"[{datetime.now()}] Отправлен шифр → {msg}")
    await context.bot.send_message(chat_id=chat_id, text=msg)

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминаний каждые 10 минут (только днём по МСК)"""
    chat_id = context.job.chat_id
    if is_moscow_daytime():
        msg = "⏰ Пора сделать дело 🔥"
        print(f"[{datetime.now()}] Напоминание отправлено пользователю {chat_id}")
        await context.bot.send_message(chat_id=chat_id, text=msg)
    else:
        print(f"[{datetime.now()}] Ночь по МСК — напоминание пропущено")

# ---- Команды ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — активация расписания"""
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🔥 Сторож на посту! Я буду присылать напоминания и шифры по расписанию.\n"
        "Команда /new — получить шифр вручную.\n"
        "Команда /test — проверить немедленную отправку напоминания."
    )

    job_queue = context.application.job_queue

    # Очистка старых задач (чтобы не дублировались)
    job_queue.scheduler.remove_all_jobs()
    print(f"[{datetime.now()}] Расписание обновлено для пользователя {chat_id}")

    # 🔁 Напоминания каждые 10 минут
    job_queue.run_repeating(
        send_reminder,
        interval=600,  # каждые 10 минут
        first=10,      # через 10 секунд после /start
        chat_id=chat_id,
        name=f"reminder_{chat_id}"
    )

    # 🕯️ Шифры в 08:00, 11:00, 17:00, 21:00 (по Москве)
    moscow_hours = [8, 11, 17, 21]
    for hour in moscow_hours:
        send_time = time(hour - 3, 0)  # переводим в UTC
        job_queue.run_daily(
            send_cipher,
            time=send_time,
            chat_id=chat_id,
            name=f"cipher_{chat_id}_{hour}"
        )

    print(f"[{datetime.now()}] Пользователь {chat_id} активировал расписание")

async def new_cipher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /new — выдать шифр вручную"""
    letter = random.choice(LETTERS)
    number = random.randint(1, 20)
    msg = f"🕯️ Новый шифр: {letter}{number}"
    print(f"[{datetime.now()}] Пользователь запросил новый шифр → {msg}")
    await update.message.reply_text(msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /test — моментальное напоминание"""
    chat_id = update.effective_chat.id
    msg = "🔔 Тестовое напоминание! Всё работает."
    print(f"[{datetime.now()}] Тестовое сообщение пользователю {chat_id}")
    await context.bot.send_message(chat_id=chat_id, text=msg)

# ---- Основной блок ----

def start_bot():
    if not TOKEN:
        print("❌ Ошибка: переменная TOKEN не найдена! Убедись, что она задана в Bothost.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_cipher))
    app.add_handler(CommandHandler("test", test))

    print("✅ Telegram bot started and polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# ---- Flask (для проверки на Bothost) ----

server = Flask(__name__)

@server.route("/")
def home():
    return "✅ Shifr Storozha bot is running!"

# ---- Точка входа ----

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    threading.Thread(
        target=lambda: server.run(host="0.0.0.0", port=PORT),
        daemon=True
    ).start()

    start_bot()

