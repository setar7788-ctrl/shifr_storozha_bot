# -*- coding: utf-8 -*-
"""
Охотник-Менеджер Telegram Bot
Часть 1: Импорты и вспомогательные функции
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

# Пути к файлам данных
TASKS_FILE = DATA_DIR / "tasks.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
DAILY_FILE = DATA_DIR / "daily.json"
CHECKINS_FILE = DATA_DIR / "checkins.json"
REWARDS_FILE = DATA_DIR / "rewards.json"
ANIMALS_FILE = DATA_DIR / "animals.json"
PHRASES_MOTIVATION_FILE = DATA_DIR / "phrases_motivation.json"
PHRASES_KICK_FILE = DATA_DIR / "phrases_kick.json"

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============== РАБОТА С JSON ==============
def ensure_data_dir():
    """Создать папку data если не существует"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(filepath: Path, default=None):
    """Загрузить JSON файл"""
    if default is None:
        default = {}
    try:
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки {filepath}: {e}")
        return default


def save_json(filepath: Path, data):
    """Сохранить данные в JSON файл"""
    try:
        ensure_data_dir()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения {filepath}: {e}")
        return False


# ============== ЗАГРУЗКА ДАННЫХ ==============
def load_settings():
    """Загрузить настройки"""
    return load_json(SETTINGS_FILE, {
        "user_id": None,
        "timezone": "Europe/Moscow",
        "weekday_wakeup": "06:00",
        "weekend_wakeup": "08:00",
        "workday_end": "22:30",
        "score_summary_time": "23:00",
        "checkin_interval_minutes": 45,
        "weekday_tasks_count": 4,
        "weekend_tasks_count": 8,
        "rank_name": "Молодой охотник",
        "rank_image_file_id": None,
        "night_image_file_id": None,
        "quarter_goals_text": "",
        "reward_high_threshold": 32,
        "reward_mid_threshold": 19,
        "loot_thresholds": {
            "lemming_max": 14,
            "hare_max": 27,
            "deer_max": 36,
            "muskox_max": 44
        }
    })


def load_tasks():
    """Загрузить все задачи"""
    return load_json(TASKS_FILE, [])


def load_daily():
    """Загрузить дневные планы"""
    return load_json(DAILY_FILE, {})


def load_checkins():
    """Загрузить чек-ины"""
    return load_json(CHECKINS_FILE, {})


def load_rewards():
    """Загрузить награды"""
    return load_json(REWARDS_FILE, [])


def load_animals():
    """Загрузить животных"""
    return load_json(ANIMALS_FILE, [])


def load_phrases_motivation():
    """Загрузить мотивационные фразы"""
    return load_json(PHRASES_MOTIVATION_FILE, [])


def load_phrases_kick():
    """Загрузить язвительные фразы"""
    return load_json(PHRASES_KICK_FILE, [])


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def get_today_str():
    """Получить сегодняшнюю дату в формате YYYY-MM-DD"""
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def get_yesterday_str():
    """Получить вчерашнюю дату"""
    yesterday = datetime.now(TIMEZONE) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def is_weekend():
    """Проверить, выходной ли сегодня (Сб=5, Вс=6)"""
    return datetime.now(TIMEZONE).weekday() >= 5


def get_tasks_count_today():
    """Получить количество задач на сегодня"""
    settings = load_settings()
    if is_weekend():
        return settings.get("weekend_tasks_count", 8)
    return settings.get("weekday_tasks_count", 4)


def get_wakeup_time():
    """Получить время подъёма на сегодня"""
    settings = load_settings()
    if is_weekend():
        time_str = settings.get("weekend_wakeup", "08:00")
    else:
        time_str = settings.get("weekday_wakeup", "06:00")
    h, m = map(int, time_str.split(":"))
    return time(hour=h, minute=m)


def parse_time(time_str):
    """Парсить время из строки HH:MM"""
    h, m = map(int, time_str.split(":"))
    return time(hour=h, minute=m)


def get_random_motivation():
    """Случайная мотивационная фраза"""
    phrases = load_phrases_motivation()
    return random.choice(phrases) if phrases else "Отлично!"


def get_random_kick():
    """Случайная язвительная фраза"""
    phrases = load_phrases_kick()
    return random.choice(phrases) if phrases else "Соберись."



