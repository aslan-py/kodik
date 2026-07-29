# План рефакторинга для полного парсинга fedresurs.ru

## 1. Анализ текущей архитектуры

### 1.1 Выявленные проблемы
- **Отсутствие парсинга данных** - сохраняется только HTML, без извлечения структурированной информации
- **Неконкретные селекторы** - используются общие ожидания вместо точных CSS-селекторов
- **Модель данных неполная** - `SearchResult` не содержит полей для извлеченных данных компании
- **Некорректное имя модели** - `models.py` вводит в заблуждение (не БД-модели)
- **Отсутствие модуля извлечения** - нет отдельного класса/функций для парсинга

### 1.2 Структура файлов для изменений
```
src/
├── bp1/
│   └── collectors/
│       └── fedresurs_rpa/
│           ├── parser.py          # Основной RPA-класс (изменения)
│           ├── schemas.py         # Переименовать из models.py
│           ├── extractor.py       # НОВЫЙ файл для парсинга данных
│           ├── constants.py       # Добавить селекторы
│           └── ...
```

## 2. План изменений

### 2.1 Переименование файла models.py → schemas.py
**Действия:**
- Переименовать `models.py` в `schemas.py`
- Обновить все импорты в:
  - `parser.py`
  - `browser.py`
  - `utils.py`
  - `test_headless.py`
- В `schemas.py` переименовать `SearchResult` → `CompanyData` (или оставить для обратной совместимости)

### 2.2 Добавление новых селекторов в constants.py
```python
# Добавить в SELECTORS:
SELECTORS.update(
    {
        # Для извлечения статуса компании
        'company_status': '.label-item-text',
        # Для основной информации компании (information-content)
        'company_info_container': '.information-content',
        # Возможные дополнительные селекторы (из анализа HTML)
        'company_name': '.company-name, .entity-header',
        'company_inn': '[data-testid="inn"], .inn-value',
        'company_address': '.company-address, .address-value',
    }
)
```

### 2.3 Создание нового модуля extractor.py

**Структура:**
```python
class CompanyDataExtractor:
    """Класс для извлечения структурированных данных из карточки компании"""

    async def extract_company_data(self, page: Page) -> dict:
        """Извлечь все данные компании"""
        return {
            'status': await self._extract_status(page),
            'full_text': await self._extract_full_text(page),
            # ... другие поля
        }

    async def _extract_status(self, page: Page) -> str:
        """Извлечь статус компании (Действующее/Ликвидировано и т.д.)"""
        # Использовать селектор .label-item-text

    async def _extract_full_text(self, page: Page) -> str:
        """Извлечь весь текст из information-content"""
        # document.querySelector(".information-content")?.innerText
```

### 2.4 Модификация schemas.py

```python
class CompanyData(BaseModel):
    """Модель данных компании"""

    success: bool
    name: str
    inn: str | None = None
    status: str | None = None  # Новое поле
    raw_text: str | None = None  # Новое поле
    file_path: str | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    proxy_used: str | None = None
    user_agent_used: str | None = None

    # Для обратной совместимости
    @property
    def html_content(self) -> str | None:
        return self.raw_text
```

### 2.5 Модификация parser.py

**Основные изменения:**

1. **Добавить импорт экстрактора:**
```python
from .extractor import CompanyDataExtractor
```

2. **Модифицировать метод `_execute_search`:**
```python
async def _execute_search(...):
    # ... существующий код до сохранения ...

    # Сохранить HTML
    await self._save_page(page, filepath)

    # НОВОЕ: Извлечение данных
    extractor = CompanyDataExtractor()
    company_data = await extractor.extract_company_data(page)

    return SearchResult(
        success=True,
        name=request.name,
        inn=request.inn,
        file_path=filepath,
        status=company_data.get('status'),
        raw_text=company_data.get('full_text'),
        # ... остальные поля
    )
```

3. **Добавить метод `_extract_data_from_page`:**
```python
async def _extract_data_from_page(self, page: Page) -> dict:
    """Извлечь структурированные данные после сохранения HTML"""
    # Использовать экстрактор
```

### 2.6 Улучшение метода `_open_company_card`

**Проблема:** текущий метод только кликает и ждет, но не проверяет успешность загрузки данных.

**Изменения:**
- Добавить ожидание конкретного элемента `.information-content`
- Проверить наличие статуса компании
- Добавить fallback-механизмы при недоступности элементов

### 2.7 Добавление методов обработки ошибок в extractor.py

```python
class ExtractionError(Exception):
    """Ошибка при извлечении данных"""

    pass


# В CompanyDataExtractor:
async def _extract_with_fallback(
    self, page: Page, selector: str, fallback_selector: str = None
):
    """Извлечь данные с fallback-механизмом"""
```

## 3. Дополнительные улучшения

### 3.1 Логирование
- Добавить логирование этапов извлечения данных
- Логировать успешность извлечения каждого поля

### 3.2 Обработка исключений
- Добавить специфичные исключения для парсинга
- Graceful degradation при отсутствии элементов

### 3.3 Кэширование селекторов
- Оптимизировать поиск элементов через `page.locator()`
- Использовать `first()` и `last()` для работы с несколькими элементами

## 4. Обновление тестов

### 4.1 Модификация test_headless.py
```python
# Добавить проверку извлеченных данных
if result.success:
    print(f'Status: {result.status}')
    print(f'Data length: {len(result.raw_text) if result.raw_text else 0}')
```

### 4.2 Создание unit-тестов для extractor.py
- Тесты с загруженным HTML из файла (как в приложении)
- Тесты на различные статусы компании

## 5. Порядок внесения изменений

1. ✅ Переименовать `models.py` → `schemas.py` и обновить импорты
2. ✅ Создать `extractor.py` с классом `CompanyDataExtractor`
3. ✅ Добавить новые селекторы в `constants.py`
4. ✅ Обновить `schemas.py` (добавить поля статуса и текста)
5. ✅ Модифицировать `parser.py` (интеграция экстрактора)
6. ✅ Обновить `test_headless.py` для проверки новых данных
7. ✅ Добавить обработку ошибок в экстрактор
8. ✅ Протестировать на реальных данных

## 6. Ожидаемый результат

После изменений код будет:
- Сохранять HTML-страницу (как сейчас)
- Извлекать структурированные данные:
  - Статус компании (из `.label-item-text`)
  - Полный текст из `.information-content`
  - В будущем можно добавлять другие поля
- Возвращать объект с полными данными
- Иметь четкое разделение ответственности (RPA-логика vs парсинг)

## 7. Потенциальные риски и их решение

| Риск | Решение |
|------|---------|
| Элементы не появляются после клика | Увеличить таймауты, добавить повторные попытки |
| Изменение структуры HTML на сайте | Использовать несколько селекторов-запасных |
| Angular не успевает отрендерить данные | Добавить ожидание конкретных элементов, не только networkidle |
| Большой объем текста в information-content | Оптимизировать извлечение, использовать innerText вместо outerHTML |
