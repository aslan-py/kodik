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
отличие от прежнего упрощённого ``HTMLParser`` (см. ``selectors.py``).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from core.config import settings

from ...core.cache import UnifiedCache
from ...core.quality import DataQualityGate
from ...logger import new_trace_id
from ...schemas import (
    AdapterState,
    AdaptiveParseResult,
    SourceClassification,
    StrategyResult,
    StrategyType,
)
from ...strategies.classifier import SourceClassifier
from ...strategies.orchestrator import AgenticOrchestrator
from ..html_cleaner import HtmlCleaner
from ..llm import AIAgent, LLMClient
from ..relevance import RelevanceFilter
from . import constants
from .content import (
    _extract_main_content,
    _extract_title,
    _is_confident_article_text,
    _looks_truncated,
    _plain_text,
)
from .pagination import (
    _items_per_page,
    _make_search_page_item,
    _page_items,
    _pagination_url,
)
from .url_utils import _is_fetchable_url

logger = logging.getLogger(__name__)


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
            self._agent,
            mode=constants.RELEVANCE_MODE,
            threshold=constants.RELEVANCE_THRESHOLD,
        )
        self._enrichment_enabled = constants.ENRICHMENT_ENABLED

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
        # Пришёл ли адаптер из кэша (а не создан в этом же прогоне) — от
        # этого зависит самокоррекция при провале качества (Шаг 21 плана
        # рефакторинга): свежесозданный адаптер сбрасывать бессмысленно.
        adapter_from_cache = adapter is not None
        if adapter is not None:
            self._logger.debug(
                'Адаптер %s: selectors=%s', source_name, adapter.selectors
            )

        # 2. Получение HTML через оркестратор. Стратегия обхода уточняется
        #    по кэшированной классификации источника и LLM-агентом (см.
        #    ``_resolve_start_strategy``).
        classification = await self._cache.get_classification(source_name)
        start_with, agent_input = await self._resolve_start_strategy(
            source_name, url, classification
        )

        strategy_result = await self._orchestrator.fetch_with_degradation(
            url,
            start_with=start_with,
            # Та же классификация, что выбрала start_with (реальная из кэша
            # либо слепая), сужает перебор до заведомо небесполезных
            # стратегий вместо полного круга по _DEGRADATION_ORDER.
            classification=agent_input,
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
        adapter = await self._ensure_adapter(
            source_name=source_name,
            url=url,
            competitor=competitor,
            html=html,
            adapter=adapter,
        )

        # 4. Сохраняем скачанную HTML-страницу результата поиска на диск.
        #    Копируем в bp1_html_dir (settings.bp1_data_root/html_pages) и
        #    кладём путь в extra.file_path, откуда его забирает runner.py
        #    при сохранении html_file_path в RawItem. Доступность файла
        #    возвращается через extra.file_saved, чтобы не ломать hashing
        #    (file_path вычищается перед расчётом хэша).
        file_path, file_saved = self._save_html(html, source_name=source_name)

        # 5-6. Элементы: страница результата поиска + собранные новости
        #    (глубокий фетч, фильтрация релевантности, LLM-обогащение).
        items = await self._assemble_items(
            url=url,
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            adapter=adapter,
            html=html,
            strategy_result=strategy_result,
            agent_input=agent_input,
            file_path=file_path,
            file_saved=file_saved,
        )

        # 7. Валидация качества + самокоррекция адаптера.
        quality_ok = await self._run_quality_gate(
            items=items,
            source_name=source_name,
            adapter=adapter,
            adapter_from_cache=adapter_from_cache,
            html=html,
        )

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
    # Выбор стартовой стратегии обхода
    # ------------------------------------------------------------------

    async def _resolve_start_strategy(
        self,
        source_name: str,
        url: str,
        classification: SourceClassification | None,
    ) -> tuple[StrategyType | None, SourceClassification]:
        """Определяет стартовую стратегию обхода и классификацию для запроса.

        ``classification`` — то, что реально было в кэше ДО этого вызова
        (или None). Если в кэше ничего не было (холодный прогон), строится
        отдельный, не кэшируемый здесь вход: "слепая" (без HTML)
        эвристическая классификация по имени/URL — даже без HTML агент
        получает source_name/URL в промпте и может опознать конкретный
        известный сайт по своим знаниям о мире (Шаг 11 плана рефакторинга,
        N4).

        LLM-агент (``AIAgent.choose_strategy``) уточняет стратегию по
        классификации; при недоступности LLM или невалидном ответе
        возвращает эвристику. Это ключевая точка, где реально вызывается
        LLM в боевом конвейере.
        """
        agent_input = classification
        if agent_input is None:
            agent_input = await self._classifier.classify(
                source_name=source_name, source_url=url
            )

        try:
            start_with = StrategyType(agent_input.recommended_strategy)
        except ValueError:
            start_with = None

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

        return start_with, agent_input

    # ------------------------------------------------------------------
    # Получение/создание адаптера
    # ------------------------------------------------------------------

    async def _ensure_adapter(
        self,
        source_name: str,
        url: str,
        competitor: str,
        html: str,
        adapter: AdapterState | None,
    ) -> AdapterState:
        """Возвращает уже закэшированный адаптер или создаёт и кэширует новый.

        Новый адаптер создаётся анализом структуры HTML через LLM. Заодно
        уточняет категоризацию источника через LLM (Шаг 10 плана
        рефакторинга, N1) — только на первом (адаптер ещё не создан)
        прогоне по источнику, не на каждом ``parse()``, чтобы не платить
        задержку LLM повторно.
        """
        if adapter is not None:
            return adapter

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

        await self._enrich_classification_with_llm(
            source_name=source_name, url=url, html=html
        )
        return adapter

    # ------------------------------------------------------------------
    # Сборка items: страница поиска + новости
    # ------------------------------------------------------------------

    async def _assemble_items(
        self,
        url: str,
        source_name: str,
        competitor: str,
        trigger: str,
        adapter: AdapterState,
        html: str,
        strategy_result: StrategyResult,
        agent_input: SourceClassification,
        file_path: str | None,
        file_saved: bool,
    ) -> list[dict[str, Any]]:
        """Строит items: страница результата поиска + собранные новости.

        Элемент — сама страница результата поиска, а НЕ первая новость.
        ``url`` = страница поиска (с поисковым запросом), ``title`` =
        собственный ``<title>`` этой страницы. Реальные новости/статьи,
        найденные на странице, попадают в ``extra.news`` (поля
        ex_title/ex_url/ex_text) — поэтому ``items.title`` НЕ равен
        ``extra.news[].ex_title``, это разные страницы.

        Глубокий фетч (пагинация + полные url) докачивает полный текст
        статей в ``extra.news``. Затем применяется семантическая фильтрация
        нерелевантных новостей (Фича 1) и, если включено, LLM-обогащение
        структурированными полями (Фича 3).
        """
        items = [
            _make_search_page_item(
                source_name=source_name,
                url=url,
                title=_extract_title(html) or source_name,
            )
        ]

        base_url = url
        news = await self._collect_news_with_pagination(
            base_url=base_url,
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            selectors=adapter.selectors,
            max_news=constants.DEFAULT_MAX_NEWS,
            initial_html=html,
            # Переиспользуем стратегию/классификацию, которые уже сработали
            # для страницы листинга — иначе deep-fetch каждой статьи заново
            # вслепую перебирает FAST→CRAWL4AI→BROWSER→... и почти никогда
            # не укладывается в ARTICLE_FETCH_TIMEOUT_SECONDS.
            start_with=strategy_result.strategy,
            classification=agent_input,
        )

        original_news_count = len(news)
        filtered_news = await self._relevance.apply(
            news, competitor, trigger, inn=None
        )
        relevance_extra = RelevanceFilter.build_extra(
            original_count=original_news_count,
            kept_count=len(filtered_news),
            mode=self._relevance._mode,
        )

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

        return items

    # ------------------------------------------------------------------
    # Контроль качества + самокоррекция адаптера
    # ------------------------------------------------------------------

    async def _run_quality_gate(
        self,
        items: list[dict[str, Any]],
        source_name: str,
        adapter: AdapterState,
        adapter_from_cache: bool,
        html: str,
    ) -> bool:
        """Валидирует items через Quality Gates и запускает самокоррекцию.

        Мутирует ``items``: добавляет ``extra.quality_levels`` (Шаг 20 плана
        рефакторинга, T6 — сводка по уровням SCHEMA/TYPES/BUSINESS/VOLUME/
        CONSISTENCY, а не только булев признак ok/low_quality) и, если
        сработала самокоррекция адаптера, ``extra.adapter_review``.

        Returns:
            True, если контроль качества пройден по всем уровням.
        """
        reports = self._quality_gate.validate_all(items)
        quality_ok = self._quality_gate.is_all_passed(reports)

        quality_levels = {
            report.level.value: {
                'passed': report.passed,
                'errors': len(report.errors),
                'warnings': len(report.warnings),
            }
            for report in reports
        }
        for item in items:
            item.setdefault('extra', {})['quality_levels'] = quality_levels

        # Шаг 21 плана рефакторинга (N6): самокоррекция адаптера по итогам
        # контроля качества.
        recommendation = await self._handle_quality_outcome(
            source_name=source_name,
            adapter=adapter,
            adapter_from_cache=adapter_from_cache,
            quality_ok=quality_ok,
            items=items,
            html=html,
        )
        if recommendation:
            for item in items:
                item.setdefault('extra', {})['adapter_review'] = recommendation

        return quality_ok

    # ------------------------------------------------------------------
    # Самокоррекция адаптера по итогам контроля качества
    # ------------------------------------------------------------------

    async def _handle_quality_outcome(
        self,
        source_name: str,
        adapter: AdapterState,
        adapter_from_cache: bool,
        quality_ok: bool,
        items: list[dict[str, Any]],
        html: str,
    ) -> dict[str, Any] | None:
        """Обновляет судьбу закэшированного адаптера по итогам качества.

        Шаг 21 плана рефакторинга (N6). Раньше ``AIAgent.analyze_result``
        и промпт ``RESULT_ANALYSIS_PROMPT`` существовали, но не вызывались
        ниоткуда, а сама рекомендация нигде не применялась — выглядело как
        самокоррекция, которой не было.

        Логика (только для адаптера, пришедшего ИЗ КЭША — свежесозданный
        сбрасывать бессмысленно, он и так только что выведен):

        - качество прошло, а на счётчике были провалы -> счётчик
          сбрасывается (адаптер «выздоровел»);
        - качество не прошло -> ``fail_count`` увеличивается; по достижении
          ``ADAPTER_FAIL_THRESHOLD`` адаптер удаляется из кэша, чтобы на
          следующем прогоне селекторы были выведены заново, а у LLM
          запрашивается диагностическая рекомендация (уходит в
          ``extra.adapter_review`` и в лог — как аудит причины сброса).

        Используется поле ``AdapterState.fail_count``, которое до этого шага
        было объявлено в схеме, но нигде не читалось и не писалось.

        Returns:
            Рекомендация LLM (если запрашивалась) или ``None``.
        """
        if not adapter_from_cache:
            return None

        if quality_ok:
            if adapter.fail_count:
                await self._cache.set_adapter(
                    source_name, adapter.model_copy(update={'fail_count': 0})
                )
                self._logger.info(
                    'Адаптер %s снова даёт качественные данные — счётчик '
                    'провалов сброшен',
                    source_name,
                )
            return None

        fail_count = adapter.fail_count + 1
        if fail_count < constants.ADAPTER_FAIL_THRESHOLD:
            await self._cache.set_adapter(
                source_name,
                adapter.model_copy(update={'fail_count': fail_count}),
            )
            self._logger.info(
                'Качество данных %s не прошло контроль (провал %d/%d) — '
                'адаптер пока сохранён',
                source_name,
                fail_count,
                constants.ADAPTER_FAIL_THRESHOLD,
            )
            return None

        recommendation: dict[str, Any] | None = None
        try:
            recommendation = await self._agent.analyze_result(
                html, items, source_name
            )
        except Exception as exc:  # pragma: no cover - зависит от LLM
            self._logger.warning(
                'Не удалось получить рекомендацию по адаптеру %s: %s',
                source_name,
                exc,
            )

        await self._cache.clear_adapter(source_name)
        self._logger.warning(
            'Адаптер %s сброшен после %d провалов качества подряд — '
            'селекторы будут выведены заново. Рекомендация LLM: %s',
            source_name,
            fail_count,
            (recommendation or {}).get('recommendation', 'n/a'),
        )
        return recommendation

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
        max_news: int = constants.DEFAULT_MAX_NEWS,
        initial_html: str | None = None,
        start_with: StrategyType | None = None,
        classification: SourceClassification | None = None,
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
            start_with: Стратегия, уже сработавшая для страницы листинга —
                переиспользуется для страниц пагинации и deep-fetch статей
                вместо слепого перебора с FAST.
            classification: Классификация источника, сузившая перебор для
                листинга — переиспользуется по той же причине.

        Returns:
            Список словарей ``{"title", "url", "text"}``.
        """
        candidates: list[tuple[str, str, str]] = []  # (title, url_abs, url_rel)
        seen: set[str] = set()
        page = 1
        html = initial_html
        # Размер страницы из метаданных LLM-анализа (если определён) —
        # выбирает стиль пагинации (offset вместо page) и сужает лимит
        # страниц в _max_pages.
        items_per_page = _items_per_page(selectors)

        while len(candidates) < max_news:
            if html is None:
                result = await self._orchestrator.fetch_with_degradation(
                    _pagination_url(base_url, page, items_per_page),
                    source_name=source_name,
                    start_with=start_with,
                    classification=classification,
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

            self._logger.debug(
                'Пагинация %s: page=%d, найдено=%d, добавлено=%d, '
                'всего=%d, items_per_page=%d, max_pages=%d',
                source_name,
                page,
                len(page_items),
                added,
                len(candidates),
                items_per_page,
                self._max_pages(selectors),
            )
            # Защита от зацикливания: на странице нет новых новостей или
            # больше нет страниц пагинации.
            if added == 0 or page >= self._max_pages(selectors):
                break
            page += 1
            html = None

        # Глубокий фетч полного текста по накопленным ссылкам.
        news = await self._deep_fetch(
            candidates,
            source_name,
            selectors,
            start_with=start_with,
            classification=classification,
        )
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
        """Верхний предел страниц пагинации за один прогон источника.

        Раньше возвращал жёстко зашитое ``10000`` — фактически «без
        лимита», и единственным ограничителем длительности прогона был
        ``max_news``. Теперь берётся из конфигурации
        (``settings.bp1_max_pagination_pages``) и дополнительно
        сужается по ``metadata.items_per_page`` адаптера, если LLM его
        определил: чтобы набрать ``DEFAULT_MAX_NEWS`` элементов, при
        ``items_per_page`` на странице достаточно
        ``ceil(max_news / items_per_page)`` страниц — ходить дальше
        бессмысленно.

        Args:
            selectors: Селекторы адаптера (могут содержать
                ``items_per_page`` в метаданных LLM-анализа).

        Returns:
            Максимальное число страниц (не меньше 1).
        """
        limit = constants.MAX_PAGINATION_PAGES
        per_page = _items_per_page(selectors)
        if per_page > 0:
            needed = math.ceil(constants.DEFAULT_MAX_NEWS / per_page)
            limit = min(limit, needed)
        return max(1, limit)

    async def _deep_fetch(
        self,
        candidates: list[tuple[str, str, str]],
        source_name: str,
        selectors: dict[str, str],
        start_with: StrategyType | None = None,
        classification: SourceClassification | None = None,
    ) -> list[dict[str, Any]]:
        """Докачивает полный текст для списка новостей (best-of каскад
        CSS → readability → LLM, см. ``_extract_article_text``).

        Каждая статья обрабатывается с ограничением конкурентности
        (``MAX_CONCURRENT_FETCHES``). При сбое всех способов извлечения
        используется заголовок (``ex_method='snippet_title'``), чтобы не
        терять новость.

        Args:
            candidates: Список ``(title, url_abs, url_rel)``.
            source_name: Имя источника.
            selectors: CSS-селекторы адаптера.
            start_with: Стратегия, уже сработавшая для страницы листинга —
                каждая статья начинает деградацию с неё, а не с FAST.
            classification: Классификация источника — сужает допустимый
                перебор стратегий так же, как для листинга.

        Returns:
            Список словарей ``ex_title``/``ex_url``/``ex_text``/
            ``ex_method``/``ex_text_length``/``ex_text_possibly_incomplete``.
        """

        # Приоритет отдаём статьям с настроенным CSS-селектором ``text``
        # (дёшево и быстро), а LLM-фолбэк оставляем для остальных. Так полный
        # текст равномерно распределяется по всем новостям, а не достаётся
        # только первым нескольким, выигравшим гонку за ресурсы.
        def _css_first_key(cand: tuple[str, str, str]) -> tuple[int, int]:
            has_css = bool((selectors or {}).get('text'))
            return (0 if has_css else 1, 0)

        ordered = sorted(candidates, key=_css_first_key)
        semaphore = asyncio.Semaphore(constants.MAX_CONCURRENT_FETCHES)

        async def _one(cand: tuple[str, str, str]) -> dict[str, Any]:
            title, url_abs, _url_rel = cand
            # Кэш полного текста по URL: повторно не скачиваем страницу и не
            # тратим LLM-токены, если текст уже извлекался ранее.
            cached = await self._cache.get_article_text(url_abs)
            if cached and cached.get('text'):
                text = cached['text']
                method = cached.get('method') or 'cache'
                possibly_incomplete = bool(
                    cached.get('possibly_incomplete', False)
                )
            else:
                try:
                    async with semaphore:
                        text, method, meta = await asyncio.wait_for(
                            self._extract_article_text(
                                url_abs,
                                source_name,
                                selectors,
                                start_with=start_with,
                                classification=classification,
                            ),
                            timeout=constants.ARTICLE_FETCH_TIMEOUT_SECONDS,
                        )
                except TimeoutError:
                    self._logger.warning(
                        'Таймаут извлечения текста статьи: %s', url_abs
                    )
                    text, method, meta = None, 'snippet_title', {}
                if not text:
                    text = title  # сниппет-фолбэк: не теряем новость
                    method = 'snippet_title'
                    possibly_incomplete = True
                else:
                    possibly_incomplete = not meta.get('complete', False)
                    await self._cache.set_article_text(
                        url_abs,
                        text,
                        method,
                        possibly_incomplete=possibly_incomplete,
                    )
            # Ключи в extra имеют префикс ex_, чтобы не конфликтовать с
            # обязательными полями item (title/url/text) на уровне BP-2.
            # method — способ получения текста: css/readability/llm/
            # snippet_page (шумный текст всей страницы)/snippet_title
            # (только заголовок, фетч не удался)/cache.
            return {
                'ex_title': title,
                'ex_url': url_abs,
                'ex_text': text,
                'ex_method': method,
                'ex_text_length': len(text) if text else 0,
                'ex_text_possibly_incomplete': possibly_incomplete,
            }

        return await asyncio.gather(*(_one(c) for c in ordered))

    async def _extract_article_text(
        self,
        url: str,
        source_name: str,
        selectors: dict[str, str],
        start_with: StrategyType | None = None,
        classification: SourceClassification | None = None,
    ) -> tuple[str | None, str, dict[str, Any]]:
        """Извлекает полный текст статьи по URL (best-of каскад).

        Пробует CSS-селектор → readability/trafilatura → LLM и выбирает
        среди успешных попыток самый длинный результат, а не просто первый
        превысивший ``MIN_ARTICLE_TEXT_LENGTH`` — иначе CSS-селектор,
        случайно зацепивший только лид-абзац, останавливал бы каскад и не
        давал шанса дойти до readability/LLM (см. ``_run_extraction_cascade``).
        Останавливается досрочно только когда результат уже "уверенно
        полный" (длиннее ``MIN_FULL_ARTICLE_TEXT_LENGTH`` и не выглядит
        обрезанным).

        ``start_with``/``classification`` — стратегия и классификация,
        уже подтверждённые для страницы листинга того же источника.
        Без них каждая статья заново вслепую перебирает всю цепочку
        деградации (FAST→CRAWL4AI→BROWSER→...), что почти никогда не
        укладывается в ``ARTICLE_FETCH_TIMEOUT_SECONDS`` — на практике это
        и есть основная причина, по которой deep-fetch массово скатывается
        в ``snippet_title``, а не логика каскада CSS/readability/LLM.

        Возвращает кортеж ``(text, method, meta)``, где ``method`` —
        ``css``, ``readability``, ``llm``, ``snippet_page`` (текст всей
        страницы без выделения статьи — может содержать меню/похожие
        новости) или ``snippet_title`` (текста не нашлось вовсе — вызывающий
        код подставит заголовок), а ``meta['complete']`` — уверенность в
        полноте текста.

        Не-HTTP(S) ссылки (``mailto:``, ``tel:``, ``javascript:``) не
        скачиваются — ни один движок обхода их не обрабатывает, поэтому сразу
        возвращается пустой результат, чтобы не тратить время на бесполезные
        попытки.
        """
        empty_meta: dict[str, Any] = {'complete': False, 'chunks_dropped': 0}
        if not _is_fetchable_url(url):
            return None, 'snippet_title', empty_meta
        result = await self._orchestrator.fetch_with_degradation(
            url,
            source_name=source_name,
            # Отдельная статья — не страница результатов поиска: у неё
            # никогда не будет разметки списка (``ul.search-results__list``
            # и т.п.), поэтому BrowserStrategy не должна ждать её появления
            # (см. пояснение у ``wait_for_listing`` в orchestrator.py).
            wait_for_listing=False,
            start_with=start_with,
            classification=classification,
        )
        if not result.success or not result.data:
            self._logger.warning(
                'Deep-fetch не удался для %s (стратегия %s): %s',
                url,
                result.strategy,
                result.error,
            )
            return None, 'snippet_title', empty_meta
        html = result.data

        (
            best_text,
            best_method,
            chunks_dropped,
        ) = await self._run_extraction_cascade(html, selectors)

        if best_text is None or best_method is None:
            # Этап D: сниппет из очищенного контента всей страницы — не
            # выделяет именно статью, может содержать меню/похожие новости.
            return self._snippet_fallback(html, empty_meta)

        # Докачка обрезанного хвоста применяется к победителю независимо
        # от метода — обрыв возможен и у CSS/readability-результата, не
        # только у LLM (сдвиг по офсету в исходном HTML от метода не
        # зависит).
        if _looks_truncated(best_text):
            best_text = await self._extract_missing_tail(
                html, best_text, source_name
            )

        meta = {
            'complete': _is_confident_article_text(best_text),
            'chunks_dropped': chunks_dropped,
        }
        return best_text, best_method, meta

    async def _run_extraction_cascade(
        self, html: str, selectors: dict[str, str]
    ) -> tuple[str | None, str | None, int]:
        """Пробует CSS → readability → LLM и возвращает самый длинный
        результат среди успешных попыток (см. ``_extract_article_text``).

        Returns:
            ``(best_text, best_method, chunks_dropped)`` — ``best_method``
            равен ``None``, если ни один этап не дал текста нужной длины.
        """
        best_text: str | None = None
        best_method: str | None = None
        chunks_dropped = 0

        def _consider(text: str | None, method: str) -> None:
            nonlocal best_text, best_method
            if text and len(text) >= constants.MIN_ARTICLE_TEXT_LENGTH:
                if best_text is None or len(text) > len(best_text):
                    best_text, best_method = text, method

        # Этап A: структурное извлечение по CSS-селектору `text`.
        text_selector = (selectors or {}).get('text')
        if text_selector:
            soup = BeautifulSoup(html, 'html.parser')
            node = soup.select_one(text_selector)
            if node is not None:
                _consider(node.get_text(' ', strip=True), 'css')

        # Этап B: детерминированное извлечение основного контента
        # (Фича 2). Использует trafilatura/readability-lxml, если доступен
        # (опциональная зависимость), чтобы получить полный текст без
        # затрат токенов LLM. Работает даже без LLM-конфига. Пропускается,
        # если этап A уже дал уверенно полный текст.
        if not _is_confident_article_text(best_text):
            readable = _extract_main_content(html)
            _consider(readable, 'readability')

        # Этап C: LLM-извлечение. Пробуется, если CSS/readability не дали
        # уверенно полного текста — не только когда они полностью
        # провалились, иначе короткий лид-абзац "глушит" каскад и мешает
        # LLM достать полный текст статьи.
        if self._should_escalate_to_llm(best_text):
            llm_text, llm_meta = await self._llm_extract_text_with_meta(html)
            chunks_dropped = llm_meta.get('chunks_dropped', 0)
            _consider(llm_text, 'llm')

        return best_text, best_method, chunks_dropped

    @staticmethod
    def _should_escalate_to_llm(best_text: str | None) -> bool:
        """Решает, пробовать ли LLM-извлечение после CSS/readability
        (этап C ``_run_extraction_cascade``).

        Короткий, но формально завершённый текст (например,
        вакансия-однострока) считается естественно коротким и не тратит
        LLM-вызов, если так настроено
        (``settings.bp1_short_text_llm_escalation``).
        """
        escalate = not _is_confident_article_text(best_text)
        if (
            escalate
            and best_text is not None
            and not settings.bp1_short_text_llm_escalation
            and not _looks_truncated(best_text)
        ):
            escalate = False
        return escalate

    @staticmethod
    def _snippet_fallback(
        html: str, empty_meta: dict[str, Any]
    ) -> tuple[str | None, str, dict[str, Any]]:
        """Этап D каскада: сниппет из очищенного контента всей страницы —
        не выделяет именно статью, может содержать меню/похожие новости.
        """
        snippet = _plain_text(html)
        if snippet:
            return snippet, 'snippet_page', empty_meta
        return None, 'snippet_title', empty_meta

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
        for attempt in range(constants.MAX_TAIL_FETCH_ATTEMPTS):
            if not _looks_truncated(result):
                break
            # Берём окно из конца документа, растущее с каждой попыткой,
            # чтобы захватить всё более ранний хвост.
            offset = max(
                0, length - constants.TAIL_FETCH_CHUNK_SIZE * (attempt + 1)
            )
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
        text, _meta = await self._llm_extract_text_with_meta(html)
        return text

    async def _llm_extract_text_with_meta(
        self, html: str
    ) -> tuple[str | None, dict[str, Any]]:
        """Извлекает текст статьи через LLM вместе с метаданными чанкирования.

        ``meta['chunks_dropped']`` > 0 означает, что статья длиннее лимита
        чанкирования и часть текста была молча отброшена (см.
        ``LLMClient._llm_extract_chunked``) — вызывающий код помечает такой
        результат как потенциально неполный, даже если по длине он формально
        прошёл порог.
        """
        try:
            cleaner = HtmlCleaner()
            cleaned = cleaner.clean(html, extract_metadata=False)
            content = cleaned.get('content', '')
            return await self._llm_client.extract_article_text_with_meta(
                content
            )
        except Exception as e:  # pragma: no cover - зависит от LLM
            self._logger.warning('Ошибка LLM-извлечения текста: %s', e)
            return None, {'chunked': False, 'chunks_dropped': 0}
