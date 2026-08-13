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
from urllib.parse import quote_plus, urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import UnifiedCache
from ..schemas import (
    SiteType,
    SourceClassification,
    SourceRegistrationResult,
    SourceType,
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


# ============================================================================
# Per-source шаблоны URL поиска (Feature: per-source search URL templates)
# ============================================================================

# Шаблон URL поиска по умолчанию: универсальный /search?q=.
# Плейсхолдер ``{q}`` заменяется на percent-кодированный поисковый параметр.
DEFAULT_SEARCH_URL_TEMPLATE = '/search?q={q}'

# Реестр per-source шаблонов URL поиска.
#
# Ключ — hostname (или его подстрока), значение — шаблон пути с плейсхолдером
# ``{q}``. Решает проблему «универсальный /search?q= поддерживается не всеми
# сайтами»: например, hh.ru (job-board) отдаёт 404 на /search?q=, но понимает
# /search/vacancy?text=. Источники, отсутствующие в реестре, используют
# ``DEFAULT_SEARCH_URL_TEMPLATE``.
_SEARCH_URL_TEMPLATES: dict[str, str] = {
    # Job-board: поиск вакансий по названию компании (без кавычек).
    'hh.ru': '/search/vacancy?text={q}',
    'habr.com': '/search?q={q}',
    # Госзакупки / реестры: поиск по ИНН (query-параметр q).
    'zakupki.gov.ru': '/search?q={q}',
    'fedresurs.ru': '/search?q={q}',
    'kad.arbitr.ru': '/search?q={q}',
    'nalog.ru': '/search?q={q}',
    'egrul.nalog.ru': '/search?q={q}',
    'fips.ru': '/search?q={q}',
}


class SearchUrlTemplateRegistry:
    """Выбирает шаблон URL поиска по источнику (с fallback на универсальный).

    Позволяет задавать специфичный для источника путь поиска (например,
    ``hh.ru -> /search/vacancy?text={q}``) вместо жёстко заданного
    ``/search?q=``. Если для источника нет шаблона — используется
    ``DEFAULT_SEARCH_URL_TEMPLATE``.
    """

    def __init__(self, templates: dict[str, str] | None = None) -> None:
        self._templates = dict(
            templates if templates is not None else _SEARCH_URL_TEMPLATES
        )

    def resolve(self, source_name: str) -> str:
        """Шаблон пути для источника или универсальный по умолчанию."""
        host = extract_host(source_name)
        for candidate, template in self._templates.items():
            if candidate in host or host in candidate:
                return template
        return DEFAULT_SEARCH_URL_TEMPLATE

    def build_url(self, source_name: str, search_param: str) -> str:
        """Строит полный URL поиска для источника.

        ``search_param`` percent-кодируется через ``quote_plus`` (пробелы ->
        ``+``, кириллица -> UTF-8 percent-последовательности), чтобы исключить
        провалы FAST-стратегии из-за ``ValueError`` на control-символах и
        ``UnicodeEncodeError`` (ascii codec) в ``urllib.request``.
        """
        host = extract_host(source_name)
        template = self.resolve(source_name)
        url = f'https://{host}{template}'
        return url.replace('{q}', quote_plus(search_param))

    def build_base_url(self, source_name: str) -> str:
        """Строит строку поиска БЕЗ подставленного аргумента запроса.

        Например для ``ptsecurity.com`` вернёт
        ``https://ptsecurity.com/search?q=``.
        Используется как ``meta.source_request_url`` (наш поисковый шаблон,
        один на всю выгрузку), в отличие от ``build_url``, который содержит
        конкретный поисковый параметр и идёт в ``items[].url``.
        """
        host = extract_host(source_name)
        template = self.resolve(source_name)
        return f'https://{host}{template}'


def build_search_url(source_name: str, search_param: str) -> str:
    """Строит URL поиска из имени источника (полный URL или домен).

    Тонкая обёртка над ``SearchUrlTemplateRegistry``: для известных источников
    используется per-source шаблон (``hh.ru -> /search/vacancy?text=``),
    для остальных — универсальный ``/search?q=``.

    Из ``source_name`` извлекается hostname, чтобы избежать битого адреса
    ``https://https://lenta.ru//search?...`` при полном URL в ``Source.name``.

    ``search_param`` percent-кодируется через ``quote_plus`` (пробелы -> ``+``,
    кириллица -> UTF-8 percent-последовательности), чтобы исключить провалы
    FAST-стратегии из-за ``ValueError`` на control-символах и
    ``UnicodeEncodeError`` (ascii codec) в ``urllib.request``.
    """
    return SearchUrlTemplateRegistry().build_url(source_name, search_param)


# ============================================================================
# Source-aware выбор поискового параметра (Feature: search param resolver)
# ============================================================================

# Домены государственных реестров/органов, где поиск даёт положительный ответ
# именно по ИНН. Дублирует классификацию (SourceType.REGISTRY), но добавляет
# надёжный fallback для неизвестных госдоменов без скачивания страницы.
_REGISTRY_INN_DOMAINS = (
    'fedresurs.ru',
    'fips.ru',
    'zakupki.gov.ru',
    'kad.arbitr.ru',
    'nalog.ru',
    'egrul.nalog.ru',
)

# Типы сайтов, где предпочтителен поиск по ИНН (госреестры/госорганы).
_INN_SITE_TYPES = frozenset({SiteType.GOVERNMENT, SiteType.LEGAL})


class SearchParamResolver:
    """Определяет поисковый параметр для конкретного источника.

    Проблема: на сайтах госорганов поиск даёт положительный ответ по ИНН, а на
    остальных — по названию конкурента. Универсальный приоритет ``ИНН ->
    trigger -> название`` не работает: многие сайты не индексируют ИНН (напр.
    hh.ru возвращает 404 на поиск по ИНН).

    Решение: по расширенной классификации источника определяется, предпочитает
    ли источник поиск по ИНН (``SourceType.REGISTRY`` / ``SiteType.GOVERNMENT``
    / ``SiteType.LEGAL`` / домен из ``_REGISTRY_INN_DOMAINS``). Если да — берём
    ИНН, иначе — название конкурента (``trigger`` или ``competitor``).
    """

    def __init__(
        self,
        registry_inn_domains: tuple[str, ...] | None = None,
        inn_site_types: frozenset[SiteType] | None = None,
    ) -> None:
        self._registry_inn_domains = (
            registry_inn_domains or _REGISTRY_INN_DOMAINS
        )
        self._inn_site_types = (
            inn_site_types if inn_site_types is not None else _INN_SITE_TYPES
        )

    def prefers_inn(
        self,
        source_name: str,
        classification: SourceClassification | None = None,
        source_type: SourceType | None = None,
        site_type: SiteType | None = None,
    ) -> bool:
        """True, если для источника предпочтителен поиск по ИНН.

        Приоритет: явный ``source_type``/``site_type``, затем классификация,
        затем fallback по домену источника.
        """
        if source_type is not None and source_type == SourceType.REGISTRY:
            return True
        if site_type is not None and site_type in self._inn_site_types:
            return True

        if classification is not None:
            if classification.source_type == SourceType.REGISTRY:
                return True
            site_type = getattr(classification, 'site_type', None)
            if site_type is not None and site_type in self._inn_site_types:
                return True

        try:
            host = extract_host(source_name)
        except ValueError:
            host = ''
        return any(domain in host for domain in self._registry_inn_domains)

    def missing_inn(
        self,
        source_name: str,
        competitor_inn: str | None,
        trigger: str | None,
        classification: SourceClassification | None = None,
        source_type: SourceType | None = None,
        site_type: SiteType | None = None,
    ) -> bool:
        """True, если для источника нужен ИНН, но у конкурента его нет.

        Для гос. источника (поиск по ИНН) без ИНН у конкурента поиск не имеет
        смысла — его следует пропустить и зафиксировать ошибку ``not INN``
        вместо выполнения бесполезного запроса по названию (которое госсайт не
        проиндексировал) и попадания некорректных данных в БД.

        ``trigger`` считается ИНН, если состоит из 10 или 12 цифр.
        """
        if not self.prefers_inn(
            source_name,
            classification=classification,
            source_type=source_type,
            site_type=site_type,
        ):
            return False
        if competitor_inn:
            return False
        if trigger and trigger.isdigit() and len(trigger) in (10, 12):
            return False
        return True

    def resolve(
        self,
        source_name: str,
        competitor_inn: str | None,
        competitor: str | None,
        trigger: str | None,
        classification: SourceClassification | None = None,
        source_type: SourceType | None = None,
        site_type: SiteType | None = None,
    ) -> str:
        """Возвращает поисковый параметр для источника.

        Для источников, предпочитающих ИНН (гос. реестры), приоритет:
        ``competitor_inn`` -> ``trigger`` (если это ИНН) -> ``competitor``.

        Для всех остальных (не-гос. источники) поиск идёт **по названию
        конкурента** ``competitor``, а не по триггеру: триггер (ключевое слово)
        не является названием компании и часто не даёт результатов о
        конкретном конкуренте (напр. поиск на hh.ru по триггеру "Москва" не
        находит вакансии ООО "АРХИТЕХ ИИ"). ``trigger`` используется как
        fallback, если название конкурента пустое.
        """
        if self.prefers_inn(
            source_name,
            classification=classification,
            source_type=source_type,
            site_type=site_type,
        ):
            if competitor_inn:
                return competitor_inn
            if trigger and trigger.isdigit() and len(trigger) in (10, 12):
                return trigger

        return competitor or trigger or ''


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
