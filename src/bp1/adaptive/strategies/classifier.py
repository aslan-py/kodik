"""
SourceClassifier — умный классификатор источников.

Определяет тип сайта (новостной, реестр, API, SPA), сложность обхода,
наличие антибот-защиты и CAPTCHA, и выбирает оптимальную стратегию.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ..hostname import KNOWN_REGISTRY_DOMAINS
from ..processing._llm.heuristics import heuristic_strategy
from ..schemas import (
    BusinessFeatures,
    ExtendedSiteClassification,
    SiteType,
    SourceClassification,
    SourceType,
    StrategyType,
    TechnicalFeatures,
)

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

# Маркеры JS-фреймворков по конкретным технологиям.
_FRAMEWORK_MARKERS: dict[str, tuple[str, ...]] = {
    'react': (
        'data-reactroot',
        'data-reactid',
        '__REACT_DEVTOOLS_GLOBAL_HOOK__',
        'react.development',
        'react.production',
    ),
    'vue': (
        'data-v-',
        '__VUE__',
        'v-if',
        'v-for',
        'v-bind',
        'vue.global',
    ),
    'angular': (
        'ng-app',
        'ng-controller',
        'ng-version',
        'angular.min',
    ),
    'nextjs': (
        '__NEXT_DATA__',
        'next-page',
    ),
    'nuxt': (
        '__NUXT__',
        'data-nuxt',
    ),
}

# Маркеры CSS-фреймворков.
_CSS_FRAMEWORK_MARKERS: dict[str, tuple[str, ...]] = {
    'bootstrap': (
        'bootstrap.min.css',
        'bootstrap.bundle',
        'btn-primary',
    ),
    'tailwind': (
        'tailwindcss',
        'tailwind.min',
        'hover:',
        'focus:',
    ),
    'material': (
        'material.',
        'mdc-',
    ),
    'semantic_ui': (
        'semantic.min.css',
        'semantic-ui',
    ),
}

# CSS-селекторы корзины/магазина (для детекции e-commerce).
_CART_SELECTORS = (
    '.cart',
    '#cart',
    '.basket',
    '.shopping-cart',
    '.buy',
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

# Домены государственных реестров — общий список, adaptive/hostname.py.
_REGISTRY_DOMAINS = KNOWN_REGISTRY_DOMAINS

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
    # Расширенные детекторы (SiteType, JS/CSS-фреймворки, мета)
    # ========================================================================

    def _detect_site_type(self, html: str) -> SiteType:
        """Определяет детализированный тип сайта по структуре HTML.

        Приоритет: schema.org разметка → Open Graph → корзина/магазин →
        маркеры контента. Возвращает ``SiteType.OTHER``, если тип не распознан.
        """
        if not html:
            return SiteType.OTHER

        soup = BeautifulSoup(html, 'html.parser')

        site_type = self._site_type_from_schema_org(soup)
        if site_type is not None:
            return site_type

        site_type = self._site_type_from_open_graph(soup)
        if site_type is not None:
            return site_type

        if any(soup.select_one(sel) for sel in _CART_SELECTORS):
            return SiteType.E_COMMERCE

        return self._site_type_from_text_markers(html.lower())

    @staticmethod
    def _site_type_from_schema_org(soup: BeautifulSoup) -> SiteType | None:
        """Определяет тип сайта по schema.org разметке, если она есть."""
        for item in soup.find_all(
            attrs={'itemtype': re.compile(r'schema\.org')}
        ):
            item_str = str(item).lower()
            if 'product' in item_str:
                return SiteType.E_COMMERCE
            if 'jobposting' in item_str:
                return SiteType.JOB_BOARD
            if 'review' in item_str:
                return SiteType.REVIEW_AGGREGATOR
            if 'faqpage' in item_str:
                return SiteType.QUESTION_ANSWER
            if 'article' in item_str:
                return SiteType.NEWS
        return None

    @staticmethod
    def _site_type_from_open_graph(soup: BeautifulSoup) -> SiteType | None:
        """Определяет тип сайта по мета-тегу Open Graph, если он есть."""
        og_type = soup.find('meta', attrs={'property': 'og:type'})
        if not og_type:
            return None
        og_value = (og_type.get('content') or '').lower()
        if og_value == 'product':
            return SiteType.E_COMMERCE
        if og_value == 'article':
            return SiteType.NEWS
        return None

    @staticmethod
    def _site_type_from_text_markers(html_lower: str) -> SiteType:
        """Определяет тип сайта по текстовым маркерам контента."""
        if 'вакансия' in html_lower or 'вакансии' in html_lower:
            return SiteType.JOB_BOARD
        if 'объявлени' in html_lower:
            return SiteType.CLASSIFIEDS
        if 'отзыв' in html_lower:
            return SiteType.REVIEW_AGGREGATOR
        return SiteType.OTHER

    def _detect_js_frameworks(self, html: str) -> list[str]:
        """Определяет JS-фреймворки по маркерам в HTML."""
        html_lower = html.lower()
        frameworks: list[str] = []
        for name, markers in _FRAMEWORK_MARKERS.items():
            if any(marker in html_lower for marker in markers):
                frameworks.append(name)
        return frameworks

    def _detect_css_patterns(self, html: str) -> list[str]:
        """Определяет CSS-фреймворки по маркерам в HTML."""
        html_lower = html.lower()
        frameworks: list[str] = []
        for name, markers in _CSS_FRAMEWORK_MARKERS.items():
            if any(marker in html_lower for marker in markers):
                frameworks.append(name)
        return frameworks

    def _detect_meta(self, html: str) -> dict[str, bool]:
        """Анализирует присутствие метрик и верификации в HTML."""
        html_lower = html.lower()
        return {
            'has_ya_metrika': 'metrika' in html_lower
            or 'yandex_metrika' in html_lower,
            'has_ga': 'google-analytics' in html_lower or 'gtag' in html_lower,
            'has_fb_pixel': 'fbq' in html_lower
            or 'facebook-pixel' in html_lower,
            'has_verification': bool(
                BeautifulSoup(html, 'html.parser').find(
                    'meta', attrs={'name': re.compile(r'verification', re.I)}
                )
            ),
        }

    async def classify_extended(
        self,
        source_name: str,
        source_url: str,
        headers: dict[str, Any] | None = None,
        html: str | None = None,
    ) -> ExtendedSiteClassification:
        """Расширенная классификация с детализацией типа сайта.

        Дополняет ``classify`` детализированным ``SiteType``, подтипом страницы
        (не определяется автоматически — ``OTHER``), бизнес- и техническими
        характеристиками. Обратно совместим с ``classify``.
        """
        base = await self.classify(
            source_name=source_name,
            source_url=source_url,
            headers=headers,
            html=html,
        )

        html_lower = (html or '').lower()
        technical = TechnicalFeatures(
            frameworks=self._detect_js_frameworks(html or ''),
            css_frameworks=self._detect_css_patterns(html or ''),
            has_antibot=base.has_antibot,
            has_captcha=base.has_captcha,
            is_spa=base.is_spa,
        )
        business = BusinessFeatures(
            has_cart=any(
                sel in html_lower for sel in ('.cart', '#cart', '.basket')
            ),
            has_search='search' in html_lower,
            has_pagination='pagination' in html_lower or 'page=' in html_lower,
        )
        meta = self._detect_meta(html or '')

        return ExtendedSiteClassification(
            source_name=base.source_name,
            site_type=self._detect_site_type(html or ''),
            confidence=(
                1.0
                if self._detect_site_type(html or '') != SiteType.OTHER
                else 0.5
            ),
            business_features=business,
            technical_features=technical,
            complexity_score=base.complexity_score,
            recommended_strategy=base.recommended_strategy,
            metadata={**meta, 'url': source_url},
        )

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
        """Выбирает оптимальную стратегию обхода.

        Тонкая обёртка над общей эвристикой ``heuristic_strategy``
        (``processing/_llm/heuristics.py``), которая используется и здесь,
        и как fallback в ``AIAgent`` — раньше логика была задублирована в
        двух местах. При CAPTCHA рекомендуется сразу HITL
        (``escalate_captcha_to_hitl=True``): для только что
        классифицированного источника это обоснованная стартовая точка
        деградации, в отличие от AIAgent-фолбэка (см. docstring
        ``heuristic_strategy``).
        """
        classification = SourceClassification(
            source_name='',
            source_type=source_type,
            has_antibot=has_antibot,
            has_captcha=has_captcha,
            is_spa=is_spa,
        )
        return heuristic_strategy(classification, escalate_captcha_to_hitl=True)
