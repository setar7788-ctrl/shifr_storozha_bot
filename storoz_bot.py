# -*- coding: utf-8 -*-
"""
Бот «Стоянка» (Мезолит)
Жёсткий дисциплинарный бот: ты живёшь только если приносишь пользу.
Период работы: с 17.01.2026 16:00 до 14.02.2026 00:00
"""

import os
import json
import random
import logging
from datetime import datetime, timedelta, time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import pytz

# ============== НАСТРОЙКИ ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_DIR = Path("/app/data")
TIMEZONE = pytz.timezone("Europe/Moscow")

# Период работы бота
BOT_START = datetime(2026, 1, 17, 16, 0, tzinfo=TIMEZONE)
BOT_END = datetime(2026, 2, 14, 0, 0, tzinfo=TIMEZONE)

# Расписание дня
WAKEUP_TIME = time(5, 30)
SLEEP_TIME = time(23, 30)

# Расписание бонусов: (час, минута, название, цена, сообщение_если_нет)
BONUS_SCHEDULE = [
    (7, 0, "breakfast_sweet", 2, "Завтрак без вкусняшки"),
    (9, 0, "coffee", 2, "Кофе запрещён до 10:00"),
    (12, 0, "lunch_sweet", 2, "Обед без вкусняшки"),
    (15, 0, "snack_1", 2, "Вкусняшка запрещена"),
    (18, 0, "dinner_sweet", 2, "Ужин без вкусняшки"),
    (21, 0, "snack_2", 2, "Вкусняшка запрещена"),
    (23, 30, "bed", 3, "Сон на коврике"),
]

# Пути к файлам
DATA_FILE = DATA_DIR / "stoyanka_data.json"
PHRASES_FILE = DATA_DIR / "phrases.json"

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============== РАБОТА С ДАННЫМИ ==============
def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_data():
    """Загрузить данные бота"""
    default = {
        "user_id": None,
        "zubiki": 0,
        "cold": 0,
        "today_bonuses_denied": [],  # бонусы, отказанные сегодня (для эскалации)
        "today_bonuses_blocked": [],  # бонусы, заблокированные до конца дня
        "last_hour_check": None,  # последняя проверка часа
        "waiting_for_benefit": False,  # ждём ответа о пользе
        "current_date": None,  # текущая дата для сброса
    }
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Добавляем недостающие поля
                for key, value in default.items():
                    if key not in data:
                        data[key] = value
                return data
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        return default


def save_data(data):
    """Сохранить данные"""
    try:
        ensure_data_dir()
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")


