"""Фильтр семантической релевантности собранных элементов (BP-1 Adaptive).

Фича 1: убирает нерелевантные новости из ``extra.news`` на финальном этапе
сбора. Оркестрирует пакетный LLM-скоринг (``AIAgent.score_relevance``) и
эвристический fallback, применяет режим фильтрации и аннотирует элементы
метаданными ``relevance`` / ``relevance_filtered`` / ``news_total`` для
аудита качества.

Режимы:
- ``off``    — без изменений;
- ``filter`` — отбросить элементы ниже порога;
- ``rank``   — отсортировать по убыванию ``relevance`` (ничего не теряем).
"""

from __future__ import annotations

from typing import Any

from ..schemas import RelevanceMode

# Режимы, в которых фильтр активен.
_FILTERING_MODES = {RelevanceMode.FILTER, RelevanceMode.RANK}


class RelevanceFilter:
    """Применяет скоринг релевантности и фильтрацию к списку элементов.

    Используется в ``AdaptiveParser`` сразу после
    ``_collect_news_with_pagination``. Не разрушает данные: при любом
    режиме в ``extra`` сохраняются метаданные фильтрации, а каждый
    элемент получает поле ``relevance``.
    """

    def __init__(
        self,
        agent: Any,
        mode: str | RelevanceMode = RelevanceMode.OFF,
        threshold: float = 0.6,
    ):
        self._agent = agent
        try:
            self._mode = RelevanceMode(mode)
        except ValueError:
            self._mode = RelevanceMode.OFF
        self._threshold = max(0.0, min(1.0, float(threshold)))

    async def apply(
        self,
        items: list[dict[str, Any]],
        competitor: str,
        trigger: str = '',
        inn: str | None = None,
    ) -> list[dict[str, Any]]:
        """Применяет скоринг релевантности и фильтрацию.

        Args:
            items: Собранные элементы ``(title, url, text)``.
            competitor: Название конкурента.
            trigger: Тема поиска (опционально).
            inn: ИНН конкурента (опционально).

        Returns:
            Отфильтрованный/ранжированный список элементов. Каждый
            элемент снабжён полем ``relevance``.
        """
        if not items or self._mode == RelevanceMode.OFF:
            return items

        scores = await self._agent.score_relevance(
            items, competitor, trigger, inn
        )
        scored = [
            self._annotate(item, scores[i]) for i, item in enumerate(items)
        ]

        if self._mode == RelevanceMode.FILTER:
            kept = [
                item for item in scored if item['relevance'] >= self._threshold
            ]
        elif self._mode == RelevanceMode.RANK:
            kept = sorted(
                scored, key=lambda it: it.get('relevance', 0.0), reverse=True
            )
        else:  # pragma: no cover - режим OFF отсечён выше
            kept = scored

        return kept

    @staticmethod
    def _annotate(
        item: dict[str, Any],
        score: dict[str, Any],
    ) -> dict[str, Any]:
        """Добавляет оценку ``relevance`` в элемент (неразрушающе)."""
        annotated = dict(item)
        annotated['relevance'] = float(score.get('score', 0.0))
        return annotated

    @staticmethod
    def build_extra(
        original_count: int,
        kept_count: int,
        mode: RelevanceMode,
    ) -> dict[str, Any]:
        """Формирует метаданные фильтрации для ``extra``."""
        return {
            'relevance_mode': mode.value,
            'news_total': original_count,
            'relevance_filtered': (
                original_count - kept_count if mode in _FILTERING_MODES else 0
            ),
        }
