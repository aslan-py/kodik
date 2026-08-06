# 🧠 Промпт для Рефакторинга `llm.py`: Интеллектуальный Парсинг Крупных HTML-Страниц с Использованием LLM

## 🎯 Контекст и Задача

Ты — ведущий AI-инженер с 10-летним опытом разработки систем обработки естественного языка и веб-автоматизации. Ты работал над проектами, где требовалось извлекать структурированные данные из огромных HTML-страниц, используя LLM с ограниченным контекстным окном.

У тебя есть существующий модуль `llm.py`, который отвечает за анализ HTML и извлечение данных с использованием LLM. Текущая реализация отправляет **весь HTML** в одном запросе, что приводит к ошибкам, так как страницы часто превышают лимит модели (например, 65,000 символов против лимита 3,000-8,000 у DeepSeek).

**Твоя задача:** Переработать алгоритм работы `llm.py`, внедрив многоступенчатый подход: **умное чанкирование → параллельное извлечение → объединение результатов**, как описано в предыдущем анализе.

**Файл для изменения:** `src/bp1/adaptive/llm.py`

---

## 📋 Текущий Код (Схематично)

```python
# src/bp1/adaptive/llm.py

class LLMClient:
    """Клиент для LLM-анализа HTML."""

    def __init__(
        self,
        model: str = "deepseek-chat",
        max_tokens: int = 4096,
        max_input_chars: int = 3000,  # ← Текущее ограничение
        api_key: str = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.max_input_chars = max_input_chars
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def analyze_structure(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str] = None,
    ) -> AdapterConfig:
        """
        Анализирует HTML и извлекает структуру данных.

        ПРОБЛЕМА: Отправляет весь HTML в одном запросе.
        Если html > max_input_chars → ошибка.
        """
        if len(html) > self.max_input_chars:
            raise ValueError(
                f"HTML слишком большой ({len(html)} символов). "
                f"Максимум: {self.max_input_chars}"
            )

        prompt = self._build_analysis_prompt(html, competitor, expected_fields)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return AdapterConfig(**json.loads(response.choices[0].message.content))

    async def extract_items(
        self,
        html: str,
        adapter: AdapterConfig,
    ) -> list[ParsedItem]:
        """
        Извлекает элементы данных по адаптеру.

        ПРОБЛЕМА: Аналогично — отправляет весь HTML целиком.
        """
        # ... аналогичная логика ...
```

### 🔴 Недостатки Текущей Реализации

1. **Жесткое ограничение по размеру** — страницы > 3000 символов падают
2. **Нет структурированного чанкирования** — даже если увеличить лимит, страница может не поместиться в контекстное окно модели
3. **Нет перекрытия между чанками** — потеря контекста на границах
4. **Нет объединения результатов** — если чанков несколько, данные не собираются воедино
5. **Нет приоритезации данных** — нет механизма, чтобы сначала проанализировать самый важный контент

---

## 🏗️ Требуемая Архитектура Нового Алгоритма

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ВХОД: HTML (до 65,000+ символов)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ШАГ 1: ОЧИСТКА И СЖАТИЕ (Preprocessing)                                  │
│  - Удаление <script>, <style>, навигации, футеров, рекламы               │
│  - Извлечение основного контента (article, main, body)                   │
│  - Преобразование в Markdown или чистую текстовую структуру              │
│  - Результат: 65,000 → ~15,000-20,000 символов                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ШАГ 2: УМНОЕ ЧАНКИРОВАНИЕ (Structured Chunking)                         │
│  - Разбиение по логическим блокам (section, article, p, div)             │
│  - Каждый чанк ≤ max_chunk_size (3,000 символов)                         │
│  - Перекрытие между чанками: overlap_size (200-500 символов)             │
│  - Результат: список из 5-7 чанков                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ШАГ 3: ПАРАЛЛЕЛЬНОЕ ИЗВЛЕЧЕНИЕ (Parallel Extraction)                    │
│  - Для каждого чанка: запрос к LLM с промптом "извлечь из этого чанка"  │
│  - asyncio.gather() для параллельного выполнения                         │
│  - Результат: список результатов от каждого чанка                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ШАГ 4: ОБЪЕДИНЕНИЕ И ДЕДУПЛИКАЦИЯ (Merge & Deduplicate)                │
│  - Объединение items из всех чанков                                       │
│  - Документ-поля (competitor, inn) — из первого чанка                   │
│  - Дедупликация по url или title                                         │
│  - Результат: единый структурированный AdapterConfig / list[ParsedItem]  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Детальная Спецификация Новых Компонентов

