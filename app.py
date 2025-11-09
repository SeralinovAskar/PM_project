import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message

# --- Конфигурация ---
TOKEN = "YOUR_BOT_TOKEN"
DATA_FILE = Path("data.json")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Работа с файлами ---
def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "tasks": [], "sprints": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Хелперы ---
def get_user_role(user_id):
    data = load_data()
    return data["users"].get(str(user_id), "member")

def is_manager(user_id):
    return get_user_role(user_id) == "manager"

async def send_reminder(chat_id, text, delay_seconds):
    await asyncio.sleep(delay_seconds)
    await bot.send_message(chat_id, f"⏰ Напоминание: <b>{text}</b>")

# --- Команды ---
@dp.message(Command("start"))
async def start(message: Message):
    data = load_data()
    uid = str(message.from_user.id)
    if uid not in data["users"]:
        # первый пользователь становится менеджером
        if len(data["users"]) == 0:
            data["users"][uid] = "manager"
            role = "manager"
        else:
            data["users"][uid] = "member"
            role = "member"
        save_data(data)
    else:
        role = data["users"][uid]

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Твоя роль: <b>{role}</b>\n\n"
        "Команды:\n"
        "/addtask — добавить задачу\n"
        "/tasks — список задач\n"
        "/done — отметить задачу выполненной\n"
        "/sprint — создать спринт (менеджер)\n"
        "/remind — установить напоминание\n"
        "/roles — список ролей\n"
        "/setrole — назначить роль"
    )

@dp.message(Command("roles"))
async def show_roles(message: Message):
    data = load_data()
    text = "👥 <b>Роли пользователей:</b>\n"
    for uid, role in data["users"].items():
        text += f"• {uid}: {role}\n"
    await message.answer(text)

@dp.message(Command("setrole"))
async def set_role(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer("❌ Только менеджер может менять роли.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /setrole <user_id> <manager|member>")
        return

    uid, role = args[1], args[2]
    if role not in ["manager", "member"]:
        await message.answer("❗ Роль должна быть 'manager' или 'member'")
        return

    data = load_data()
    data["users"][uid] = role
    save_data(data)
    await message.answer(f"✅ Роль пользователя {uid} изменена на <b>{role}</b>")

@dp.message(Command("addtask"))
async def add_task(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer("❌ Только менеджер может добавлять задачи.")
        return

    args = message.text.replace("/addtask", "").strip()
    if not args:
        await message.answer("Использование: /addtask <описание задачи>")
        return

    data = load_data()
    task = {
        "id": len(data["tasks"]) + 1,
        "text": args,
        "done": False,
        "assigned_to": None
    }
    data["tasks"].append(task)
    save_data(data)
    await message.answer(f"✅ Задача добавлена: <b>{args}</b>")

@dp.message(Command("tasks"))
async def list_tasks(message: Message):
    data = load_data()
    user_id = str(message.from_user.id)
    role = get_user_role(user_id)

    if role == "manager":
        tasks = data["tasks"]
    else:
        tasks = [t for t in data["tasks"] if t.get("assigned_to") in (None, user_id)]

    if not tasks:
        await message.answer("📭 Нет задач для отображения.")
        return

    text = "📋 <b>Текущие задачи:</b>\n\n"
    for task in tasks:
        status = "✅" if task["done"] else "🕓"
        assigned = f"(для {task['assigned_to']})" if task["assigned_to"] else ""
        text += f"{status} <b>{task['id']}</b>. {task['text']} {assigned}\n"

    await message.answer(text)

@dp.message(Command("done"))
async def mark_done(message: Message):
    args = message.text.replace("/done", "").strip()
    if not args.isdigit():
        await message.answer("Использование: /done <номер задачи>")
        return

    task_id = int(args)
    data = load_data()
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["done"] = True
            save_data(data)
            await message.answer(f"✅ Задача <b>{task_id}</b> выполнена.")
            return

    await message.answer("❌ Задача не найдена.")

@dp.message(Command("sprint"))
async def create_sprint(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer("❌ Только менеджер может создавать спринты.")
        return

    args = message.text.replace("/sprint", "").strip()
    if not args:
        await message.answer("Использование: /sprint <название спринта>")
        return

    data = load_data()
    sprint = {
        "id": len(data["sprints"]) + 1,
        "name": args,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    data["sprints"].append(sprint)
    save_data(data)
    await message.answer(f"🚀 Спринт создан: <b>{args}</b>")

@dp.message(Command("remind"))
async def remind_command(message: Message):
    args = message.text.replace("/remind", "").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("Использование: /remind <минуты> <текст>")
        return

    try:
        minutes = int(args[0])
    except ValueError:
        await message.answer("❗ Время должно быть числом (в минутах)")
        return

    text = args[1]
    delay = minutes * 60
    asyncio.create_task(send_reminder(message.chat.id, text, delay))
    await message.answer(f"⏰ Напоминание установлено через {minutes} мин.")

# --- Запуск ---
async def main():
    print("🚀 Agile Bot запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

