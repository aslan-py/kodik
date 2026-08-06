# 🧠 Промпт для Рефакторинга `llm.py` и Устранения Разрыва с `parser.py`

## 🎯 Контекст и Архитектурный Вызов

Ты — ведущий AI-инженер и промпт-инженер с 10-летним опытом разработки систем, интегрирующих LLM с веб-скрапингом. Ты работал над проектами, где требовалось извлекать структурированные данные из огромных HTML-страниц, используя LLM с ограниченным контекстным окном.

**Твоя задача:** Переработать модуль `llm.py` и устранить разрыв между LLM-анализом и извлечением селекторов в `parser.py`.

### 🔴 Текущая Проблема

В текущей реализации существует **критический разрыв**:

1. **`LLMClient.analyze_structure()`** возвращает `AdapterConfig.expected_schema` (только названия полей)
2. **`AdaptiveParser`** создаёт `AdapterState.selectors` как **пустые строки**:
   ```python
   adapter = AdapterState(
       selectors=dict.fromkeys(config.expected_schema, ''),  # ← ПРОБЛЕМА!
       schema_config=config.expected_schema,
   )
   ```
3. В результате **селекторы никогда не заполняются**, и работает только эвристический `_LinkCollector`

**Последствия:**
- ❌ LLM-анализ тратится впустую (возвращает только схему, но не селекторы)
- ❌ Парсинг не использует найденные селекторы
- ❌ Качество извлечения данных низкое
- ❌ Не работает адаптивный парсинг с Scrapling

---

## 📋 Требуемые Изменения

### 1. `llm.py` — Добавление `extract_selector`

```python
async def analyze_structure(
    self,
    html: str,
    competitor: str,
    expected_fields: list[str] | None = None,
) -> dict[str, Any]:  # ← Теперь возвращает ВЕСЬ словарь с selectors + schema
    """
    Анализирует HTML и возвращает:
    - selectors: dict[str, str] — CSS-селекторы для каждого поля
    - schema: dict[str, str] — типы данных для каждого поля
    - confidence: float — уверенность в извлечении
    """
```

**Промпт должен возвращать:**
```json
{
    "selectors": {
        "container": "article, .news-item, .post, .vacancy-card",
        "title": "h1, h2, .title, .post-title, .vacancy-name",
        "text": ".content, .description, .post-content, .vacancy-description",
        "published_at": ".date, time, .published, .publish-date",
        "region": ".region, .location, .city",
        "media_name": ".source, .media, .publisher",
        "url": "a[href]"
    },
    "schema": {
        "title": "string",
        "text": "string",
        "published_at": "string",
        "region": "string",
        "url": "string",
        "media_name": "string"
    },
    "confidence": 0.85,
    "metadata": {
        "has_pagination": true,
        "pagination_selector": "a.next, .pagination .next",
        "items_per_page": 20
    }
}
```

### 2. `parser.py` — Исправление создания `AdapterState`

```python
# Было (ПРОБЛЕМА):
adapter = AdapterState(
    selectors=dict.fromkeys(config.expected_schema, ''),  # ← пустые строки!
    schema_config=config.expected_schema,
)

# Должно быть (ИСПРАВЛЕНИЕ):
analysis = await self._llm_client.analyze_structure(html, competitor)
adapter = AdapterState(
    source_name=source_name,
    selectors=analysis.get('selectors', {}),  # ← реальные селекторы!
    schema_config=analysis.get('schema', {}),
    confidence=analysis.get('confidence', 0.7),
    version=1,
)
```

### 3. Умное Чанкирование для Больших HTML

Добавить поддержку обработки больших страниц через чанкирование:

```python
async def analyze_structure_chunked(
    self,
    html: str,
    competitor: str,
    expected_fields: list[str] | None = None,
    max_chunk_size: int = 8000,
) -> dict[str, Any]:
    """
    Анализирует структуру с чанкированием для больших HTML.

    1. Очистка HTML
    2. Разбиение на логические чанки с перекрытием (overlap=500)
    3. Параллельный анализ каждого чанка через LLM
    4. Объединение результатов (слияние селекторов, усреднение confidence)
    """
```

---

## 📊 Детальная Спецификация Компонентов

### 1. Обновленный `LLMClient`

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `analyze_structure` | `async def analyze_structure(html, competitor, expected_fields=None) -> dict` | Анализ структуры с возвратом selectors + schema |
| `analyze_structure_chunked` | `async def analyze_structure_chunked(html, competitor, expected_fields=None, max_chunk_size=8000) -> dict` | Чанкированная версия |
| `_extract_json_from_response` | `def _extract_json_from_response(content) -> dict` | Извлечение JSON из ответа LLM |
| `_merge_chunk_results` | `def _merge_chunk_results(results) -> dict` | Объединение результатов чанков |

### 2. Обновленный `AdaptiveParser`

| Изменение | Описание |
|-----------|----------|
| Исправление `AdapterState` | Передача реальных селекторов из LLM |
| Использование `extract_selector` | Вместо `_LinkCollector` при наличии селекторов |
| Поддержка `source_request_url` | Сохранение URL запроса |

### 3. Оптимизация Чанкирования

| Параметр | Значение | Описание |
|----------|----------|----------|
| `max_chunk_size` | 8000 | Максимальный размер чанка |
| `overlap_size` | 500 | Перекрытие между чанками |
| `max_chunks` | 10 | Максимальное количество чанков |
| `parallel_workers` | 5 | Количество параллельных запросов |