def load_phrases():
    """Загрузить фразы"""
    default = {
        "hour_success": [
            "Тебя заметили. Пока живёшь.",
            "Польза есть. Стоянка терпит.",
            "Час не пустой. Можешь остаться.",
            "Работа видна. Пока не гонят."
        ],
        "hour_fail": [
            "Час пустой. Стоянка не платит за воздух.",
            "Ты здесь зря.",
            "Пустота. Зубиков нет.",
            "Без пользы — без еды. Логично."
        ],
        "cold_warning": [
            "Холод растёт. Ещё один пустой час — штраф.",
            "Два часа без пользы. Стоянка злится.",
            "Ты остываешь. Это плохо."
        ],
        "cold_penalty": [
            "Штраф. -1 зубик. Стоянка не терпит бездельников.",
            "Слишком долго без пользы. -1 зубик.",
            "Холод достиг предела. Плати."
        ],
        "bonus_allowed": [
            "Зубиков хватает. Разрешено.",
            "Заработал — получи.",
            "Польза была — комфорт разрешён."
        ],
        "bonus_denied": [
            "Зубиков мало. Не заслужил.",
            "Хочешь комфорт — покажи пользу.",
            "Нет зубиков — нет бонуса. Просто."
        ],
        "bonus_blocked": [
            "Второй отказ. Бонус заблокирован до завтра.",
            "Ты дважды не заработал. Заблокировано.",
            "Эскалация. До конца дня — без этого."
        ],
        "done_task": [
            "Дело сделано. +1 зубик.",
            "Принято. Зубик начислен.",
            "Работа есть. +1."
        ],
        "morning_tasks_yes": [
            "Хорошо. Работай.",
            "Задачи есть. Вперёд.",
            "Не трать время на разговоры. Делай."
        ],
        "morning_tasks_no": [
            "Нет задач? Вот тебе шифры. Сам разберёшься.",
            "Без плана? Держи коды. Расшифруй сам.",
            "Лентяй без списка. Вот шифры:"
        ],
        "sleep_bed": [
            "Кровать разрешена. Спи.",
            "Заработал комфорт. Отдыхай.",
            "Зубиков хватило. Кровать твоя."
        ],
        "sleep_floor": [
            "Зубиков мало. Коврик.",
            "Не заработал кровать. Пол.",
            "Комфорт не для тебя сегодня. Коврик."
        ],
        "identity": [
            "Ты не герой. Ты пришлый. Сначала работа.",
            "Ты никто. Докажи обратное.",
            "Пришлый у стоянки. Помни своё место."
        ],
        "benefit_question": [
            "Была польза за последний час?",
            "Час прошёл. Польза была?",
            "Отчитайся. Был толк?"
        ],
        "no_answer_penalty": [
            "Молчание = нет пользы.",
            "Не ответил — значит бездельничал.",
            "Тишина. Засчитано как ноль."
        ],
        "bot_end": [
            "Срок вышел. Стоянка закрыта. Пора делать нового бота.",
            "14 февраля. Конец эксперимента. Создавай новый порядок.",
            "Время Мезолита закончилось. Что дальше — решать тебе."
        ]
    }
    try:
        if PHRASES_FILE.exists():
            with open(PHRASES_FILE, "r", encoding="utf-8") as f:
                phrases = json.load(f)
                # Добавляем недостающие категории
                for key, value in default.items():
                    if key not in phrases:
                        phrases[key] = value
                return phrases
        # Создаём файл с дефолтными фразами
        ensure_data_dir()
        with open(PHRASES_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки фраз: {e}")
        return default


def get_phrase(category: str) -> str:
    """Получить случайную фразу из категории"""
    phrases = load_phrases()
    if category in phrases and phrases[category]:
        return random.choice(phrases[category])
    return "..."


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def now_msk():
    """Текущее время по Москве"""
    return datetime.now(TIMEZONE)


def today_str():
    """Сегодняшняя дата строкой"""
    return now_msk().strftime("%Y-%m-%d")


def is_bot_active():
    """Проверить, активен ли бот (в пределах периода работы)"""
    now = now_msk()
    return BOT_START <= now < BOT_END


def is_working_hours():
    """Проверить рабочие часы (5:30 - 23:30)"""
    now = now_msk()
    current_time = now.time()
    return WAKEUP_TIME <= current_time <= SLEEP_TIME


def reset_daily_if_needed(data):
    """Сбросить дневные данные если новый день"""
    current_date = today_str()
    if data.get("current_date") != current_date:
        data["current_date"] = current_date
        data["today_bonuses_denied"] = []
        data["today_bonuses_blocked"] = []
        data["cold"] = 0  # Сбрасываем холод на новый день
        save_data(data)
    return data


# ============== УТРЕННИЙ ПРОТОКОЛ ==============
async def send_morning_message(context: ContextTypes.DEFAULT_TYPE):
    """Утреннее сообщение в 5:30"""
    if not is_bot_active():
        await check_bot_end(context)
        return
    
    data = load_data()
    user_id = data.get("user_id")
    if not user_id:
        return
    
    data = reset_daily_if_needed(data)
    
    # Статус
    zubiki = data.get("zubiki", 0)
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, есть задачи", callback_data="morning_yes")],
        [InlineKeyboardButton("❌ Нет задач", callback_data="morning_no")]
    ]
    
    text = f"☀️ Подъём, Пришлый.\n\n"
    text += f"💀 Зубики: {zubiki}\n"
    text += f"❄️ Холод: 0\n\n"
    text += f"Есть ли у тебя минимум 3 задачи в задачнике?"
    
    await context.bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_morning_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на утренний вопрос"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "morning_yes":
        phrase = get_phrase("morning_tasks_yes")
        await query.edit_message_text(f"✅ {phrase}")
        
    elif query.data == "morning_no":
        # Генерируем шифры
        p = f"P{random.randint(1, 20)}"
        m = f"M{random.randint(1, 20)}"
        g = f"G{random.randint(1, 20)}"
        
        phrase = get_phrase("morning_tasks_no")
        await query.edit_message_text(f"❌ {phrase}\n\n🔢 Шифры:\n• {p}\n• {m}\n• {g}\n\nРасшифруй сам.")
    
    # Запускаем первую проверку пользы через расчётное время
    schedule_next_benefit_check(context)


