"""
AdaptiveParser — интеллектуальный парсинг с анализом структуры HTML.

Поток:
1. Получить HTML через Orchestrator
2. Анализ структуры (извлечение селекторов)
3. Сохранение адаптера в кэш
4. Парсинг HTML в элементы
5. Валидация через Quality Gates
6. Конвертация в результат

Извлечение элементов по CSS-селекторам выполняется через ``BeautifulSoup``
(bs4), что обеспечивает корректную обработку вложенных контейнеров в
отличие от прежнего упрощённого ``HTMLParser``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.config import settings

from ..core.cache import UnifiedCache
from ..core.quality import DataQualityGate
from ..logger import new_trace_id
from ..schemas import (
    AdapterState,
    AdaptiveParseResult,
    SourceClassification,
    StrategyResult,
    StrategyType,
)
from ..strategies.classifier import SourceClassifier
from ..strategies.orchestrator import AgenticOrchestrator
from .html_cleaner import HtmlCleaner
from .llm import AIAgent, LLMClient
from .relevance import RelevanceFilter

logger = logging.getLogger(__name__)

# Максимальное количество новостей, собираемых за один проход пагинации.
DEFAULT_MAX_NEWS = settings.bp1_max_news_per_source

# Минимальная длина текста, при которой результат извлечения считается
# успешным (для каскада CSS → LLM → сниппет).
MIN_ARTICLE_TEXT_LENGTH = settings.bp1_min_article_text_length

# Максимальное количество одновременно докачиваемых статей (глубокий фетч).
MAX_CONCURRENT_FETCHES = settings.bp1_max_concurrent_fetches

# Таймаут (в секундах) на извлечение полного текста одной статьи. Защищает
# глубокий фетч от зависания на проблемной странице, чтобы медленная статья
# не занимала слот конкурентности и не лишала остальные новости полного
# текста (раньше первые 1-2 статьи «съедали» все ресурсы, а остальные падали
# в сниппет-фолбэк).
ARTICLE_FETCH_TIMEOUT_SECONDS = settings.bp1_article_fetch_timeout_seconds

# Режим фильтрации релевантности (off/filter/rank) и порог по умолчанию.
RELEVANCE_MODE = getattr(settings, 'bp1_relevance_mode', 'off')
RELEVANCE_THRESHOLD = float(getattr(settings, 'bp1_relevance_threshold', 0.6))

# Включает LLM-обогащение событий структурированными полями.
ENRICHMENT_ENABLED = bool(getattr(settings, 'bp1_enrichment_enabled', False))

# Минимальное количество символов, при котором извлечённый LLM/CSS текст
# считается полным. Если текст короче — вероятна обрезка, и нужна докачка
# хвоста.
MIN_FULL_ARTICLE_TEXT_LENGTH = settings.bp1_min_full_article_text_length

# Максимальное количество итераций докачки обрезанного хвоста статьи.
MAX_TAIL_FETCH_ATTEMPTS = settings.bp1_max_tail_fetch_attempts

# Максимальное количество байт исходного HTML, отдаваемых LLM в одном запросе
# докачки хвоста (смещение по оффсету в конец документа).
TAIL_FETCH_CHUNK_SIZE = 12000

# Служебные пути URL, которые не являются элементами данных и должны быть
# отброшены при извлечении (логин, регистрация, cookie-политика и т.п.).
# Проверяются по подстроке пути — работают независимо от того, в каком теге
# живёт ссылка на странице (nav, div, span и т.д.).
_NOISE_URL_PATTERNS: tuple[str, ...] = (
    '/account/',
    '/login',
    '/signup',
    '/register',
    '/logout',
    '/recover',
    '/reset',
    '/article/cookie_policy',
    '/cookie_policy',
    '/privacy',
    '/favicon',
)


def _is_noise_url(url: str) -> bool:
    """Возвращает True, если URL является служебным и его нужно отбросить.

    Проверяет по подстроке пути из ``_NOISE_URL_PATTERNS``. Логин, cookie-
    политика и подобные служебные ссылки не являются элементами данных: они
    дублируются на странице и порождают ложные ``duplicate key`` на уровне
    CONSISTENCY-карантина.

    Не отбрасываются: пустые/корневые ссылки и обычные навигационные пункты
    (например ``/#forburger`` или ``mailto:``) — они не служебные и должны
    сохраняться.
    """
    if not url or not isinstance(url, str):
        return False

    path = url.split('?', 1)[0].split('#', 1)[0]
    if any(pattern in path for pattern in _NOISE_URL_PATTERNS):
        return True
    # Служебные ссылки ограничены шаблонами выше. Не-HTTP(S) ссылки
    # (``mailto:``, ``tel:``, ``javascript:``) не считаются шумом здесь:
    # их отфильтровывает ``_is_fetchable_url`` на уровне кандидатов.
    return False


def _reject_non_http_scheme(url: str) -> bool:
    """Возвращает True для явных не-HTTP(S) схем
    (``mailto:``, ``tel:``, ``javascript:``).

    Относительные ссылки (без ``:``) и обычные URL пропускаются — они
    нормализуются в абсолютные через ``_to_absolute``.
    """
    if not url or not isinstance(url, str):
        return False
    if ':' not in url:
        return False
    scheme = url.split(':', 1)[0].lower()
    return scheme not in ('http', 'https')


def _to_absolute(url: str, base_url: str) -> str:
    """Превращает относительный путь в полный абсолютный URL.

    Схема/домен берутся из ``base_url`` (URL страницы результата поиска).
    Уже абсолютные ссылки (``http://``, ``https://``, ``mailto:``) возвращаются
    без изменений, чтобы не ломать другие типы ссылок.

    Args:
        url: Ссылка, извлечённая из заголовка новости (может быть
            относительной, например ``/about/news/...``).
        base_url: Базовый URL страницы, на которой найдена ссылка.

    Returns:
        Полный абсолютный URL.
    """
    if not url or not isinstance(url, str):
        return ''
    if '://' in url:
        return url
    return urljoin(base_url, url)


def _is_fetchable_url(url: str) -> bool:
    """Возвращает True, если по URL можно выполнить HTTP-запрос.

    Отфильтровывает ``mailto:``, ``tel:``, ``javascript:`` и прочие схемы, не
    являющиеся ``http``/``https``. Такие ссылки не скачиваются стратегиями
    обхода (FAST/CRAWL4AI/BROWSER падают на них с ошибкой URL scheme), поэтому
    на уровне глубокого фетча они пропускаются, а элемент остаётся со
    сниппетом-заголовком.
    """
    if not url or not isinstance(url, str):
        return False
    scheme = url.split(':', 1)[0].lower()
    return scheme in ('http', 'https')


class _LinkCollector(HTMLParser):
    """Собирает ссылки и заголовки из HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_text: list[str] = []
        self._in_a = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        if tag == 'a':
            self._in_a = True
            self._current_text = []
            href = dict(attrs).get('href')
            if href:
                self._pending_href = href

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self._in_a:
            self._in_a = False
            text = ' '.join(self._current_text).strip()
            href = getattr(self, '_pending_href', '')
            # Относительные ссылки (без ``:``) сохраняются — они станут
            # абсолютными через ``_to_absolute``. Не-HTTP(S) схемы
            # (``mailto:``, ``tel:``, ``javascript:``) в парсинг не попадают.
            if text and href and not _reject_non_http_scheme(href):
                self.links.append((text, href))


def _extract_by_selectors(
    html: str, selectors: dict[str, str]
) -> list[dict[str, str]]:
    """Извлекает элементы по CSS-селекторам через BeautifulSoup.

    Для каждого контейнера (``selectors['container']``) извлекает поля
    (title, text, url, published_at, region, media_name) по соответствующим
    селекторам. Корректно обрабатывает вложенные контейнеры.

    Args:
        html: Исходный HTML.
        selectors: Словарь ``{поле: css-селектор}``, где ``container`` —
            селектор контейнера элемента.

    Returns:
        Список извлечённых элементов (словарей с полями).
    """
    container_selector = (selectors.get('container') or '').strip()
    if not container_selector:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.select(container_selector)
    items: list[dict[str, str]] = []

    for container in containers:
        item: dict[str, str] = {}
        for field, selector in selectors.items():
            if field == 'container' or not selector:
                continue
            node = container.select_one(selector)
            if node is None:
                continue
            if field == 'url':
                href = node.get('href') or node.get('src') or ''
                item[field] = str(href).strip()
            else:
                text = node.get_text(' ', strip=True)
                if text:
                    item[field] = text
        if item:
            items.append(item)

    return items


class AdaptiveParser:
    """
    Интеллектуальный парсер с анализом структуры и адаптивным движком.

    Поток:
    1. Проверка кэша адаптеров
    2. Если адаптер есть → парсинг с сохранёнными селекторами
    3. Если адаптера нет → анализ структуры → генерация адаптера
    4. Сохранение адаптера в кэш
    5. Парсинг HTML в элементы
    6. Валидация качества
    7. Возврат результата
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        logger: logging.Logger | None = None,
        redis_client: Any = None,
    ):
        self._orchestrator = AgenticOrchestrator(
            headless=headless, timeout_ms=timeout
        )
        self._cache = UnifiedCache(redis_client=redis_client)
        self._quality_gate = DataQualityGate()
        self._llm_client = LLMClient(logger=logger)
        self._agent = AIAgent(logger=logger)
        self._classifier = SourceClassifier(logger=logger)
        self._logger = logger or logging.getLogger(__name__)

        # Фильтр семантической релевантности (Фича 1) и обогащение (Фича 3).
        self._relevance = RelevanceFilter(
            self._agent, mode=RELEVANCE_MODE, threshold=RELEVANCE_THRESHOLD
        )
        self._enrichment_enabled = ENRICHMENT_ENABLED

    def bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к кэшу для хранения классификаций."""
        if self._cache.redis is None:
            self._cache.redis = redis_client

    async def parse(
        self,
        url: str,
        source_name: str,
        competitor: str = '',
        trigger: str = '',
        expected_schema: dict[str, Any] | None = None,
        **kwargs,
    ) -> AdaptiveParseResult:
        """
        Основной метод парсинга.

        1. Проверка кэша адаптеров
        2. Если адаптер есть → парсинг с сохранёнными селекторами
        3. Если адаптера нет → анализ структуры → генерация адаптера
        4. Сохранение адаптера в кэш
        5. Парсинг HTML в элементы
        6. Валидация качества
        7. Возврат результата
        """
        trace_id = new_trace_id()
        start = time.monotonic()

        # 1. Проверка кэша адаптеров.
        adapter = await self._cache.get_adapter(source_name)

        # 2. Получение HTML через оркестратор.
        #    Если классификация источника уже сохранена — начинаем с
        #    рекомендованной стратегии, чтобы не сканировать все подряд.
        #    Дополнительно стратегию уточняет LLM-агент
        #    (AIAgent.choose_strategy), что позволяет в ряде стратегий/случаев
        #    обращаться к LLM. При недоступности LLM или невалидном ответе
        #    агент возвращает эвристику.
        #
        #    classification — то, что реально было в кэше ДО этого вызова
        #    (или None). Именно это значение уходит ниже в
        #    _reconcile_classification/_enrich_classification_with_llm —
        #    от него зависит, была ли классификация закэширована раньше.
        #    Подменять его "слепой" классификацией здесь нельзя: тогда
        #    "classification is None" перестанет означать "ничего не было
        #    в кэше", и первый успешный прогон перестанет туда писать.
        start_with: StrategyType | None = None
        classification = await self._cache.get_classification(source_name)

        # Шаг 11 плана рефакторинга (N4): раньше агент консультировался
        # только если классификация уже была в кэше — на первом (холодном)
        # прогоне по источнику агент не участвовал вообще. Строим для него
        # отдельный, не кэшируемый здесь вход: при отсутствии кэша —
        # "слепая" (без HTML) эвристическая классификация по имени/URL.
        # Даже без HTML агент получает source_name/URL в промпте и может
        # опознать конкретный известный сайт по своим знаниям о мире.
        agent_input = classification
        if agent_input is None:
            agent_input = await self._classifier.classify(
                source_name=source_name, source_url=url
            )

        try:
            start_with = StrategyType(agent_input.recommended_strategy)
        except ValueError:
            start_with = None
        # LLM-агент уточняет стратегию обхода по классификации (fallback —
        # эвристика при недоступности LLM). Это ключевая точка, где реально
        # вызывается LLM в боевом конвейере.
        try:
            agent_strategy = await self._agent.choose_strategy(agent_input)
            if agent_strategy is not None:
                start_with = agent_strategy
                self._logger.info(
                    'Агент выбрал стратегию %s для %s (LLM-решение)',
                    agent_strategy.value,
                    source_name,
                )
        except Exception as exc:  # pragma: no cover - зависит от LLM
            self._logger.warning(
                'Ошибка выбора стратегии агентом для %s: %s',
                source_name,
                exc,
            )

        strategy_result = await self._orchestrator.fetch_with_degradation(
            url,
            start_with=start_with,
            source_name=source_name,
        )
        if not strategy_result.success or not strategy_result.data:
            elapsed = int((time.monotonic() - start) * 1000)
            return AdaptiveParseResult(
                status='error',
                source_name=source_name,
                url=url,
                strategy_used=strategy_result.strategy,
                error=strategy_result.error or 'failed to fetch content',
                elapsed_ms=elapsed,
                trace_id=trace_id,
            )

        html = strategy_result.data

        # 2.1 Обновляем классификацию по факту успешного запроса (Шаги 8-9
        #     плана рефакторинга, REFACTORING_PLAN.md — N2/N3).
        await self._reconcile_classification(
            source_name=source_name,
            url=url,
            html=html,
            classification=classification,
            strategy_result=strategy_result,
        )

        # 3. Если адаптера нет — анализируем структуру и генерируем адаптер.
        if adapter is None:
            config = await self._llm_client.analyze_structure(
                html, competitor=competitor
            )
            adapter = AdapterState(
                source_name=source_name,
                # Реальные CSS-селекторы из LLM-анализа (не пустые строки).
                selectors=config.selectors,
                schema_config=config.expected_schema,
                confidence=config.confidence,
            )
            await self._cache.set_adapter(source_name, adapter)

            # 3.1 Уточняем категоризацию через LLM (Шаг 10 плана
            #     рефакторинга, REFACTORING_PLAN.md — N1). Вызывается
            #     только на первом (адаптер ещё не создан) прогоне по
            #     источнику — не на каждом parse(), чтобы не платить
            #     задержку LLM повторно.
            await self._enrich_classification_with_llm(
                source_name=source_name, url=url, html=html
            )

        # 4. Сохраняем скачанную HTML-страницу результата поиска на диск.
        #    Копируем в bp1_html_dir (settings.bp1_data_root/html_pages) и
        #    кладём путь в extra.file_path, откуда его забирает runner.py
        #    при сохранении html_file_path в RawItem. Доступность файла
        #    возвращается через extra.file_saved, чтобы не ломать hashing
        #    (file_path вычищается перед расчётом хэша).
        file_path, file_saved = self._save_html(html, source_name=source_name)

        # 5. Элемент — сама страница результата поиска, а НЕ первая новость.
        #    url = страница поиска (с поисковым запросом), title = собственный
        #    <title> этой страницы. Реальные новости/статьи, найденные на
        #    странице, попадают в extra.news (поля ex_title/ex_url/ex_text).
        #    Поэтому items.title НЕ равен extra.news[].ex_title — разные
        #    страницы.
        items = [
            _make_search_page_item(
                source_name=source_name,
                url=url,
                title=_extract_title(html) or source_name,
            )
        ]

        # 6. Глубокий фетч: докачиваем полный текст статей (пагинация +
        #    полные url) в extra.news. Ключи внутри каждого элемента имеют
        #    префикс ex_ (ex_title/ex_url/ex_text), чтобы не конфликтовать
        #    с обязательными полями item. Выполняется только для новостных
        #    источников (заголовки-ссылки на статьи).
        base_url = url
        news = await self._collect_news_with_pagination(
            base_url=base_url,
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            selectors=adapter.selectors,
            max_news=DEFAULT_MAX_NEWS,
            initial_html=html,
        )

        # Фича 1: семантическая фильтрация нерелевантных новостей.
        # Скоринг каждого элемента относительно конкурента/темы с последующей
        # фильтрацией (filter) или ранжированием (rank). Метрики попадают в
        # extra для аудита качества.
        original_news_count = len(news)
        filtered_news = await self._relevance.apply(
            news, competitor, trigger, inn=None
        )
        relevance_extra = RelevanceFilter.build_extra(
            original_count=original_news_count,
            kept_count=len(filtered_news),
            mode=self._relevance._mode,
        )

        # Фича 3: LLM-обогащение отфильтрованных событий структурированными
        # полями (published_at, author, keywords, summary, компания/ИНН).
        if self._enrichment_enabled and filtered_news:
            filtered_news = await self._enrich_news(
                filtered_news, competitor, trigger
            )

        for item in items:
            extra = item.setdefault('extra', {})
            extra['news'] = filtered_news
            extra.update(relevance_extra)
            if file_path:
                extra['file_path'] = file_path
            extra['file_saved'] = file_saved

        # 7. Валидация качества.
        reports = self._quality_gate.validate_all(items)
        quality_ok = self._quality_gate.is_all_passed(reports)

        elapsed = int((time.monotonic() - start) * 1000)
        return AdaptiveParseResult(
            status='ok' if quality_ok else 'low_quality',
            source_name=source_name,
            url=url,
            strategy_used=strategy_result.strategy,
            items=items,
            raw_text=html,
            adapter_version=adapter.version,
            elapsed_ms=elapsed,
            trace_id=trace_id,
        )

    # ------------------------------------------------------------------
    # Обновление классификации по факту успешного запроса
    # ------------------------------------------------------------------

    async def _reconcile_classification(
        self,
        source_name: str,
        url: str,
        html: str,
        classification: SourceClassification | None,
        strategy_result: StrategyResult,
    ) -> None:
        """Обновляет кэш классификации по факту успешного запроса.

        Объединяет два уточнения (Шаги 8-9 плана рефакторинга,
        REFACTORING_PLAN.md — N2/N3):

        1. (Шаг 8) ``recommended_strategy`` — стратегия, которая реально
           сработала (``strategy_result.strategy``), а не та, что была
           предсказана до запроса. Раньше кэшировалась один раз и не
           обновлялась — каждый повторный прогон по источнику заново
           проходил всю лестницу деградации, прежде чем дойти до рабочей
           стратегии.
        2. (Шаг 9) ``has_antibot``/``has_captcha``/``is_spa`` —
           доопределяются по реальному HTML (``SourceClassifier.classify()``
           раньше вызывался без html/headers и не мог их определить для
           источников вне жёстко прошитого ``_KNOWN_SOURCES``) и по тому,
           какая стратегия потребовалась для успеха: сама по себе успешная
           STEALTH/HITL — сильный сигнал наличия защиты, даже если её
           маркеров не видно в уже обойдённом HTML. Флаги только
           усиливаются (``False -> True``) и никогда не сбрасываются
           обратно одним снимком HTML — отсутствие маркера в конкретном
           ответе не опровергает ранее подтверждённую защиту.

        Ничего не пишет в кэш, если ни один признак не изменился —
        не тратим запись в Redis на каждый успешный прогон впустую.
        """
        detected = await self._classifier.classify(
            source_name=source_name, source_url=url, html=html
        )
        actual_strategy = strategy_result.strategy
        has_antibot = detected.has_antibot or actual_strategy in (
            StrategyType.STEALTH,
            StrategyType.HITL,
        )
        has_captcha = (
            detected.has_captcha or actual_strategy == StrategyType.HITL
        )
        is_spa = detected.is_spa or actual_strategy == StrategyType.BROWSER

        base = classification or detected
        changed = (
            classification is None
            or base.recommended_strategy != actual_strategy.value
            or base.has_antibot != has_antibot
            or base.has_captcha != has_captcha
            or base.is_spa != is_spa
        )
        if not changed:
            return

        updated = base.model_copy(
            update={
                'recommended_strategy': actual_strategy.value,
                'has_antibot': has_antibot,
                'has_captcha': has_captcha,
                'is_spa': is_spa,
            }
        )
        await self._cache.set_classification(source_name, updated)
        self._logger.info(
            'Классификация %s обновлена по факту успеха: strategy=%s '
            'antibot=%s captcha=%s spa=%s',
            source_name,
            actual_strategy.value,
            has_antibot,
            has_captcha,
            is_spa,
        )

    async def _enrich_classification_with_llm(
        self, source_name: str, url: str, html: str
    ) -> None:
        """Уточняет закэшированную классификацию через LLM (Шаг 10, N1).

        ``LLMClient.classify_with_llm()`` — самый детальный инструмент
        категоризации пакета (20 типов сайта, бизнес- и технические
        признаки, промпт ``SITE_CLASSIFICATION_PROMPT_V2``), но раньше не
        вызывался из боевого конвейера ни разу — только из ручного
        smoke-теста. Использует другую доменную схему
        (``ExtendedSiteClassification``), чем ``SourceClassification``,
        которая реально управляет выбором стратегии, поэтому сливаем
        осторожно:

        - ``source_type`` НЕ трогаем: ``to_source_classification()``
          всегда возвращает ``SourceType.UNKNOWN`` — это ограничение
          конвертера (``ExtendedSiteClassification`` не хранит
          ``SourceType``), а не сигнал от LLM, который можно доверять
          больше эвристики.
        - ``has_antibot``/``has_captcha``/``is_spa`` только усиливаются
          (``False -> True``), как и в ``_reconcile_classification``
          (Шаг 9) — неуверенный или ошибочный LLM-ответ не должен отменить
          уже подтверждённую эвристикой/стратегией защиту.
        - ``recommended_strategy`` НЕ трогаем: это эмпирический факт
          (реально сработавшая стратегия, Шаг 8), предсказание LLM до
          попытки не может быть надёжнее уже подтверждённого результата.

        Не пробрасывает исключения: сбой LLM (таймаут, невалидный ответ)
        не должен ронять сбор — при ошибке классификация остаётся такой,
        какой её оставили эвристика/Шаг 8-9.
        """
        try:
            extended = await self._llm_client.classify_with_llm(html, url)
        except Exception as exc:  # pragma: no cover - зависит от LLM
            self._logger.warning(
                'Ошибка LLM-категоризации источника %s: %s', source_name, exc
            )
            return

        llm_derived = extended.to_source_classification()
        current = await self._cache.get_classification(source_name)
        base = current or llm_derived

        has_antibot = base.has_antibot or llm_derived.has_antibot
        has_captcha = base.has_captcha or llm_derived.has_captcha
        is_spa = base.is_spa or llm_derived.is_spa

        changed = (
            current is None
            or base.has_antibot != has_antibot
            or base.has_captcha != has_captcha
            or base.is_spa != is_spa
        )
        if not changed:
            return

        updated = base.model_copy(
            update={
                'has_antibot': has_antibot,
                'has_captcha': has_captcha,
                'is_spa': is_spa,
            }
        )
        await self._cache.set_classification(source_name, updated)
        self._logger.info(
            'Классификация %s уточнена через LLM (site_type=%s, '
            'confidence=%.2f)',
            source_name,
            extended.site_type.value,
            extended.confidence,
        )

    # ------------------------------------------------------------------
    # Сохранение HTML на диск
    # ------------------------------------------------------------------

    def _save_html(
        self, html: str, source_name: str
    ) -> tuple[str | None, bool]:
        """Сохраняет скачанную HTML-страницу на диск в ``bp1_html_dir``.

        Файл записывается непосредственно в целевую директорию
        (``settings.bp1_data_root/html_pages``), а не во временную папку
        парсера, как это делают специализированные RPA-адаптеры. Возвращает
        кортеж ``(file_path, saved)``: путь к сохранённому файлу и флаг,
        удалось ли его записать. Путь попадает в ``extra.file_path`` и далее
        используется runner.py для проставления ``html_file_path`` в RawItem.

        Args:
            html: Содержимое HTML-страницы.
            source_name: Имя источника (для уникального имени файла).

        Returns:
            ``(str | None, bool)`` — путь и признак успешного сохранения.
        """
        try:
            target_dir = Path(settings.bp1_html_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            safe = (
                ''.join(
                    c if c.isalnum() or c in '._-' else '_' for c in source_name
                )
                or 'adaptive'
            )
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f'{safe}_{ts}.html'
            file_path = target_dir / filename

            file_path.write_text(html or '', encoding='utf-8')
            self._logger.info('HTML сохранён на диск: %s', file_path)
            return str(file_path), True
        except (OSError, PermissionError) as exc:
            self._logger.error(
                'Не удалось сохранить HTML на диск (%s): %s',
                settings.bp1_html_dir,
                exc,
            )
            return None, False

    # ------------------------------------------------------------------
    # Пагинация и глубокий фетч
    # ------------------------------------------------------------------

    async def _collect_news_with_pagination(
        self,
        base_url: str,
        source_name: str,
        competitor: str,
        trigger: str,
        selectors: dict[str, str],
        max_news: int = DEFAULT_MAX_NEWS,
        initial_html: str | None = None,
    ) -> list[dict[str, Any]]:
        """Собирает новости со страниц пагинации до лимита ``max_news``.

        Каждая страница обрабатывается через ``_page_items`` (извлечение
        заголовков-ссылок), затем по накопленным ссылкам запускается глубокий
        фетч полного текста (каскад CSS → LLM → сниппет).

        Args:
            base_url: URL первой страницы результата поиска.
            source_name: Имя источника.
            competitor: Конкурент.
            trigger: Тема поиска.
            selectors: CSS-селекторы адаптера.
            max_news: Максимальное количество новостей (по умолчанию 50).
            initial_html: HTML первой страницы (уже скачан).

        Returns:
            Список словарей ``{"title", "url", "text"}``.
        """
        candidates: list[tuple[str, str, str]] = []  # (title, url_abs, url_rel)
        seen: set[str] = set()
        page = 1
        html = initial_html

        while len(candidates) < max_news:
            if html is None:
                result = await self._orchestrator.fetch_with_degradation(
                    _pagination_url(base_url, page),
                    source_name=source_name,
                )
                if not result.success or not result.data:
                    break
                html = result.data

            page_items = _page_items(
                html,
                source_name,
                competitor,
                trigger,
                selectors=selectors,
                base_url=base_url,
            )
            added = 0
            for title, url_abs, url_rel in page_items:
                if len(candidates) >= max_news:
                    break
                if url_abs in seen or not url_abs:
                    continue
                seen.add(url_abs)
                candidates.append((title, url_abs, url_rel))
                added += 1

            # Защита от зацикливания: на странице нет новых новостей или
            # больше нет страниц пагинации.
            if added == 0 or page >= self._max_pages(selectors):
                break
            page += 1
            html = None

        # Глубокий фетч полного текста по накопленным ссылкам.
        news = await self._deep_fetch(candidates, source_name, selectors)
        return news

    async def _enrich_news(
        self,
        news: list[dict[str, Any]],
        competitor: str,
        trigger: str,
    ) -> list[dict[str, Any]]:
        """Обогащает события структурированными полями через LLM (Фича 3).

        Для каждого события с полным текстом (``ex_text``) вызывается
        ``AIAgent.enrich_event``; извлечённые поля (published_at, author,
        keywords, summary, mentioned_company/inn, sentiment) добавляются в
        элемент. При недоступности LLM или сбое элемент остаётся без
        обогащения (не ломаем конвейер).

        Args:
            news: Список событий ``(ex_title, ex_url, ex_text, ...)``.
            competitor: Название конкурента.
            trigger: Тема поиска.

        Returns:
            Список событий с добавленным словарём ``ex_enrichment`` (только
            для тех, где извлечение удалось).
        """
        enriched: list[dict[str, Any]] = []
        for entry in news:
            text = entry.get('ex_text') or ''
            if not text:
                enriched.append(entry)
                continue
            data = await self._agent.enrich_event(text, competitor, trigger)
            if data:
                entry = dict(entry)
                entry['ex_enrichment'] = data
            enriched.append(entry)
        return enriched

    def _max_pages(self, selectors: dict[str, str]) -> int:
        """Ограничение числа страниц из конфигурации (если есть)."""
        # По умолчанию пагинация не ограничена (регулируется лимитом новостей).
        return 10000

    async def _deep_fetch(
        self,
        candidates: list[tuple[str, str, str]],
        source_name: str,
        selectors: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Докачивает полный текст для списка новостей (каскад CSS → LLM).

        Каждая статья обрабатывается с ограничением конкурентности
        (``MAX_CONCURRENT_FETCHES``). При сбое всех способов извлечения
        используется сниппет (заголовок), чтобы не терять новость.

        Args:
            candidates: Список ``(title, url_abs, url_rel)``.
            source_name: Имя источника.
            selectors: CSS-селекторы адаптера.

        Returns:
            Список ``{"title", "url", "text"}`` (url — полная ссылка).
        """

        # Приоритет отдаём статьям с настроенным CSS-селектором ``text``
        # (дёшево и быстро), а LLM-фолбэк оставляем для остальных. Так полный
        # текст равномерно распределяется по всем новостям, а не достаётся
        # только первым нескольким, выигравшим гонку за ресурсы.
        def _css_first_key(cand: tuple[str, str, str]) -> tuple[int, int]:
            has_css = bool((selectors or {}).get('text'))
            return (0 if has_css else 1, 0)

        ordered = sorted(candidates, key=_css_first_key)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

        async def _one(cand: tuple[str, str, str]) -> dict[str, Any]:
            title, url_abs, _url_rel = cand
            # Кэш полного текста по URL: повторно не скачиваем страницу и не
            # тратим LLM-токены, если текст уже извлекался ранее.
            cached = await self._cache.get_article_text(url_abs)
            if cached and cached.get('text'):
                text = cached['text']
                method = cached.get('method') or 'cache'
            else:
                try:
                    async with semaphore:
                        text, method = await asyncio.wait_for(
                            self._extract_article_text(
                                url_abs, source_name, selectors
                            ),
                            timeout=ARTICLE_FETCH_TIMEOUT_SECONDS,
                        )
                except TimeoutError:
                    self._logger.warning(
                        'Таймаут извлечения текста статьи: %s', url_abs
                    )
                    text, method = None, 'timeout'
                if not text:
                    text = title  # сниппет-фолбэк: не теряем новость
                    method = 'snippet'
                else:
                    await self._cache.set_article_text(url_abs, text, method)
            # Ключи в extra имеют префикс ex_, чтобы не конфликтовать с
            # обязательными полями item (title/url/text) на уровне BP-2.
            # method — способ получения текста (css/llm/snippet/cache).
            return {
                'ex_title': title,
                'ex_url': url_abs,
                'ex_text': text,
                'ex_method': method,
            }

        return await asyncio.gather(*(_one(c) for c in ordered))

    async def _extract_article_text(
        self,
        url: str,
        source_name: str,
        selectors: dict[str, str],
    ) -> tuple[str | None, str]:
        """Извлекает полный текст статьи по URL (каскад CSS → LLM → сниппет).

        Возвращает кортеж ``(text, method)``, где method — способ получения:
        ``css``, ``llm`` или ``snippet``.

        Не-HTTP(S) ссылки (``mailto:``, ``tel:``, ``javascript:``) не
        скачиваются — ни один движок обхода их не обрабатывает, поэтому сразу
        возвращается сниппет, чтобы не тратить время на бесполезные попытки.
        """
        if not _is_fetchable_url(url):
            return None, 'snippet'
        result = await self._orchestrator.fetch_with_degradation(
            url, source_name=source_name
        )
        if not result.success or not result.data:
            return None, 'snippet'
        html = result.data

        # Этап A: структурное извлечение по CSS-селектору `text`.
        text_selector = (selectors or {}).get('text')
        if text_selector:
            soup = BeautifulSoup(html, 'html.parser')
            node = soup.select_one(text_selector)
            if node is not None:
                text = node.get_text(' ', strip=True)
                if len(text) >= MIN_ARTICLE_TEXT_LENGTH:
                    return text, 'css'

        # Этап B: детерминированное извлечение основного контента
        # (Фича 2). Использует trafilatura/readability-lxml, если доступен
        # (опциональная зависимость), чтобы получить полный текст без
        # затрат токенов LLM. Работает даже без LLM-конфига.
        readable = _extract_main_content(html)
        if readable and len(readable) >= MIN_ARTICLE_TEXT_LENGTH:
            return readable, 'readability'

        # Этап C: LLM-извлечение (fallback при сбое CSS/детерминированного
        # извлечения). Если результат подозрительно короткий или обрывается
        # без финального знака препинания — считаем текст обрезанным и
        # пробуем докачать хвост.
        llm_text = await self._llm_extract_text(html)
        if llm_text and len(llm_text) >= MIN_ARTICLE_TEXT_LENGTH:
            if _looks_truncated(llm_text):
                llm_text = await self._extract_missing_tail(
                    html, llm_text, source_name
                )
            return llm_text, 'llm'

        # Этап D: сниппет из очищенного контента.
        snippet = _plain_text(html)
        if snippet:
            return snippet, 'snippet'
        return None, 'snippet'

    async def _extract_missing_tail(
        self,
        html: str,
        extracted: str,
        source_name: str,
    ) -> str:
        """Докачивает обрезанный хвост статьи по оффсету в исходном HTML.

        LLM-извлечение часто теряет окончание длинных статей из-за лимита
        токенов одного запроса или ограничения числа чанков. Если текст
        оборван (нет финального знака препинания или он слишком короткий),
        идём в конец исходного HTML и повторно извлекаем текст из хвоста,
        приклеивая его к уже полученному.

        Args:
            html: Исходный HTML статьи.
            extracted: Уже извлечённый (обрезанный) текст.
            source_name: Имя источника.

        Returns:
            Полный текст с доклеенным хвостом или исходный текст, если
            докачка не дала нового контента.
        """
        result = extracted
        length = len(html)
        for attempt in range(MAX_TAIL_FETCH_ATTEMPTS):
            if not _looks_truncated(result):
                break
            # Берём окно из конца документа, растущее с каждой попыткой,
            # чтобы захватить всё более ранний хвост.
            offset = max(0, length - TAIL_FETCH_CHUNK_SIZE * (attempt + 1))
            tail_html = html[offset:]
            tail_text = await self._llm_extract_text(tail_html)
            if not tail_text:
                break
            tail_text = tail_text.strip()
            if tail_text in result or not tail_text:
                break
            result = f'{result}\n\n{tail_text}'
        return result

    async def _llm_extract_text(self, html: str) -> str | None:
        """Извлекает основной текст статьи через LLM (если настроен)."""
        try:
            cleaner = HtmlCleaner()
            cleaned = cleaner.clean(html, extract_metadata=False)
            content = cleaned.get('content', '')
            return await self._llm_client.extract_article_text(content)
        except Exception as e:  # pragma: no cover - зависит от LLM
            self._logger.warning('Ошибка LLM-извлечения текста: %s', e)
            return None


def _extract_main_content(html: str) -> str | None:
    """Детерминированно извлекает основной контент статьи (Фича 2).

    Пытается использовать ``trafilatura`` (или ``readability-lxml``), если
    они установлены — опциональные зависимости. Это даёт полный текст
    статьи без затрат токенов LLM и работает даже без LLM-конфига. При
    отсутствии библиотек возвращает ``None`` (каскад идёт дальше к LLM).
    """
    try:
        import trafilatura  # type: ignore

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if extracted and len(extracted) >= MIN_ARTICLE_TEXT_LENGTH:
            return extracted.strip()
    except Exception:
        pass

    try:
        from readability import Document  # type: ignore

        doc = Document(html)
        text = doc.summary(html_partial=True)
        soup = BeautifulSoup(text, 'html.parser')
        content = soup.get_text(' ', strip=True)
        if content and len(content) >= MIN_ARTICLE_TEXT_LENGTH:
            return content
    except Exception:
        pass

    return None


def _plain_text(html: str) -> str:
    """Возвращает плоский текст из HTML (убирает разметку и шум)."""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(
            ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']
        ):
            tag.decompose()
        return soup.get_text(' ', strip=True)
    except Exception:
        return ''


def _looks_truncated(text: str) -> bool:
    """Возвращает True, если извлечённый текст, вероятно, обрезан.

    Длинный текст (больше ``MIN_FULL_ARTICLE_TEXT_LENGTH``), заканчивающийся
    без финального знака препинания, или текст с маркерами обрыва
    (``[...]``, ``…``) считается неполным. Такой результат нуждается в
    докачке хвоста через ``_extract_missing_tail``.
    """
    if not text:
        return False
    stripped = text.rstrip()
    if any(marker in stripped[-8:] for marker in ('...', '…', '[...]')):
        return True
    if len(stripped) < MIN_FULL_ARTICLE_TEXT_LENGTH:
        return False
    return stripped[-1:] not in ('.', '!', '?')


def _pagination_url(base_url: str, page: int) -> str:
    """Возвращает URL страницы пагинации с подставленным номером.

    Если в базовом URL уже есть query-параметр, номер страницы добавляется
    как ``&page=N``, иначе — как ``?page=N``.
    """
    if page <= 1:
        return base_url
    sep = '&' if '?' in base_url else '?'
    return f'{base_url}{sep}page={page}'


def _page_items(
    html: str,
    source_name: str,
    competitor: str,
    trigger: str,
    selectors: dict[str, str],
    base_url: str,
) -> list[tuple[str, str, str]]:
    """Извлекает пары ``(title, url_abs, url_rel)`` из страницы результатов.

    Использует селектор ``container``/``url``/``title`` адаптера, если задан,
    иначе — эвристический сбор ссылок. ``url_abs`` — полный абсолютный URL.
    """
    selectors = selectors or {}
    pairs: list[tuple[str, str]] = []

    # Если задан контейнер, извлекаем элементы по селекторам полей адаптера.
    # Если контейнер есть, но у него нет рабочих селекторов ``url``/``title``
    # (LLM вернул только ``container``, а остальные поля пустые) — по
    # ``_extract_by_selectors`` мы не сможем собрать ни одного элемента
    # (url/title пустые → все отбрасываются). Тогда деградируем к
    # эвристическому сбору ссылок внутри контейнера, чтобы не терять выдачу.
    has_container = bool((selectors.get('container') or '').strip())
    has_field_selectors = bool(selectors.get('url') and selectors.get('title'))

    if has_container and has_field_selectors:
        for raw in _extract_by_selectors(html, selectors):
            url_rel = raw.get('url', '')
            title = raw.get('title', '')
            if (
                _is_noise_url(url_rel)
                or _reject_non_http_scheme(url_rel)
                or not title
            ):
                continue
            pairs.append((title, url_rel))
            if len(pairs) >= DEFAULT_MAX_NEWS:
                break
    else:
        # Эвристический сбор ссылок. Если контейнер задан, ограничиваем сбор
        # его областью (иначе соберутся навигационные ссылки шапки/подвала).
        if has_container:
            soup = BeautifulSoup(html, 'html.parser')
            container = soup.select_one(selectors['container'])
            container_html = str(container) if container is not None else html
        else:
            container_html = html
        collector = _LinkCollector()
        collector.feed(container_html)
        for title, href in collector.links:
            if _is_noise_url(href) or _reject_non_http_scheme(href):
                continue
            pairs.append((title, href))
            if len(pairs) >= DEFAULT_MAX_NEWS:
                break

    return [
        (title, _to_absolute(url_rel, base_url), url_rel)
        for title, url_rel in pairs
    ]


def _extract_title(html: str) -> str | None:
    """Возвращает текст из тега ``<title>`` HTML-страницы (или None)."""
    try:
        soup = BeautifulSoup(html or '', 'html.parser')
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        return None
    return None


def _make_search_page_item(
    source_name: str,
    url: str,
    title: str,
) -> dict[str, Any]:
    """Формирует элемент для самой страницы результата поиска.

    Первая страница — это страница поиска, а не первая новость. Поэтому
    ``url`` = страница поиска (с поисковым запросом), ``title`` = собственный
    ``<title>`` этой страницы. Найденные новости попадают в ``extra.news``
    (поля ex_title/ex_url/ex_text), т.е. ``items.title`` НЕ равен
    ``extra.news[].ex_title`` — это разные страницы.
    """
    return {
        'url': url,
        'title': title,
        'text': None,
        'published_at': None,
        'region': None,
        'media_name': source_name,
        'extra': {},
    }


def _make_item(
    source_name: str,
    competitor: str,
    trigger: str,
    url: str,
    title: str,
    text: str | None = None,
    published_at: str | None = None,
    region: str | None = None,
    media_name: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Формирует элемент данных из извлечённых полей.

    ``competitor``/``trigger`` НЕ попадают в ``extra`` — это поля уровня
    ``meta`` (переносятся в ParsedResponse.meta в bridge.py). URL нормализуется
    до полного абсолютного (``base_url`` = URL страницы результата поиска),
    т.к. относительные ссылки ломают dedup_key и media_domain в BP-2.
    """
    return {
        'url': _to_absolute(url, base_url or ''),
        'title': title,
        'text': text,
        'published_at': published_at,
        'region': region,
        'media_name': media_name or source_name,
        'extra': {},
    }


def _parse_items(
    html: str,
    source_name: str,
    competitor: str,
    trigger: str,
    selectors: dict[str, str] | None = None,
    base_url: str | None = None,
) -> list[dict[str, Any]]:
    """
    Извлекает элементы из HTML.

    Если задан селектор ``container`` — извлекает элементы по селекторам
    адаптера (title, text, url, published_at, region) через BeautifulSoup.
    Иначе использует эвристический парсер ссылок: каждая ссылка с текстом
    становится кандидатом в элемент. ``base_url`` (URL страницы результата
    поиска) используется для нормализации относительных ссылок в полные.
    """
    selectors = selectors or {}

    if selectors.get('container'):
        items: list[dict[str, Any]] = []
        for raw in _extract_by_selectors(html, selectors):
            if _is_noise_url(raw.get('url')) or _reject_non_http_scheme(
                raw.get('url')
            ):
                continue
            items.append(
                _make_item(
                    source_name=source_name,
                    competitor=competitor,
                    trigger=trigger,
                    url=raw.get('url', ''),
                    title=raw.get('title', ''),
                    text=raw.get('text'),
                    published_at=raw.get('published_at'),
                    region=raw.get('region'),
                    media_name=raw.get('media_name'),
                    base_url=base_url,
                )
            )
            if len(items) >= DEFAULT_MAX_NEWS:
                break
        return items

    collector = _LinkCollector()
    collector.feed(html)

    items = []
    for title, href in collector.links:
        if _is_noise_url(href) or _reject_non_http_scheme(href):
            continue
        items.append(
            _make_item(
                source_name=source_name,
                competitor=competitor,
                trigger=trigger,
                url=href,
                title=title,
                base_url=base_url,
            )
        )
        if len(items) >= DEFAULT_MAX_NEWS:
            break
    return items
