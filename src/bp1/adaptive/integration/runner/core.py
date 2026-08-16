"""
AdaptiveRunner — единая точка входа для адаптивного сбора данных.

Режимы:
- 'adaptive': только адаптивный парсинг
- 'hybrid': адаптивный + legacy fallback
- 'fallback': adaptive → legacy → browser → wayback → HITL

Класс собран из двух подмешиваемых наборов методов (см. ``probing.py`` —
резолвинг поискового URL, ``batch.py`` — пакетный/конкурентный запуск),
чтобы одна логическая сущность ``AdaptiveRunner`` не жила в одном файле
на 1000+ строк — методы каждой зоны ответственности при этом остаются
обычными методами `self.*`, без изменения публичного API.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.bp1.storage import RawDataService
from src.bp1.tasks import get_search_task_config

from ...core.cache import UnifiedCache
from ...core.quality import DataQualityGate
from ...schemas import (
    PipelineReport,
    PipelineStage,
    SourceClassification,
    UnifiedConfig,
)
from ...strategies.classifier import SourceClassifier
from ..bridge import AdaptiveBridgeParser
from ..search_probe import SearchUrlProber, _normalize_target_text
from ..sources import SearchParamResolver, build_search_url, extract_host
from .batch import _BatchMixin
from .probing import _ProbingMixin

logger = logging.getLogger(__name__)


def _collect_quality_levels(response: Any) -> dict[str, Any]:
    """Достаёт сводку уровней Quality Gate из ответа парсера.

    Уровни кладёт ``AdaptiveBridgeParser`` в ``response.metrics``
    (см. ``ParsedMetrics`` в ``base_parser.py``, Шаг 20 плана рефакторинга,
    T6). Возвращает пустой словарь, если парсер их не проставил
    (специализированные RPA-адаптеры вроде fedresurs не проходят через
    ``DataQualityGate``).
    """
    metrics = getattr(response, 'metrics', None)
    levels = getattr(metrics, 'quality_levels', None)
    return levels or {}


def check_strategy_chain(orchestrator: Any) -> dict[str, bool]:
    """Проверяет, какие стратегии деградации реально доступны.

    ``Crawl4AIStrategy``/``StealthStrategy``/``BrowserStrategy`` зависят от
    опциональных пакетов (``crawl4ai``, ``playwright``). Если пакет не
    установлен, стратегия молча падает в рантайме и эффективная цепочка
    деградации короче ожидаемой — раньше это никак не было видно (T6:
    «нет наблюдаемости за тихой деградацией цепочки»).

    Returns:
        ``{имя стратегии: доступна ли}`` — импорт проверяется без запуска
        браузера, поэтому вызов дешёвый.
    """
    import importlib.util

    availability = {
        'crawl4ai': importlib.util.find_spec('crawl4ai') is not None,
        'playwright': importlib.util.find_spec('playwright') is not None,
    }
    registered = getattr(orchestrator, '_strategies', {}) or {}
    availability['registered_count'] = len(registered)
    return availability


class AdaptiveRunner(_ProbingMixin, _BatchMixin):
    """
    Единая точка входа для адаптивного сбора данных.

    Выполняет полный цикл: получение задачи, классификация источника,
    адаптивный парсинг, валидация качества, сохранение в RawItem,
    сохранение HTML + JSON на диск, обновление Redis (дедупликация).
    """

    def __init__(
        self,
        mode: str = 'adaptive',
        headless: bool = True,
        timeout: int = 60000,
        quality_gate_enabled: bool = True,
        cache_profiles: bool = True,
        max_concurrent: int = 5,
        use_probing: bool = True,
    ):
        self.mode = mode
        self.headless = headless
        self.timeout = timeout
        self.quality_gate_enabled = quality_gate_enabled
        self.cache_profiles = cache_profiles
        self.max_concurrent = max_concurrent
        self.use_probing = use_probing

        # Единая конфигурация пайплайна (UnifiedConfig).
        self.config = UnifiedConfig(
            mode=mode,
            headless=headless,
            timeout=timeout,
            quality_gate_enabled=quality_gate_enabled,
            cache_profiles=cache_profiles,
            max_concurrent=max_concurrent,
        )

        self._parser = AdaptiveBridgeParser(headless=headless, timeout=timeout)
        self._quality_gate = DataQualityGate()
        self._cache = UnifiedCache()
        self._classifier = SourceClassifier()
        self._search_param_resolver = SearchParamResolver()
        self._prober = SearchUrlProber(fetch=self._fetch_content)
        self._logger = logging.getLogger(__name__)
        # Фабрика сессий для конкурентного режима run_all (Шаг 17 плана
        # рефакторинга): каждая параллельная задача работает со СВОЕЙ
        # сессией — ``AsyncSession`` нельзя использовать одновременно из
        # нескольких корутин (asyncpg: "another operation is in progress").
        # Подменяется в тестах, чтобы не требовать живую БД.
        self._session_factory: Any = None
        # Пробинг поискового URL: по умолчанию включён. Fetch-функция
        # подключается реальным HTTP-загрузчиком по умолчанию (чтобы пробинг
        # не падал на заглушке NotImplementedError), но может быть заменена
        # через bind_probe_fetch на любой другой загрузчик (браузер/httpx).
        self._prober = SearchUrlProber(
            fetch=self._default_probe_fetch,
            looks_like_search_results=self._default_looks_like,
            post=self._default_probe_post,
        )

    def _bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к кэшу для хранения классификаций."""
        if self._cache.redis is None:
            self._cache.redis = redis_client

    async def _fetch_content(self, url: str) -> str | None:
        """Скачивает HTML через оркестратор для перебора параметров.

        Возвращает ``None``, если страница недоступна или пуста.
        """
        try:
            orchestrator = self._parser._adaptive_parser._orchestrator
            result = await orchestrator.fetch_with_degradation(url)
            if result.success and result.data:
                return result.data
        except Exception as e:
            self._logger.warning(
                'Ошибка фетча при переборе параметров (%s): %s', url, e
            )
        return None

    def _get_parser_for_source(self, source_name: str):
        """Вернуть специализированный RPA-парсер для источника.

        Для источников с готовым адаптером (fedresurs.ru и др.) возвращает
        парсер из ParserFactory, который применяет полноценный RPA-сценарий
        (обход QRATOR, поиск по ИНН, открытие карточки компании). Для
        остальных источников возвращает None — используется универсальный
        AdaptiveBridgeParser.
        """
        try:
            from src.bp1.parsers import ParserFactory

            # Парсеры зарегистрированы по URL-префиксам (например,
            # 'https://fedresurs.ru/'), поэтому ищем по домену источника.
            registered = ParserFactory.list_sources()
            key = None
            for candidate in registered:
                if candidate == 'adaptive':
                    continue
                if source_name in candidate or candidate in source_name:
                    key = candidate
                    break
            if key is None:
                return None

            parser = ParserFactory.get_parser(
                key,
                **{
                    'headless': self.headless,
                    'timeout': self.timeout,
                },
            )
            # Не используем универсальный адаптивный парсер как
            # специализированный — он уже является fallback по умолчанию.
            if parser.get_parser_type() == 'adaptive':
                return None
            return parser
        except Exception as e:
            self._logger.warning(
                'Не удалось получить специализированный парсер для %s: %s',
                source_name,
                e,
            )
            return None

    @staticmethod
    def _check_task_active(
        config: dict[str, Any], task_id: int
    ) -> dict[str, Any] | None:
        """Возвращает результат-пропуск, если задача, её источник или
        конкурент неактивны, иначе ``None`` (можно продолжать ``run_task``).

        Флаг ``is_active`` у SearchTask может быть True, но если сам
        источник или конкурент выключены (is_active=False), задачу
        пропускаем — адаптивный парсинг ведётся только по активным source
        и competitor.
        """
        if not config['is_active']:
            return {'status': 'skipped', 'reason': 'inactive'}
        if not config.get('source_is_active', True):
            return {
                'status': 'skipped',
                'reason': 'source_inactive',
                'search_task_id': task_id,
            }
        if not config.get('competitor_is_active', True):
            return {
                'status': 'skipped',
                'reason': 'competitor_inactive',
                'search_task_id': task_id,
            }
        return None

    async def _resolve_classification(
        self, source_name: str
    ) -> SourceClassification:
        """Классифицирует источник с кэшированием в Redis."""
        classification = await self._cache.get_classification(source_name)
        if classification is None:
            classification = await self._classifier.classify(
                source_name=source_name,
                source_url=source_name,
            )
            await self._cache.set_classification(source_name, classification)
        else:
            self._logger.info(
                'Классификация источника %s взята из кэша (стратегия=%s)',
                source_name,
                classification.recommended_strategy,
            )
        return classification

    async def _execute_parse(
        self,
        source_name: str,
        url: str,
        competitor: str,
        trigger: str,
        competitor_inn: str | None,
        parse_kwargs: dict[str, Any],
    ) -> Any:
        """Выбирает специализированный RPA-парсер или универсальный
        адаптивный (``_get_parser_for_source``) и выполняет парсинг.
        """
        parser = self._get_parser_for_source(source_name)
        if parser is not None:
            # Специализированный RPA-адаптер (fedresurs.ru и др.).
            # Такой парсер ожидает базовый URL источника, а не URL
            # поиска (например, FedresursAdapter принимает
            # 'https://fedresurs.ru').
            parser_url = f'https://{extract_host(source_name)}'
            if competitor_inn:
                parse_kwargs['inn'] = competitor_inn
                parse_kwargs['name'] = competitor
            elif trigger and trigger.isdigit() and len(trigger) in (10, 12):
                parse_kwargs['inn'] = trigger
                parse_kwargs['name'] = competitor
            else:
                parse_kwargs['name'] = trigger or competitor
            return await parser.parse(parser_url, **parse_kwargs)

        # Универсальный адаптивный парсер. Передаём реальное имя
        # источника (hostname), чтобы адаптер/классификация/профиль
        # кэшировались именно под этим источником, а не под общим
        # именем 'adaptive'.
        return await self._parser.parse(
            url,
            source_name=source_name,
            **parse_kwargs,
        )

    async def run_task(
        self,
        task_id: int,
        session: AsyncSession,
        redis_client: Any,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Выполняет одну задачу адаптивного сбора.

        Поток:
        1. Получить SearchTask из БД
        2. Классифицировать источник
        3. Выполнить адаптивный парсинг (с fallback)
        4. Валидировать качество
        5. Сохранить в RawItem (PostgreSQL JSONB)
        6. Сохранить HTML + JSON на диск
        7. Обновить Redis (дедупликация)
        8. Вернуть результат
        """
        # Отчёт пайплайна (PipelineReport) для отслеживания стадий.
        report_start = time.monotonic()
        pipeline_id = uuid.uuid4().hex
        report = PipelineReport(
            pipeline_id=pipeline_id,
            mode=self.mode,
        )
        stages: list[PipelineStage] = []

        def _add_stage(
            name: str,
            status: str = 'ok',
            detail: dict[str, Any] | None = None,
        ) -> None:
            stages.append(
                PipelineStage(
                    name=name,
                    status=status,
                    detail=detail or {},
                )
            )

        # 1. Получаем конфигурацию задачи.
        config = await get_search_task_config(task_id, session)

        skip = self._check_task_active(config, task_id)
        if skip is not None:
            return skip

        source_name = config['source']
        competitor = config['competitor']
        trigger = config['trigger']
        competitor_inn = config['competitor_inn']

        # 2. Классифицируем источник (с кэшированием в Redis).
        self._bind_redis(redis_client)
        self._parser.bind_redis(redis_client)
        classification = await self._resolve_classification(source_name)
        _add_stage(
            'classify',
            detail={'strategy': classification.recommended_strategy},
        )

        # 3. Определяем поисковый параметр с учётом типа источника.
        #
        #    Source-aware логика (SearchParamResolver): на сайтах госорганов
        #    (SourceType.REGISTRY / SiteType.GOVERNMENT / известные госдомены)
        #    поиск даёт положительный ответ по ИНН, на всех остальных — по
        #    названию конкурента (competitor). Универсальный приоритет
        #    ``ИНН -> trigger -> название`` не работает: многие сайты не
        #    индексируют ИНН (напр. hh.ru возвращает 404 на поиск по ИНН).
        resolver = self._search_param_resolver
        search_param = resolver.resolve(
            source_name,
            competitor_inn=competitor_inn,
            competitor=competitor,
            trigger=trigger,
            classification=classification,
        )
        url = build_search_url(source_name, search_param)
        source_request_url = url

        # 3.0. Пропуск гос. источника без ИНН.
        #
        #    Если источнику нужен поиск по ИНН, а у конкурента ИНН нет,
        #    поиск не имеет смысла: госсайт не проиндексировал название
        #    компании, поэтому запрос по названию вернёт пустой/мусорный
        #    результат. Фиксируем error "not INN" вместо бесполезной работы.
        if resolver.missing_inn(
            source_name,
            competitor_inn=competitor_inn,
            trigger=trigger,
            classification=classification,
        ):
            self._logger.info(
                'Пропуск задачи %s: источник %s требует ИНН, '
                'а у конкурента %s его нет (not INN)',
                task_id,
                source_name,
                competitor,
            )
            service = RawDataService(session, redis_client)
            raw_item_id = await service.persist_error(
                search_task_id=task_id,
                error_message='not INN',
                source_request_url=source_request_url,
            )
            return {
                'status': 'error',
                'search_task_id': task_id,
                'raw_item_id': raw_item_id,
                'error': 'not INN',
                'source': source_name,
            }

        # 3.1. Circuit breaker: если источник временно заблокирован в Redis
        #     (все стратегии падали недавно), пропускаем задачу, не тратя
        #     ресурсы на парсинг.
        if await self._cache.is_source_blocked(source_name):
            self._logger.info(
                'Источник %s временно заблокирован (circuit breaker), '
                'задача %s пропущена',
                source_name,
                task_id,
            )
            return {
                'status': 'source_unavailable',
                'search_task_id': task_id,
                'source': source_name,
                'reason': 'circuit_open',
            }

        # 3.2. Адаптивный перебор параметров/форм/реформулировок.
        #      Сначала пробуем параметр, распознанный из HTML-формы поиска
        #      (если найден), затем типовые q/query/text/..., затем
        #      реформулировки запроса. Успешный URL передаётся дальше
        #      в парсер как фактический адрес страницы результатов.
        probe_report: dict[str, Any] | None = None
        # Найденный на странице результатов вариант названия конкурента:
        # 'full' (с ОПФ) | 'stripped' (без ОПФ/кавычек) | None. Используется
        # далее как имя конкурента при сборе новостей, чтобы перебирать
        # новости именно того варианта, который реально есть на странице.
        matched_variant: str | None = None
        if self._prober is not None:
            try:
                plan = await self._prober.probe(
                    url,
                    search_param,
                    source_type=classification.source_type,
                    target_name=competitor,
                    target_inn=competitor_inn,
                )
                probe_report = plan.to_extra()
                # Проверяем, что у нас есть данные о переборе.
                if probe_report is not None:
                    wins = [a for a in plan.attempts if a.ok]
                    if wins:
                        url = wins[0].url
                        source_request_url = url
                        matched_variant = wins[0].matched_variant
                        self._logger.info(
                            'Адаптивный перебор: успех (kind=%s, label=%s) '
                            'для %s',
                            wins[0].kind,
                            wins[0].label,
                            source_name,
                        )
                    else:
                        self._logger.info(
                            'Адаптивный перебор не дал результатов для %s '
                            '(перебрано %d вариантов)',
                            source_name,
                            len(plan.attempts),
                        )
            except Exception as e:
                self._logger.warning(
                    'Ошибка адаптивного перебора параметров (%s): %s',
                    source_name,
                    e,
                )
                probe_report = None

        # Имя конкурента, по которому собираем новости: берём тот вариант
        # названия, который реально присутствует на странице результатов
        # (полное с ОПФ или без ОПФ/кавычек). Это ключевое исправление
        # «каши»: раньше новости перебирались по полному названию даже там,
        # где страница содержала конкурента без ОПФ (или наоборот).
        news_competitor = competitor
        if matched_variant:
            if matched_variant == 'stripped':
                stripped_name = _normalize_target_text(competitor, True)
                if stripped_name:
                    news_competitor = stripped_name
            # 'full' — оставляем полное название как есть.

        parse_kwargs = {
            'search_task_id': task_id,
            'competitor': news_competitor,
            'trigger': trigger,
            'source_request_url': source_request_url,
        }

        # 3.2. Пробинг поискового URL: кэш → пробинг → fallback.
        #      Итоговый ``url`` (для парсинга) и ``probed`` (для метаданных
        #      и повторного кэширования) получаем до вызова парсера.
        url, probed = await self._get_or_probe_url(
            source_name=source_name,
            search_param=search_param,
            target_name=competitor or trigger or '',
            redis_client=redis_client,
        )
        if probed is not None:
            parse_kwargs['probed_url'] = probed
        # В meta сохраняется исходный (не пробованный) URL задачи, чтобы
        # source_request_url не менялся от того, что кэш нагрелся.

        # 4. Выполняем парсинг.
        #    Для источников с готовым RPA-адаптером (fedresurs.ru и др.)
        #    используем специализированный парсер из ParserFactory, который
        #    применяет полноценный RPA-сценарий (обход QRATOR, поиск по ИНН,
        #    открытие карточки компании). Иначе — универсальный адаптивный
        #    (см. ``_execute_parse``).
        try:
            response = await self._execute_parse(
                source_name,
                url,
                competitor,
                trigger,
                competitor_inn,
                parse_kwargs,
            )
            # Шаг 20 плана рефакторинга (T6): реально сработавшая стратегия
            # и уровни Quality Gate. ``getattr(response, 'strategy_used')``
            # здесь всегда давал None — у ParsedResponse такого поля нет,
            # оно приходит в metrics (см. bridge.py/ParsedMetrics).
            metrics = getattr(response, 'metrics', None)
            _add_stage(
                'parse',
                detail={
                    'items': len(response.items),
                    'strategy': getattr(metrics, 'strategy_used', None),
                    'quality_status': getattr(metrics, 'quality_status', None),
                    'quality_levels': _collect_quality_levels(response),
                },
            )
            # Источник успешно спарсен — снимаем временную блокировку и
            # сбрасываем счётчик подряд идущих отказов.
            await self._cache.unblock_source(source_name)
            await self._cache.reset_fail_count(source_name)
        except Exception as e:
            self._logger.error(
                'Ошибка адаптивного парсинга (task_id=%s, source=%s): %s',
                task_id,
                source_name,
                e,
            )
            await self._record_source_failure(source_name, session)
            service = RawDataService(session, redis_client)
            raw_item_id = await service.persist_error(
                search_task_id=task_id,
                error_message=str(e),
                source_request_url=source_request_url,
            )
            return {
                'status': 'error',
                'search_task_id': task_id,
                'raw_item_id': raw_item_id,
                'error': str(e),
            }

        # 5. Сохраняем результат через общий сервис персистентности
        #    (хэширование, дедупликация по Redis, HTML/JSON на диск, RawItem).
        service = RawDataService(session, redis_client)
        data_dict = response.model_dump()
        html_source_path = getattr(response, 'html_file_path', None)

        persisted = await service.persist(
            search_task_id=task_id,
            response_data=data_dict,
            source_request_url=source_request_url,
            html_source_path=html_source_path,
        )

        # 6. Финализируем отчёт пайплайна.
        _add_stage(
            'save',
            detail={
                'raw_item_id': persisted.get('raw_item_id'),
                'status_type': persisted.get('status_type'),
                'hash': persisted.get('hash'),
            },
        )
        report.stages = stages
        report.finished_at = datetime.now()
        report.total_duration_ms = int((time.monotonic() - report_start) * 1000)
        report.overall_status = 'ok'

        # Шаг 20 плана рефакторинга (T6): в сводку идёт РЕАЛЬНО сработавшая
        # стратегия. Раньше сюда попадала classification.recommended_strategy
        # — предсказание до попытки, из-за чего разбивка по стратегиям в
        # отчётах показывала намерение, а не факт.
        metrics = getattr(response, 'metrics', None)
        persisted['strategy'] = (
            getattr(metrics, 'strategy_used', None)
            or classification.recommended_strategy
        )
        persisted['strategy_recommended'] = classification.recommended_strategy
        persisted['quality_status'] = getattr(metrics, 'quality_status', None)
        persisted['quality_levels'] = _collect_quality_levels(response)
        persisted['source_items'] = len(response.items)
        persisted['empty_reason'] = getattr(
            getattr(response, 'meta', None), 'empty_reason', None
        )
        persisted['source'] = source_name
        persisted['pipeline_report'] = report.model_dump(mode='json')
        # Отчёт адаптивного перебора параметров/форм/реформулировок.
        # Позволяет увидеть, какой query-параметр и формулировка сработали.
        if probe_report is not None:
            persisted['probe_report'] = probe_report
        return persisted