---

## 📝 Промпт для `analyze_structure`

```markdown
Ты — эксперт по анализу HTML-страниц и извлечению структурированных данных.

## Задача:
Проанализируй HTML-код страницы и определи CSS-селекторы для извлечения данных.

## Входные данные:
- URL: {url}
- Конкурент: {competitor}
- Ожидаемые поля: {expected_fields}
- HTML (первые 8000 символов): {html}

## Требования:
1. Найди контейнер, который содержит список элементов (новости, вакансии, товары)
2. Для каждого поля определи CSS-селектор
3. Определи схему данных (типы полей)
4. Найди пагинацию (если есть)

## Ответь ТОЛЬКО в формате JSON:

{
    "selectors": {
        "container": "article, .news-item, .vacancy-card, .product-item, .post",
        "title": "h1, h2, h3, .title, .post-title, .vacancy-name, .item-title",
        "text": ".content, .description, .post-content, .vacancy-description, .item-description",
        "published_at": ".date, time, .published, .publish-date, .item-date",
        "region": ".region, .location, .city, .address",
        "media_name": ".source, .media, .publisher, .site-name",
        "url": "a[href]"
    },
    "schema": {
        "title": "string",
        "text": "string",
        "published_at": "string",
        "region": "string",
        "url": "string",
        "media_name": "string"
    },
    "confidence": 0.85,
    "metadata": {
        "has_pagination": true,
        "pagination_selector": "a.next, .pagination .next, .pager-next",
        "pagination_pattern": "page={page}",
        "items_per_page": 20,
        "page_type": "list",
        "site_structure": "article-based"
    }
}

## Правила:
1. Селекторы должны быть максимально специфичными, но устойчивыми к изменениям
2. Используй data-атрибуты если они есть (они более стабильны)
3. Для контейнера используй тег + класс (например, article.news-item)
4. Для полей используй классы с описательными названиями
5. Если поле не найдено, оставь пустую строку
6. Confidence — уверенность в извлечении (0.0-1.0)
7. Если есть пагинация — укажи селектор для кнопки "далее"
```

---

## 🏗️ Новый Алгоритм `llm.py`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    analyze_structure(html, competitor)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. ОЧИСТКА HTML                                                           │
│  - Удаление <script>, <style>, навигации, футеров                         │
│  - Извлечение основного контента                                          │
│  - Результат: ~15,000-20,000 символов                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. ПРОВЕРКА РАЗМЕРА                                                       │
│  - Если размер <= max_chunk_size (8000) → прямой анализ                   │
│  - Если размер > max_chunk_size → чанкирование                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│  3a. ПРЯМОЙ АНАЛИЗ               │  │  3b. ЧАНКИРОВАННЫЙ АНАЛИЗ        │
│  - Один запрос к LLM             │  │  - Разбиение на логические блоки │
│  - Парсинг JSON                  │  │  - Перекрытие 500 символов       │
│  - Возврат selectors + schema    │  │  - Параллельные запросы          │
└──────────────────────────────────┘  │  - Объединение результатов       │
                    │                   └──────────────────────────────────┘
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. ПОСТ-ОБРАБОТКА                                                        │
│  - Проверка наличия обязательных полей                                    │
│  - Нормализация селекторов                                                │
│  - Вычисление общей уверенности                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. ВОЗВРАТ РЕЗУЛЬТАТА                                                    │
│  - selectors: dict[str, str]                                              │
│  - schema: dict[str, str]                                                 │
│  - confidence: float                                                      │
│  - metadata: dict                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Структура Файлов После Рефакторинга

```
src/bp1/adaptive/
├── llm.py                    # Обновленный — analyze_structure() возвращает selectors
├── parser.py                 # Обновленный — использует реальные селекторы
├── chunker.py                # НОВЫЙ — умное чанкирование
├── html_cleaner.py           # НОВЫЙ — очистка HTML
├── prompts.py                # НОВЫЙ — промпты для LLM
└── tests/
    ├── test_llm.py           # Тесты LLMClient
    ├── test_parser.py        # Тесты AdaptiveParser
    └── test_chunker.py       # Тесты чанкирования
```

---

## ✅ Критерии Приемки

1. ✅ `LLMClient.analyze_structure()` возвращает **реальные CSS-селекторы**
2. ✅ `AdaptiveParser` использует селекторы из LLM (не пустые строки)
3. ✅ Поддержка чанкирования для больших HTML (>8000 символов)
4. ✅ Перекрытие между чанками (overlap=500) для сохранения контекста
5. ✅ Параллельное извлечение из чанков через asyncio.gather
6. ✅ Объединение результатов из чанков (слияние селекторов)
7. ✅ Fallback на эвристический парсер при отсутствии селекторов
8. ✅ Все тесты проходят (минимум 85% покрытия)
9. ✅ Документация обновлена

---

## 🎯 Итоговое Задание

Создай **обновленный модуль `llm.py`**, который:

1. **Возвращает реальные CSS-селекторы** (не только схему)
2. **Поддерживает чанкирование** для больших страниц
3. **Имеет fallback на эвристику** при недоступности LLM
4. **Использует параллельные запросы** для ускорения
5. **Объединяет результаты** из нескольких чанков
6. **Устраняет разрыв** между LLM-анализом и `parser.py`
