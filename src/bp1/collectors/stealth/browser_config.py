"""Аргументы запуска браузера, конфиг контекста и инъекция стелса."""

from pathlib import Path

from playwright.async_api import BrowserContext

_JS_EVASIONS_PATH = Path(__file__).parent / 'js_evasions.js'


def get_launch_args(headless: bool = True) -> list[str]:
    """Вернуть аргументы запуска Chromium для антидетекта.

    Args:
        headless: Использовать --headless=new режим.
    """
    args = [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--window-size=1920,1080',
    ]
    if headless:
        args.insert(0, '--headless=new')
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
    context: BrowserContext, js_path: str | None = None
) -> None:
    """Внедрить JS-скрипты обхода детекта в контекст браузера.

    Должен вызываться ДО создания страниц.

    Args:
        context: Playwright BrowserContext.
        js_path: Путь к пользовательскому JS-файлу.
                 Если None, используется встроенный js_evasions.js.
    """
    path = Path(js_path) if js_path else _JS_EVASIONS_PATH
    script = path.read_text(encoding='utf-8')
    await context.add_init_script(script)
