# Stealth — модуль антиобнаружения для Playwright

Переиспользуемый модуль для обхода систем антибот-защиты (QRATOR, Cloudflare и др.) при работе с Playwright в Python.

## Установка зависимостей

```bash
pip install playwright
playwright install chromium
```

## Структура модуля

```
stealth/
├── __init__.py          # Публичный API
├── js_evasions.js       # JS-скрипты обнаружения (navigator, plugins, WebGL)
├── browser_config.py    # Конфигурация запуска браузера и контекста
└── qrator_bypass.py     # Логика обхода QRATOR anti-bot
```

## Быстрый старт

```python
import asyncio
from playwright.async_api import async_playwright
from stealth import (
    get_launch_args,
    get_context_config,
    apply_stealth,
    bypass_qrator,
)


async def main():
    pw = await async_playwright().start()

    # 1. Запуск браузера с anti-detection аргументами
    browser = await pw.chromium.launch(
        headless=True,
        args=get_launch_args(headless=True),
    )

    # 2. Создание контекста с нужными настройками
    context = await browser.new_context(
        **get_context_config(user_agent='Mozilla/5.0 ...')
    )

    # 3. Инъекция JS-обманок (ДО создания страниц!)
    await apply_stealth(context)

    page = await context.new_page()

    # 4. Обход QRATOR (если сайт использует эту защиту)
    loaded = await bypass_qrator(page, context, 'https://fedresurs.ru')
    if loaded:
        print('Сайт загружен!')

    # ... работа со страницей ...

    await browser.close()
    await pw.stop()


asyncio.run(main())
```

## API

### `get_launch_args(headless=True)`

Возвращает список аргументов для запуска Chromium с обходом детекции.

| Аргумент | Описание |
|----------|----------|
| `headless` | `True` — режим `--headless=new` (по умолчанию), `False` — обычный режим |

**Возвращаемое значение:** `list[str]`

**Пример:**
```python
args = get_launch_args(headless=True)
# ['--headless=new', '--disable-blink-features=AutomationControlled',
#  '--no-sandbox', '--disable-dev-shm-usage', '--window-size=1920,1080']
```

---

### `get_context_config(locale, timezone, viewport_width, viewport_height, user_agent)`

Возвращает словарь kwargs для `browser.new_context()`.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `locale` | `str` | `"ru-RU"` | Язык браузера |
| `timezone` | `str` | `"Europe/Moscow"` | Часовой пояс |
| `viewport_width` | `int` | `1920` | Ширина viewport |
| `viewport_height` | `int` | `1080` | Высота viewport |
| `user_agent` | `str \| None` | `None` | Кастомный UA (если None — используется стандартный Playwright) |

**Возвращаемое значение:** `dict`

**Пример:**
```python
config = get_context_config(
    locale='en-US',
    timezone='America/New_York',
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...',
)
context = await browser.new_context(**config)
```

---

### `apply_stealth(context, js_path=None)`

Инжектирует JS-скрипты обмана в контекст браузера. **Вызывать ДО создания страниц.**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `context` | `BrowserContext` | Playwright контекст |
| `js_path` | `str \| None` | Путь к кастомному JS-файлу. Если `None` — используется встроенный `js_evasions.js` |

**Что делает скрипт `js_evasions.js`:**
- `navigator.webdriver` → `undefined` (скрывает признак автоматизации)
- Эмуляция `window.chrome` (app, runtime, csi, loadTimes)
- Фейковые плагины (Chrome PDF Plugin, Chrome PDF Viewer, Native Client)
- Подмена `navigator.languages`, `platform`, `vendor`
- `navigator.hardwareConcurrency` = 8, `deviceMemory` = 8, `maxTouchPoints` = 0
- `window.outerWidth/outerHeight` = 1920x1080
- WebGL vendor/renderer spoofing (Intel UHD 630)

