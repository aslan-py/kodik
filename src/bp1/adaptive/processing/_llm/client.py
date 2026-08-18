"""Клиентский слой LLM (BP-1 Adaptive).

Содержит ``BaseLLMClient`` — общую основу для ``LLMClient`` и ``AIAgent``:
конфигурация модели, ленивое создание ``AsyncOpenAI``-клиента и единый
метод ``_complete`` с ретраями, таймаутом и логированием задержек.
Также добавляет корректное закрытие клиента (``aclose``).
"""

from __future__ import annotations

import asyncio
import logging

from core.config import settings

from . import constants


def default_model() -> str:
    """Модель LLM по умолчанию из настроек."""
    return settings.llm_model


def default_base_url() -> str | None:
    """Базовый URL LLM-провайдера из настроек (если задан)."""
    return settings.llm_base_url


def has_llm_config() -> bool:
    """Проверяет, задана ли конфигурация LLM."""
    return bool(settings.llm_api_key)


class BaseLLMClient:
    """Общая основа для LLM-клиентов.

    Инкапсулирует конфигурацию модели (``model``, ``base_url``, ``api_key``),
    ленивое создание ``AsyncOpenAI``-клиента и сетевые вызовы с ретраями.
    Устраняет дублирование между ``LLMClient`` и ``AIAgent``.
    """

    def __init__(
        self,
        model: str | None = None,
        logger: logging.Logger | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = constants.DEFAULT_TIMEOUT_S,
        max_retries: int = constants.DEFAULT_MAX_RETRIES,
    ) -> None:
        self._model = model or default_model()
        self._base_url = base_url or default_base_url()
        self._logger = logger or logging.getLogger(__name__)
        self._api_key = api_key or settings.llm_api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = None

    def _get_client(self):
        """Лениво создаёт и возвращает AsyncOpenAI-клиент."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._client

    async def _complete(self, prompt: str, **kwargs) -> str | None:
        """Единая точка вызова chat.completions.create с ретраями.

        Args:
            prompt: Пользовательский промпт.
            **kwargs: Дополнительные параметры (``max_tokens``,
                ``temperature`` и т.д.), переданные в ``create``.

        Returns:
            str | None: Текст ответа модели или ``None`` при ошибке.
        """
        client = self._get_client()
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=self._model,
                    messages=[{'role': 'user', 'content': prompt}],
                    **kwargs,
                )
                content = response.choices[0].message.content
                return (content or '').strip() or None
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = min(
                        constants.RETRY_BASE_DELAY_S * (2 ** (attempt - 1)),
                        constants.RETRY_MAX_DELAY_S,
                    )
                    self._logger.warning(
                        'LLM-вызов не удался (попытка %d/%d): %s. '
                        'Повтор через %.1fс',
                        attempt,
                        self._max_retries,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)

        self._logger.error(
            'LLM-вызов не удался после %d попыток: %s',
            self._max_retries,
            last_error,
        )
        if last_error is not None:
            raise last_error
        return None

    async def aclose(self) -> None:
        """Закрывает AsyncOpenAI-клиент, освобождая HTTP-пулы."""
        if self._client is not None:
            close = getattr(self._client, 'aclose', None)
            if callable(close):
                await close()
            self._client = None

    async def __aenter__(self) -> BaseLLMClient:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()
