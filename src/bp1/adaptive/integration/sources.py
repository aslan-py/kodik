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
from ..hostname import KNOWN_REGISTRY_DOMAINS, try_extract_host
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
    (``lenta.ru``). Для не-URL поднимает ``ValueError`` (в отличие от
    ``core.cache._canonical_source_name``, здесь невалидный ввод должен
    быть виден пользователю, а не тихо проглочен как ключ кэша). Разбор
    hostname — общий с ``core.cache`` (``adaptive.hostname.try_extract_host``).
    """
    host = try_extract_host(url_or_domain)
    if host is None:
        raise ValueError('Некорректная ссылка на сайт')
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
    # rbc.ru использует query=, не q= (проверено вручную в браузере —
    # реальная форма поиска ведёт на /search?query=...).
    'rbc.ru': '/search?query={q}',
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
# Общий список — adaptive/hostname.py::KNOWN_REGISTRY_DOMAINS.
_REGISTRY_INN_DOMAINS = KNOWN_REGISTRY_DOMAINS

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

    def __init__(
        self,
        session: AsyncSession,
        redis_client=None,
        prober=None,
    ) -> None:
        self.session = session
        self._cache = UnifiedCache(redis_client=redis_client)
        self._classifier = SourceClassifier()
        # Проубер для проверки поискового эндпоинта при регистрации
        # (Шаг 19 плана рефакторинга). Инжектируется, чтобы тесты и
        # программные вызовы не ходили в сеть; при probe_search=True и
        # отсутствии явного проубера создаётся транспорт по умолчанию.
        self._prober = prober

    async def classify(self, url: str) -> SourceClassification:
        """Классифицирует сайт по hostname и исходному URL."""
        host = extract_host(url)
        return await self._classifier.classify(
            source_name=host,
            source_url=url,
        )

    def _default_prober(self):
        """Проубер с реальным HTTP-транспортом (GET + POST)."""
        from .runner import AdaptiveRunner
        from .search_probe import SearchUrlProber

        return SearchUrlProber(
            fetch=AdaptiveRunner._default_probe_fetch,
            looks_like_search_results=AdaptiveRunner._default_looks_like,
            post=AdaptiveRunner._default_probe_post,
        )

    async def probe_search_endpoint(
        self,
        source_name: str,
        classification: SourceClassification | None = None,
    ):
        """Проверяет, отвечает ли поисковый эндпоинт источника.

        Шаг 19 плана рефакторинга: раньше пробинг выполнялся только в
        ``AdaptiveRunner`` при первой боевой задаче, поэтому ``add-source``
        не сообщал, работает ли поиск на источнике вообще.

        Ограничение (осознанное): на этапе регистрации конкурента ещё нет,
        поэтому проверять «нашлась ли цель в выдаче» не по чему —
        выполняется health-check с нейтральным запросом и без
        ``target_name``. Это подтверждает, что эндпоинт отвечает
        осмысленным HTML, но не доказывает, что выбранный query-параметр
        действительно понимается сайтом.

        ``classification`` (если передана — см. ``register()``) позволяет
        эскалировать fetch-транспорт до лестницы деградации оркестратора
        для источников с антибот/SPA-защитой — без неё голый HTTP-запрос
        получит пустой ответ, и health-check ничего не проверит.

        Returns:
            ``ProbedUrl`` найденного варианта или ``None``.
        """
        prober = self._prober or self._default_prober()
        base_url = SearchUrlTemplateRegistry().build_base_url(source_name)
        # Нейтральный запрос: имя самого источника. Не привязан к
        # конкуренту (его на этом этапе нет) и безопасен для любого сайта.
        neutral_query = extract_host(source_name).split('.')[0]
        try:
            return await prober.probe_async(
                base_url=base_url,
                search_query=neutral_query,
                target_name='',
                classification=classification,
            )
        except Exception as e:
            logger.warning(
                'Проверка поискового эндпоинта %s не выполнена: %s',
                source_name,
                e,
            )
            return None

    async def register(
        self,
        url: str,
        redis_client=None,
        probe_search: bool = False,
    ) -> SourceRegistrationResult:
        """Добавляет источник в БД и сохраняет классификацию в хранилище.

        1. Нормализует URL до ``scheme://hostname/``.
        2. Классифицирует сайт.
        3. Создаёт ``Source``, если такого имени ещё нет (идемпотентно).
        4. Кэширует классификацию в Redis (ключ ``bp1:classification:{host}``).
        5. При ``probe_search=True`` — проверяет поисковый эндпоинт и
           кэширует результат на уровне источника (Шаг 19 плана).

        ``probe_search`` выключен по умолчанию: программные вызовы и тесты
        не должны неожиданно ходить в сеть. CLI ``add-source`` включает его.
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

        search_probe = None
        if probe_search:
            search_probe = await self.probe_search_endpoint(
                source_name, classification=classification
            )
            if search_probe is not None:
                # Кэшируем на уровне ИСТОЧНИКА (ключ без поискового
                # запроса). Пер-конкурентный ключ здесь заполнить нельзя:
                # конкурента на этапе регистрации нет, а чужой search_url
                # искал бы не ту компанию. Эта запись используется как
                # подсказка "какой query-параметр понимает сайт" при первом
                # боевом пробинге (AdaptiveRunner._get_or_probe_url).
                try:
                    await self._cache.set_probed_url(source_name, search_probe)
                except Exception as e:
                    logger.warning(
                        'Не удалось закэшировать probed URL для %s: %s',
                        source_name,
                        e,
                    )

        return SourceRegistrationResult(
            host=host,
            source_name=source_name,
            created=created,
            source_id=source_id,
            classification=classification,
            search_probe=search_probe,
        )