**Пример:**
```python
# Со встроенным скриптом
await apply_stealth(context)

# С кастомным скриптом
await apply_stealth(context, js_path='./my_evasions.js')
```

---

### `bypass_qrator(page, context, target_url, timeout)`

Обходит QRATOR anti-bot защиту (используется на fedresurs.ru).

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `page` | `Page` | — | Playwright страница |
| `context` | `BrowserContext` | — | Контекст (нужен для чтения cookies) |
| `target_url` | `str` | `"https://fedresurs.ru"` | Базовый URL сайта |
| `timeout` | `int` | `60000` | Таймаут навигации (мс) |

**Возвращаемое значение:** `bool` — `True` если главная страница загружена.

**Алгоритм обхода:**
1. Переход на `target_url` → получаем 401 (JS challenge)
2. Ожидание 25 секунд — QRATOR ставит cookie `qrator_jsr`
3. Переход на `/search` — сервер отвечает 200
4. Клик по логотипу (`a[href="/"]`) → переход на главную страницу

**Пример:**
```python
loaded = await bypass_qrator(page, context, 'https://fedresurs.ru')
if not loaded:
    print('Не удалось обойти QRATOR')
```

## Константы QRATOR

В `qrator_bypass.py` определены тайминги (можно переопределить):

```python
from stealth.qrator_bypass import (
    QRATOR_CHALLENGE_WAIT_MS,  # 25000 — ожидание JS challenge
    QRATOR_POST_NAVIGATION_WAIT_MS,  # 3000  — ожидание после перехода на /search
    QRATOR_LOGO_CLICK_WAIT_MS,  # 5000  — ожидание после клика по логотипу
)
```

## Интеграция в пакеты парсинга

Модуль `stealth/` расположен в корне проекта `Testing/` и предназначен для переиспользования во всех пакетах парсинга.

**Подключение в другом пакете:**
```python
import sys
from pathlib import Path

# Добавляем корень проекта в путь
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from stealth import (
    apply_stealth,
    get_launch_args,
    get_context_config,
    bypass_qrator,
)
```

**Пример интеграции в BrowserManager:**
```python
from stealth.browser_config import (
    apply_stealth,
    get_context_config,
    get_launch_args,
)


class BrowserManager:
    async def start(self):
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=self._headless,
            args=get_launch_args(headless=self._headless),
        )
        context = await browser.new_context(**get_context_config())
        await apply_stealth(context)
        return context
```

**Параметр `qrator_bypass` в SearchRequest:**

Пакет `fedresurs_rpa` поддерживает опциональный QRATOR bypass через параметр `qrator_bypass` в `SearchRequest`:

```python
from fedresurs_rpa import FedresursRPA
from fedresurs_rpa.models import SearchRequest

# С QRATOR bypass (по умолчанию) — для fedresurs.ru
request = SearchRequest(
    name='ООО "Компания"',
    inn='6318034066',
    qrator_bypass=True,  # обход QRATOR (25с ожидание + двухшаговая навигация)
)

# Без QRATOR bypass — для сайтов без anti-bot защиты
request = SearchRequest(
    name='ООО "Компания"',
    inn='1234567890',
    qrator_bypass=False,  # обычная навигация page.goto()
)
```

| Значение | Поведение |
|----------|-----------|
| `qrator_bypass=True` (по умолчанию) | Двухшаговая навигация: 401 → ожидание cookie → /search → клик по логотипу |
| `qrator_bypass=False` | Обычный `page.goto()` с ожиданием 3 секунды |

## Совместимость

- **Python:** 3.9+
- **Playwright:** 1.40.0+
- **Браузеры:** Chromium (основной), Firefox, WebKit (тестированы)

## Тестирование

Запуск теста fedresurs.ru:
```bash
cd Testing
python -m fedresurs_rpa.test_headless
```

Запуск теста всех браузеров:
```bash
cd Testing/fedresurs_all_browsers
node test_all_browsers.mjs
```
