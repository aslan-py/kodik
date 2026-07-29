# Промпт для точечного исправления кода парсинга

## Контекст задачи
Ты — эксперт по парсингу веб-страниц на Python с использованием Playwright. Твоя задача — внести точечные изменения в существующий RPA-парсер для fedresurs.ru, чтобы добавить извлечение структурированных данных из карточки компании. Текущий код сохраняет только HTML-страницу, но не извлекает конкретную информацию.

## Исходные данные

### Структура страницы для парсинга (из предоставленного HTML)
```html
<!-- Статус компании -->
<div _ngcontent-mhn-c68="" class="label-item-text">Действующее</div>

<!-- Основная информация компании -->
<div class="information-content">
  <!-- Здесь находится вся текстовая информация о компании -->
</div>
```

### Текущий код (файл parser.py, метод `_execute_search`)
```python
# Клик по первому результату для открытия карточки компании
await self._open_company_card(page)

timestamp = datetime.now()
filename = generate_filename(
    name=request.name,
    inn=request.inn,
    timestamp=timestamp,
)
filepath = os.path.join(request.output_dir, filename)

await self._save_page(page, filepath)

logger.info('Поиск успешно завершён: %s', filepath)

return SearchResult(
    success=True,
    name=request.name,
    inn=request.inn,
    file_path=filepath,
    timestamp=timestamp,
    proxy_used=format_proxy_string(proxy),
    user_agent_used=browser_manager.user_agent,
)
```

## Задача

Внеси следующие точечные изменения в код:

### 1. Создай новый файл `extractor.py` в той же директории

Добавь класс `CompanyDataExtractor` со следующими методами:
- `async def extract_company_data(self, page: Page) -> dict` — основной метод извлечения
- `async def _extract_status(self, page: Page) -> str` — извлечение статуса из `.label-item-text`
- `async def _extract_full_text(self, page: Page) -> str` — извлечение всего текста из `.information-content`
- `async def _extract_with_fallback(self, page: Page, selector: str, fallback_selectors: list[str] = None) -> str` — метод с fallback-селекторами

Особенности реализации:
- Используй Playwright локаторы (`page.locator()`, `.first`, `.inner_text()`)
- Добавь обработку ошибок (если элемент не найден — возвращать пустую строку или None)
- Добавь логирование каждого шага извлечения

### 2. Модифицируй файл `parser.py`

**Изменение 1:** Добавь импорт в начало файла
```python
from .extractor import CompanyDataExtractor
```

**Изменение 2:** После сохранения страницы (после `await self._save_page(page, filepath)`), добавь блок извлечения данных:

```python
# Извлечение структурированных данных
logger.info('Извлечение данных компании...')
extractor = CompanyDataExtractor()
company_data = await extractor.extract_company_data(page)

# Логирование результатов
logger.info('Статус компании: %s', company_data.get('status'))
logger.info(
    'Извлечено текста: %d символов', len(company_data.get('full_text', ''))
)
```

**Изменение 3:** Модифицируй возвращаемый `SearchResult`, добавив новые поля:

```python
return SearchResult(
    success=True,
    name=request.name,
    inn=request.inn,
    file_path=filepath,
    status=company_data.get('status'),
    raw_text=company_data.get('full_text'),
    timestamp=timestamp,
    proxy_used=format_proxy_string(proxy),
    user_agent_used=browser_manager.user_agent,
)
```

**Изменение 4:** Улучши метод `_open_company_card`, добавив ожидание конкретного элемента `.information-content`:

