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
    StrategyType,
)
from ..strategies.orchestrator import AgenticOrchestrator
from .html_cleaner import HtmlCleaner
from .llm import AIAgent, LLMClient

logger = logging.getLogger(__name__)

# Максимальное количество новостей, собираемых за один проход пагинации.
DEFAULT_MAX_NEWS = 5

# Минимальная длина текста, при которой результат извлечения считается
# успешным (для каскада CSS → LLM → сниппет).
MIN_ARTICLE_TEXT_LENGTH = 100

# Максимальное количество одновременно докачиваемых статей (глубокий фетч).
MAX_CONCURRENT_FETCHES = 5

# Таймаут (в секундах) на извлечение полного текста одной статьи. Защищает
# глубокий фетч от зависания на проблемной странице, чтобы медленная статья
# не занимала слот конкурентности и не лишала остальные новости полного
# текста (раньше первые 1-2 статьи «съедали» все ресурсы, а остальные падали
# в сниппет-фолбэк).
ARTICLE_FETCH_TIMEOUT_SECONDS = 20.0

# Минимальное количество символов, при котором извлечённый LLM/CSS текст
# считается полным. Если текст короче — вероятна обрезка, и нужна докачка
# хвоста.
MIN_FULL_ARTICLE_TEXT_LENGTH = 300

# Максимальное количество итераций докачки обрезанного хвоста статьи.
MAX_TAIL_FETCH_ATTEMPTS = 3

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
        self._logger = logger or logging.getLogger(__name__)

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
        start_with: StrategyType | None = None
        classification = await self._cache.get_classification(source_name)
        if classification is not None:
            try:
                start_with = StrategyType(classification.recommended_strategy)
            except ValueError:
                start_with = None
        # LLM-агент уточняет стратегию обхода по классификации (fallback —
        # эвристика при недоступности LLM). Это ключевая точка, где реально
        # вызывается LLM в боевом конвейере. Если классификация ещё не
        # рассчитана (нет в кэше) — агент не вызываем и используем дефолт.
        if classification is not None:
            try:
                agent_strategy = await self._agent.choose_strategy(
                    classification
                )
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
        for item in items:
            item.setdefault('extra', {})['news'] = news
            if file_path:
                item['extra']['file_path'] = file_path
            item['extra']['file_saved'] = file_saved

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

        # Этап B: LLM-извлечение (fallback при сбое CSS). Если результат
        # подозрительно короткий или обрывается без финального знака
        # препинания — считаем текст обрезанным и пробуем докачать хвост.
        llm_text = await self._llm_extract_text(html)
        if llm_text and len(llm_text) >= MIN_ARTICLE_TEXT_LENGTH:
            if _looks_truncated(llm_text):
                llm_text = await self._extract_missing_tail(
                    html, llm_text, source_name
                )
            return llm_text, 'llm'

        # Этап C: сниппет из очищенного контента.
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

    if selectors.get('container'):
        for raw in _extract_by_selectors(html, selectors)[:DEFAULT_MAX_NEWS]:
            url_rel = raw.get('url', '')
            title = raw.get('title', '')
            if (
                _is_noise_url(url_rel)
                or _reject_non_http_scheme(url_rel)
                or not title
            ):
                continue
            pairs.append((title, url_rel))
    else:
        collector = _LinkCollector()
        collector.feed(html)
        for title, href in collector.links[:DEFAULT_MAX_NEWS]:
            if _is_noise_url(href) or _reject_non_http_scheme(href):
                continue
            pairs.append((title, href))

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
        return [
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
            for raw in _extract_by_selectors(html, selectors)[:DEFAULT_MAX_NEWS]
            if (
                not _is_noise_url(raw.get('url'))
                and not _reject_non_http_scheme(raw.get('url'))
            )
        ]

    collector = _LinkCollector()
    collector.feed(html)

    return [
        _make_item(
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            url=href,
            title=title,
            base_url=base_url,
        )
        for title, href in collector.links[:DEFAULT_MAX_NEWS]
        if not _is_noise_url(href) and not _reject_non_http_scheme(href)
    ]
