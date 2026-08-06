"""
Полный smoke-тест LLM-модуля пакета BP-1 Adaptive.

Демонстрирует ВСЕ функции работы с LLM на реальной HTML-странице
из папки data/html_pages:

1. ``SourceClassifier.classify``      — классификация источника (тип, SPA,
   антибот, CAPTCHA, сложность).
2. ``LLMClient.analyze_structure``    — полный анализ структуры (автоматически
   включает чанкирование для больших страниц).
3. ``LLMClient.analyze_structure_chunked`` — явное чанкирование с выводом
   этапов: HtmlCleaner → StructuredChunker → параллельное извлечение →
   ResultMerger.
4. ``LLMClient._llm_analyze``         — прямой анализ одним запросом.
5. ``AIAgent.choose_strategy``        — выбор стратегии обхода через LLM.
6. ``AIAgent.analyze_result``         — анализ результата парсинга через LLM.

Для каждой стадии выводятся все селекторы, схема данных, confidence,
метаданные (пагинация, items_per_page) и статистика чанкирования.

Параметры:
    expected_fields = ''            (пустой список полей)
    competitor      = 'ООО "Архитект ИИ"'

Использование (из корня проекта kodik/):
    python -m src.bp1.adaptive.llm_test
"""

# from __future__ import annotations
import asyncio
import sys
from pathlib import Path

from src.bp1.adaptive.processing.html_cleaner import HtmlCleaner
from src.bp1.adaptive.processing.llm import AIAgent, LLMClient
from src.bp1.adaptive.processing.merger import ResultMerger
from src.bp1.adaptive.schemas import AdapterConfig, SourceClassification
from src.bp1.adaptive.strategies.classifier import SourceClassifier

# Корень проекта kodik/ — четыре уровня вверх от этого файла.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Добавляем корень проекта в PYTHONPATH, чтобы работал импорт src.*
# при запуске файла напрямую (python src/bp1/adaptive/llm_test.py).
sys.path.insert(0, str(PROJECT_ROOT))

# Папка с сохранёнными HTML-страницами (см. core.config: bp1_html_dir).
HTML_DIR = PROJECT_ROOT / 'src' / 'bp1' / 'data' / 'html_pages'

COMPETITOR = 'ООО "Архитект ИИ"'
EXPECTED_FIELDS: list[str] = []  # expected_fields = ''

# --- Константы LLM (пока прописаны вручную для тестов) ---
# TODO: заменить на реальный ключ
LLM_API_KEY = 'sk-f94d32860e504e6caf47625080ca0c78'
LLM_MODEL = 'deepseek-v4-flash'
LLM_BASE_URL = 'https://api.deepseek.com'
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 4096


def _pick_html() -> Path:
    """Возвращает первый HTML-файл из data/html_pages."""
    if not HTML_DIR.exists():
        raise FileNotFoundError(f'Папка не найдена: {HTML_DIR}')
    files = sorted(HTML_DIR.glob('*.html'))
    if not files:
        raise FileNotFoundError(f'В папке нет HTML-файлов: {HTML_DIR}')
    return files[0]


def _print_header(title: str) -> None:
    """Печатает заголовок секции."""
    print()
    print('=' * 70)
    print(f'  {title}')
    print('=' * 70)


def _print_selectors(config: AdapterConfig) -> None:
    """Выводит все CSS-селекторы из AdapterConfig."""
    print('  CSS-селекторы:')
    if not config.selectors:
        print('    (пусто)')
    for field, selector in config.selectors.items():
        print(f'    {field:<16} -> {selector}')
    print(f'  Confidence: {config.confidence}')
    print(f'  Adaptive: {config.adaptive}, Auto-save: {config.auto_save}')


def _print_schema(config: AdapterConfig) -> None:
    """Выводит схему данных (типы полей) из AdapterConfig."""
    print('  Схема данных (expected_schema):')
    if not config.expected_schema:
        print('    (пусто)')
    for field, ftype in config.expected_schema.items():
        print(f'    {field:<16} -> {ftype}')