async def send_morning_message(context: ContextTypes.DEFAULT_TYPE):
    """Отправить утреннее сообщение с выбором роли"""
    settings = load_settings()
    user_id = settings.get("user_id")
    
    if not user_id:
        logger.warning("user_id не установлен, утреннее сообщение не отправлено")
        return
    
    rank_name = settings.get("rank_name", "Молодой охотник")
    rank_image = settings.get("rank_image_file_id")
    goals = settings.get("quarter_goals_text", "Цели не установлены")
    
    # Текст приветствия
    greeting = f"☀️ *Доброе утро, охотник!*\nТвой ранг: *{rank_name}*"
    
    # Отправляем картинку ранга если есть
    if rank_image:
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=rank_image,
                caption=greeting,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки картинки ранга: {e}")
            await context.bot.send_message(chat_id=user_id, text=greeting, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=user_id, text=greeting, parse_mode="Markdown")
    
    # Отправляем квартальные цели
    goals_text = f"🏹 *КАРТА ОХОТЫ НА КВАРТАЛ:*\n\n{goals}"
    await context.bot.send_message(chat_id=user_id, text=goals_text, parse_mode="Markdown")
    
    # Кнопки выбора роли
    keyboard = [
        [InlineKeyboardButton("💰 Мультимиллионер", callback_data="role_multimillionaire")],
        [InlineKeyboardButton("🛡 Герой", callback_data="role_hero")],
        [InlineKeyboardButton("🧡 Добрый папа", callback_data="role_papa")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text="*Кем ты будешь сегодня?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ============== ВЫБОР РОЛИ И ФОРМИРОВАНИЕ ПЛАНА ==============
async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора роли дня"""
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("role_"):
        return
    
    role = query.data.replace("role_", "")
    role_names = {
        "multimillionaire": "💰 Мультимиллионер",
        "hero": "🛡 Герой",
        "papa": "🧡 Добрый папа"
    }
    
    await query.edit_message_text(f"Сегодня ты — *{role_names.get(role, role)}*", parse_mode="Markdown")
    
    # Формируем план на день
    tasks_for_today = generate_daily_plan(role)
    
    # Сохраняем в daily.json
    daily = load_daily()
    today = get_today_str()
    
    # Проверяем перенос с вчера
    yesterday = get_yesterday_str()
    carried_over = False
    if yesterday in daily and daily[yesterday].get("reward_sacrificed"):
        carried_over = True
    
    daily[today] = {
        "role_of_day": role,
        "tasks": [t["id"] for t in tasks_for_today],
        "completed_tasks": [],
        "carry_over_tasks": [],
        "reward_sacrificed": False,
        "carried_over_from_yesterday": carried_over,
        "done_task_count": 0
    }
    save_json(DAILY_FILE, daily)
    
    # Отправляем план
    tasks_text = "🎯 *Твой план охотника на сегодня:*\n\n"
    for i, task in enumerate(tasks_for_today, 1):
        tasks_text += f"{i}) {task['text']}\n"
    
    tasks_text += "\n_Охота началась! Первый чек-ин через 45 минут._"
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=tasks_text,
        parse_mode="Markdown"
    )
    
    # Запускаем пинги
    schedule_checkins(context, query.message.chat_id)


def generate_daily_plan(role_of_day: str) -> list:
    """Сформировать план задач на день"""
    tasks = load_tasks()
    daily = load_daily()
    settings = load_settings()
    
    # Базовое количество задач
    base_count = get_tasks_count_today()
    
    # Проверяем перенесённые задачи со вчера
    yesterday = get_yesterday_str()
    carried_tasks = []
    
    if yesterday in daily:
        yesterday_data = daily[yesterday]
        if yesterday_data.get("reward_sacrificed") and yesterday_data.get("carry_over_tasks"):
            carry_ids = yesterday_data["carry_over_tasks"]
            carried_tasks = [t for t in tasks if t["id"] in carry_ids and not t["is_done"]]
            # Уменьшаем количество задач на 1 если есть перенос
            if carried_tasks:
                base_count = max(1, base_count - 1)
    
    # Незавершённые задачи по категориям
    available = {
        "multimillionaire": [t for t in tasks if t["category"] == "multimillionaire" and not t["is_done"]],
        "hero": [t for t in tasks if t["category"] == "hero" and not t["is_done"]],
        "papa": [t for t in tasks if t["category"] == "papa" and not t["is_done"]]
    }
    
    # Убираем перенесённые из доступных
    carried_ids = [t["id"] for t in carried_tasks]
    for cat in available:
        available[cat] = [t for t in available[cat] if t["id"] not in carried_ids]
    
    # Сортируем по times_given (меньше = приоритетнее)
    for cat in available:
        available[cat].sort(key=lambda x: x["times_given"])
    
    selected = list(carried_tasks)  # Начинаем с перенесённых
    selected_ids = set(carried_ids)
    
    # Добираем до нужного количества
    remaining = base_count - len(selected)
    
    # Сначала по одной из каждой категории (кроме уже добавленных)
    categories = ["multimillionaire", "hero", "papa"]
    for cat in categories:
        if remaining <= 0:
            break
        for task in available[cat]:
            if task["id"] not in selected_ids:
                selected.append(task)
                selected_ids.add(task["id"])
                remaining -= 1
                break
    
    # Остальные из роли дня
    if remaining > 0 and role_of_day in available:
        for task in available[role_of_day]:
            if remaining <= 0:
                break
            if task["id"] not in selected_ids:
                selected.append(task)
                selected_ids.add(task["id"])
                remaining -= 1
    
    # Если всё ещё не хватает — берём из любых категорий
    if remaining > 0:
        all_available = [t for t in tasks if not t["is_done"] and t["id"] not in selected_ids]
        all_available.sort(key=lambda x: x["times_given"])
        for task in all_available:
            if remaining <= 0:
                break
            selected.append(task)
            selected_ids.add(task["id"])
            remaining -= 1
    
    return selected



def schedule_checkins(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Запланировать пинги каждые 45 минут"""
    settings = load_settings()
    interval = settings.get("checkin_interval_minutes", 45)
    workday_end = parse_time(settings.get("workday_end", "22:30"))
    
    # Удаляем старые джобы пингов
    current_jobs = context.job_queue.get_jobs_by_name("checkin")
    for job in current_jobs:
        job.schedule_removal()
    
    # Первый пинг через interval минут
    context.job_queue.run_repeating(
        send_checkin,
        interval=timedelta(minutes=interval),
        first=timedelta(minutes=interval),
        chat_id=chat_id,
        name="checkin",
        data={"chat_id": chat_id}
    )
    
    logger.info(f"Пинги запланированы каждые {interval} минут")


async def send_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Отправить пинг-сообщение"""
    job = context.job
    chat_id = job.data["chat_id"] if job.data else job.chat_id
    
    settings = load_settings()
    workday_end = parse_time(settings.get("workday_end", "22:30"))
    
    # Проверяем, не закончился ли рабочий день
    now = datetime.now(TIMEZONE).time()
    if now >= workday_end:
        logger.info("Рабочий день закончился, пинги остановлены")
        job.schedule_removal()
        return
    
    # Проверяем, есть ли план на сегодня
    daily = load_daily()
    today = get_today_str()
    if today not in daily:
        logger.info("Нет плана на сегодня, пинг пропущен")
        return
    
    today_data = daily[today]
    tasks_count = len(today_data.get("tasks", []))
    done_count = today_data.get("done_task_count", 0)
    
    # Формируем кнопки
    keyboard = []
    
    # Кнопка "Выполнил задачу" доступна только если не все задачи отмечены
    if done_count < tasks_count:
        keyboard.append([InlineKeyboardButton("1️⃣ Выполнил задачу (+3 🔥)", callback_data="checkin_done_task")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Все задачи выполнены!", callback_data="checkin_all_done")])
    
    keyboard.extend([
        [InlineKeyboardButton("2️⃣ Работаю над задачами (+2 🔥)", callback_data="checkin_on_tasks")],
        [InlineKeyboardButton("3️⃣ Важное, но не по плану (+1 🔥)", callback_data="checkin_other_work")],
        [InlineKeyboardButton("4️⃣ Просто отвлёкся (+0 🔥)", callback_data="checkin_distracted")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="⏰ *Как продвигается охота за задачами?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ============== ОБРАБОТКА ОТВЕТОВ НА ПИНГИ ==============
async def handle_checkin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать ответ на пинг"""
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("checkin_"):
        return
    
    response_type = query.data.replace("checkin_", "")
    
    # Если нажал "все задачи выполнены" — это просто информация
    if response_type == "all_done":
        await query.edit_message_text("✅ Все задачи уже отмечены! Продолжай работать 💪")
        return
    
    # Сохраняем ответ в checkins.json
    checkins = load_checkins()
    today = get_today_str()
    now_time = datetime.now(TIMEZONE).strftime("%H:%M")
    
    if today not in checkins:
        checkins[today] = []
    
    checkins[today].append({
        "time": now_time,
        "answer": response_type
    })
    save_json(CHECKINS_FILE, checkins)
    
    # Если выполнил задачу — увеличиваем счётчик
    if response_type == "done_task":
        daily = load_daily()
        if today in daily:
            daily[today]["done_task_count"] = daily[today].get("done_task_count", 0) + 1
            save_json(DAILY_FILE, daily)
    
    # Определяем ответную фразу
    if response_type in ["done_task", "on_tasks", "other_work"]:
        phrase = get_random_motivation()
        points = {"done_task": 3, "on_tasks": 2, "other_work": 1}[response_type]
        response_text = f"{phrase}\n\n_+{points} 🔥_"
    else:  # distracted
        phrase = get_random_kick()
        response_text = f"{phrase}\n\n_+0 🔥_"
    
    await query.edit_message_text(response_text, parse_mode="Markdown")


# ============== ПОДСЧЁТ ОЧКОВ ==============
def calculate_today_score():
    """Подсчитать очки за сегодня"""
    checkins = load_checkins()
    today = get_today_str()
    
    if today not in checkins:
        return 0, 0, 0
    
    points_map = {
        "done_task": 3,
        "on_tasks": 2,
        "other_work": 1,
        "distracted": 0
    }
    
    today_checkins = checkins[today]
    total_score = 0
    checkin_count = len(today_checkins)
    
    # Считаем сколько done_task было
    done_task_count = sum(1 for c in today_checkins if c["answer"] == "done_task")
    
    for checkin in today_checkins:
        answer = checkin.get("answer", "distracted")
        total_score += points_map.get(answer, 0)
    
    # Максимум: done_task * tasks_count + остальные * 2
    daily = load_daily()
    tasks_count = len(daily.get(today, {}).get("tasks", [])) if today in daily else 4
    
    # Максимум = tasks_count * 3 + (checkin_count - tasks_count) * 2
    if checkin_count <= tasks_count:
        max_score = checkin_count * 3
    else:
        max_score = tasks_count * 3 + (checkin_count - tasks_count) * 2
    
    return total_score, max_score, checkin_count


def get_today_progress():
    """Получить текущий прогресс за сегодня"""
    score, max_score, checkins = calculate_today_score()
    daily = load_daily()
    today = get_today_str()
    
    tasks_total = 0
    tasks_done = 0
    
    if today in daily:
        tasks_total = len(daily[today].get("tasks", []))
        tasks_done = daily[today].get("done_task_count", 0)
    
    return {
        "score": score,
        "max_score": max_score,
        "checkins": checkins,
        "tasks_total": tasks_total,
        "tasks_done": tasks_done
    }



async def send_evening_tasks_request(context: ContextTypes.DEFAULT_TYPE):
    """Запросить какие задачи выполнены"""
    settings = load_settings()
    user_id = settings.get("user_id")
    
    if not user_id:
        return
    
    # Останавливаем пинги
    current_jobs = context.job_queue.get_jobs_by_name("checkin")
    for job in current_jobs:
        job.schedule_removal()
    
    daily = load_daily()
    today = get_today_str()
    
    if today not in daily or not daily[today].get("tasks"):
        await context.bot.send_message(
            chat_id=user_id,
            text="🌙 День подходит к концу. Сегодня план не был сформирован.\nОтдыхай, завтра новая охота!"
        )
        return
    
    tasks = load_tasks()
    today_task_ids = daily[today]["tasks"]
    today_tasks = [t for t in tasks if t["id"] in today_task_ids]
    
    # Сохраняем порядок
    task_map = {t["id"]: t for t in today_tasks}
    today_tasks = [task_map[tid] for tid in today_task_ids if tid in task_map]
    
    text = "🌙 *День подходит к концу.*\nЧто из плана ты завершил?\n\n"
    for i, task in enumerate(today_tasks, 1):
        text += f"{i}) {task['text']}\n"
    
    text += "\n_Ответь номерами через запятую, например: 1,3_\n_Если ничего — напиши 0_"
    
    # Сохраняем состояние ожидания ответа
    context.user_data["waiting_for_completed"] = True
    context.user_data["today_tasks"] = today_tasks
    
    await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")


# ============== ОБРАБОТКА ОТВЕТА О ВЫПОЛНЕННЫХ ЗАДАЧАХ ==============
async def handle_completed_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать ответ с номерами выполненных задач"""
    if not context.user_data.get("waiting_for_completed"):
        return False
    
    text = update.message.text.strip()
    today_tasks = context.user_data.get("today_tasks", [])
    
    # Парсим номера
    completed_indices = []
    if text != "0":
        try:
            parts = text.replace(" ", "").split(",")
            completed_indices = [int(p) - 1 for p in parts if p.isdigit()]
        except:
            await update.message.reply_text("Не понял. Напиши номера через запятую (например: 1,3) или 0")
            return True
    
    # Получаем ID выполненных и невыполненных задач
    completed_ids = []
    uncompleted_ids = []
    
    for i, task in enumerate(today_tasks):
        if i in completed_indices:
            completed_ids.append(task["id"])
        else:
            uncompleted_ids.append(task["id"])
    
    # Обновляем tasks.json
    tasks = load_tasks()
    for task in tasks:
        if task["id"] in completed_ids:
            task["is_done"] = True
            task["times_given"] = task.get("times_given", 0) + 1
        elif task["id"] in uncompleted_ids:
            task["times_given"] = task.get("times_given", 0) + 1
            task["times_skipped"] = task.get("times_skipped", 0) + 1
    save_json(TASKS_FILE, tasks)
    
    # Обновляем daily.json
    daily = load_daily()
    today = get_today_str()
    daily[today]["completed_tasks"] = completed_ids
    save_json(DAILY_FILE, daily)
    
    context.user_data["waiting_for_completed"] = False
    context.user_data["uncompleted_ids"] = uncompleted_ids
    context.user_data["uncompleted_tasks"] = [t for t in today_tasks if t["id"] in uncompleted_ids]
    
    # Если есть невыполненные — спрашиваем про перенос
    if uncompleted_ids:
        keyboard = [
            [InlineKeyboardButton("💾 Сохранить задачи (без награды)", callback_data="evening_sacrifice")],
            [InlineKeyboardButton("🎁 Забрать награду", callback_data="evening_reward")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Выполнено: {len(completed_ids)} из {len(today_tasks)}\n\n"
            "Остались незавершённые задачи.\n"
            "Хочешь пожертвовать наградой, чтобы перенести их на завтра?",
            reply_markup=reply_markup
        )
    else:
        # Все выполнены — сразу к награде
        await update.message.reply_text(f"🎉 *Все {len(completed_ids)} задач выполнены!*", parse_mode="Markdown")
        await schedule_final_summary(context, update.effective_chat.id, sacrificed=False)
    
    return True


# ============== ВЫБОР: СОХРАНИТЬ ИЛИ НАГРАДА ==============
async def handle_evening_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать выбор вечером"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "evening_sacrifice":
        # Хочет сохранить задачи
        uncompleted = context.user_data.get("uncompleted_tasks", [])
        
        if len(uncompleted) == 1:
            # Только одна задача — сразу сохраняем
            await save_carried_tasks(context, query.message.chat_id, [uncompleted[0]["id"]])
            await query.edit_message_text(
                f"💾 Задача сохранена на завтра:\n• {uncompleted[0]['text']}\n\n"
                "Ты пожертвовал наградой ради неё.\n"
                "_Настоящий охотник отвечает за свой след._",
                parse_mode="Markdown"
            )
            await send_goodnight(context, query.message.chat_id)
        else:
            # Несколько — спрашиваем какие
            text = "Какие задачи сохранить на завтра?\n\n"
            for i, task in enumerate(uncompleted, 1):
                text += f"{i}) {task['text']}\n"
            text += "\n_Ответь номерами через запятую:_"
            
            context.user_data["waiting_for_carry"] = True
            await query.edit_message_text(text, parse_mode="Markdown")
    
    elif query.data == "evening_reward":
        # Хочет награду
        daily = load_daily()
        today = get_today_str()
        daily[today]["reward_sacrificed"] = False
        daily[today]["carry_over_tasks"] = []
        save_json(DAILY_FILE, daily)
        
        await query.edit_message_text("🎁 Отлично! Награда будет в 23:00")
        await schedule_final_summary(context, query.message.chat_id, sacrificed=False)


# ============== ОБРАБОТКА ВЫБОРА ЗАДАЧ ДЛЯ ПЕРЕНОСА ==============
async def handle_carry_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать выбор задач для переноса"""
    if not context.user_data.get("waiting_for_carry"):
        return False
    
    text = update.message.text.strip()
    uncompleted = context.user_data.get("uncompleted_tasks", [])
    
    try:
        parts = text.replace(" ", "").split(",")
        indices = [int(p) - 1 for p in parts if p.isdigit()]
        carry_ids = [uncompleted[i]["id"] for i in indices if 0 <= i < len(uncompleted)]
    except:
        await update.message.reply_text("Не понял. Напиши номера через запятую (например: 1,2)")
        return True
    
    if not carry_ids:
        await update.message.reply_text("Не выбрано ни одной задачи. Попробуй ещё раз.")
        return True
    
    context.user_data["waiting_for_carry"] = False
    
    await save_carried_tasks(context, update.effective_chat.id, carry_ids)
    
    carried_names = [t["text"] for t in uncompleted if t["id"] in carry_ids]
    text = "💾 *Задачи сохранены на завтра:*\n"
    for name in carried_names:
        text += f"• {name}\n"
    text += "\nТы пожертвовал наградой ради них.\n_Настоящий охотник отвечает за свой след._"
    
    await update.message.reply_text(text, parse_mode="Markdown")
    await send_goodnight(context, update.effective_chat.id)
    
    return True


async def save_carried_tasks(context, chat_id, carry_ids):
    """Сохранить перенесённые задачи"""
    daily = load_daily()
    today = get_today_str()
    daily[today]["reward_sacrificed"] = True
    daily[today]["carry_over_tasks"] = carry_ids
    save_json(DAILY_FILE, daily)


# ============== ИТОГИ ДНЯ (23:00) ==============
async def schedule_final_summary(context, chat_id, sacrificed=False):
    """Запланировать или сразу отправить итоги"""
    settings = load_settings()
    summary_time = parse_time(settings.get("score_summary_time", "23:00"))
    now = datetime.now(TIMEZONE)
    
    # Если уже позже времени итогов — отправляем сразу
    if now.time() >= summary_time:
        await send_final_summary(context, chat_id)
    else:
        # Планируем на нужное время
        target = now.replace(hour=summary_time.hour, minute=summary_time.minute, second=0)
        delay = (target - now).total_seconds()
        context.job_queue.run_once(
            lambda ctx: send_final_summary(ctx, chat_id),
            when=delay,
            name="final_summary"
        )


async def send_final_summary(context: ContextTypes.DEFAULT_TYPE, chat_id: int = None):
    """Отправить итоги дня с наградой и добычей"""
    if chat_id is None:
        job = context.job
        chat_id = job.chat_id if hasattr(job, 'chat_id') else load_settings().get("user_id")
    
    daily = load_daily()
    today = get_today_str()
    
    # Если награда пожертвована — не отправляем итоги
    if today in daily and daily[today].get("reward_sacrificed"):
        return
    
    score, max_score, checkin_count = calculate_today_score()
    settings = load_settings()
    
    # Определяем вердикт
    if max_score > 0:
        percent = int(score / max_score * 100)
    else:
        percent = 0
    
    if percent >= 80:
        verdict = "🔥 Супердень!"
    elif percent >= 60:
        verdict = "💪 Крепкий день!"
    elif percent >= 40:
        verdict = "👍 Нормальный день"
    else:
        verdict = "😐 День-разбор"
    
    summary_text = (
        f"📊 *ИТОГИ ОХОТЫ*\n\n"
        f"Чек-инов: {checkin_count}\n"
        f"Очки: {score} из {max_score} ({percent}%)\n"
        f"Вердикт: {verdict}"
    )
    
    await context.bot.send_message(chat_id=chat_id, text=summary_text, parse_mode="Markdown")
    
    # Награда
    reward = get_reward_by_score(score, settings)
    if reward:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎁 *Твоя награда:*\n{reward['text']}",
            parse_mode="Markdown"
        )
    
    # Добыча
    animal = get_animal_by_score(score, settings)
    if animal:
        animal_text = f"🏆 *Сегодняшняя добыча:*\n*{animal['name']}*\n\n_{animal['description']}_\n\n\"{animal['verdict']}\""
        
        if animal.get("image_file_id"):
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=animal["image_file_id"],
                    caption=animal_text,
                    parse_mode="Markdown"
                )
            except:
                await context.bot.send_message(chat_id=chat_id, text=animal_text, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=animal_text, parse_mode="Markdown")
    
    # Картинка спокойной ночи
    await send_goodnight(context, chat_id)


