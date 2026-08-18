"""Центральный реестр всех моделей проекта.

Импортируется в alembic/env.py — регистрирует все модели в Base.metadata,
что необходимо для autogenerate миграций.

При добавлении нового BP — добавить одну строку импорта сюда.
env.py трогать не нужно.
"""

import core.pipeline  # noqa: F401 — PipelineControlMarker
import src.bp1  # Trigger, Competitor, Source, SearchTask, RawItem
import src.bp2  # Region, BlackDomain, StopWord, TopicLimit, NormalizedItem
import src.bp3  # Category, Department, CategorizedEvent
import src.bp4  # ShowcaseEvent
import src.bp5  # EventType, Channel, RoutingRule, Alert
import src.bp6  # ActionItem
import src.bp7  # noqa: F401 — SourceCandidate
