from langchain_openai import ChatOpenAI

from core.config import settings

API_BASE = 'https://openrouter.ai/api/v1'  # https://openrouter.ai/api/v1   https://api.kodikrouter.ru/v1


def get_llm() -> ChatOpenAI:
    """Собрать клиент LLM (ChatOpenAI поверх OpenRouter) с ключом из настроек."""  # noqa
    return ChatOpenAI(
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=API_BASE,
        model=settings.bp3_model,
        temperature=0,
        max_tokens=4096,
    )
