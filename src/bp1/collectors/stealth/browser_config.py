"""Аргументы запуска браузера, конфиг контекста и инъекция стелса.

Все функции имеют параметры по умолчанию, обеспечивающие полный стелс.
Для сайтов, где стелс ломает JS (например, kad.arbitr.ru), можно
выборочно отключить отдельные инъекции через skip-флаги.
"""

from pathlib import Path

from playwright.async_api import BrowserContext

_JS_EVASIONS_PATH = Path(__file__).parent / 'js_evasions.js'

# Маркеры секций в js_evasions.js
_SECTION_MARKERS = {
    'webdriver': '// === SECTION: webdriver ===',
    'chrome': '// === SECTION: chrome ===',
    'plugins': '// === SECTION: plugins ===',
    'navigator': '// === SECTION: navigator ===',
    'webgl': '// === SECTION: webgl ===',
}


def _parse_js_sections(script: str) -> dict[str, str]:
    """Разобрать JS-скрипт на именованные секции.

    Секции разделяются маркерами вида ``// === SECTION: name ===``.
    """
    sections: dict[str, str] = {}
    lines = script.splitlines(keepends=True)

    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        # Проверяем, не является ли строка маркером секции
        found_section = None
        for name, marker in _SECTION_MARKERS.items():
            if line.strip() == marker:
                found_section = name
                break

        if found_section is not None:
            # Сохраняем предыдущую секцию
            if current_section is not None:
                sections[current_section] = ''.join(current_lines)
            current_section = found_section
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    # Сохраняем последнюю секцию
    if current_section is not None:
        sections[current_section] = ''.join(current_lines)

    return sections


def get_launch_args(
    headless: bool = True,
    headless_mode: str = 'new',
) -> list[str]:
    """Вернуть аргументы запуска Chromium для антидетекта.

    Args:
        headless: Использовать headless-режим.
        headless_mode: Режим headless:
            - 'new' (по умолчанию) — ``--headless=new`` (современный headless)
            - 'old' — ``--headless`` (классический headless)
            - 'legacy' — без флага ``--headless`` (только для headless=False)
    """
    args = [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--window-size=1920,1080',
    ]
    if headless:
        if headless_mode == 'new':
            args.insert(0, '--headless=new')
        elif headless_mode == 'old':
            args.insert(0, '--headless')
        # headless_mode='legacy' — не добавляем --headless
    return args


def get_context_config(
    locale: str = 'ru-RU',
    timezone: str = 'Europe/Moscow',
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    user_agent: str | None = None,
) -> dict:
    """Вернуть kwargs для Playwright BrowserContext.

    Args:
        locale: Локаль браузера.
        timezone: Часовой пояс браузера.
        viewport_width: Ширина окна просмотра.
        viewport_height: Высота окна просмотра.
        user_agent: Пользовательский User-Agent.
                    Если None, используется стандартный Playwright.
    """
    config: dict = {
        'viewport': {'width': viewport_width, 'height': viewport_height},
        'locale': locale,
        'timezone_id': timezone,
        'extra_http_headers': {
            'Accept-Language': f'{locale},ru;q=0.9,en-US;q=0.8,en;q=0.7',
        },
    }
    if user_agent:
        config['user_agent'] = user_agent
    return config


async def apply_stealth(
    context: BrowserContext,
    js_path: str | None = None,
    *,
    skip_webdriver: bool = False,
    skip_chrome: bool = False,
    skip_plugins: bool = False,
    skip_navigator: bool = False,
    skip_webgl: bool = False,
) -> None:
    """Внедрить JS-скрипты обхода детекта в контекст браузера.

    Должен вызываться ДО создания страниц.

    Args:
        context: Playwright BrowserContext.
        js_path: Путь к пользовательскому JS-файлу.
                 Если None, используется встроенный js_evasions.js.
        skip_webdriver: Не скрывать ``navigator.webdriver``.
        skip_chrome: Не эмулировать ``window.chrome``.
        skip_plugins: Не подменять ``navigator.plugins``.
        skip_navigator: Не подменять ``navigator.languages``,
                       ``platform``, ``vendor`` и др.
        skip_webgl: Не спуфить WebGL vendor/renderer.

    Note:
        По умолчанию все skip-флаги ``False`` — применяется полный стелс.
        Для сайтов, где стелс ломает JS (например, kad.arbitr.ru),
        можно установить нужные флаги в ``True``.
    """
    path = Path(js_path) if js_path else _JS_EVASIONS_PATH
    full_script = path.read_text(encoding='utf-8')

    # Если все флаги True — ничего не применяем
    if all(
        [skip_webdriver, skip_chrome, skip_plugins, skip_navigator, skip_webgl]
    ):
        return

    # Если все флаги False — применяем весь скрипт целиком (по умолчанию)
    if not any(
        [skip_webdriver, skip_chrome, skip_plugins, skip_navigator, skip_webgl]
    ):
        await context.add_init_script(full_script)
        return

    # Иначе — разбираем на секции и применяем только разрешённые
    sections = _parse_js_sections(full_script)

    skip_map = {
        'webdriver': skip_webdriver,
        'chrome': skip_chrome,
        'plugins': skip_plugins,
        'navigator': skip_navigator,
        'webgl': skip_webgl,
    }

    selected_parts: list[str] = []
    for section_name, section_code in sections.items():
        if not skip_map.get(section_name, False):
            selected_parts.append(section_code)

    if selected_parts:
        combined_script = '\n'.join(selected_parts)
        await context.add_init_script(combined_script)
