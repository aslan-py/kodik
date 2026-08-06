"""
HITL (Human-in-the-Loop) для обхода CAPTCHA и сложных задач.

Управляет профилями браузеров (cookies, состояние) и позволяет
человеку решить CAPTCHA один раз, после чего результат кэшируется.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from .schemas import HITLRequest, HITLResponse

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Управление профилями браузеров.

    Хранит cookies и состояние сессии на диске в profiles_dir.
    """

    def __init__(self, profiles_dir: str = './src/bp1/data/profiles'):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, source_name: str) -> Path:
        safe_name = source_name.replace('/', '_').replace(':', '_')
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
        """Обновить профиль (cookies, состояние)."""
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
    ):
        self._profiles = ProfileManager(profiles_dir=profiles_dir)
        self._logger = logger or logging.getLogger(__name__)
        self._requests: dict[str, HITLRequest] = {}

    async def handle_challenge(
        self,
        url: str,
        source_name: str,
        challenge_type: str = 'captcha',
        timeout_s: int = 120,
    ) -> HITLResponse:
        """
        Обработать CAPTCHA с участием человека.

        Если профиль уже существует — возвращает его без участия человека.
        Иначе запускает видимый браузер, ожидает решения CAPTCHA человеком
        и сохраняет cookies в профиль для повторного использования.
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

        self._logger.warning(
            'Требуется решение CAPTCHA для %s (запрос %s, URL: %s, тип: %s)',
            source_name,
            request_id,
            url,
            challenge_type,
        )

        # Запускаем видимый браузер и ждём решения CAPTCHA человеком.
        cookies = await self._launch_browser(url, timeout_s)
        if cookies is None:
            return HITLResponse(
                request_id=request_id,
                success=False,
                profile_id=profile_id,
                error='challenge requires human interaction',
            )

        self._profiles.update_profile(profile_id, cookies)
        request.status = 'resolved'
        return HITLResponse(
            request_id=request_id,
            success=True,
            profile_id=profile_id,
            cookies=cookies,
        )

    async def _launch_browser(
        self, url: str, timeout_s: int
    ) -> dict[str, Any] | None:
        """
        Запускает видимый браузер и ожидает решения CAPTCHA.

        Возвращает cookies после решения или None при таймауте/ошибке.
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(url, timeout=timeout_s * 1000)
                # Ждём, пока человек решит CAPTCHA.
                await page.wait_for_timeout(timeout_s * 1000)
                cookies = await context.cookies()
                await context.close()
                await browser.close()
                return {c['name']: c['value'] for c in cookies}
        except Exception as e:
            self._logger.warning('Ошибка браузера HITL для %s: %s', url, e)
            return None

    async def check_status(self, request_id: str) -> HITLRequest:
        """Проверить статус запроса."""
        return self._requests.get(
            request_id,
            HITLRequest(
                request_id=request_id,
                url='',
                status='not_found',
            ),
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
        return HITLResponse(
            request_id=request_id,
            success=True,
            profile_id=request.profile_id,
            cookies=cookies or {},
        )
