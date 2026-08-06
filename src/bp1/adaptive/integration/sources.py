"""
Регистрация новых источников (BP-1 Adaptive).

Позволяет пользователю добавить источник по ссылке: URL нормализуется до
``scheme://hostname/`` (полный URL, как в ``Source.name``), сайт
классифицируется через ``SourceClassifier``, запись ``Source`` создаётся
в БД (идемпотентно), а классификация сохраняется в Redis для повторного
использования.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import UnifiedCache
from ..schemas import (
    SourceClassification,
    SourceRegistrationResult,
)
from ..strategies.classifier import SourceClassifier

logger = logging.getLogger(__name__)


def extract_host(url_or_domain: str) -> str:
    """Возвращает hostname в нижнем регистре без ведущего ``www.``.

    Принимает и полный URL (``https://www.lenta.ru/news/1``), и голый домен
    (``lenta.ru``). Для не-URL поднимает ``ValueError``.
    """
    value = url_or_domain.strip()
    if not value or any(ch.isspace() for ch in value):
        raise ValueError('Некорректная ссылка на сайт')
    if '://' not in value:
        value = f'https://{value}'
    host = urlsplit(value).hostname
    if not host:
        raise ValueError('Некорректная ссылка на сайт')
    host = host.lower()
    if host.startswith('www.'):
        host = host[4:]
    return host


def normalize_source_url(url: str) -> str:
    """Нормализует URL до вида ``scheme://hostname/``.

    ``https://www.lenta.ru/news/1`` -> ``https://lenta.ru/``.
    Используется как значение ``Source.name``.
    """
    host = extract_host(url)
    split = urlsplit(url if '://' in url else f'https://{url}')
    scheme = split.scheme or 'https'
    return f'{scheme}://{host}/'


def build_search_url(source_name: str, search_param: str) -> str:
    """Строит URL поиска из имени источника (полный URL или домен).

    Из ``source_name`` извлекается hostname, чтобы избежать битого адреса
    ``https://https://lenta.ru//search?...`` при полном URL в ``Source.name``.
    """
    host = extract_host(source_name)
    return f'https://{host}/search?q={search_param}'


class SourceRegistrationService:
    """Регистрация источника: классификация + запись в БД + кэш в Redis."""

    def __init__(self, session: AsyncSession, redis_client=None) -> None:
        self.session = session
        self._cache = UnifiedCache(redis_client=redis_client)
        self._classifier = SourceClassifier()

    async def classify(self, url: str) -> SourceClassification:
        """Классифицирует сайт по hostname и исходному URL."""
        host = extract_host(url)
        return await self._classifier.classify(
            source_name=host,
            source_url=url,
        )

    async def register(
        self, url: str, redis_client=None
    ) -> SourceRegistrationResult:
        """Добавляет источник в БД и сохраняет классификацию в хранилище.

        1. Нормализует URL до ``scheme://hostname/``.
        2. Классифицирует сайт.
        3. Создаёт ``Source``, если такого имени ещё нет (идемпотентно).
        4. Кэширует классификацию в Redis (ключ ``bp1:classification:{host}``).
        """
        if redis_client is not None:
            self._cache.redis = redis_client

        source_name = normalize_source_url(url)
        host = extract_host(url)
        classification = await self.classify(url)

        from src.bp1.models import Source

        stmt = select(Source).where(Source.name == source_name)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            created = False
            source_id = existing.id
        else:
            source = Source(name=source_name)
            self.session.add(source)
            await self.session.flush()
            created = True
            source_id = source.id
            logger.info(
                'Зарегистрирован источник %s (id=%s)', source_name, source_id
            )

        await self._cache.set_classification(host, classification)

        return SourceRegistrationResult(
            host=host,
            source_name=source_name,
            created=created,
            source_id=source_id,
            classification=classification,
        )