# ============== ПОЧАСОВАЯ ПРОВЕРКА ПОЛЬЗЫ ==============
def schedule_next_benefit_check(context: ContextTypes.DEFAULT_TYPE):
    """Запланировать следующую проверку пользы"""
    # Удаляем старые джобы
    for job in context.job_queue.get_jobs_by_name("benefit_check"):
        job.schedule_removal()
    for job in context.job_queue.get_jobs_by_name("benefit_timeout"):
        job.schedule_removal()
    
    if not is_bot_active():
        return
    
    now = now_msk()
    current_time = now.time()
    
    # Определяем следующий час проверки
    # Проверки идут: 5:30, 6:30, 7:30, ... 22:30, 23:30
    if current_time < WAKEUP_TIME:
        # До подъёма — ждём 5:30
        next_check = now.replace(hour=5, minute=30, second=0, microsecond=0)
    elif current_time >= SLEEP_TIME:
        # После отбоя — ждём завтрашнего утра
        tomorrow = now + timedelta(days=1)
        next_check = tomorrow.replace(hour=5, minute=30, second=0, microsecond=0)
    else:
        # В рабочее время — следующий :30
        if current_time.minute < 30:
            next_check = now.replace(minute=30, second=0, microsecond=0)
        else:
            next_hour = now + timedelta(hours=1)
            next_check = next_hour.replace(minute=30, second=0, microsecond=0)
        
        # Проверяем что не вышли за 23:30
        if next_check.time() > SLEEP_TIME:
            tomorrow = now + timedelta(days=1)
            next_check = tomorrow.replace(hour=5, minute=30, second=0, microsecond=0)
    
    delay = (next_check - now).total_seconds()
    if delay < 0:
        delay = 60  # Минимум минута
    
    data = load_data()
    user_id = data.get("user_id")
    if user_id:
        context.job_queue.run_once(
            send_benefit_check,
            when=delay,
            name="benefit_check",
            data={"user_id": user_id}
        )
        logger.info(f"Следующая проверка пользы через {int(delay/60)} мин")


async def send_benefit_check(context: ContextTypes.DEFAULT_TYPE):
    """Отправить вопрос о пользе"""
    if not is_bot_active():
        await check_bot_end(context)
        return
    
    if not is_working_hours():
        schedule_next_benefit_check(context)
        return
    
    job = context.job
    user_id = job.data.get("user_id")
    
    data = load_data()
    data = reset_daily_if_needed(data)
    data["waiting_for_benefit"] = True
    data["last_hour_check"] = now_msk().isoformat()
    save_data(data)
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, была польза", callback_data="benefit_yes")],
        [InlineKeyboardButton("❌ Нет, пользы не было", callback_data="benefit_no")]
    ]
    
    phrase = get_phrase("benefit_question")
    zubiki = data.get("zubiki", 0)
    cold = data.get("cold", 0)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"⏰ {phrase}\n\n💀 Зубики: {zubiki} | ❄️ Холод: {cold}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Таймаут на ответ — 1 час
    context.job_queue.run_once(
        benefit_timeout,
        when=timedelta(hours=1),
        name="benefit_timeout",
        data={"user_id": user_id}
    )


async def benefit_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Таймаут — пользователь не ответил"""
    job = context.job
    user_id = job.data.get("user_id")
    
    data = load_data()
    if not data.get("waiting_for_benefit"):
        return  # Уже ответил
    
    # Засчитываем как "нет"
    data["waiting_for_benefit"] = False
    cold = data.get("cold", 0) + 1
    data["cold"] = cold
    
    phrase = get_phrase("no_answer_penalty")
    response = f"⏰ {phrase}"
    
    # Проверяем штраф за холод
    if cold >= 2:
        zubiki = data.get("zubiki", 0)
        new_zubiki = max(0, zubiki - 1)
        data["zubiki"] = new_zubiki
        penalty_phrase = get_phrase("cold_penalty")
        response += f"\n\n❄️ {penalty_phrase}\n💀 Зубики: {new_zubiki}"
    else:
        response += f"\n❄️ Холод: {cold}/2"
    
    save_data(data)
    await context.bot.send_message(chat_id=user_id, text=response)
    
    schedule_next_benefit_check(context)


async def handle_benefit_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа о пользе"""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    if not data.get("waiting_for_benefit"):
        await query.edit_message_text("⏰ Время ответа истекло.")
        return
    
    # Отменяем таймаут
    for job in context.job_queue.get_jobs_by_name("benefit_timeout"):
        job.schedule_removal()
    
    data["waiting_for_benefit"] = False
    
    if query.data == "benefit_yes":
        # +1 зубик, сброс холода
        zubiki = data.get("zubiki", 0) + 1
        data["zubiki"] = zubiki
        data["cold"] = 0
        save_data(data)
        
        phrase = get_phrase("hour_success")
        await query.edit_message_text(f"✅ {phrase}\n\n💀 +1 зубик. Всего: {zubiki}")
        
    elif query.data == "benefit_no":
        # Увеличиваем холод
        cold = data.get("cold", 0) + 1
        data["cold"] = cold
        
        phrase = get_phrase("hour_fail")
        response = f"❌ {phrase}\n\n❄️ Холод: {cold}/2"
        
        # Штраф за холод >= 2
        if cold >= 2:
            zubiki = data.get("zubiki", 0)
            new_zubiki = max(0, zubiki - 1)
            data["zubiki"] = new_zubiki
            penalty_phrase = get_phrase("cold_penalty")
            response += f"\n\n💀 {penalty_phrase}\nЗубики: {new_zubiki}"
        
        save_data(data)
        await query.edit_message_text(response)
    
    schedule_next_benefit_check(context)


