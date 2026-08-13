"""Регрессия конфигурации внешних вызовов BP-3."""

from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from core.config import Settings, settings
from core.enums import SourceSearchDepth
from src.bp3 import config as llm_config
from src.bp3.models_llm import ProjectContext
from src.bp3.modules import source_finder_module

REQUIRED_SETTINGS = {
    'postgres_user': 'test',
    'postgres_password': 'test',
    'postgres_db': 'test',
    'mail_username': 'test',
    'mail_password': 'test',
    'mail_from': 'test@example.com',
    'mail_server': 'localhost',
    'telegram_bot_token': 'test',
    'test_tg': 1,
    'test_email': 'test@example.com',
    'api_port': 8000,
    'jwt_secret_key': 'test',
    'openrouter_api_key': 'test',
    'tavily_api_key': 'test',
    'deepseek_token': 'test',
}


def test_search_depth_values_match_tavily_contract():
    assert {item.value for item in SourceSearchDepth} == {
        'advanced',
        'basic',
        'fast',
        'ultra-fast',
    }


def test_llm_defaults_are_applied():
    configured = Settings(_env_file=None, **REQUIRED_SETTINGS)

    assert configured.bp3_llm_temperature == 0
    assert configured.bp3_llm_max_tokens == 4096


def test_invalid_search_depth_is_rejected_at_startup():
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            **REQUIRED_SETTINGS,
            bp3_search_depth='deeper',
        )

    message = str(error.value)
    assert 'bp3_search_depth' in message
    for value in ('advanced', 'basic', 'fast', 'ultra-fast'):
        assert value in message


def test_search_volume_can_be_overridden_through_environment(monkeypatch):
    monkeypatch.setenv('BP3_SEARCH_MAX_RESULTS', '7')

    configured = Settings(_env_file=None, **REQUIRED_SETTINGS)

    assert configured.bp3_search_max_results == 7


def test_source_finder_uses_configured_search_parameters(monkeypatch):
    search = Mock(
        return_value={
            'results': [
                {
                    'url': f'https://source-{index}.example/news',
                    'score': 0.9,
                }
                for index in range(7)
            ]
        }
    )
    monkeypatch.setattr(source_finder_module.client, 'search', search)
    monkeypatch.setattr(source_finder_module.time, 'sleep', Mock())
    monkeypatch.setattr(settings, 'bp3_search_max_results', 7)
    monkeypatch.setattr(settings, 'bp3_search_depth', SourceSearchDepth.fast)
    monkeypatch.setattr(settings, 'bp3_search_time_range', 'month')

    context = ProjectContext(
        competitors=[{1: 'Компания'}],
        domains=['known.example'],
    )
    result = source_finder_module.SourceFinderModule().process(context)

    search.assert_called_once_with(
        query='Найди новые источники новостей о компании Компания',
        topic='news',
        max_results=7,
        search_depth='fast',
        time_range='month',
        exclude_domains=['known.example'],
        include_answer=False,
        include_raw_content=False,
    )
    assert len(result.domains_to_add[1]['sources']) == 7


def test_llm_uses_configured_parameters(monkeypatch):
    constructor = Mock(return_value=object())
    monkeypatch.setattr(llm_config, 'ChatOpenAI', constructor)
    monkeypatch.setattr(settings, 'bp3_llm_base_url', 'https://llm.example/v1')
    monkeypatch.setattr(settings, 'bp3_llm_temperature', 0.25)
    monkeypatch.setattr(settings, 'bp3_llm_max_tokens', 1234)

    llm_config.get_llm()

    constructor.assert_called_once_with(
        openai_api_key=settings.openrouter_api_key,
        openai_api_base='https://llm.example/v1',
        model=settings.bp3_model,
        temperature=0.25,
        max_tokens=1234,
    )
