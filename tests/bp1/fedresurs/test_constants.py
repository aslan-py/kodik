"""Тесты для constants.py — константы, SELECTORS, генерация UA и задержек."""

from src.bp1.collectors.fedresurs_rpa.constants import (
    BASE_URL,
    DEFAULT_DELAY_BETWEEN_REQUESTS,
    DEFAULT_ELEMENT_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT,
    HUMAN_DELAY_RANGE,
    SELECTORS,
    TYPING_DELAY_MS,
    USER_AGENTS,
    VIEWPORT,
    get_human_delay,
    get_random_delay,
    get_random_user_agent,
)


class TestConstants:
    """Тесты для скалярных констант."""

    def test_base_url(self):
        """BASE_URL корректный."""
        assert BASE_URL == 'https://fedresurs.ru'

    def test_timeouts(self):
        """Таймауты имеют корректные значения."""
        assert DEFAULT_TIMEOUT == 60000
        assert DEFAULT_ELEMENT_TIMEOUT == 10000
        assert DEFAULT_RETRY_COUNT == 3

    def test_delays(self):
        """Задержки имеют корректные диапазоны."""
        assert DEFAULT_DELAY_BETWEEN_REQUESTS == (1.0, 3.0)
        assert HUMAN_DELAY_RANGE == (0.3, 0.5)
        assert TYPING_DELAY_MS == 50

    def test_viewport(self):
        """VIEWPORT имеет корректные размеры."""
        assert VIEWPORT == {'width': 1920, 'height': 1080}


class TestUserAgents:
    """Тесты для USER_AGENTS."""

    def test_pool_not_empty(self):
        """Пул UA не пуст."""
        assert len(USER_AGENTS) > 0

    def test_all_start_with_mozilla(self):
        """Все UA начинаются с 'Mozilla/5.0'."""
        for ua in USER_AGENTS:
            assert ua.startswith('Mozilla/5.0')

    def test_all_contain_chrome(self):
        """Все UA содержат Chrome."""
        for ua in USER_AGENTS:
            assert 'Chrome' in ua


class TestSelectors:
    """Тесты для SELECTORS."""

    def test_contains_required_keys(self):
        """SELECTORS содержит все обязательные ключи."""
        required_keys = [
            'combobox',
            'search_input_container',
            'search_button_container',
            'results_link_text',
            'company_status',
            'company_info_container',
            'company_name',
        ]
        for key in required_keys:
            assert key in SELECTORS, f'Missing key: {key}'

    def test_values_are_strings(self):
        """Все значения SELECTORS — строки."""
        for key, value in SELECTORS.items():
            assert isinstance(value, str), (
                f'Key {key} is not a string: {type(value)}'
            )


class TestGetRandomUserAgent:
    """Тесты для get_random_user_agent()."""

    def test_returns_string(self):
        """Возвращает строку."""
        ua = get_random_user_agent()
        assert isinstance(ua, str)

    def test_returns_from_pool(self):
        """Возвращает UA из пула USER_AGENTS."""
        ua = get_random_user_agent()
        assert ua in USER_AGENTS

    def test_multiple_calls_varied(self):
        """За несколько вызовов возвращаются разные UA (вероятностно)."""
        results = {get_random_user_agent() for _ in range(20)}
        # при 20 вызовах из 5 UA должно быть минимум 2 разных
        assert len(results) >= 2


class TestGetRandomDelay:
    """Тесты для get_random_delay()."""

    def test_returns_float(self):
        """Возвращает float."""
        delay = get_random_delay()
        assert isinstance(delay, float)

    def test_in_range(self):
        """Значение в диапазоне (1.0, 3.0)."""
        for _ in range(100):
            delay = get_random_delay()
            assert 1.0 <= delay <= 3.0, f'Delay {delay} out of range'


class TestGetHumanDelay:
    """Тесты для get_human_delay()."""

    def test_returns_float(self):
        """Возвращает float."""
        delay = get_human_delay()
        assert isinstance(delay, float)

    def test_in_range(self):
        """Значение в диапазоне (0.3, 0.5)."""
        for _ in range(100):
            delay = get_human_delay()
            assert 0.3 <= delay <= 0.5, f'Delay {delay} out of range'
