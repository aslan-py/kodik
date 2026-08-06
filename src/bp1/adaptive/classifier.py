"""
SourceClassifier — умный классификатор источников.

Определяет тип сайта (новостной, реестр, API, SPA), сложность обхода,
наличие антибот-защиты и CAPTCHA, и выбирает оптимальную стратегию.
"""

from __future__ import annotations

import logging
from typing import Any

from .schemas import SourceClassification, SourceType, StrategyType

logger = logging.getLogger(__name__)

# Маркеры SPA-фреймворков в HTML.
_SPA_MARKERS = (
    # Angular
    'ng-app',
    'ng-controller',
    'ng-version',
    'ng-',
    'angular',
    # React
    'data-reactroot',
    'id="app"',
    'id="root"',
    # Vue / Nuxt
    'vue',
    'nuxt',
    # Next.js
    'next-data',
    '__NEXT_DATA__',
    '__NUXT__',
)

# Маркеры CAPTCHA-виджетов.
_CAPTCHA_MARKERS = (
    'recaptcha',
    'hcaptcha',
    'g-recaptcha',
    'captcha',
)

# Маркеры антибот-защиты в заголовках/HTML.
_ANTIBOT_MARKERS = (
    'cloudflare',
    'cf-ray',
    'cf-cache-status',
    'datadome',
    # QRATOR
    'qrator',
    'qrator_jsr',
    '__qrator',
    'jsid',
    'akamai',
    'incapsula',
)

# Домены, которые являются API-эндпоинтами.
_API_DOMAINS = ('api.', 'api-', '.api.')

# Домены государственных реестров.
_REGISTRY_DOMAINS = (
    'fedresurs.ru',
    'fips.ru',
    'zakupki.gov.ru',
    'kad.arbitr.ru',
    'nalog.ru',
    'egrul.nalog.ru',
)

# Известные источники с их характеристиками защиты.
# Используется, когда headers/html недоступны (классификация по имени/URL).
# Ключ — домен источника, значение — кортеж (has_antibot, has_captcha, is_spa).
_KNOWN_SOURCES: dict[str, tuple[bool, bool, bool]] = {
    # QRATOR антибот-защита + Angular SPA
    'fedresurs.ru': (True, False, True),
    # QRATOR антибот-защита + Angular SPA
    'kad.arbitr.ru': (True, False, True),
    # Антибот-защита (зависит от региона)
    'zakupki.gov.ru': (True, False, False),
    # Антибот-защита
    'nalog.ru': (True, False, False),
    'egrul.nalog.ru': (True, False, False),
    # FIPS — статический сайт
    'fips.ru': (False, False, False),
}


