"""
AdaptiveBridgeParser — мост между Adaptive и BP-1 BaseParser.

Реализует BaseParser из bp1, используя AdaptiveParser для сбора данных
и конвертируя результат в ParsedResponse (совместимость с BP-1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.bp1.base_parser import BaseParser, ParsedItem, ParsedResponse

from ..processing.parser import AdaptiveParser


class AdaptiveBridgeParser(BaseParser):
    """
    Универсальный адаптер, реализующий BaseParser.

    Использует AdaptiveParser для сбора данных и конвертирует
    результат в ParsedResponse (совместимость с BP-1).
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        source_name: str = 'adaptive',
        redis_client: Any = None,
    ):
        self._adaptive_parser = AdaptiveParser(
            headless=headless, timeout=timeout, redis_client=redis_client
        )
        self._headless = headless
        self._timeout = timeout
        self._source_name = source_name

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        """
        Выполняет адаптивный парсинг и возвращает ParsedResponse.

        Конвертация:
        - AdaptiveParseResult.items → ParsedResponse.items
        - meta формируется из kwargs (search_task_id, competitor, trigger)

        ``source_name`` для адаптера/классификации/профиля берётся из
        ``kwargs`` (реальный источник задачи), иначе из ``self._source_name``.
        Это гарантирует, что кэш привязывается к конкретному источнику, а не
        к общему имени ``'adaptive'``.
        """
        competitor = kwargs.get('competitor', '')
        trigger = kwargs.get('trigger', '')
        source_name = kwargs.get('source_name') or self._source_name

        result = await self._adaptive_parser.parse(
            url=url,
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            expected_schema=kwargs.get('expected_schema'),
            # Точная строка поискового запроса (см. runner/core.py) — нужна
            # для сброса именно закэшированного под неё probed_url при
            # повторном провале RELEVANCE (change
            # verify-search-probe-relevance).
            search_param=kwargs.get('search_param', ''),
        )

        if result.status == 'error':
            raise RuntimeError(result.error or 'adaptive parse failed')

        # AdaptiveParser отдаёт «сырые» элементы своего внутреннего формата:
        # обычные события как есть, плюс — для источников с поиском —
        # служебный элемент «страница результатов поиска» с полным списком
        # новостей в extra.news (см.
        # processing/parser.py::_make_search_page_item).
        # Эта страница сама по себе не событие БП-1 (её нет в контракте
        # ABOUT.md), поэтому в items она не попадает — раскладывается на:
        #   - настоящие события (каждая новость -> отдельный ParsedItem);
        #   - служебные поля (quality_levels/relevance_mode/...) -> metrics.
        items: list[ParsedItem] = []
        promoted: list[ParsedItem] = []
        run_metrics: dict[str, Any] = {}
        html_file_path: str | None = None

        for raw_item in result.items:
            extra = dict(raw_item.get('extra') or {})
            # Ключ 'news' есть в extra ТОЛЬКО у служебной страницы поиска
            # (_make_search_page_item в parser.py всегда его проставляет,
            # даже пустым списком при нулевой выдаче) — проверяем именно
            # наличие ключа, а не истинность списка. Раньше здесь стояло
            # `if news:` (истинность после pop), из-за чего поиск с нулевой
            # выдачей (news == []) не считался страницей поиска: ветка
            # переноса метрик не срабатывала, и вся служебная диагностика
            # (quality_levels/relevance_mode/...) утекала в meta/items
            # вместо metrics — тот самый баг, который эта переработка
            # должна была устранить.
            is_search_page = 'news' in extra
            news = extra.pop('news', None) or []

            if is_search_page:
                # Служебные метрики сбора относятся ко всей выгрузке, а не
                # к конкретному событию — переносим в metrics (раздел
                # ABOUT.md для служебных полей), а не оставляем в items.
                for key in (
                    'relevance_mode',
                    'news_total',
                    'relevance_filtered',
                    'quality_levels',
                    'file_saved',
                ):
                    if key in extra:
                        run_metrics[key] = extra.pop(key)
                if 'file_path' in extra:
                    html_file_path = extra.pop('file_path')

                for entry in news:
                    if not isinstance(entry, dict):
                        continue
                    ex_url = entry.get('ex_url', '')
                    if not ex_url:
                        continue
                    ex_title = entry.get('ex_title', '') or raw_item.get(
                        'title', ''
                    )
                    ex_text = entry.get('ex_text')
                    promoted.append(
                        ParsedItem(
                            # Полный абсолютный URL события (иначе не
                            # работает dedup_key и media_domain в BP-2).
                            url=ex_url,
                            title=ex_title,
                            text=ex_text,
                            # published_at/region/media_name — уже извлечены
                            # селекторами адаптера на уровне листинга
                            # (_page_items -> _run_extraction_cascade), а не
                            # LLM-обогащением и не URL источника: если
                            # значения нет — остаётся null, а не заглушка.
                            published_at=entry.get('ex_published_at'),
                            region=entry.get('ex_region'),
                            media_name=entry.get('ex_media_name'),
                            # Пусто (по запросу) — диагностика
                            # (ex_method/relevance/enrichment/...) писалась
                            # сюда раньше, но признана неструктурированным
                            # мусором. title/text уже несут ex_title/ex_text
                            # как обязательные поля контракта — данные не
                            # теряются.
                            extra={},
                        )
                    )
                # Служебная страница результатов поиска — не самостоятельное
                # событие, в items не попадает (см. пояснение выше).
                continue

            items.append(
                ParsedItem(
                    url=raw_item.get('url', ''),
                    title=raw_item.get('title', '') or raw_item.get('text', ''),
                    text=raw_item.get('text'),
                    published_at=raw_item.get('published_at'),
                    region=raw_item.get('region'),
                    media_name=raw_item.get('media_name'),
                    extra=extra,
                )
            )

        items = items + promoted
        if not items:
            empty_reason = (
                'all_items_filtered'
                if run_metrics.get('news_total', 0) > 0
                else 'no_extractable_items'
            )
        else:
            empty_reason = None

        meta: dict[str, Any] = {
            'search_task_id': kwargs.get('search_task_id'),
            # Источник = реальный источник задачи, а не 'adaptive'.
            'source': source_name,
            'competitor': competitor,
            'trigger': trigger or None,
            # Ссылка на НАШ поисковый запрос (одна на всю выгрузку).
            'source_request_url': kwargs.get('source_request_url') or url,
            # Время съёма; в хэш НЕ включается, иначе всегда 'changed'.
            'fetched_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
            'items_count': len(items),
            'empty_reason': empty_reason,
        }

        probed_url = kwargs.get('probed_url')
        metrics: dict[str, Any] = {
            # Информация о пробинге (URL после поиска; если None — fallback).
            'probed_url': (
                probed_url.search_url if probed_url is not None else None
            ),
            # Шаг 20 плана рефакторинга (T6): реально сработавшая стратегия
            # и статус качества. Раньше терялись при конвертации
            # AdaptiveParseResult -> ParsedResponse, из-за чего в отчёте
            # прогона фигурировала лишь ПРЕДСКАЗАННАЯ стратегия
            # (classification.recommended_strategy), а не фактическая.
            'strategy_used': result.strategy_used.value,
            'quality_status': result.status,
            **run_metrics,
        }

        return ParsedResponse(
            meta=meta,
            items=items,
            metrics=metrics,
            html_file_path=html_file_path,
        )

    def get_source_name(self) -> str:
        return self._source_name

    def get_parser_type(self) -> str:
        return 'adaptive'

    def bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к внутреннему парсеру."""
        self._adaptive_parser.bind_redis(redis_client)