### 1. `HtmlCleaner` — Очистка и Сжатие HTML

```python
class HtmlCleaner:
    """
    Очищает HTML от шума и сжимает его до основного контента.
    """

    def clean(
        self,
        html: str,
        extract_metadata: bool = True,
        min_text_length: int = 100,
    ) -> dict[str, Any]:
        """
        Очищает HTML и возвращает структурированный контент.

        Args:
            html: Сырой HTML.
            extract_metadata: Извлекать ли метаданные (title, description).
            min_text_length: Минимальная длина текста для сохранения блока.

        Returns:
            dict:
                - content: Очищенный HTML или Markdown.
                - metadata: dict с title, description, keywords.
                - blocks: list[dict] — список логических блоков для чанкирования.
                - stats: dict с количеством блоков, исходным и очищенным размером.
        """
```

**Алгоритм очистки:**
1. Парсинг HTML через BeautifulSoup.
2. Удаление тегов: `script`, `style`, `nav`, `footer`, `header`, `aside`, `noscript`.
3. Удаление атрибутов: `onclick`, `onload`, `onerror` и других JavaScript-событий.
4. Извлечение основного контента: поиск тегов `article`, `main`, `section`, `body`.
5. Преобразование в структурированный формат с сохранением иерархии (HTML/JSON/Markdown).
6. Извлечение метаданных: `title`, `description`, `keywords` (из `<meta>` тегов).

---

### 2. `StructuredChunker` — Умное Чанкирование

```python
class StructuredChunker:
    """
    Разбивает очищенный HTML на логические чанки с перекрытием.
    """

    def __init__(
        self,
        max_chunk_size: int = 3000,
        overlap_size: int = 300,
        block_tags: list[str] = None,
    ):
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.block_tags = block_tags or ["section", "article", "div", "p"]

    def chunk(self, cleaned_content: dict[str, Any]) -> list[Chunk]:
        """
        Разбивает очищенный контент на чанки.

        Args:
            cleaned_content: Результат HtmlCleaner.clean().

        Returns:
            list[Chunk]:
                - index: int — порядковый номер чанка.
                - content: str — текст чанка.
                - start_block: int — индекс начального блока.
                - end_block: int — индекс конечного блока.
                - metadata: dict — метаданные блока (заголовки, структура).
        """
```

**Алгоритм чанкирования:**
1. Извлечь логические блоки из `cleaned_content.blocks`.
2. Для каждого блока определить его размер.
3. Собирать блоки в чанк, пока размер не превысит `max_chunk_size`.
4. При превышении — завершить чанк и начать новый.
5. Добавить перекрытие: последние `overlap_size` символов из предыдущего чанка в начало следующего.
6. Сохранить метаданные каждого чанка (заголовок блока, структура).

```python
@dataclass
class Chunk:
    """Структура для хранения чанка."""
    index: int
    content: str
    start_block: int
    end_block: int
    metadata: dict[str, Any]
    size: int = 0
```

---

### 3. `LLMExtractor` — Параллельное Извлечение

