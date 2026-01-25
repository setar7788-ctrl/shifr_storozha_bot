# -*- coding: utf-8 -*-
"""
Бот «Стоянка» (Мезолит) v4.3 — Добытчик
Логика: Сделал дело = +12ч сытости, Попробовал = +4ч сытости
Режимы: Хорошо (<12ч), Нехорошо (12-24ч), Бунт (>24ч)
ДОБАВЛЕНО: Диагностика таймера и тестовая команда /test_dopamine
"""

import os
import json
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import pytz

# ============== НАСТРОЙКИ ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_DIR = Path("/app/data")
TIMEZONE = pytz.timezone("Europe/Moscow")

# Период работы
BOT_START = datetime(2026, 1, 17, 16, 0, tzinfo=TIMEZONE)
BOT_END = datetime(2026, 2, 14, 0, 0, tzinfo=TIMEZONE)

# Расписание
WAKEUP_HOUR = 5
WAKEUP_MINUTE = 30
SLEEP_HOUR = 23
SLEEP_MINUTE = 0

# Дофаминовые подарки: с 6:55 до 22:55
DOPAMINE_START_HOUR = 6
DOPAMINE_END_HOUR = 22

# Лимиты голода
HUNGER_WARNING_HOURS = 12  # Режим "Нехорошо"
HUNGER_RIOT_HOURS = 24     # Режим "Бунт"

# Картинка для сна
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/setar7788-ctrl/shifr_storozha_bot/main"
NIGHT_IMAGE = f"{GITHUB_RAW_BASE}/для%20телефона.png"

# Пути к файлам
DATA_FILE = DATA_DIR / "stoyanka_data.json"
PHRASES_FILE = DATA_DIR / "phrases.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============== РАБОТА С ДАННЫМИ ==============
def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_data():
    default = {
        "user_id": None,
        "current_date": None,
        "morning_done": False,
        "last_feed_time": None,
        "hunger_notified": False,  # Отправлено ли уведомление о режиме "Нехорошо"
        "last_dopamine_hour": None,  # Последний час когда отправлен дофамин
        "goodnight_sent": False,  # Отправлено ли пожелание сна сегодня
    }
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, value in default.items():
                    if key not in data:
                        data[key] = value
                return data
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        return default


def save_data(data):
    try:
        ensure_data_dir()
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")


