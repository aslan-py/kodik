"""
HITL (Human-in-the-Loop) для обхода CAPTCHA и сложных задач.

Управляет профилями браузеров (cookies, состояние) и позволяет
человеку решить CAPTCHA один раз, после чего результат кэшируется.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from ..core.cache import UnifiedCache
from ..integration.sources import extract_host
from ..schemas import HITLRequest, HITLResponse

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Управление профилями браузеров.

    Хранит cookies и состояние сессии. По умолчанию — на диске в
    ``profiles_dir``. Если передан ``cache`` (``UnifiedCache``), профили
    хранятся через него (единое хранилище профилей), что устраняет
    дублирование с ``UnifiedCache``.
    """

    def __init__(
        self,
        profiles_dir: str = './src/bp1/data/profiles',
        cache: UnifiedCache | None = None,
    ):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        # Единое хранилище профилей (унификация с UnifiedCache).
        self._cache = cache

    def _profile_path(self, source_name: str) -> Path:
        # Приводим имя источника к каноническому hostname, чтобы профиль
        # находился независимо от формы ввода (https://lenta.ru/ == lenta.ru).
        try:
            safe_name = extract_host(source_name)
        except ValueError:
            safe_name = source_name
        return self.profiles_dir / f'{safe_name}.json'

    def get_profile(self, source_name: str) -> str | None:
        """Получить путь к профилю."""
        path = self._profile_path(source_name)
        return str(path) if path.exists() else None

    def create_profile(self, source_name: str) -> str:
        """Создать новый профиль."""
        path = self._profile_path(source_name)
        if not path.exists():
            path.write_text(
                json.dumps({'source': source_name, 'cookies': {}}),
                encoding='utf-8',
            )
        return str(path)

    def update_profile(self, profile_id: str, cookies: dict) -> None:
        """Обновить профиль (cookies, состояние).

        Если задан ``cache`` (``UnifiedCache``) — профиль дополнительно
        сохраняется в единое хранилище профилей кэша.
        """
        path = Path(profile_id)
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                data = {}
        data['cookies'] = cookies
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        # Синхронизация с единым хранилищем профилей UnifiedCache.
        if self._cache is not None:
            source_name = data.get('source', 'unknown')
            try:
                import asyncio

                asyncio.get_running_loop().create_task(
                    self._cache.set_profile(source_name, data)
                )
            except RuntimeError:
                # Нет запущенного event loop — сохраняем синхронно через
                # временный loop (не критично для профилей).
                self._sync_profile_sync(source_name, data)

    def _sync_profile_sync(
        self, source_name: str, data: dict[str, Any]
    ) -> None:
        """Синхронно сохраняет профиль в UnifiedCache при отсутствии loop."""
        if self._cache is None:
            return
        try:
            import asyncio

            asyncio.run(self._cache.set_profile(source_name, data))
        except Exception as e:
            logger.warning(
                'Не удалось синхронизировать профиль %s с кэшем: %s',
                source_name,
                e,
            )


