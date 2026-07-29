import os

from langchain_openai import ChatOpenAI

OPENROUTER_BASE = 'https://openrouter.ai/api/v1'
DEFAULT_MODEL = 'openai/gpt-4o-mini'


def get_llm() -> ChatOpenAI:
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError('OPENROUTER_API_KEY не задан')
    return ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=OPENROUTER_BASE,
        model=os.getenv('OPENROUTER_MODEL', DEFAULT_MODEL),
        temperature=0,
        max_tokens=4096,
    )