# ============== БОНУСЫ ==============
async def check_bonus(context: ContextTypes.DEFAULT_TYPE):
    """Проверка бонуса по расписанию"""
    if not is_bot_active():
        return
    
    job = context.job
    bonus_name = job.data.get("bonus_name")
    price = job.data.get("price")
    deny_message = job.data.get("deny_message")
    user_id = job.data.get("user_id")
    
    data = load_data()
    data = reset_daily_if_needed(data)
    zubiki = data.get("zubiki", 0)
    blocked = data.get("today_bonuses_blocked", [])
    denied = data.get("today_bonuses_denied", [])
    
    # Проверяем блокировку
    if bonus_name in blocked:
        phrase = get_phrase("bonus_blocked")
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🚫 {bonus_name.upper()}: Заблокировано до завтра."
        )
        return
    
    # Проверяем зубики
    if zubiki >= price:
        # Списываем и разрешаем
        data["zubiki"] = zubiki - price
        save_data(data)
        
        phrase = get_phrase("bonus_allowed")
        bonus_text = get_bonus_text(bonus_name)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ {bonus_text}: {phrase}\n💀 -{price} зубиков. Осталось: {data['zubiki']}"
        )
    else:
        # Отказ
        if bonus_name in denied:
            # Второй отказ — блокировка
            blocked.append(bonus_name)
            data["today_bonuses_blocked"] = blocked
            save_data(data)
            
            phrase = get_phrase("bonus_blocked")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🚫 {deny_message}\n\n❄️ {phrase}"
            )
        else:
            # Первый отказ
            denied.append(bonus_name)
            data["today_bonuses_denied"] = denied
            save_data(data)
            
            phrase = get_phrase("bonus_denied")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ {deny_message}\n\n💀 {phrase} (нужно {price}, есть {zubiki})"
            )


def get_bonus_text(bonus_name: str) -> str:
    """Человекочитаемое название бонуса"""
    names = {
        "breakfast_sweet": "🍬 Вкусняшка к завтраку",
        "coffee": "☕ Кофе",
        "lunch_sweet": "🍬 Вкусняшка к обеду",
        "snack_1": "🍬 Вкусняшка (15:00)",
        "dinner_sweet": "🍬 Вкусняшка к ужину",
        "snack_2": "🍬 Вкусняшка (21:00)",
        "bed": "🛏 Кровать",
    }
    return names.get(bonus_name, bonus_name)