async def send_goodnight(context, chat_id):
    """Отправить картинку спокойной ночи"""
    settings = load_settings()
    night_image = settings.get("night_image_file_id")
    
    if night_image:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=night_image,
                caption="🌙 Охота завершена. Спокойной ночи, охотник."
            )
        except:
            await context.bot.send_message(chat_id=chat_id, text="🌙 Охота завершена. Спокойной ночи, охотник.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="🌙 Охота завершена. Спокойной ночи, охотник.")


# ============== НАГРАДА И ДОБЫЧА ==============
def get_reward_by_score(score: int, settings: dict):
    """Получить награду по очкам"""
    rewards = load_rewards()
    high_threshold = settings.get("reward_high_threshold", 32)
    mid_threshold = settings.get("reward_mid_threshold", 19)
    
    if score >= high_threshold:
        level = "high"
    elif score >= mid_threshold:
        level = "mid"
    else:
        level = "low"
    
    level_rewards = [r for r in rewards if r.get("level") == level]
    return random.choice(level_rewards) if level_rewards else None


def get_animal_by_score(score: int, settings: dict):
    """Получить добычу по очкам с элементом случайности"""
    animals = load_animals()
    thresholds = settings.get("loot_thresholds", {})
    
    lemming_max = thresholds.get("lemming_max", 14)
    hare_max = thresholds.get("hare_max", 27)
    deer_max = thresholds.get("deer_max", 36)
    muskox_max = thresholds.get("muskox_max", 44)
    
    # Определяем шансы по таблице
    if score <= lemming_max:
        choices = [1]  # 100% лемминг
    elif score <= hare_max:
        choices = [2, 2, 2, 1, 1]  # 60% заяц, 40% лемминг
    elif score <= deer_max:
        choices = [3, 3, 3, 3, 3, 2, 2, 2, 4, 4]  # 50% олень, 30% заяц, 20% овцебык
    elif score <= muskox_max:
        choices = [4, 4, 4, 4, 4, 3, 3, 3, 3, 5]  # 50% овцебык, 40% олень, 10% зубр
    else:
        choices = [5]  # 100% зубр
    
    level = random.choice(choices)
    animal = next((a for a in animals if a.get("level") == level), None)
    return animal



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    
    # Сохраняем user_id
    settings = load_settings()
    settings["user_id"] = user_id
    save_json(SETTINGS_FILE, settings)
    
    await update.message.reply_text(
        "🏹 *Добро пожаловать, охотник!*\n\n"
        "Я — твой Охотник-Менеджер.\n"
        "Каждое утро я буду будить тебя, давать задачи и следить за прогрессом.\n\n"
        "Команды:\n"
        "/status — текущий статус\n"
        "/tasks — задачи на сегодня\n"
        "/pinok — получить пинок\n"
        "/set_rank_image — установить картинку ранга\n"
        "/set_night_image — установить картинку на ночь\n"
        "/set_animal_image — установить картинку животного\n"
        "/morning — запустить утро вручную\n\n"
        "_Охота начинается завтра в 6:00!_",
        parse_mode="Markdown"
    )
    
    # Планируем утренние сообщения
    schedule_daily_jobs(context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status — текущий статус"""
    settings = load_settings()
    progress = get_today_progress()
    
    rank = settings.get("rank_name", "Молодой охотник")
    goals = settings.get("quarter_goals_text", "Не установлены")
    
    text = (
        f"🏹 *Статус охотника*\n\n"
        f"Ранг: *{rank}*\n\n"
        f"📊 *Сегодня:*\n"
        f"Чек-инов: {progress['checkins']}\n"
        f"Очки: {progress['score']} из {progress['max_score']}\n"
        f"Задач выполнено: {progress['tasks_done']} из {progress['tasks_total']}\n\n"
        f"🎯 *Квартальные цели:*\n{goals}"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /tasks — задачи на сегодня"""
    daily = load_daily()
    today = get_today_str()
    
    if today not in daily or not daily[today].get("tasks"):
        await update.message.reply_text(
            "📋 На сегодня план не сформирован.\n"
            "Используй /morning чтобы начать день."
        )
        return
    
    tasks = load_tasks()
    today_data = daily[today]
    today_task_ids = today_data["tasks"]
    completed_ids = today_data.get("completed_tasks", [])
    done_count = today_data.get("done_task_count", 0)
    
    task_map = {t["id"]: t for t in tasks}
    
    text = "🎯 *План на сегодня:*\n\n"
    for i, tid in enumerate(today_task_ids, 1):
        task = task_map.get(tid)
        if task:
            status = "✅" if tid in completed_ids else "⬜"
            text += f"{status} {i}) {task['text']}\n"
    
    text += f"\n_Отмечено через пинги: {done_count} из {len(today_task_ids)}_"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_pinok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /pinok — получить пинок"""
    phrase = get_random_kick()
    progress = get_today_progress()
    
    text = (
        f"👊 {phrase}\n\n"
        f"📊 Сегодня: {progress['checkins']} чек-инов, "
        f"{progress['score']} из {progress['max_score']} очков\n"
        f"Задач: {progress['tasks_done']} из {progress['tasks_total']}"
    )
    
    await update.message.reply_text(text)


async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /morning — запустить утро вручную"""
    await send_morning_message(context)


async def cmd_set_rank_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /set_rank_image — установить картинку ранга"""
    context.user_data["waiting_for_image"] = "rank"
    await update.message.reply_text("📷 Отправь картинку для ранга:")


async def cmd_set_night_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /set_night_image — установить ночную картинку"""
    context.user_data["waiting_for_image"] = "night"
    await update.message.reply_text("📷 Отправь картинку для ночного сообщения:")


async def cmd_set_animal_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /set_animal_image — установить картинку животного"""
    animals = load_animals()
    
    keyboard = []
    for animal in animals:
        keyboard.append([InlineKeyboardButton(animal["name"], callback_data=f"setanimal_{animal['level']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери животное:", reply_markup=reply_markup)


async def handle_animal_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора животного для картинки"""
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("setanimal_"):
        return
    
    level = int(query.data.replace("setanimal_", ""))
    context.user_data["waiting_for_image"] = f"animal_{level}"
    
    await query.edit_message_text(f"📷 Отправь картинку для животного уровня {level}:")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученной фотографии"""
    waiting = context.user_data.get("waiting_for_image")
    
    if not waiting:
        return
    
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    if waiting == "rank":
        settings = load_settings()
        settings["rank_image_file_id"] = file_id
        save_json(SETTINGS_FILE, settings)
        await update.message.reply_text("✅ Картинка ранга установлена!")
    
    elif waiting == "night":
        settings = load_settings()
        settings["night_image_file_id"] = file_id
        save_json(SETTINGS_FILE, settings)
        await update.message.reply_text("✅ Ночная картинка установлена!")
    
    elif waiting.startswith("animal_"):
        level = int(waiting.replace("animal_", ""))
        animals = load_animals()
        for animal in animals:
            if animal.get("level") == level:
                animal["image_file_id"] = file_id
                break
        save_json(ANIMALS_FILE, animals)
        await update.message.reply_text(f"✅ Картинка животного уровня {level} установлена!")
    
    context.user_data["waiting_for_image"] = None


# ============== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ==============
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    # Проверяем ожидание ответа о выполненных задачах
    if await handle_completed_tasks(update, context):
        return
    
    # Проверяем ожидание выбора задач для переноса
    if await handle_carry_selection(update, context):
        return


# ============== ПЛАНИРОВАНИЕ ЕЖЕДНЕВНЫХ ЗАДАЧ ==============
def schedule_daily_jobs(context: ContextTypes.DEFAULT_TYPE):
    """Запланировать ежедневные задачи"""
    settings = load_settings()
    
    # Удаляем старые джобы
    for job_name in ["morning_weekday", "morning_weekend", "evening_tasks"]:
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in jobs:
            job.schedule_removal()
    
    # Утро будни (Пн-Пт)
    weekday_time = parse_time(settings.get("weekday_wakeup", "06:00"))
    context.job_queue.run_daily(
        send_morning_message,
        time=weekday_time,
        days=(0, 1, 2, 3, 4),
        name="morning_weekday"
    )
    
    # Утро выходные (Сб-Вс)
    weekend_time = parse_time(settings.get("weekend_wakeup", "08:00"))
    context.job_queue.run_daily(
        send_morning_message,
        time=weekend_time,
        days=(5, 6),
        name="morning_weekend"
    )
    
    # Вечер — запрос задач
    evening_time = parse_time(settings.get("workday_end", "22:30"))
    context.job_queue.run_daily(
        send_evening_tasks_request,
        time=evening_time,
        name="evening_tasks"
    )
    
    logger.info("Ежедневные задачи запланированы")


# ============== MAIN ==============
def main():
    """Запуск бота"""
    ensure_data_dir()
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("pinok", cmd_pinok))
    app.add_handler(CommandHandler("morning", cmd_morning))
    app.add_handler(CommandHandler("set_rank_image", cmd_set_rank_image))
    app.add_handler(CommandHandler("set_night_image", cmd_set_night_image))
    app.add_handler(CommandHandler("set_animal_image", cmd_set_animal_image))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_role_selection, pattern="^role_"))
    app.add_handler(CallbackQueryHandler(handle_checkin_response, pattern="^checkin_"))
    app.add_handler(CallbackQueryHandler(handle_evening_choice, pattern="^evening_"))
    app.add_handler(CallbackQueryHandler(handle_animal_selection, pattern="^setanimal_"))
    
    # Фото и текст
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Бот запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
