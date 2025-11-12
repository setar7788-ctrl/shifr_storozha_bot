from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random, os, threading
from datetime import datetime, time, timedelta
from flask import Flask

# ---- Настройки ----

TOKEN = os.environ.get("TOKEN") or os.environ.get("BOT_TOKEN")
LETTERS = ['М', 'Г', 'П']
DATA_DIR = "/app/data"
LAST_CHAT_FILE = os.path.join(DATA_DIR, "last_chat.txt")

# ---- Вспомогательные функции ----

def is_moscow_daytime() -> bool:
    """Проверяем, сейчас 8:00–22:00 по Москве"""
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    return 8 <= now_msk.hour < 22

def save_last_chat(chat_id: int):
    """Сохраняем ID последнего пользователя"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_CHAT_FILE, "w") as f:
        f.write(str(chat_id))
    print(f"[{datetime.now()}] 💾 Сохранён chat_id: {chat_id}")

def load_last_chat() -> int | None:
    """Загружаем ID последнего пользователя"""
    if os.path.exists(LAST_CHAT_FILE):
        with open(LAST_CHAT_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except:
                return None
    return None

# ---- Задачи ----

async def send_cipher(context: ContextTypes.DEFAULT_TYPE):
    """Отправка случайного шифра"""
    chat_id = context.job.chat_id
    letter = random.choice(LETTERS)
    number = random.randint(1, 20)
    msg = f"🕯️ Шифр Сторожа: {letter}{number}"
    print(f"[{datetime.now()}] Отправлен шифр → {msg}")
    await context.bot.send_message(chat_id=chat_id, text=msg)

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминания каждые 30 минут (только днём по МСК)"""
    chat_id = context.job.chat_id
    if is_moscow_daytime():
        msg = "⏰ Пора сделать дело 🔥"
        print(f"[{datetime.now()}] Напоминание отправлено пользователю {chat_id}")
        await context.bot.send_message(chat_id=chat_id, text=msg)
    else:
        print(f"[{datetime.now()}] 🌙 Ночь по МСК — напоминание пропущено")

# ---- Команды ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — активация расписания"""
    chat_id = update.effective_chat.id
    save_last_chat(chat_id)

    await update.message.reply_text(
        "🔥 Сторож на посту! Я буду присылать напоминания и шифры по расписанию.\n"
        "Команда /new — получить шифр вручную.\n"
        "Команда /test — проверить немедленную отправку напоминания."
    )

    job_queue = context.application.job_queue

    # Удаляем старые задачи только для этого пользователя
    for job in job_queue.get_jobs_by_name(f"reminder_{chat_id}"):
        job.schedule_removal()
    for hour in [7, 11, 17, 22]:
        for job in job_queue.get_jobs_by_name(f"cipher_{chat_id}_{hour}"):
            job.schedule_removal()

    print(f"[{datetime.now()}] 🔄 Расписание обновлено для пользователя {chat_id}")

    # 🔁 Напоминания каждые 30 минут
    job_queue.run_repeating(
        send_reminder,
        interval=1800,  # каждые 30 минут
        first=10,       # через 10 секунд
        chat_id=chat_id,
        name=f"reminder_{chat_id}"
    )

    # 🕯️ Шифры в 07:00, 11:00, 17:00, 22:00 (по Москве)
    moscow_hours = [7, 11, 17, 22]
    for hour in moscow_hours:
        send_time = time(hour - 3, 0)  # UTC-сдвиг
        job_queue.run_daily(
            send_cipher,
            time=send_time,
            chat_id=chat_id,
            name=f"cipher_{chat_id}_{hour}"
        )

    print(f"[{datetime.now()}] ✅ Пользователь {chat_id} активировал расписание")

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

    # ✅ Восстановление расписания при рестарте
    last_chat = load_last_chat()
    if last_chat:
        print(f"[{datetime.now()}] ♻️ Восстанавливаю расписание для chat_id={last_chat}")
        jq = app.job_queue
        jq.run_repeating(send_reminder, interval=1800, first=15, chat_id=last_chat, name=f"reminder_{last_chat}")

        for hour in [7, 11, 17, 22]:
            send_time = time(hour - 3, 0)
            jq.run_daily(send_cipher, time=send_time, chat_id=last_chat, name=f"cipher_{last_chat}_{hour}")
    else:
        print(f"[{datetime.now()}] ⚠️ Нет сохранённого chat_id, жду команду /start")

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
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=PORT), daemon=True).start()
    start_bot()
