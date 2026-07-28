"""Конвейер BP-5: витрина → детектор значимых событий → журнал alert.

Берёт новые/изменившиеся строки showcase_event, ищет среди них значимые
события по ключевым словам (event_type), маршрутизирует по матрице
(routing_rule: тип + приоритет → конкретный получатель + канал + режим)
и пишет журнал доставок (alert).

Порядок шагов:

  1. отобрать события под проверку — select_pending_events (crud)
  2. найти совпавший тип по keywords — detect_event_type
  3. найти правила для (тип, приоритет) — load_routing_rules (crud)
  4. собрать строки alert — build_alert_rows
  5. записать пачкой (ON CONFLICT DO NOTHING) — insert_alerts (crud)
  6. пометить все проверенные — mark_checked (crud), НЕЗАВИСИМО от результата

Порог значимости — не хардкод «только П1/П2»: значим тот, для кого в
routing_rule нашлась строка на пару (тип, приоритет). Правило «расширение»
осознанно заведено на П3 — подтверждает, что порог живёт в справочнике,
а не в коде (см. src/bp5/BP5_README.md).

Доставка — заглушка: instant сразу помечается sent, без обращения к
telegram/email API (интеграция с каналами — отдельная задача, не в этом
конвейере). digest остаётся queued — заберёт джоба-сводка по расписанию.

Две точки входа: sync_alerts(session) — шаги 1-6 в ЧУЖОЙ сессии, без commit
(используется сидером); run_bp5() — самостоятельный прогон со своей сессией
и commit.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.enums import AlertStatus, DeliveryMode
from src.bp4.constants import PRIORITY_FROM_DISPLAY
from src.bp4.models import ShowcaseEvent
from src.bp5.crud import Bp5Crud
from src.bp5.models import EventType, RoutingRule

# ============================================================================
#  Детекция типа события
# ============================================================================


def detect_event_type(
    title: str | None, event_types: Sequence[EventType]
) -> int | None:
    """Первый event_type, чьи keywords встретились в title (без регистра).

    Первое совпадение побеждает (порядок из БД) — событие относят ровно
    к одному типу. Если заголовок описывает сразу два значимых события
    («суд» и «тендер» в одной новости) — поймается только первый по
    порядку; матчинг всех подошедших типов — расширение на будущее,
    сейчас не требуется.
    """
    haystack = (title or '').lower()
    for event_type in event_types:
        if any(kw.lower() in haystack for kw in event_type.keywords):
            return event_type.id
    return None


# ============================================================================
#  Сборка строк alert
# ============================================================================


def build_alert_rows(
    event: ShowcaseEvent,
    matched_type_id: int,
    rules: Sequence[RoutingRule],
    *,
    now: datetime,
) -> list[dict]:
    """Правила для (тип, приоритет) → строки под запись в alert.

    Одна строка правила — одна строка алерта: несколько получателей и/или
    каналов на пару (тип, приоритет) дают несколько строк alert, это и
    есть множественная доставка одного события (ТЗ п. BP-5).

    priority снимаем с САМОГО события (не с правила): это «приоритет на
    момент алерта», а правило меняется независимо от факта.
    """
    priority = PRIORITY_FROM_DISPLAY[event.priority]
    rows: list[dict] = []
    for rule in rules:
        delivered = rule.mode == DeliveryMode.instant
        rows.append(
            {
                'showcase_event_id': event.id,
                'event_type_id': matched_type_id,
                'priority': priority,
                'user_id': rule.user_id,
                'channel_id': rule.channel_id,
                'mode': rule.mode,
                'status': AlertStatus.sent if delivered else AlertStatus.queued,
                'sent_at': now if delivered else None,
            }
        )
    return rows


# ============================================================================
#  Оркестратор — весь конвейер BP-5 в один прогон (шаги помечены ниже)
# ============================================================================


async def sync_alerts(session: AsyncSession) -> dict:
    """Синхронизировать алерты в переданной сессии (без commit).

    Вынесено отдельно от run_bp5, чтобы прогон можно было выполнить внутри
    чужой транзакции — так его вызывает сидер (core/scripts/seed_all.py),
    не открывая вторую сессию и не коммитя посреди своей.

    Возвращает сводку прогона: сколько событий проверено, сколько из них
    оказались значимыми (нашёлся event_type), сколько строк alert записано.
    """
    crud = Bp5Crud(session)
    now = datetime.now(UTC)

    # Справочники детектора — грузим один раз на весь прогон
    event_types = await crud.load_event_types()
    routing_rules = await crud.load_routing_rules()

    # Шаг 1 — отобрать события под проверку
    pending = await crud.select_pending_events()

    rows: list[dict] = []
    matched = 0
    checked_ids: list[int] = []
    for event in pending:
        checked_ids.append(event.id)

        # Шаг 2 — найти совпавший тип по keywords
        matched_type_id = detect_event_type(event.title, event_types)
        if matched_type_id is None:
            continue
        matched += 1

        # Шаг 3 — найти правила для (тип, приоритет)
        priority = PRIORITY_FROM_DISPLAY[event.priority]
        rules = routing_rules.get((matched_type_id, priority), [])
        if not rules:
            continue

        # Шаг 4 — собрать строки alert
        rows.extend(build_alert_rows(event, matched_type_id, rules, now=now))

    # Шаг 5 — записать пачкой (идемпотентно)
    inserted = await crud.insert_alerts(rows)

    # Шаг 6 — пометить ВСЕ проверенные, независимо от результата
    await crud.mark_checked(checked_ids, now)

    return {
        'pending': len(pending),
        'matched': matched,
        'alerts': inserted,
    }


async def run_bp5() -> dict:
    """Один самостоятельный прогон конвейера BP-5: витрина → alert.

    Открывает свою сессию, синхронизирует алерты и коммитит.
    Возвращает сводку прогона (сколько событий обработано).
    """
    async with AsyncSessionLocal() as session:
        summary = await sync_alerts(session)
        await session.commit()
        return summary


if __name__ == '__main__':
    import asyncio

    result = asyncio.run(run_bp5())
    print(result)