```python
async def _open_company_card(self, page: Page) -> None:
    """Кликнуть по первому результату для открытия карточки компании."""
    logger.info('Открытие карточки компании...')

    try:
        # Ожидание ссылки "Вся информация"
        link = page.locator('a').filter(has_text='Вся информация').first
        await link.wait_for(state='visible', timeout=15000)
        await link.click()

        # Ожидание загрузки страницы карточки компании
        await page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(3)

        # Ожидание появления информации о компании (улучшенный блок)
        try:
            # Ожидаем появления контента компании
            await page.wait_for_selector('.information-content', timeout=15000)
            logger.info('Контент компании загружен')
        except Exception as e:
            logger.warning('Не удалось найти .information-content: %s', e)
            # Пробуем альтернативные селекторы
            try:
                await page.wait_for_selector(
                    '.company-name, .entity-header, app-company-card, [class*="company"]',
                    timeout=10000,
                )
                logger.info('Компания загружена (альтернативный селектор)')
            except Exception:
                logger.warning(
                    'Не удалось найти информацию о компании, продолжаем...'
                )

        logger.info('Карточка компании загружена')
    except Exception as e:
        logger.warning('Не удалось открыть карточку компании: %s', e)
```

### 3. Модифицируй файл `schemas.py` (переименованный из `models.py`)

Добавь новые поля в `SearchResult`:

```python
class SearchResult(BaseModel):
    """Модель результата операции поиска."""

    success: bool
    name: str
    inn: str | None = None
    file_path: str | None = None
    html_content: str | None = None
    status: str | None = None  # НОВОЕ: статус компании
    raw_text: str | None = None  # НОВОЕ: полный текст из information-content
    error: str | None = None
    error_type: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    proxy_used: str | None = None
    user_agent_used: str | None = None
```

### 4. Добавь новые селекторы в `constants.py`

Добавь в словарь `SELECTORS`:

```python
SELECTORS = {
    # ... существующие селекторы ...
    'company_status': '.label-item-text',  # Статус компании
    'company_info_container': '.information-content',  # Основной контейнер с информацией
    'company_name': '.company-name, .entity-header',  # Название компании
    'company_inn': '[data-testid="inn"], .inn-value',  # ИНН компании
}
```

### 5. Модифицируй файл `test_headless.py` для проверки новых данных

Добавь вывод извлеченной информации:

```python
if result.success:
    print(f'\nOK: {result.name} (ИНН: {result.inn})')
    print(f'  File: {result.file_path}')
    print(f'  Status: {result.status}')
    print(
        f'  Data length: {len(result.raw_text) if result.raw_text else 0} characters'
    )
    print(f'  Timestamp: {result.timestamp}')
    if result.raw_text:
        print(f'  Preview: {result.raw_text[:200]}...')
else:
    print(f'\nFAIL: {result.error}')
    print(f'  Error type: {result.error_type}')
```

## Важные требования к реализации

1. **Обработка ошибок**: Все методы извлечения должны быть обернуты в try-except с логированием, чтобы ошибка парсинга не прерывала весь процесс
2. **Логирование**: Добавь логирование на каждом этапе с использованием существующего `logger`
3. **Асинхронность**: Все методы должны быть асинхронными (`async/await`)
4. **Fallback-механизмы**: Для каждого селектора предусмотри 2-3 альтернативных варианта
5. **Таймауты**: Используй разумные таймауты (10-15 секунд для ожидания элементов)
6. **Импорты**: Все импорты должны быть корректными с учетом структуры пакета

## Критерии приемки

- [ ] Создан файл `extractor.py` с классом `CompanyDataExtractor`
- [ ] Все методы извлечения работают асинхронно
- [ ] В `parser.py` добавлена интеграция с экстрактором
- [ ] В `schemas.py` добавлены новые поля
- [ ] В `constants.py` добавлены новые селекторы
- [ ] Тест `test_headless.py` выводит извлеченные данные
- [ ] Код содержит обработку ошибок и логирование
- [ ] Все импорты корректны

## Дополнительные указания

- Не изменяй существующую логику работы браузера и обхода QRATOR
- Сохрани обратную совместимость с существующими вызовами
- Используй существующие утилиты и константы
- Следуй стилю кодирования проекта

Внеси все перечисленные изменения в соответствующие файлы, следуя плану и требованиям.
