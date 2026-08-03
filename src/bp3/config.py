import os

from langchain_openai import ChatOpenAI

API_BASE = 'https://api.kodikrouter.ru/v1'
DEFAULT_MODEL = 'openai/gpt-4o-mini'


def get_llm() -> ChatOpenAI:
    api_key = os.getenv('KODIK_API_KEY')
    if not api_key:
        raise ValueError('KODIK_API_KEY не задан')
    return ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=API_BASE,
        model=os.getenv('MODEL', DEFAULT_MODEL),
        temperature=0,
        max_tokens=4096,
    )
