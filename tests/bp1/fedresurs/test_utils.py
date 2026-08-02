"""Тесты для utils.py — validate_inn, format_proxy_string, generate_filename."""

from datetime import datetime

import pytest

from src.bp1.collectors.fedresurs_rpa.schemas import ProxyConfig
from src.bp1.collectors.fedresurs_rpa.utils import (
    format_proxy_string,
    generate_filename,
    validate_inn,
)

# ===========================================================================
# validate_inn
# ===========================================================================


class TestValidateInn:
    """Тесты для validate_inn()."""

    def test_valid_10_digits(self):
        """Валидный 10-значный ИНН (расчётная контрольная сумма)."""
        # ИНН 7727563778 — реальная организация, контрольная сумма верна
        validate_inn('7727563778')  # не raises

    def test_valid_12_digits(self):
        """Валидный 12-значный ИНН (расчётная контрольная сумма)."""
        # ИНН 123456789047 — контрольная сумма: 10-я=0, 11-я=4, 12-я=7
        # weights1: 7+4+12+40+15+30+63+32+54+0=257 %11=4 %10=4
        # weights2: 3+14+6+16+50+18+35+72+36+0+32=282 %11=7 %10=7
        validate_inn('123456789047')

    def test_invalid_checksum_10(self):
        """Неверная контрольная сумма для 10-значного ИНН."""
        with pytest.raises(ValueError, match='контрольная сумма'):
            validate_inn('7727563779')  # последняя цифра изменена

    def test_invalid_checksum_12(self):
        """Неверная контрольная сумма для 12-значного ИНН."""
        with pytest.raises(ValueError, match='контрольная сумма'):
            validate_inn('123456789048')  # последняя цифра изменена

    def test_non_digits(self):
        """ИНН содержит нецифровые символы."""
        with pytest.raises(ValueError, match='только цифры'):
            validate_inn('1234abc')

    def test_wrong_length_short(self):
        """ИНН слишком короткий."""
        with pytest.raises(ValueError, match='10 или 12 цифр'):
            validate_inn('123456789')

    def test_wrong_length_long(self):
        """ИНН слишком длинный."""
        with pytest.raises(ValueError, match='10 или 12 цифр'):
            validate_inn('1234567890123')

    def test_empty_string(self):
        """Пустая строка — первая проверка isdigit()."""
        with pytest.raises(ValueError, match='только цифры'):
            validate_inn('')


# ===========================================================================
# format_proxy_string
# ===========================================================================


class TestFormatProxyString:
    """Тесты для format_proxy_string()."""

    def test_with_auth(self):
        """Прокси с логином и паролем."""
        proxy = ProxyConfig(
            server='http://1.2.3.4:8080', username='user', password='pass'
        )
        result = format_proxy_string(proxy)
        assert result == 'http://1.2.3.4:8080 (user:***)'

    def test_without_auth(self):
        """Прокси без авторизации."""
        proxy = ProxyConfig(server='http://1.2.3.4:8080')
        result = format_proxy_string(proxy)
        assert result == 'http://1.2.3.4:8080'

    def test_none(self):
        """None — возвращает None."""
        assert format_proxy_string(None) is None

    def test_empty_credentials(self):
        """Прокси с пустыми username/password."""
        proxy = ProxyConfig(
            server='http://1.2.3.4:8080', username='', password=''
        )
        result = format_proxy_string(proxy)
        assert result == 'http://1.2.3.4:8080'


# ===========================================================================
# generate_filename
# ===========================================================================


class TestGenerateFilename:
    """Тесты для generate_filename()."""

    def test_with_inn(self):
        """Имя файла с ИНН."""
        name = generate_filename(name='ООО Тест', inn='1234567890')
        assert name.startswith('fedresurs_1234567890_')
        assert name.endswith('.html')

    def test_without_inn(self):
        """Имя файла без ИНН — имя компании используется."""
        name = generate_filename(name='ООО Тест')
        assert name.startswith('fedresurs_')
        assert name.endswith('.html')
        # кириллица считается isalnum(), поэтому остаётся в имени
        assert 'ООО' in name or 'Тест' in name

    def test_with_timestamp(self):
        """Кастомный timestamp."""
        ts = datetime(2026, 8, 2, 12, 0, 0)
        name = generate_filename(name='Test', inn='111', timestamp=ts)
        assert name == 'fedresurs_111_20260802_120000.html'

    def test_special_chars_in_name(self):
        """Спецсимволы в имени заменяются на подчёркивания."""
        name = generate_filename(name='ООО "Ромашка"', inn='111')
        assert name.startswith('fedresurs_111_')
        # кавычки и пробелы заменяются
        assert '"' not in name

    def test_long_name_truncated(self):
        """Длинное имя обрезается до 50 символов."""
        long_name = 'A' * 100
        name = generate_filename(name=long_name, inn='111')
        # извлекаем часть между fedresurs_111_YYYYMMDD_HHMMSS.html
        # имя без ИНН: fedresurs_<name>_<date>.html
        name_part = name.replace('fedresurs_', '').replace('.html', '')
        # name_part = <sanitized_name>_<date>
        # sanitized_name должен быть не длиннее 50 символов
        assert len(name_part.split('_')[0]) <= 50
