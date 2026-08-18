import random
import string

# Можно расширить своим списком словарных ников — они обычно ценнее случайных наборов букв
DICTIONARY = [
    "crypto", "ton", "shop", "game", "pro", "dev", "news", "chat", "team", "club",
    "world", "life", "music", "film", "book", "art", "code", "tech", "market", "trade",
]


def random_candidates(length: int, count: int, use_digits: bool = True) -> list[str]:
    """Случайные варианты заданной длины (username должен начинаться с буквы)."""
    charset = string.ascii_lowercase + (string.digits if use_digits else "")
    result: set[str] = set()
    while len(result) < count:
        first = random.choice(string.ascii_lowercase)
        rest = "".join(random.choice(charset) for _ in range(length - 1))
        result.add(first + rest)
    return list(result)


def dictionary_candidates(min_len: int, max_len: int) -> list[str]:
    return [w for w in DICTIONARY if min_len <= len(w) <= max_len]
