# -*- coding: utf-8 -*-
"""
Охотник-Менеджер Telegram Bot
Исправленная версия с картинками из GitHub и случайным выбором задач
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

# Картинки из GitHub репозитория
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/setar7788-ctrl/shifr_storozha_bot/main"
IMAGES = {
    "rank": f"{GITHUB_RAW_BASE}/Молодой%20Охотник.jpg",
    "night": f"{GITHUB_RAW_BASE}/для%20телефона.png",
    "animals": {
        1: f"{GITHUB_RAW_BASE}/Leming.jpg",
        2: f"{GITHUB_RAW_BASE}/Zayac.jpg",
        3: f"{GITHUB_RAW_BASE}/Olen.jpg",
        4: f"{GITHUB_RAW_BASE}/ovczebyk-ajstok.jpg",
        5: f"{GITHUB_RAW_BASE}/zubr.jpg",
    }
}

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
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(filepath: Path, default=None):
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
    return load_json(TASKS_FILE, [])


def load_daily():
    return load_json(DAILY_FILE, {})


def load_checkins():
    return load_json(CHECKINS_FILE, {})


def load_rewards():
    return load_json(REWARDS_FILE, [])


def load_animals():
    return load_json(ANIMALS_FILE, [])


def load_phrases_motivation():
    return load_json(PHRASES_MOTIVATION_FILE, [])


def load_phrases_kick():
    return load_json(PHRASES_KICK_FILE, [])


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def get_today_str():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def get_yesterday_str():
    yesterday = datetime.now(TIMEZONE) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def is_weekend():
    return datetime.now(TIMEZONE).weekday() >= 5


def get_tasks_count_today():
    settings = load_settings()
    if is_weekend():
        return settings.get("weekend_tasks_count", 8)
    return settings.get("weekday_tasks_count", 4)


def parse_time(time_str):
    h, m = map(int, time_str.split(":"))
    return time(hour=h, minute=m)


def get_random_motivation():
    phrases = load_phrases_motivation()
    return random.choice(phrases) if phrases else "Отлично!"


def get_random_kick():
    phrases = load_phrases_kick()
    return random.choice(phrases) if phrases else "Соберись."


# ============== УТРЕННЕЕ СООБЩЕНИЕ ==============
async def send_morning_message(context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    user_id = settings.get("user_id")
    
    if not user_id:
        logger.warning("user_id не установлен")
        return
    
    rank_name = settings.get("rank_name", "Молодой охотник")
    goals = settings.get("quarter_goals_text", "Цели не установлены")
    
    greeting = f"☀️ Доброе утро, охотник!\nТвой ранг: {rank_name}"
    try:
        await context.bot.send_photo(chat_id=user_id, photo=IMAGES["rank"], caption=greeting)
    except Exception as e:
        logger.error(f"Ошибка картинки ранга: {e}")
        await context.bot.send_message(chat_id=user_id, text=greeting)
    
    goals_text = f"🏹 КАРТА ОХОТЫ НА КВАРТАЛ:\n\n{goals}"
    await context.bot.send_message(chat_id=user_id, text=goals_text)
    
    keyboard = [
        [InlineKeyboardButton("💰 Мультимиллионер", callback_data="role_multimillionaire")],
        [InlineKeyboardButton("🛡 Герой", callback_data="role_hero")],
        [InlineKeyboardButton("🧡 Добрый папа", callback_data="role_papa")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text="Кем ты будешь сегодня?", reply_markup=reply_markup)


# ============== ВЫБОР РОЛИ ==============
async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("role_"):
        return
    
    role = query.data.replace("role_", "")
    role_names = {"multimillionaire": "💰 Мультимиллионер", "hero": "🛡 Герой", "papa": "🧡 Добрый папа"}
    
    await query.edit_message_text(f"Сегодня ты — {role_names.get(role, role)}")
    
    tasks_for_today = generate_daily_plan(role)
    
    daily = load_daily()
    today = get_today_str()
    yesterday = get_yesterday_str()
    carried_over = yesterday in daily and daily[yesterday].get("reward_sacrificed", False)
    
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
    
    tasks_text = "🎯 Твой план охотника на сегодня:\n\n"
    for i, task in enumerate(tasks_for_today, 1):
        tasks_text += f"{i}) {task['text']}\n"
    tasks_text += "\nОхота началась! Первый чек-ин через 45 минут. ❤️"
    
    await context.bot.send_message(chat_id=query.message.chat_id, text=tasks_text)
    schedule_checkins(context, query.message.chat_id)


def generate_daily_plan(role_of_day: str) -> list:
    """Сформировать план задач на день со СЛУЧАЙНЫМ выбором"""
    tasks = load_tasks()
    daily = load_daily()
    base_count = get_tasks_count_today()
    
    # Проверяем перенесённые задачи со вчера
    yesterday = get_yesterday_str()
    carried_tasks = []
    
    if yesterday in daily:
        yesterday_data = daily[yesterday]
        if yesterday_data.get("reward_sacrificed") and yesterday_data.get("carry_over_tasks"):
            carry_ids = yesterday_data["carry_over_tasks"]
            carried_tasks = [t for t in tasks if t["id"] in carry_ids and not t.get("is_done")]
            if carried_tasks:
                base_count = max(1, base_count - 1)
    
    # Незавершённые задачи по категориям
    available = {
        "multimillionaire": [t for t in tasks if t.get("category") == "multimillionaire" and not t.get("is_done")],
        "hero": [t for t in tasks if t.get("category") == "hero" and not t.get("is_done")],
        "papa": [t for t in tasks if t.get("category") == "papa" and not t.get("is_done")]
    }
    
    # Убираем перенесённые из доступных
    carried_ids = [t["id"] for t in carried_tasks]
    for cat in available:
        available[cat] = [t for t in available[cat] if t["id"] not in carried_ids]
    
    selected = list(carried_tasks)
    selected_ids = set(carried_ids)
    remaining = base_count - len(selected)
    
    # Сначала по одной СЛУЧАЙНОЙ задаче из каждой категории
    for cat in ["multimillionaire", "hero", "papa"]:
        if remaining <= 0:
            break
        cat_tasks = [t for t in available[cat] if t["id"] not in selected_ids]
        if cat_tasks:
            task = random.choice(cat_tasks)  # СЛУЧАЙНЫЙ выбор
            selected.append(task)
            selected_ids.add(task["id"])
            remaining -= 1
    
    # Остальные СЛУЧАЙНО из роли дня
    if remaining > 0 and role_of_day in available:
        role_tasks = [t for t in available[role_of_day] if t["id"] not in selected_ids]
        if role_tasks:
            # Берём случайные задачи из роли дня
            count_to_take = min(remaining, len(role_tasks))
            random_tasks = random.sample(role_tasks, count_to_take)
            for task in random_tasks:
                selected.append(task)
                selected_ids.add(task["id"])
                remaining -= 1
    
    # Если всё ещё не хватает — берём СЛУЧАЙНО из любых категорий
    if remaining > 0:
        all_available = [t for t in tasks if not t.get("is_done") and t["id"] not in selected_ids]
        if all_available:
            count_to_take = min(remaining, len(all_available))
            random_tasks = random.sample(all_available, count_to_take)
            for task in random_tasks:
                selected.append(task)
                selected_ids.add(task["id"])
                remaining -= 1
    
    # Перемешиваем финальный список для разнообразия порядка
    random.shuffle(selected)
    
    return selected


# ============== ПИНГИ ==============
def schedule_checkins(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    settings = load_settings()
    interval = settings.get("checkin_interval_minutes", 45)
    
    for job in context.job_queue.get_jobs_by_name("checkin"):
        job.schedule_removal()
    
    context.job_queue.run_repeating(
        send_checkin,
        interval=timedelta(minutes=interval),
        first=timedelta(minutes=interval),
        chat_id=chat_id,
        name="checkin",
        data={"chat_id": chat_id}
    )
    logger.info(f"Пинги каждые {interval} мин")


async def send_checkin(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"] if job.data else job.chat_id
    
    settings = load_settings()
    workday_end = parse_time(settings.get("workday_end", "22:30"))
    
    if datetime.now(TIMEZONE).time() >= workday_end:
        job.schedule_removal()
        return
    
    daily = load_daily()
    today = get_today_str()
    if today not in daily:
        return
    
    today_data = daily[today]
    tasks_count = len(today_data.get("tasks", []))
    done_count = today_data.get("done_task_count", 0)
    
    keyboard = []
    if done_count < tasks_count:
        keyboard.append([InlineKeyboardButton("1️⃣ Выполнил задачу (+3 🔥)", callback_data="checkin_done_task")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Все задачи выполнены!", callback_data="checkin_all_done")])
    
    keyboard.extend([
        [InlineKeyboardButton("2️⃣ Работаю над задачами (+2 🔥)", callback_data="checkin_on_tasks")],
        [InlineKeyboardButton("3️⃣ Важное, но не по плану (+1 🔥)", callback_data="checkin_other_work")],
        [InlineKeyboardButton("4️⃣ Просто отвлёкся (+0 🔥)", callback_data="checkin_distracted")]
    ])
    
    await context.bot.send_message(chat_id=chat_id, text="⏰ Как продвигается охота?", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_checkin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("checkin_"):
        return
    
    response_type = query.data.replace("checkin_", "")
    
    if response_type == "all_done":
        await query.edit_message_text("✅ Все задачи отмечены! Продолжай 💪")
        return
    
    checkins = load_checkins()
    today = get_today_str()
    if today not in checkins:
        checkins[today] = []
    checkins[today].append({"time": datetime.now(TIMEZONE).strftime("%H:%M"), "answer": response_type})
    save_json(CHECKINS_FILE, checkins)
    
    if response_type == "done_task":
        daily = load_daily()
        if today in daily:
            daily[today]["done_task_count"] = daily[today].get("done_task_count", 0) + 1
            save_json(DAILY_FILE, daily)
    
    if response_type in ["done_task", "on_tasks", "other_work"]:
        phrase = get_random_motivation()
        points = {"done_task": 3, "on_tasks": 2, "other_work": 1}[response_type]
        await query.edit_message_text(f"{phrase}\n\n+{points} 🔥")
    else:
        await query.edit_message_text(f"{get_random_kick()}\n\n+0 🔥")


# ============== ПОДСЧЁТ ОЧКОВ ==============
def calculate_today_score():
    checkins = load_checkins()
    today = get_today_str()
    if today not in checkins:
        return 0, 0, 0
    
    points_map = {"done_task": 3, "on_tasks": 2, "other_work": 1, "distracted": 0}
    today_checkins = checkins[today]
    total_score = sum(points_map.get(c.get("answer", "distracted"), 0) for c in today_checkins)
    checkin_count = len(today_checkins)
    
    daily = load_daily()
    tasks_count = len(daily.get(today, {}).get("tasks", [])) if today in daily else 4
    max_score = min(checkin_count, tasks_count) * 3 + max(0, checkin_count - tasks_count) * 2
    
    return total_score, max_score, checkin_count


def get_today_progress():
    score, max_score, checkins = calculate_today_score()
    daily = load_daily()
    today = get_today_str()
    tasks_total = len(daily.get(today, {}).get("tasks", [])) if today in daily else 0
    tasks_done = daily.get(today, {}).get("done_task_count", 0) if today in daily else 0
    return {"score": score, "max_score": max_score, "checkins": checkins, "tasks_total": tasks_total, "tasks_done": tasks_done}


# ============== ВЕЧЕР ==============
async def send_evening_tasks_request(context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    user_id = settings.get("user_id")
    if not user_id:
        return
    
    for job in context.job_queue.get_jobs_by_name("checkin"):
        job.schedule_removal()
    
    daily = load_daily()
    today = get_today_str()
    if today not in daily or not daily[today].get("tasks"):
        await context.bot.send_message(chat_id=user_id, text="🌙 Сегодня план не был сформирован. Отдыхай!")
        return
    
    tasks = load_tasks()
    task_map = {t["id"]: t for t in tasks}
    today_tasks = [task_map[tid] for tid in daily[today]["tasks"] if tid in task_map]
    
    text = "🌙 День подходит к концу.\nЧто из плана ты завершил?\n\n"
    for i, task in enumerate(today_tasks, 1):
        text += f"{i}) {task['text']}\n"
    text += "\nОтветь номерами через запятую (1,3) или 0"
    
    context.user_data["waiting_for_completed"] = True
    context.user_data["today_tasks"] = today_tasks
    await context.bot.send_message(chat_id=user_id, text=text)


async def handle_completed_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_completed"):
        return False
    
    text = update.message.text.strip()
    today_tasks = context.user_data.get("today_tasks", [])
    
    completed_indices = []
    if text != "0":
        try:
            completed_indices = [int(p) - 1 for p in text.replace(" ", "").split(",") if p.isdigit()]
        except:
            await update.message.reply_text("Не понял. Напиши номера через запятую или 0")
            return True
    
    completed_ids = [today_tasks[i]["id"] for i in completed_indices if 0 <= i < len(today_tasks)]
    uncompleted_ids = [t["id"] for i, t in enumerate(today_tasks) if i not in completed_indices]
    
    tasks = load_tasks()
    for task in tasks:
        if task["id"] in completed_ids:
            task["is_done"] = True
            task["times_given"] = task.get("times_given", 0) + 1
        elif task["id"] in uncompleted_ids:
            task["times_given"] = task.get("times_given", 0) + 1
            task["times_skipped"] = task.get("times_skipped", 0) + 1
    save_json(TASKS_FILE, tasks)
    
    daily = load_daily()
    today = get_today_str()
    daily[today]["completed_tasks"] = completed_ids
    save_json(DAILY_FILE, daily)
    
    context.user_data["waiting_for_completed"] = False
    context.user_data["uncompleted_tasks"] = [t for t in today_tasks if t["id"] in uncompleted_ids]
    
    if uncompleted_ids:
        keyboard = [
            [InlineKeyboardButton("💾 Сохранить задачи (без награды)", callback_data="evening_sacrifice")],
            [InlineKeyboardButton("🎁 Забрать награду", callback_data="evening_reward")]
        ]
        await update.message.reply_text(
            f"✅ Выполнено: {len(completed_ids)} из {len(today_tasks)}\n\nПеренести незавершённые на завтра?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(f"🎉 Все {len(completed_ids)} задач выполнены!")
        await schedule_final_summary(context, update.effective_chat.id)
    return True


async def handle_evening_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "evening_sacrifice":
        uncompleted = context.user_data.get("uncompleted_tasks", [])
        if len(uncompleted) == 1:
            daily = load_daily()
            today = get_today_str()
            daily[today]["reward_sacrificed"] = True
            daily[today]["carry_over_tasks"] = [uncompleted[0]["id"]]
            save_json(DAILY_FILE, daily)
            await query.edit_message_text(f"💾 Задача сохранена: {uncompleted[0]['text']}")
            await send_goodnight(context, query.message.chat_id)
        else:
            text = "Какие сохранить?\n\n"
            for i, t in enumerate(uncompleted, 1):
                text += f"{i}) {t['text']}\n"
            context.user_data["waiting_for_carry"] = True
            await query.edit_message_text(text)
    elif query.data == "evening_reward":
        daily = load_daily()
        today = get_today_str()
        daily[today]["reward_sacrificed"] = False
        save_json(DAILY_FILE, daily)
        await query.edit_message_text("🎁 Награда в 23:00!")
        await schedule_final_summary(context, query.message.chat_id)


async def handle_carry_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_carry"):
        return False
    
    uncompleted = context.user_data.get("uncompleted_tasks", [])
    try:
        indices = [int(p) - 1 for p in update.message.text.replace(" ", "").split(",") if p.isdigit()]
        carry_ids = [uncompleted[i]["id"] for i in indices if 0 <= i < len(uncompleted)]
    except:
        await update.message.reply_text("Не понял. Номера через запятую.")
        return True
    
    if not carry_ids:
        await update.message.reply_text("Не выбрано задач.")
        return True
    
    context.user_data["waiting_for_carry"] = False
    daily = load_daily()
    today = get_today_str()
    daily[today]["reward_sacrificed"] = True
    daily[today]["carry_over_tasks"] = carry_ids
    save_json(DAILY_FILE, daily)
    
    names = [t["text"] for t in uncompleted if t["id"] in carry_ids]
    await update.message.reply_text("💾 Сохранено:\n" + "\n".join(f"• {n}" for n in names))
    await send_goodnight(context, update.effective_chat.id)
    return True


# ============== ИТОГИ ==============
async def schedule_final_summary(context, chat_id):
    settings = load_settings()
    summary_time = parse_time(settings.get("score_summary_time", "23:00"))
    now = datetime.now(TIMEZONE)
    
    if now.time() >= summary_time:
        await send_final_summary(context, chat_id)
    else:
        target = now.replace(hour=summary_time.hour, minute=summary_time.minute, second=0)
        context.job_queue.run_once(lambda ctx: send_final_summary(ctx, chat_id), when=(target - now).total_seconds())


async def send_final_summary(context: ContextTypes.DEFAULT_TYPE, chat_id: int = None):
    if chat_id is None:
        chat_id = load_settings().get("user_id")
    
    daily = load_daily()
    today = get_today_str()
    if today in daily and daily[today].get("reward_sacrificed"):
        return
    
    score, max_score, checkin_count = calculate_today_score()
    percent = int(score / max_score * 100) if max_score > 0 else 0
    
    if percent >= 80:
        verdict = "🔥 Супердень!"
    elif percent >= 60:
        verdict = "💪 Крепкий день!"
    elif percent >= 40:
        verdict = "👍 Нормальный день"
    else:
        verdict = "😐 День-разбор"
    
    await context.bot.send_message(chat_id=chat_id, text=f"📊 ИТОГИ\n\nЧек-инов: {checkin_count}\nОчки: {score}/{max_score} ({percent}%)\n{verdict}")
    
    settings = load_settings()
    reward = get_reward_by_score(score, settings)
    if reward:
        await context.bot.send_message(chat_id=chat_id, text=f"🎁 Награда:\n{reward['text']}")
    
    animal = get_animal_by_score(score, settings)
    if animal:
        level = animal.get("level", 1)
        image_url = IMAGES["animals"].get(level)
        text = f"🏆 Добыча: {animal['name']}\n\n{animal['description']}\n\n\"{animal['verdict']}\""
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=text)
        except:
            await context.bot.send_message(chat_id=chat_id, text=text)
    
    await send_goodnight(context, chat_id)


async def send_goodnight(context, chat_id):
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=IMAGES["night"], caption="🌙 Спокойной ночи, охотник.")
    except:
        await context.bot.send_message(chat_id=chat_id, text="🌙 Спокойной ночи, охотник.")


def get_reward_by_score(score, settings):
    rewards = load_rewards()
    high = settings.get("reward_high_threshold", 32)
    mid = settings.get("reward_mid_threshold", 19)
    level = "high" if score >= high else ("mid" if score >= mid else "low")
    level_rewards = [r for r in rewards if r.get("level") == level]
    return random.choice(level_rewards) if level_rewards else None


def get_animal_by_score(score, settings):
    animals = load_animals()
    th = settings.get("loot_thresholds", {})
    if score <= th.get("lemming_max", 14):
        choices = [1]
    elif score <= th.get("hare_max", 27):
        choices = [2, 2, 2, 1, 1]
    elif score <= th.get("deer_max", 36):
        choices = [3, 3, 3, 3, 3, 2, 2, 2, 4, 4]
    elif score <= th.get("muskox_max", 44):
        choices = [4, 4, 4, 4, 4, 3, 3, 3, 3, 5]
    else:
        choices = [5]
    return next((a for a in animals if a.get("level") == random.choice(choices)), None)


# ============== КОМАНДЫ ==============
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = load_settings()
    settings["user_id"] = user_id
    save_json(SETTINGS_FILE, settings)
    
    await update.message.reply_text(
        "🏹 Добро пожаловать, охотник!\n\n"
        "Команды:\n/status — статус\n/tasks — задачи\n/pinok — пинок\n/morning — начать день\n\n"
        "Охота начинается завтра в 6:00!"
    )
    schedule_daily_jobs(context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    p = get_today_progress()
    goals = settings.get("quarter_goals_text", "Не установлены")
    await update.message.reply_text(
        f"🏹 Статус\n\nРанг: {settings.get('rank_name', 'Молодой охотник')}\n\n"
        f"📊 Сегодня:\nЧек-инов: {p['checkins']}\nОчки: {p['score']}/{p['max_score']}\n"
        f"Задач: {p['tasks_done']}/{p['tasks_total']}\n\n🎯 Цели:\n{goals}"
    )


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    daily = load_daily()
    today = get_today_str()
    if today not in daily or not daily[today].get("tasks"):
        await update.message.reply_text("📋 План не сформирован. /morning")
        return
    
    tasks = load_tasks()
    task_map = {t["id"]: t for t in tasks}
    today_data = daily[today]
    completed = today_data.get("completed_tasks", [])
    
    text = "🎯 План:\n\n"
    for i, tid in enumerate(today_data["tasks"], 1):
        t = task_map.get(tid)
        if t:
            text += f"{'✅' if tid in completed else '⬜'} {i}) {t['text']}\n"
    text += f"\nОтмечено: {today_data.get('done_task_count', 0)}/{len(today_data['tasks'])}"
    await update.message.reply_text(text)


async def cmd_pinok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_today_progress()
    await update.message.reply_text(f"👊 {get_random_kick()}\n\n📊 {p['checkins']} чек-инов, {p['score']}/{p['max_score']} очков")


async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_morning_message(context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_completed_tasks(update, context):
        return
    if await handle_carry_selection(update, context):
        return


def schedule_daily_jobs(context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    for name in ["morning_weekday", "morning_weekend", "evening_tasks"]:
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    
    context.job_queue.run_daily(send_morning_message, time=parse_time(settings.get("weekday_wakeup", "06:00")), days=(0,1,2,3,4), name="morning_weekday")
    context.job_queue.run_daily(send_morning_message, time=parse_time(settings.get("weekend_wakeup", "08:00")), days=(5,6), name="morning_weekend")
    context.job_queue.run_daily(send_evening_tasks_request, time=parse_time(settings.get("workday_end", "22:30")), name="evening_tasks")
    logger.info("Jobs scheduled")


def main():
    ensure_data_dir()
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("pinok", cmd_pinok))
    app.add_handler(CommandHandler("morning", cmd_morning))
    app.add_handler(CallbackQueryHandler(handle_role_selection, pattern="^role_"))
    app.add_handler(CallbackQueryHandler(handle_checkin_response, pattern="^checkin_"))
    app.add_handler(CallbackQueryHandler(handle_evening_choice, pattern="^evening_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
