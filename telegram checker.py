"""
Проверка доступности username в Telegram.

ВАЖНО: обычный Bot API не умеет проверять "свободен ли username" — это делается
только через MTProto-метод account.checkUsername, который доступен исключительно
от имени обычного (не бот) Telegram-аккаунта. Поэтому здесь используется Telethon
с api_id/api_hash, которые нужно получить на https://my.telegram.org.

При первом запуске Telethon попросит номер телефона и код подтверждения —
после этого создастся файл сессии, и дальше всё работает без участия человека.
"""

import asyncio
import logging

from telethon import TelegramClient
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import UsernameInvalidError, UsernameOccupiedError, FloodWaitError

log = logging.getLogger("telegram_checker")


class UsernameChecker:
    def __init__(self, api_id: int, api_hash: str, session_name: str = "checker_session"):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self._lock = asyncio.Lock()  # чтобы не долбить API параллельными запросами

    async def start(self):
        await self.client.start()

    async def stop(self):
        await self.client.disconnect()

    async def is_free(self, username: str) -> str:
        """
        Возвращает один из статусов: 'free' | 'taken' | 'invalid' | 'flood' | 'error'
        """
        username = username.strip().lstrip("@")
        if not (5 <= len(username) <= 32):
            return "invalid"

        async with self._lock:
            try:
                result = await self.client(CheckUsernameRequest(username))
                return "free" if result else "taken"
            except UsernameOccupiedError:
                return "taken"
            except UsernameInvalidError:
                return "invalid"
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                return "flood"
            except Exception as e:
                # Реальная сетевая/прочая ошибка — не путаем её с "занят", логируем
                log.warning("Ошибка при проверке @%s: %s", username, e)
                return "error"
