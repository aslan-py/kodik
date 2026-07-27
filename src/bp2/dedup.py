"""dedup_key для BP-2: стабильный хэш бизнес-полей события.

Вынесено в src/bp2 (а не в seed-скриптах — они временные и удаляемые), чтобы
normalize_item и сиды считали ключ ОДНОЙ формулой. Иначе одно и то же событие
получит разные ключи и не склеится через ON CONFLICT (dedup_key UNIQUE).

Формула по ABOUT.md, BP-2 п.4: hash(competitor | norm(title) | published |
region). norm гасит регистр/пунктуацию/пробелы в заголовке, чтобы «Бегемот»
и "бегемот!" дали один ключ.
"""

import hashlib
import re


def norm(s: str | None) -> str:
    """Нормализация строки для ключа: lower, без пунктуации, схлоп пробелов."""
    s = (s or '').lower()
    s = re.sub(r'[^\w\s]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def make_dedup_key(
    competitor: str | None,
    title: str | None,
    published: str | None,
    region: str | None,
) -> str:
    """sha256 бизнес-полей: у одной новости на разных сайтах ключ совпадает."""
    raw = f'{competitor or ""}|{norm(title)}|{published or ""}|{region or ""}'
    return hashlib.sha256(raw.encode()).hexdigest()