```python
class LLMExtractor:
    """
    Извлекает данные из чанков с использованием LLM.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        max_workers: int = 5,
        timeout: int = 30,
    ):
        self.llm_client = llm_client
        self.max_workers = max_workers
        self.timeout = timeout

    async def extract_from_chunk(
        self,
        chunk: Chunk,
        competitor: str,
        expected_fields: list[str],
    ) -> dict[str, Any]:
        """
        Извлекает данные из одного чанка.

        Args:
            chunk: Чанк для анализа.
            competitor: Название конкурента.
            expected_fields: Ожидаемые поля для извлечения.

        Returns:
            dict: Извлеченные данные (items, metadata, confidence).
        """

    async def extract_all(
        self,
        chunks: list[Chunk],
        competitor: str,
        expected_fields: list[str],
    ) -> list[dict[str, Any]]:
        """
        Извлекает данные из всех чанков параллельно.

        Использует asyncio.gather() для максимальной производительности.
        """
        tasks = [
            self.extract_from_chunk(chunk, competitor, expected_fields)
            for chunk in chunks
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

**Промпт для извлечения из одного чанка:**

```python
def _build_extraction_prompt(
    chunk: Chunk,
    competitor: str,
    expected_fields: list[str],
) -> str:
    return f"""
    Проанализируй следующий фрагмент HTML-страницы.

    Задача: Извлечь структурированные данные о компании "{competitor}" и её деятельности.

    Ожидаемые поля: {', '.join(expected_fields)}

    Важно:
    1. Извлекай ТОЛЬКО из этого фрагмента.
    2. Если поле не найдено в этом фрагменте, верни null.
    3. Для ссылок всегда возвращай полный URL (добавляй base_url если нужно).
    4. Даты приводи к формату YYYY-MM-DD, если это возможно.

    ФРАГМЕНТ HTML (часть {chunk.index} из {total_chunks}):
    ```html
    {chunk.content}
    ```

    Верни JSON с извлеченными данными в формате:
    {{
        "items": [
            {{
                "url": "https://example.com/item/1",
                "title": "Название события",
                "text": "Описание...",
                "published_at": "2024-01-01",
                "region": "Москва",
                "media_name": "СМИ",
                "extra": {{"field1": "value1"}}
            }}
        ],
        "metadata": {{
            "total_items_found": 5,
            "confidence": 0.95,
            "notes": "Дополнительная информация"
        }}
    }}
    """