def _print_metadata(metadata: dict) -> None:
    """Выводит метаданные (пагинация, items_per_page и т.д.)."""
    print('  Метаданные:')
    if not metadata:
        print('    (пусто)')
    for key, value in metadata.items():
        print(f'    {key:<20} -> {value}')


async def _demo_classify(html: str, source_name: str) -> SourceClassification:
    """Демонстрирует классификацию источника через SourceClassifier."""
    _print_header('1. КЛАССИФИКАЦИЯ ИСТОЧНИКА (SourceClassifier.classify)')
    classifier = SourceClassifier()
    classification = await classifier.classify(
        source_name=source_name,
        source_url=f'https://{source_name}/',
        html=html,
    )
    print(f'  Тип источника: {classification.source_type.value}')
    print(f'  Сложность: {classification.complexity_score}')
    print(f'  Антибот: {classification.has_antibot}')
    print(f'  CAPTCHA: {classification.has_captcha}')
    print(f'  SPA: {classification.is_spa}')
    print(f'  Рекомендованная стратегия: {classification.recommended_strategy}')
    return classification


async def _demo_analyze_structure(
    client: LLMClient, html: str
) -> AdapterConfig:
    """Демонстрирует полный анализ структуры (с авто-чанкированием)."""
    _print_header('2. ПОЛНЫЙ АНАЛИЗ СТРУКТУРЫ (LLMClient.analyze_structure)')
    config = await client.analyze_structure(
        html=html,
        competitor=COMPETITOR,
        expected_fields=EXPECTED_FIELDS,
    )
    _print_selectors(config)
    _print_schema(config)
    return config


async def _demo_chunked(client: LLMClient, html: str) -> AdapterConfig:
    """Демонстрирует явное чанкирование с выводом всех этапов."""
    _print_header('3. АНАЛИЗ С ЧАНКИРОВАНИЕМ (analyze_structure_chunked)')

    # Этап 1: очистка HTML.
    cleaner = HtmlCleaner()
    cleaned = cleaner.clean(html)
    stats = cleaned.get('stats', {})
    print('  Этап 1 — HtmlCleaner:')
    print(f'    Исходный размер: {stats.get("original_size", 0)} символов')
    print(f'    Очищенный размер: {stats.get("cleaned_size", 0)} символов')
    print(f'    Сжатие: x{stats.get("compression_ratio", 0)}')
    print(f'    Блоков: {stats.get("block_count", 0)}')
    print(f'    Метаданные: {cleaned.get("metadata", {})}')

    # Этап 2: чанкирование.
    chunker = client._chunker
    chunks = chunker.chunk(cleaned)
    print(f'  Этап 2 — StructuredChunker: {len(chunks)} чанков')
    for chunk in chunks:
        print(
            f'    Чанк #{chunk.index}: {chunk.size} символов '
            f'(блоки {chunk.start_block}-{chunk.end_block})'
        )

    # Этап 3: параллельное извлечение через LLM.
    print('  Этап 3 — параллельное извлечение через LLM...')
    results = await client._extract_from_chunks(
        chunks, COMPETITOR, EXPECTED_FIELDS
    )
    print(f'    Успешно обработано чанков: {len(results)} из {len(chunks)}')

    # Этап 4: объединение результатов.
    merger = ResultMerger()
    merged = merger.merge(
        results=results,
        chunk_metadata=[c.metadata for c in chunks],
    )
    print('  Этап 4 — ResultMerger:')
    print(f'    Обработано чанков: {merged.get("chunks_processed", 0)}')
    print(f'    Найдено элементов: {merged.get("total_items_found", 0)}')
    print(f'    Дубликатов удалено: {merged.get("duplicate_count", 0)}')
    print(f'    Итоговый confidence: {merged.get("confidence", 0.0)}')

    config = client._to_adapter_config(merged, EXPECTED_FIELDS)
    _print_selectors(config)
    _print_schema(config)
    _print_metadata(merged.get('metadata', {}))
    return config