def load_phrases():
    default = {
        "hunter_morning": [
            "Вставай, Добытчик. Племя ждёт.",
            "Новый день. Новая охота.",
            "Солнце встало. Пора на охоту."
        ],
        "tribe_fed": [
            "Племя сыто. Ты — молодец.",
            "Еда есть. Племя благодарит.",
            "Добыча принята. Все сыты."
        ],
        "tribe_tried": [
            "Попытка засчитана. +4 часа.",
            "Не вышло, но ты пытался.",
            "Племя видит твои усилия."
        ],
        "tribe_hungry_warning": [
            "Племя голодает. Где еда?",
            "12 часов без добычи. Неси еду!",
            "Люди ждут. Охотник, действуй!"
        ],
        "tribe_riot": [
            "БУНТ! Племя в ярости!",
            "24 часа голода! Люди злятся!",
            "Охотник провалился! БУНТ!"
        ],
        "dopamine_common": [
            "☀️ Момент покоя. Ты справляешься.",
            "🌿 Вдохни. Всё идёт как надо.",
            "💪 Племя сыто. Ты — хороший добытчик."
        ],
        "dopamine_rare": [
            "🌟 Редкая удача! Найден мёд диких пчёл!",
            "🎯 Твой бросок точен. Племя гордится.",
            "🔥 Огонь горит ярко. Всё хорошо."
        ],
        "dopamine_legendary": [
            "⚡ ЛЕГЕНДА! Духи предков улыбаются тебе!",
            "🏆 Великий охотник! Песни сложат о тебе!",
            "✨ Невероятно! Такое бывает раз в жизни!"
        ],
        "goodnight": [
            "Спокойной ночи, охотник."
        ],
        "bot_end": [
            "Сезон охоты окончен. Пора делать нового бота."
        ]
    }
    try:
        if PHRASES_FILE.exists():
            with open(PHRASES_FILE, "r", encoding="utf-8") as f:
                phrases = json.load(f)
                for key, value in default.items():
                    if key not in phrases:
                        phrases[key] = value
                return phrases
        ensure_data_dir()
        with open(PHRASES_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки фраз: {e}")
        return default


def get_phrase(category: str) -> str:
    phrases = load_phrases()
    if category in phrases and phrases[category]:
        return random.choice(phrases[category])
    return "..."


def get_dopamine_phrase() -> str:
    """Получить дофаминовую фразу с учётом редкости"""
    phrases = load_phrases()
    roll = random.randint(1, 100)
    
    # 70% - обычные, 25% - редкие, 5% - легендарные
    if roll <= 70:
        category = "dopamine_common"
    elif roll <= 95:
        category = "dopamine_rare"
    else:
        category = "dopamine_legendary"
    
    if category in phrases and phrases[category]:
        return random.choice(phrases[category])
    return "☀️ Хороший момент."


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def now_msk():
    return datetime.now(TIMEZONE)


def today_str():
    return now_msk().strftime("%Y-%m-%d")


def is_bot_active():
    now = now_msk()
    return BOT_START <= now < BOT_END


def reset_daily_if_needed(data):
    current_date = today_str()
    if data.get("current_date") != current_date:
        data["current_date"] = current_date
        data["morning_done"] = False
        data["hunger_notified"] = False
        data["last_dopamine_hour"] = None
        data["goodnight_sent"] = False
        save_data(data)
    return data


def get_hunger_hours(data) -> float:
    """Сколько часов племя без еды"""
    last_feed_str = data.get("last_feed_time")
    if not last_feed_str:
        return 0
    
    last_feed = datetime.fromisoformat(last_feed_str)
    delta = now_msk() - last_feed
    return delta.total_seconds() / 3600


def get_hunger_mode(data) -> str:
    """Определить режим: good, bad, riot"""
    hours = get_hunger_hours(data)
    if hours < HUNGER_WARNING_HOURS:
        return "good"
    elif hours < HUNGER_RIOT_HOURS:
        return "bad"
    else:
        return "riot"


# ============== ГЛАВНЫЙ ТАЙМЕР ==============
async def main_timer(context: ContextTypes.DEFAULT_TYPE):
    """Срабатывает каждую минуту"""
    if not is_bot_active():
        await check_bot_end(context)
        return
    
    data = load_data()
    user_id = data.get("user_id")
    if not user_id:
        logger.info("⏰ Таймер: нет user_id")
        return
    
    data = reset_daily_if_needed(data)
    now = now_msk()
    current_hour = now.hour
    current_minute = now.minute
    
    logger.info(f"⏰ Таймер сработал: {current_hour}:{current_minute:02d} МСК")
    
    # 1. Утреннее сообщение (после 5:30)
    if current_hour >= WAKEUP_HOUR:
        if current_hour == WAKEUP_HOUR and current_minute < WAKEUP_MINUTE:
            pass  # Ещё рано
        elif not data.get("morning_done"):
            logger.info("📨 Отправляю утренние задачи")
            await send_morning_tasks(context, user_id, data)
            data = load_data()  # Перезагружаем
    
    # 2. Проверка голода
    mode = get_hunger_mode(data)
    logger.info(f"🍖 Режим голода: {mode}")
    
    if mode == "bad":
        # Режим "Нехорошо" — одно уведомление
        if not data.get("hunger_notified"):
            logger.info("⚠️ Отправляю предупреждение о голоде")
            data["hunger_notified"] = True
            save_data(data)
            phrase = get_phrase("tribe_hungry_warning")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🍖⚠️ {phrase}"
            )
    
    elif mode == "riot":
        # Режим "Бунт" — каждые 30 минут
        if current_minute in [0, 30]:
            logger.info("🔥 Отправляю сообщение о бунте")
            phrase = get_phrase("tribe_riot")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔥🔥🔥 {phrase}"
            )
    
    elif mode == "good":
        # Режим "Хорошо" — сбрасываем флаг уведомления
        if data.get("hunger_notified"):
            data["hunger_notified"] = False
            save_data(data)
        
        # Дофаминовый подарок в :55 (с 6:55 до 22:55)
        logger.info(f"🎁 Проверка дофамина: минута={current_minute}, час={current_hour}, last_dopamine_hour={data.get('last_dopamine_hour')}")
        if current_minute == 55:
            logger.info(f"🎁 Минута 55! Проверяю диапазон часов: {DOPAMINE_START_HOUR} <= {current_hour} <= {DOPAMINE_END_HOUR}")
            if DOPAMINE_START_HOUR <= current_hour <= DOPAMINE_END_HOUR:
                logger.info(f"🎁 Час подходит! Проверяю last_dopamine_hour: {data.get('last_dopamine_hour')} != {current_hour}")
                if data.get("last_dopamine_hour") != current_hour:
                    logger.info("🎁✅ ОТПРАВЛЯЮ ДОФАМИНОВУЮ НАГРАДУ!")
                    data["last_dopamine_hour"] = current_hour
                    save_data(data)
                    phrase = get_dopamine_phrase()
                    await context.bot.send_message(chat_id=user_id, text=phrase)
                else:
                    logger.info(f"🎁❌ Уже отправлял в этом часу (last={data.get('last_dopamine_hour')})")
            else:
                logger.info(f"🎁❌ Час не подходит для дофамина")
        else:
            logger.info(f"🎁 Не 55 минута, пропускаю")
    
    # 3. Пожелание сна (23:00, только в режиме "Хорошо")
    if current_hour == SLEEP_HOUR and current_minute == 0:
        if not data.get("goodnight_sent") and mode == "good":
            logger.info("🌙 Отправляю пожелание сна")
            data["goodnight_sent"] = True
            save_data(data)
            await send_goodnight(context, user_id)


