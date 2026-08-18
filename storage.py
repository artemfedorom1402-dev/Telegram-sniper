import json
import os
from threading import Lock

_PATH = "watchlist.json"
_lock = Lock()


def _load() -> dict:
    if not os.path.exists(_PATH):
        return {}
    with open(_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add(chat_id: int, username: str):
    with _lock:
        data = _load()
        chat_list = data.setdefault(str(chat_id), [])
        username = username.lstrip("@")
        if username not in chat_list:
            chat_list.append(username)
        _save(data)


def remove(chat_id: int, username: str):
    with _lock:
        data = _load()
        chat_list = data.get(str(chat_id), [])
        username = username.lstrip("@")
        if username in chat_list:
            chat_list.remove(username)
        _save(data)


def get(chat_id: int) -> list[str]:
    return _load().get(str(chat_id), [])


def all_items() -> dict:
    return _load()