class HITLManager:
    """
    Human-in-the-Loop для обхода CAPTCHA.

    Поток:
    1. Проверить существующий профиль
    2. Если профиля нет → запустить Playwright в видимом режиме
    3. Пользователь решает CAPTCHA
    4. Сохранить профиль для повторного использования
    5. Вернуться к автоматическому режиму
    """

    def __init__(
        self,
        profiles_dir: str = './src/bp1/data/profiles',
        logger: logging.Logger | None = None,
        requests_dir: str | None = None,
        cache: UnifiedCache | None = None,
    ):
        self._profiles = ProfileManager(profiles_dir=profiles_dir, cache=cache)
        self._logger = logger or logging.getLogger(__name__)
        self._requests: dict[str, HITLRequest] = {}

        # Персистентное хранилище запросов на диске (JSON-файлы).
        # Если requests_dir задан — запросы сохраняются на диск и
        # восстанавливаются при создании экземпляра.
        self._requests_dir: Path | None = None
        if requests_dir:
            self._requests_dir = Path(requests_dir)
            self._requests_dir.mkdir(parents=True, exist_ok=True)
            self._load_requests()

    async def handle_challenge(
        self,
        url: str,
        source_name: str,
        challenge_type: str = 'captcha',
        timeout_s: int = 120,
        poll_interval_s: float = 2.0,
    ) -> HITLResponse:
        """
        Обработать CAPTCHA с участием человека.

        Если профиль уже существует — возвращает его без участия человека.
        Иначе запускает видимый браузер, ожидает решения CAPTCHA человеком
        (детектируя момент решения по изменению URL/cookies/исчезновению
        CAPTCHA-виджета) и сохраняет cookies в профиль для повторного
        использования. После решения возвращает HTML страницы.

        Args:
            url: Целевой URL.
            source_name: Имя источника.
            challenge_type: Тип вызова (по умолчанию ``captcha``).
            timeout_s: Максимальное время ожидания решения, секунд.
            poll_interval_s: Интервал опроса состояния страницы, секунд.
        """
        request_id = uuid.uuid4().hex
        profile_id = self._profiles.get_profile(source_name)

        if profile_id:
            self._logger.info(
                'Найден профиль HITL для %s: %s',
                source_name,
                profile_id,
            )
            return HITLResponse(
                request_id=request_id,
                success=True,
                profile_id=profile_id,
            )

        # Создаём профиль и запрос.
        profile_id = self._profiles.create_profile(source_name)
        request = HITLRequest(
            request_id=request_id,
            url=url,
            challenge_type=challenge_type,
            profile_id=profile_id,
        )
        self._requests[request_id] = request
        self._persist_request(request)

        self._logger.warning(
            'Требуется решение CAPTCHA для %s (запрос %s, URL: %s, тип: %s)',
            source_name,
            request_id,
            url,
            challenge_type,
        )

        # Запускаем видимый браузер и ждём решения CAPTCHA человеком.
        result = await self._launch_browser(
            url, timeout_s, poll_interval_s=poll_interval_s
        )
        if result is None:
            return HITLResponse(
                request_id=request_id,
                success=False,
                profile_id=profile_id,
                error='challenge requires human interaction',
            )

        cookies, html = result
        self._profiles.update_profile(profile_id, cookies)
        request.status = 'resolved'
        self._persist_request(request)
        return HITLResponse(
            request_id=request_id,
            success=True,
            profile_id=profile_id,
            cookies=cookies,
            html=html,
        )

    async def _launch_browser(
        self,
        url: str,
        timeout_s: int,
        poll_interval_s: float = 2.0,
    ) -> tuple[dict[str, Any], str] | None:
        """
        Запускает видимый браузер и ожидает решения CAPTCHA.

        Вместо фиксированного ожидания опрашивает состояние страницы в цикле
        и детектирует момент решения CAPTCHA по одному из признаков:
        - URL изменился относительно исходного (произошла навигация);
        - появились новые cookies (например, сессионные после решения);
        - CAPTCHA-виджет исчез из DOM.

        Возвращает кортеж ``(cookies, html)`` после решения или ``None``
        при таймауте/ошибке.
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(url, timeout=timeout_s * 1000)

                initial_url = page.url
                initial_cookies = {
                    c['name']: c['value'] for c in await context.cookies()
                }

                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline:
                    await page.wait_for_timeout(int(poll_interval_s * 1000))

                    current_url = page.url
                    current_cookies = {
                        c['name']: c['value'] for c in await context.cookies()
                    }

                    # Признак решения: URL изменился (навигация после CAPTCHA).
                    if current_url != initial_url:
                        self._logger.info(
                            'CAPTCHA решена: URL изменился %s -> %s',
                            initial_url,
                            current_url,
                        )
                        break

                    # Признак решения: появились новые cookies.
                    if current_cookies != initial_cookies:
                        self._logger.info(
                            'CAPTCHA решена: изменились cookies (%d -> %d)',
                            len(initial_cookies),
                            len(current_cookies),
                        )
                        break

                    # Признак решения: CAPTCHA-виджет исчез из DOM.
                    if not await self._has_captcha_widget(page):
                        self._logger.info('CAPTCHA решена: виджет исчез из DOM')
                        break

                cookies = {
                    c['name']: c['value'] for c in await context.cookies()
                }
                html = await page.content()
                await context.close()
                await browser.close()
                return cookies, html
        except Exception as e:
            self._logger.warning('Ошибка браузера HITL для %s: %s', url, e)
            return None

    @staticmethod
    async def _has_captcha_widget(page: Any) -> bool:
        """
        Проверяет наличие CAPTCHA-виджета в DOM страницы.

        Ищет маркеры reCAPTCHA/hCaptcha/Cloudflare Turnstile. Если ни один
        маркер не найден — считается, что CAPTCHA отсутствует (решена).
        """
        try:
            markers = (
                'g-recaptcha',
                'h-captcha',
                'cf-turnstile',
                'recaptcha',
                'hcaptcha',
                'captcha',
            )
            for marker in markers:
                locator = f'[class*="{marker}"], [id*="{marker}"]'
                if await page.locator(locator).count():
                    return True
            return False
        except Exception:
            # При ошибке доступа к DOM считаем, что виджет ещё есть,
            # чтобы не завершить ожидание преждевременно.
            return True

    async def check_status(self, request_id: str) -> HITLRequest:
        """Проверить статус запроса.

        Сначала ищет запрос в памяти, затем — на диске (если задан
        ``requests_dir``), что позволяет восстановить статус после
        перезапуска процесса.
        """
        request = self._requests.get(request_id)
        if request is not None:
            return request

        # Восстановление с диска (персистентность).
        if self._requests_dir is not None:
            path = self._request_path(request_id)
            if path.exists():
                try:
                    return HITLRequest.model_validate_json(
                        path.read_text(encoding='utf-8')
                    )
                except Exception as e:
                    self._logger.warning(
                        'Не удалось загрузить запрос %s: %s', request_id, e
                    )

        return HITLRequest(
            request_id=request_id,
            url='',
            status='not_found',
        )

    def resolve(
        self,
        request_id: str,
        cookies: dict[str, Any] | None = None,
    ) -> HITLResponse:
        """Отметить запрос как решённый и сохранить cookies в профиль."""
        request = self._requests.get(request_id)
        if request is None:
            return HITLResponse(
                request_id=request_id,
                success=False,
                error='request not found',
            )

        if request.profile_id and cookies:
            self._profiles.update_profile(request.profile_id, cookies)

        request.status = 'resolved'
        self._persist_request(request)
        return HITLResponse(
            request_id=request_id,
            success=True,
            profile_id=request.profile_id,
            cookies=cookies or {},
        )

    # ========================================================================
    # Персистентность запросов (диск)
    # ========================================================================

    def _request_path(self, request_id: str) -> Path:
        """Путь к JSON-файлу запроса."""
        return self._requests_dir / f'{request_id}.json'

    def _persist_request(self, request: HITLRequest) -> None:
        """Сохраняет запрос на диск (если каталог задан)."""
        if self._requests_dir is None:
            return
        try:
            self._request_path(request.request_id).write_text(
                request.model_dump_json(),
                encoding='utf-8',
            )
        except Exception as e:
            self._logger.warning(
                'Не удалось сохранить запрос %s на диск: %s',
                request.request_id,
                e,
            )

    def _load_requests(self) -> None:
        """Загружает запросы с диска при инициализации."""
        if self._requests_dir is None:
            return
        for path in sorted(self._requests_dir.glob('*.json')):
            try:
                request = HITLRequest.model_validate_json(
                    path.read_text(encoding='utf-8')
                )
                self._requests[request.request_id] = request
            except Exception as e:
                self._logger.warning(
                    'Не удалось загрузить запрос %s: %s', path.name, e
                )
