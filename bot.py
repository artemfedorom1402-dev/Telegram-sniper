import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from telegram_checker import UsernameChecker
from fragment_checker import check_fragment
from candidate_generator import random_candidates
import storage

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID_RAW = os.getenv("API_ID", "0")
API_HASH = os.getenv("API_HASH", "")
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "300"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

# Проверка настроек при старте — без этого бот падал бы с непонятной ошибкой
if not BOT_TOKEN or "вставьте" in BOT_TOKEN:
    sys.exit("Ошибка: BOT_TOKEN не задан в .env. Откройте .env и впишите токен от @BotFather.")
if not API_ID_RAW.isdigit() or API_ID_RAW == "0":
    sys.exit("Ошибка: API_ID не задан в .env. Получите его на https://my.telegram.org")
if not API_HASH or "вставьте" in API_HASH:
    sys.exit("Ошибка: API_HASH не задан в .env. Получите его на https://my.telegram.org")

API_ID = int(API_ID_RAW)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
checker: UsernameChecker | None = None

STATUS_TEXT = {
    "free": "✅ Свободен",
    "taken": "❌ Занят",
    "invalid": "⚠️ Некорректная длина/формат",
    "flood": "⏳ Лимит запросов Telegram, попробуйте чуть позже",
    "error": "❗ Не удалось проверить (сетевая ошибка), попробуйте ещё раз",
}


async def format_report(username: str) -> str:
    status = await checker.is_free(username)
    lines = [f"@{username}: {STATUS_TEXT.get(status, status)}"]

    if status == "free":
        frag = await check_fragment(username)
        if frag["status"] in ("not_listed", "error"):
            lines.append(f"  Fragment: {frag['note']}")
        else:
            price_part = f", цена: {frag['price']}" if frag["price"] else ""
            lines.append(f"  Fragment: {frag['status']}{price_part} — {frag['url']}")

        n = len(username)
        if n <= 4:
            lines.append("  💎 Очень редкий (≤4 символа)")
        elif n == 5:
            lines.append("  💰 Премиальный (5 символов)")
        elif n <= 7:
            lines.append("  🙂 Неплохой (короткий)")

    return "\n".join(lines)


@dp.message(Command("start", "help"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я ищу свободные Telegram-юзернеймы и проверяю их ликвидность на Fragment.\n\n"
        "Команды:\n"
        "/check имя1 имя2 ... — проверить конкретные ники\n"
        "/scan длина [сколько_найти] — сгенерировать и найти свободные варианты\n"
        "/monitor имя — сообщу, когда ник освободится\n"
        "/unmonitor имя — снять с наблюдения\n"
        "/list — список наблюдаемых ников"
    )


@dp.message(Command("check"))
async def cmd_check(message: Message):
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /check username1 username2 ...")
        return
    await message.answer("Проверяю...")
    reports = [await format_report(u) for u in args[:10]]
    await message.answer("\n\n".join(reports))


@dp.message(Command("scan"))
async def cmd_scan(message: Message):
    parts = message.text.split()[1:]
    if not parts:
        await message.answer("Использование: /scan длина [сколько_найти]")
        return

    try:
        length = int(parts[0])
        target_count = int(parts[1]) if len(parts) > 1 else 3
    except ValueError:
        await message.answer("Длина и количество должны быть числами. Пример: /scan 5 3")
        return

    if not (5 <= length <= 32):
        await message.answer("Telegram-юзернеймы могут быть от 5 до 32 символов. Укажите длину в этом диапазоне.")
        return
    if not (1 <= target_count <= 10):
        await message.answer("Укажите сколько найти от 1 до 10, чтобы не спамить запросами.")
        return

    await message.answer(f"Ищу свободные ники длиной {length}, цель — {target_count} шт...")

    found = []
    checked = 0
    batch_size = 20
    while len(found) < target_count and checked < 500:
        for candidate in random_candidates(length, batch_size):
            checked += 1
            if await checker.is_free(candidate) == "free":
                found.append(candidate)
                if len(found) >= target_count:
                    break

    if not found:
        await message.answer(f"Проверил {checked} вариантов, свободных не нашёл. Попробуйте другую длину.")
        return

    reports = [await format_report(u) for u in found]
    await message.answer(f"Проверено вариантов: {checked}\n\n" + "\n\n".join(reports))


@dp.message(Command("monitor"))
async def cmd_monitor(message: Message):
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /monitor username")
        return
    username = args[0].lstrip("@")
    storage.add(message.chat.id, username)
    await message.answer(f"Слежу за @{username}. Сообщу, как только он освободится.")


@dp.message(Command("unmonitor"))
async def cmd_unmonitor(message: Message):
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /unmonitor username")
        return
    username = args[0].lstrip("@")
    storage.remove(message.chat.id, username)
    await message.answer(f"Снял @{username} с наблюдения.")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    items = storage.get(message.chat.id)
    if not items:
        await message.answer("Список наблюдения пуст.")
        return
    await message.answer("Наблюдаю за:\n" + "\n".join(f"@{u}" for u in items))


async def monitor_loop():
    while True:
        for chat_id, usernames in storage.all_items().items():
            for username in list(usernames):
                if await checker.is_free(username) == "free":
                    try:
                        await bot.send_message(int(chat_id), f"🎉 @{username} освободился!")
                    except Exception:
                        pass
                    storage.remove(int(chat_id), username)
        await asyncio.sleep(MONITOR_INTERVAL)


async def main():
    global checker
    checker = UsernameChecker(API_ID, API_HASH)
    await checker.start()
    asyncio.create_task(monitor_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