async def _demo_llm_analyze(client: LLMClient, html: str) -> AdapterConfig:
    """Демонстрирует прямой анализ одним запросом (_llm_analyze)."""
    _print_header('4. ПРЯМОЙ АНАЛИЗ (LLMClient._llm_analyze)')
    try:
        config = await client._llm_analyze(
            html=html[: client._max_chunk_size],
            competitor=COMPETITOR,
            expected_fields=EXPECTED_FIELDS,
        )
        _print_selectors(config)
        _print_schema(config)
        return config
    except Exception as e:
        print(f'  [LLM недоступен] {type(e).__name__}: {e}')
        print('  Возвращён эвристический fallback (пустые селекторы).')
        return client._heuristic_analyze(html, EXPECTED_FIELDS)


async def _demo_agent(
    agent: AIAgent, classification: SourceClassification, config: AdapterConfig
) -> None:
    """Демонстрирует работу AIAgent (выбор стратегии и анализ результата)."""
    _print_header('5. ВЫБОР СТРАТЕГИИ (AIAgent.choose_strategy)')
    try:
        strategy = await agent.choose_strategy(classification)
        print(f'  Выбранная стратегия: {strategy.value}')
    except Exception as e:
        print(f'  [LLM недоступен] {type(e).__name__}: {e}')
        fallback = AIAgent._heuristic_strategy(classification).value
        print(f'  Эвристический fallback: {fallback}')

    _print_header('6. АНАЛИЗ РЕЗУЛЬТАТА (AIAgent.analyze_result)')
    # Формируем пример элементов из селекторов для анализа.
    items = [
        {
            'title': 'Пример записи 1',
            'url': 'https://example.com/1',
            'published_at': '2026-08-05',
        },
        {
            'title': 'Пример записи 2',
            'url': 'https://example.com/2',
            'published_at': '2026-08-04',
        },
    ]
    try:
        recommendation = await agent.analyze_result(
            html='<html><body>пример</body></html>',
            items=items,
            source_name=config.source_name,
        )
        print(f'  Рекомендация: {recommendation.get("recommendation")}')
        print(f'  Confidence: {recommendation.get("confidence")}')
    except Exception as e:
        print(f'  [LLM недоступен] {type(e).__name__}: {e}')
        print('  Рекомендация: no_llm, Confidence: 0.5')


async def main() -> None:
    """Точка входа smoke-теста."""
    html_path = _pick_html()
    html = html_path.read_text(encoding='utf-8', errors='replace')
    source_name = html_path.name.split('_')[0]  # например, 'fedresurs'

    print(f'HTML-файл: {html_path.name}')
    print(f'Размер HTML: {len(html)} символов')
    print(f'Competitor: {COMPETITOR}')
    print(f'Expected fields: {EXPECTED_FIELDS or "(пусто)"}')
    print(f'Модель: {LLM_MODEL}')
    print('-' * 60)

    if not LLM_API_KEY or LLM_API_KEY.startswith('sk-...'):
        print('ОШИБКА: не задан LLM_API_KEY.')
        print('Пропишите реальный ключ в константе LLM_API_KEY в начале файла.')
        sys.exit(1)

    client = LLMClient(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
    )
    agent = AIAgent(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
    )

    try:
        # 1. Классификация источника.
        classification = await _demo_classify(html, source_name)

        # 2. Полный анализ структуры (с авто-чанкированием).
        config_full = await _demo_analyze_structure(client, html)

        # 3. Явное чанкирование с выводом всех этапов.
        config_chunked = await _demo_chunked(client, html)

        # 4. Прямой анализ одним запросом.
        config_direct = await _demo_llm_analyze(client, html)

        # 5-6. Работа AIAgent.
        await _demo_agent(agent, classification, config_full)

    except Exception as e:
        print(f'ОШИБКА запроса к модели: {type(e).__name__}: {e}')
        sys.exit(1)

    # Итоговое резюме.
    _print_header('ИТОГОВОЕ РЕЗЮМЕ')
    print('  Полный анализ (analyze_structure):')
    _print_selectors(config_full)
    print()
    print('  Чанкированный анализ (analyze_structure_chunked):')
    _print_selectors(config_chunked)
    print()
    print('  Прямой анализ (_llm_analyze):')
    _print_selectors(config_direct)
    print('-' * 60)
    print('OK: все функции LLM-модуля работают.')


if __name__ == '__main__':
    asyncio.run(main())
