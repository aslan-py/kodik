"""Общая нормализация hostname источника (BP-1 Adaptive).

Единственный источник истины для разбора «источник в любом виде
(``https://www.lenta.ru/news/1``, ``lenta.ru``, ``LENTA.RU``) -> канонический
hostname без ``www.``». Вынесено в отдельный модуль без внутренних
зависимостей пакета, чтобы им могли пользоваться и ``core.cache`` (ключи
кэша адаптеров/классификации), и ``integration.sources`` (регистрация
источников, поисковые URL) без циклического импорта между ними — раньше
логика была продублирована в обоих местах по этой же причине.
"""

from __future__ import annotations

from urllib.parse import urlsplit


def try_extract_host(value: str) -> str | None:
    """Возвращает hostname в нижнем регистре без ведущего ``www.``.

    Принимает и полный URL (``https://www.lenta.ru/news/1``), и голый домен
    (``lenta.ru``). Возвращает ``None``, если ``value`` пустая, содержит
    пробельные символы или не удаётся распарсить как хост.

    Решение о том, что делать с невалидным вводом, остаётся за вызывающим
    кодом: где-то это должно быть исключение для пользователя (регистрация
    источника по ссылке), где-то — lenient fallback на исходную строку
    (внутренний ключ кэша, где сбой парсинга не должен ронять пайплайн).
    """
    text = (value or '').strip()
    if not text or any(ch.isspace() for ch in text):
        return None
    try:
        host = urlsplit(text if '://' in text else f'https://{text}').hostname
    except Exception:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith('www.'):
        host = host[4:]
    return host