class SourceClassifier:
    """
    Умный классификатор источников.

    Определяет тип сайта, сложность и выбирает оптимальную стратегию
    на основе URL, заголовков ответа и анализа HTML.
    """

    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger(__name__)

    async def classify(
        self,
        source_name: str,
        source_url: str,
        headers: dict[str, Any] | None = None,
        html: str | None = None,
    ) -> SourceClassification:
        """
        Классифицирует источник по URL, заголовкам и HTML.

        Критерии:
        - Тип источника (новостной, реестр, API, SPA)
        - Наличие антибот-защиты (Cloudflare, DataDome, QRATOR)
        - Наличие CAPTCHA
        - SPA или статический HTML
        - Выбор стратегии: FAST → CRAWL4AI → BROWSER → WAYBACK
        """
        headers = headers or {}
        html = html or ''

        source_type = self._detect_source_type(source_name, source_url)

        # База известных источников: если источник известен, используем
        # его характеристики как основу, а headers/html дополняют детекцию.
        known = self._get_known_source(source_name, source_url)

        has_antibot = self._detect_antibot(headers, html)
        has_captcha = self._detect_captcha(html)
        is_spa = self._detect_spa(html)

        if known is not None:
            known_antibot, known_captcha, known_spa = known
            has_antibot = has_antibot or known_antibot
            has_captcha = has_captcha or known_captcha
            is_spa = is_spa or known_spa

        # SPA-приложение с неизвестным типом классифицируется как SPA.
        if is_spa and source_type == SourceType.UNKNOWN:
            source_type = SourceType.SPA

        complexity = self._compute_complexity(
            source_type, has_antibot, has_captcha, is_spa
        )
        strategy = self._pick_strategy(
            source_type, has_antibot, has_captcha, is_spa
        )

        classification = SourceClassification(
            source_name=source_name,
            source_type=source_type,
            complexity_score=complexity,
            has_antibot=has_antibot,
            has_captcha=has_captcha,
            is_spa=is_spa,
            recommended_strategy=strategy.value,
        )

        self._logger.info(
            'Источник классифицирован: %s (тип=%s, сложность=%.2f, '
            'стратегия=%s, антибот=%s, SPA=%s, CAPTCHA=%s)',
            source_name,
            source_type.value,
            complexity,
            strategy.value,
            has_antibot,
            is_spa,
            has_captcha,
        )
        return classification

    # ========================================================================
    # Детекторы
    # ========================================================================

    def _detect_source_type(
        self, source_name: str, source_url: str
    ) -> SourceType:
        """Определяет тип источника по имени и URL."""
        url = source_url.lower()
        name = source_name.lower()

        if any(domain in url or domain in name for domain in _API_DOMAINS):
            return SourceType.API

        if any(domain in url or domain in name for domain in _REGISTRY_DOMAINS):
            return SourceType.REGISTRY

        if any(
            marker in url
            for marker in ('news', 'ria', 'lenta', 'tass', 'rbc', 'interfax')
        ):
            return SourceType.NEWS

        return SourceType.UNKNOWN

    def _get_known_source(
        self, source_name: str, source_url: str
    ) -> tuple[bool, bool, bool] | None:
        """Возвращает характеристики известного источника.

        Ищет домен источника в базе ``_KNOWN_SOURCES`` по имени или URL.
        Возвращает кортеж (has_antibot, has_captcha, is_spa) или None,
        если источник неизвестен.
        """
        url = source_url.lower()
        name = source_name.lower()

        for domain, features in _KNOWN_SOURCES.items():
            if domain in url or domain in name:
                return features
        return None

    def _detect_antibot(self, headers: dict[str, Any], html: str) -> bool:
        """Определяет наличие антибот-защиты."""
        header_text = ' '.join(f'{k}:{v}' for k, v in headers.items()).lower()
        html_lower = html.lower()

        for marker in _ANTIBOT_MARKERS:
            if marker in header_text or marker in html_lower:
                return True
        return False

    def _detect_captcha(self, html: str) -> bool:
        """Определяет наличие CAPTCHA-виджетов."""
        html_lower = html.lower()
        return any(marker in html_lower for marker in _CAPTCHA_MARKERS)

    def _detect_spa(self, html: str) -> bool:
        """Определяет, является ли сайт SPA-приложением."""
        html_lower = html.lower()
        return any(marker in html_lower for marker in _SPA_MARKERS)

    # ========================================================================
    # Оценка сложности и выбор стратегии
    # ========================================================================

    def _compute_complexity(
        self,
        source_type: SourceType,
        has_antibot: bool,
        has_captcha: bool,
        is_spa: bool,
    ) -> float:
        """Вычисляет оценку сложности от 0.0 до 1.0."""
        score = 0.0

        if source_type == SourceType.API:
            score += 0.1
        elif source_type == SourceType.REGISTRY:
            score += 0.4
        elif source_type == SourceType.SPA:
            score += 0.5
        elif source_type == SourceType.NEWS:
            score += 0.2

        if has_antibot:
            score += 0.3
        if has_captcha:
            score += 0.3
        if is_spa:
            score += 0.2

        return min(score, 1.0)

    def _pick_strategy(
        self,
        source_type: SourceType,
        has_antibot: bool,
        has_captcha: bool,
        is_spa: bool,
    ) -> StrategyType:
        """Выбирает оптимальную стратегию обхода."""
        if source_type == SourceType.API:
            return StrategyType.FAST

        if has_captcha:
            return StrategyType.HITL

        if has_antibot:
            return StrategyType.STEALTH

        if is_spa:
            return StrategyType.BROWSER

        return StrategyType.FAST