# ============== УТРЕННЕЕ СООБЩЕНИЕ ==============
async def send_morning_tasks(context: ContextTypes.DEFAULT_TYPE, user_id: int, data: dict):
    data["morning_done"] = True
    
    # Если первый запуск — устанавливаем время кормления
    if not data.get("last_feed_time"):
        data["last_feed_time"] = now_msk().isoformat()
    
    save_data(data)
    
    # Генерируем 4 шифра: 2G, 1P, 1M
    g1 = f"G{random.randint(1, 20)}"
    g2 = f"G{random.randint(21, 40)}"
    p1 = f"P{random.randint(1, 20)}"
    m1 = f"M{random.randint(1, 20)}"
    
    tasks_list = [g1, g2, p1, m1]
    random.shuffle(tasks_list)
    
    phrase = get_phrase("hunter_morning")
    hours = get_hunger_hours(data)
    time_left = max(0, HUNGER_WARNING_HOURS - hours)
    
    text = f"☀️ {phrase}\n\n"
    text += f"🏹 Твои цели на сегодня:\n"
    for task in tasks_list:
        text += f"• `{task}`\n"
    text += f"\n⏳ До голода: {time_left:.1f} ч."
    
    await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
    logger.info("Утренние задачи выданы")


# ============== ПОЖЕЛАНИЕ СНА ==============
async def send_goodnight(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=NIGHT_IMAGE,
            caption="🌙 " + get_phrase("goodnight")
        )
    except Exception as e:
        logger.error(f"Ошибка отправки картинки: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="🌙 " + get_phrase("goodnight")
        )
    logger.info("Пожелание сна отправлено")


