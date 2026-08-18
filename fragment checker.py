"""
Оценка ликвидности username на Fragment (fragment.com).

У Fragment нет официального публичного API, поэтому используется простой
HTML-парсинг страницы https://fragment.com/username/<name>. Это best-effort:
если Fragment поменяет вёрстку сайта, возможно потребуется поправить парсинг.
"""

import re
import aiohttp
from bs4 import BeautifulSoup

FRAGMENT_URL = "https://fragment.com/username/{username}"


async def check_fragment(username: str) -> dict:
    username = username.strip().lstrip("@")
    url = FRAGMENT_URL.format(username=username)
    result = {
        "username": username,
        "url": url,
        "status": "unknown",
        "price": None,
        "note": "",
    }

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            async with session.get(url, timeout=15) as resp:
                status_code = resp.status
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Fragment не всегда отдаёт 404 для несуществующих username — подстраховываемся
        # проверкой текста страницы (эвристика, может потребовать правок при смене вёрстки)
        not_found_markers = ("page not found", "страница не найдена", "not found")
        if status_code == 404 or any(m in text.lower() for m in not_found_markers):
            result["status"] = "not_listed"
            result["note"] = "Не выставлялся на Fragment — короткие/словарные ники обычно ценнее."
            return result

        price_match = re.search(r"(\d[\d\s]*\.?\d*)\s*(TON|\$)", text)

        if "sold" in text.lower():
            result["status"] = "sold"
        elif "auction" in text.lower():
            result["status"] = "on_auction"
        else:
            result["status"] = "listed"

        if price_match:
            result["price"] = f"{price_match.group(1).strip()} {price_match.group(2)}"

    except Exception as e:
        result["status"] = "error"
        result["note"] = f"Не удалось получить данные с Fragment ({e}). Проверьте вручную: {url}"

    return result
