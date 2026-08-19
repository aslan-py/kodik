"""Настройки LLM-клиента."""

from langchain_openai import ChatOpenAI

from core.config import settings


def get_llm() -> ChatOpenAI:
    """Создаёт клиента LLM с настройками из конфига."""
    return ChatOpenAI(
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=settings.bp3_llm_base_url,
        model=settings.bp3_model,
        temperature=settings.bp3_llm_temperature,
        max_tokens=settings.bp3_llm_max_tokens,
    )