# ============== КОМАНДЫ ==============
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    data["user_id"] = user_id
    data["current_date"] = today_str()
    if not data.get("last_feed_time"):
        data["last_feed_time"] = now_msk().isoformat()
    save_data(data)
    
    if not is_bot_active():
        if now_msk() >= BOT_END:
            await update.message.reply_text(f"🏁 {get_phrase('bot_end')}")
        else:
            await update.message.reply_text("⏳ Бот ещё не запущен.")
        return
    
    hours = get_hunger_hours(data)
    time_left = max(0, HUNGER_WARNING_HOURS - hours)
    
    await update.message.reply_text(
        f"🏹 ДОБЫТЧИК — МЕЗОЛИТ\n\n"
        f"Твоя задача: кормить племя.\n\n"
        f"Команды:\n"
        f"/done или напиши 'сделал' — Принёс добычу (+12ч)\n"
        f"/tried или напиши 'попробовал' — Попытался, отложил (+4ч)\n"
        f"/status — Проверить статус\n\n"
        f"⏳ До голода: {time_left:.1f} ч.\n\n"
        f"Бот работает до 14.02.2026"
    )


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сделал дело — +12 часов сытости"""
    if not is_bot_active():
        await update.message.reply_text("Бот неактивен.")
        return
    
    data = load_data()
    
    # Добавляем 12 часов к текущему времени
    data["last_feed_time"] = now_msk().isoformat()
    data["hunger_notified"] = False
    save_data(data)
    
    phrase = get_phrase("tribe_fed")
    
    await update.message.reply_text(
        f"✅ {phrase}\n\n"
        f"🍖 +12 часов сытости\n"
        f"⏳ До голода: 12.0 ч."
    )


async def cmd_tried(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Попробовал, но отложил — +4 часа сытости"""
    if not is_bot_active():
        await update.message.reply_text("Бот неактивен.")
        return
    
    data = load_data()
    
    # ПРАВИЛЬНАЯ ЛОГИКА: уменьшаем текущий голод на 4 часа
    # Если племя было голодно 2 часа, после /tried будет "голодно" -2 часа (т.е. в кредите!)
    current_hunger_hours = get_hunger_hours(data)
    new_hunger_hours = current_hunger_hours - 4  # Может быть отрицательным!
    
    # Устанавливаем время последнего кормления
    # Если new_hunger_hours отрицательный, то last_feed_time окажется в будущем (кредит)
    new_feed_time = now_msk() - timedelta(hours=new_hunger_hours)
    
    data["last_feed_time"] = new_feed_time.isoformat()
    data["hunger_notified"] = False
    save_data(data)
    
    # Пересчитываем после сохранения
    hours = get_hunger_hours(data)
    time_left = max(0, HUNGER_WARNING_HOURS - hours)
    
    phrase = get_phrase("tribe_tried")
    
    await update.message.reply_text(
        f"🔄 {phrase}\n\n"
        f"🍖 +4 часа сытости\n"
        f"⏳ До голода: {time_left:.1f} ч."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    data = reset_daily_if_needed(data)
    
    hours = get_hunger_hours(data)
    mode = get_hunger_mode(data)
    
    if mode == "good":
        time_left = HUNGER_WARNING_HOURS - hours
        status_text = f"✅ Племя сыто\n⏳ До голода: {time_left:.1f} ч."
        status_emoji = "😊"
    elif mode == "bad":
        time_left = HUNGER_RIOT_HOURS - hours
        status_text = f"⚠️ Племя голодает!\n⏳ До бунта: {time_left:.1f} ч."
        status_emoji = "😟"
    else:
        overtime = hours - HUNGER_RIOT_HOURS
        status_text = f"🔥 БУНТ! Голод {overtime:.1f} ч. сверх нормы!"
        status_emoji = "😡"
    
    await update.message.reply_text(
        f"📊 СТАТУС ДОБЫТЧИКА {status_emoji}\n\n"
        f"🍖 Без еды: {hours:.1f} ч.\n"
        f"{status_text}\n\n"
        f"Команды:\n"
        f"/done или 'сделал' — Принёс добычу (+12ч)\n"
        f"/tried или 'попробовал' — Попытался (+4ч)"
    )


async def cmd_test_dopamine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ДИАГНОСТИКА: Проверка дофаминовой системы"""
    data = load_data()
    now = now_msk()
    current_hour = now.hour
    current_minute = now.minute
    mode = get_hunger_mode(data)
    
    # Информация о состоянии
    info = f"🔍 ДИАГНОСТИКА ДОФАМИНА\n\n"
    info += f"⏰ Текущее время: {now.strftime('%H:%M:%S')} МСК\n"
    info += f"📅 Дата: {now.strftime('%Y-%m-%d')}\n"
    info += f"🕐 Час: {current_hour}\n"
    info += f"🕐 Минута: {current_minute}\n\n"
    info += f"🍖 Режим: {mode}\n"
    info += f"🎁 last_dopamine_hour: {data.get('last_dopamine_hour')}\n\n"
    info += f"📋 Диапазон дофамина: {DOPAMINE_START_HOUR}:55 - {DOPAMINE_END_HOUR}:55\n"
    info += f"✅ Бот активен: {is_bot_active()}\n\n"
    
    # Проверки
    if mode != "good":
        info += f"❌ Режим не 'good' (текущий: {mode})\n"
    else:
        info += f"✅ Режим 'good'\n"
    
    if not (DOPAMINE_START_HOUR <= current_hour <= DOPAMINE_END_HOUR):
        info += f"❌ Час {current_hour} вне диапазона {DOPAMINE_START_HOUR}-{DOPAMINE_END_HOUR}\n"
    else:
        info += f"✅ Час {current_hour} в диапазоне\n"
    
    if data.get("last_dopamine_hour") == current_hour:
        info += f"⚠️ Дофамин уже отправлялся в этом часу\n"
    else:
        info += f"✅ Можно отправить дофамин\n"
    
    await update.message.reply_text(info)
    
    # Принудительно отправляем награду для теста
    logger.info("🧪 TEST: Принудительная отправка дофамина")
    phrase = get_dopamine_phrase()
    await update.message.reply_text(f"🧪 ТЕСТ:\n{phrase}")
    
    # Сбрасываем last_dopamine_hour для повторного теста
    data["last_dopamine_hour"] = None
    save_data(data)


# ============== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ==============
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения для русских команд"""
    text = update.message.text.lower().strip()
    
    # Проверяем на русские команды
    if "сделал" in text or "сделала" in text:
        await cmd_done(update, context)
    elif "попробовал" in text or "попробовала" in text:
        await cmd_tried(update, context)
    # Можно добавить другие варианты:
    # elif "статус" in text:
    #     await cmd_status(update, context)


# ============== ПРОВЕРКА ОКОНЧАНИЯ ==============
async def check_bot_end(context: ContextTypes.DEFAULT_TYPE):
    if now_msk() >= BOT_END:
        data = load_data()
        user_id = data.get("user_id")
        if user_id:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🏁 {get_phrase('bot_end')}"
            )


# ============== MAIN ==============
def main():
    ensure_data_dir()
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды на английском
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("tried", cmd_tried))
    app.add_handler(CommandHandler("test_dopamine", cmd_test_dopamine))  # Диагностика
    
    # Обработчик текстовых сообщений для русских команд
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_text
    ))
    
    # Главный таймер — каждую минуту
    app.job_queue.run_repeating(main_timer, interval=60, first=10)
    
    logger.info("Бот Добытчик v4.3 запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