def schedule_bonuses(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Запланировать все бонусы на сегодня"""
    # Удаляем старые
    for job in context.job_queue.get_jobs_by_name("bonus"):
        job.schedule_removal()
    
    now = now_msk()
    today = now.date()
    
    for hour, minute, name, price, deny_msg in BONUS_SCHEDULE:
        bonus_time = datetime.combine(today, time(hour, minute), tzinfo=TIMEZONE)
        
        # Если время уже прошло сегодня — пропускаем
        if bonus_time <= now:
            continue
        
        delay = (bonus_time - now).total_seconds()
        
        context.job_queue.run_once(
            check_bonus,
            when=delay,
            name="bonus",
            data={
                "bonus_name": name,
                "price": price,
                "deny_message": deny_msg,
                "user_id": user_id
            }
        )
    
    logger.info("Бонусы запланированы")


# ============== КОМАНДА /done ==============
async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отметить выполненное дело"""
    if not is_bot_active():
        await update.message.reply_text("Бот неактивен.")
        return
    
    data = load_data()
    zubiki = data.get("zubiki", 0) + 1
    data["zubiki"] = zubiki
    save_data(data)
    
    phrase = get_phrase("done_task")
    await update.message.reply_text(f"✅ {phrase}\n💀 Всего зубиков: {zubiki}")


# ============== КОМАНДА /status ==============
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус"""
    data = load_data()
    data = reset_daily_if_needed(data)
    
    zubiki = data.get("zubiki", 0)
    cold = data.get("cold", 0)
    blocked = data.get("today_bonuses_blocked", [])
    
    # Оставшиеся бонусы на сегодня
    now = now_msk()
    remaining_bonuses = []
    for hour, minute, name, price, _ in BONUS_SCHEDULE:
        bonus_time = time(hour, minute)
        if now.time() < bonus_time and name not in blocked:
            remaining_bonuses.append(f"  {get_bonus_text(name)}: {price} зуб.")
    
    text = f"📊 СТАТУС ПРИШЛОГО\n\n"
    text += f"🏛 Эра: Мезолит\n"
    text += f"👤 Ранг: Пришлый у стоянки\n\n"
    text += f"💀 Зубики: {zubiki}\n"
    text += f"❄️ Холод: {cold}/2\n\n"
    
    if blocked:
        text += f"🚫 Заблокировано сегодня:\n"
        for b in blocked:
            text += f"  • {get_bonus_text(b)}\n"
        text += "\n"
    
    if remaining_bonuses:
        text += f"📅 Предстоящие бонусы:\n"
        text += "\n".join(remaining_bonuses)
    else:
        text += "📅 Все бонусы на сегодня прошли."
    
    phrase = get_phrase("identity")
    text += f"\n\n💬 {phrase}"
    
    await update.message.reply_text(text)


# ============== КОМАНДА /start ==============
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск бота"""
    user_id = update.effective_user.id
    
    data = load_data()
    data["user_id"] = user_id
    data["current_date"] = today_str()
    save_data(data)
    
    if not is_bot_active():
        if now_msk() >= BOT_END:
            phrase = get_phrase("bot_end")
            await update.message.reply_text(f"🏁 {phrase}")
        else:
            await update.message.reply_text("⏳ Бот ещё не запущен. Старт: 17.01.2026 в 16:00")
        return
    
    phrase = get_phrase("identity")
    
    await update.message.reply_text(
        f"🏕 СТОЯНКА — МЕЗОЛИТ\n\n"
        f"Ты — Пришлый. Тебя терпят, пока есть польза.\n\n"
        f"💀 Зубики: 0\n"
        f"❄️ Холод: 0\n\n"
        f"Команды:\n"
        f"/status — статус\n"
        f"/done — отметить дело (+1 зубик)\n\n"
        f"💬 {phrase}\n\n"
        f"Бот работает до 14.02.2026"
    )
    
    # Запускаем расписание
    schedule_daily_jobs(context)
    schedule_bonuses(context, user_id)
    schedule_next_benefit_check(context)


# ============== ПРОВЕРКА ОКОНЧАНИЯ ==============
async def check_bot_end(context: ContextTypes.DEFAULT_TYPE):
    """Проверить окончание работы бота"""
    if now_msk() >= BOT_END:
        data = load_data()
        user_id = data.get("user_id")
        if user_id:
            phrase = get_phrase("bot_end")
            zubiki = data.get("zubiki", 0)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🏁 {phrase}\n\n📊 Итого заработано: {zubiki} зубиков"
            )
        
        # Останавливаем все джобы
        for job in context.job_queue.jobs():
            job.schedule_removal()


# ============== ПЛАНИРОВЩИК ==============
def schedule_daily_jobs(context: ContextTypes.DEFAULT_TYPE):
    """Запланировать ежедневные джобы"""
    # Удаляем старые
    for name in ["morning", "check_end"]:
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    
    # Утреннее сообщение в 5:30
    context.job_queue.run_daily(
        send_morning_message,
        time=WAKEUP_TIME,
        name="morning"
    )
    
    # Проверка окончания каждый час
    context.job_queue.run_repeating(
        check_bot_end,
        interval=timedelta(hours=1),
        first=timedelta(minutes=1),
        name="check_end"
    )
    
    logger.info("Ежедневные джобы запланированы")


# ============== MAIN ==============
def main():
    ensure_data_dir()
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("done", cmd_done))
    
    app.add_handler(CallbackQueryHandler(handle_morning_response, pattern="^morning_"))
    app.add_handler(CallbackQueryHandler(handle_benefit_response, pattern="^benefit_"))
    
    logger.info("Бот Стоянка запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
