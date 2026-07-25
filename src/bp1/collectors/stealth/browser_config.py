"""Browser launch args, context config, and stealth injection."""

from pathlib import Path

from playwright.async_api import BrowserContext

_JS_EVASIONS_PATH = Path(__file__).parent / "js_evasions.js"


def get_launch_args(headless: bool = True) -> list[str]:
    """Return Chromium launch args for anti-detection.

    Args:
        headless: Use --headless=new mode.
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1920,1080",
    ]
    if headless:
        args.insert(0, "--headless=new")
    return args


def get_context_config(
    locale: str = "ru-RU",
    timezone: str = "Europe/Moscow",
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    user_agent: str | None = None,
) -> dict:
    """Return Playwright BrowserContext kwargs.

    Args:
        locale: Browser locale.
        timezone: Browser timezone.
        viewport_width: Viewport width.
        viewport_height: Viewport height.
        user_agent: Custom User-Agent. If None, Playwright default is used.
    """
    config: dict = {
        "viewport": {"width": viewport_width, "height": viewport_height},
        "locale": locale,
        "timezone_id": timezone,
        "extra_http_headers": {
            "Accept-Language": f"{locale},ru;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }
    if user_agent:
        config["user_agent"] = user_agent
    return config


async def apply_stealth(
    context: BrowserContext,
    js_path: str | None = None
) -> None:
    """Inject JS evasion scripts into browser context.

    Must be called BEFORE creating pages.

    Args:
        context: Playwright BrowserContext.
        js_path: Path to custom JS file. If None, uses bundled js_evasions.js.
    """
    path = Path(js_path) if js_path else _JS_EVASIONS_PATH
    script = path.read_text(encoding="utf-8")
    await context.add_init_script(script)
    """Inject JS evasion scripts into browser context.

    Must be called BEFORE creating pages.

    Args:
        context: Playwright BrowserContext.
        js_path: Path to custom JS file. If None, uses bundled js_evasions.js.
    """
    path = Path(js_path) if js_path else _JS_EVASIONS_PATH
    script = path.read_text(encoding="utf-8")
    await context.add_init_script(script)