```

---

### 4. `ResultMerger` — Объединение и Дедупликация

```python
class ResultMerger:
    """
    Объединяет результаты из всех чанков.
    """

    def __init__(
        self,
        dedup_key: str = "url",
        merge_metadata: bool = True,
    ):
        self.dedup_key = dedup_key
        self.merge_metadata = merge_metadata

    def merge(
        self,
        results: list[dict[str, Any]],
        chunk_metadata: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Объединяет результаты из чанков в единый структурированный ответ.

        Args:
            results: Список результатов от каждого чанка.
            chunk_metadata: Метаданные каждого чанка.

        Returns:
            dict:
                - items: list[dict] — объединенный список элементов.
                - metadata: dict — метаданные объединенного результата.
                - confidence: float — общая уверенность.
                - chunks_processed: int — количество обработанных чанков.
                - total_items_found: int — общее количество найденных элементов.
                - duplicate_count: int — количество удаленных дубликатов.
        """
```

**Алгоритм объединения:**
1. Собрать все `items` из всех результатов.
2. Применить дедупликацию по `dedup_key` (по умолчанию `url`).
3. Если у элементов нет `url`, использовать `title` + `published_at` как ключ.
4. Для документа-полей (competitor, inn) взять значение из первого найденного.
5. Вычислить общую уверенность как среднее арифметическое.
6. Вернуть объединенный результат.

---

### 5. Обновленный `LLMClient` (Главный Оркестратор)

```python
class LLMClient:
    """
    Клиент для LLM-анализа HTML с поддержкой умного чанкирования.
    """

    def __init__(
        self,
        model: str = "deepseek-chat",
        max_tokens: int = 4096,
        max_input_chars: int = 3000,
        overlap_size: int = 300,
        api_key: str = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.max_input_chars = max_input_chars
        self.overlap_size = overlap_size

        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.cleaner = HtmlCleaner()
        self.chunker = StructuredChunker(
            max_chunk_size=max_input_chars,
            overlap_size=overlap_size,
        )
        self.extractor = LLMExtractor(self)
        self.merger = ResultMerger()

    async def analyze_structure(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str] = None,
    ) -> AdapterConfig:
        """
        Анализирует HTML и извлекает структуру данных.

        Теперь поддерживает большие страницы через чанкирование.
        """
        # 1. Очистка и сжатие
        cleaned = self.cleaner.clean(html)

        # 2. Умное чанкирование
        chunks = self.chunker.chunk(cleaned)

        if len(chunks) == 1:
            # Если контент помещается в один чанк — обрабатываем напрямую
            return await self._analyze_single_chunk(
                chunks[0].content,
                competitor,
                expected_fields,
            )

        # 3. Параллельное извлечение из всех чанков
        results = await self.extractor.extract_all(
            chunks=chunks,
            competitor=competitor,
            expected_fields=expected_fields,
        )

        # 4. Объединение результатов
        merged = self.merger.merge(
            results=results,
            chunk_metadata=[c.metadata for c in chunks],
        )

        # 5. Формирование AdapterConfig
        return self._to_adapter_config(merged)

    async def extract_items(
        self,
        html: str,
        adapter: AdapterConfig,
    ) -> list[ParsedItem]:
        """
        Извлекает элементы данных по адаптеру.

        Аналогично использует чанкирование.
        """
        # ... аналогичная логика ...
```

---

## 📁 Структура Новых Файлов

Создай следующие файлы в `src/bp1/adaptive/`:

```
src/bp1/adaptive/
├── llm.py                    # Обновленный LLMClient (главный оркестратор)
├── html_cleaner.py           # HtmlCleaner — очистка и сжатие
├── chunker.py                # StructuredChunker — умное чанкирование
├── extractor.py              # LLMExtractor — параллельное извлечение
├── merger.py                 # ResultMerger — объединение и дедупликация
├── schemas.py                # Добавить Chunk, ExtractionResult, MergedResult
└── tests/
    ├── test_html_cleaner.py
    ├── test_chunker.py
    ├── test_extractor.py
    └── test_merger.py
```

---

## 🧪 Требования к Тестированию

1. **Тест очистки**: HTML с 65,000 символов → очищенный контент ~15,000 символов.
2. **Тест чанкирования**: 15,000 символов → 5 чанков по ~3,000 символов + перекрытие 300 символов.
3. **Тест извлечения**: Каждый чанк возвращает корректные данные (не менее 80% точности).
4. **Тест объединения**: Дубликаты удалены, итоговое количество элементов = сумме уникальных элементов из чанков.
5. **Интеграционный тест**: Реальный запрос к DeepSeek для страницы > 65,000 символов — успешное выполнение.

---

## ✅ Критерии Приемки

1. ✅ LLMClient обрабатывает страницы любого размера (до 1,000,000 символов).
2. ✅ Очистка HTML уменьшает объем минимум в 2-3 раза.
3. ✅ Чанкирование сохраняет логическую структуру контента.
4. ✅ Перекрытие между чанками предотвращает потерю контекста.
5. ✅ Параллельное извлечение работает асинхронно (asyncio.gather).
6. ✅ Объединение данных корректно собирает результаты из всех чанков.
7. ✅ Дедупликация работает по URL (или title+published_at).
8. ✅ Точность извлечения не ниже, чем при обработке всей страницы целиком.
9. ✅ Все тесты проходят (минимум 85% покрытия).
10. ✅ Документация обновлена.

---

## 🎯 Итоговое Задание

Переработай `llm.py`, внедрив многоступенчатый алгоритм обработки больших HTML-страниц. Создай интеллектуальную систему, которая:

1. **Очищает HTML** от шума, сжимая объем данных.
2. **Разбивает на логические чанки** с перекрытием для сохранения контекста.
3. **Извлекает данные параллельно** из каждого чанка с использованием LLM.
4. **Объединяет результаты**, удаляя дубликаты и сохраняя всю информацию.
