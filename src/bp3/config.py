import os

from langchain_openai import ChatOpenAI

API_BASE = 'https://openrouter.ai/api/v1'  # https://openrouter.ai/api/v1   https://api.kodikrouter.ru/v1
DEFAULT_MODEL = (
    'openai/gpt-4o-mini'  # openai/gpt-5     openai/gpt-4o-mini    openai/gpt-4o
)


def get_llm() -> ChatOpenAI:
    api_key = os.getenv(
        'OPENROUTER_API_KEY'
    )  # OPENROUTER_API_KEY   KODIK_API_KEY
    if not api_key:
        raise ValueError('KODIK_API_KEY не задан')
    return ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=API_BASE,
        model=os.getenv('MODEL', DEFAULT_MODEL),
        temperature=0,
        max_tokens=4096,
    )
