"""Конвейер BP-5: витрина → детектор значимых событий → журнал alert.

Берёт новые/изменившиеся строки showcase_event, ищет среди них значимые
события по ключевым словам (event_type), маршрутизирует по матрице
(routing_rule: (тип + приоритет) ИЛИ приоритет → конкретный получатель +
канал + режим) и пишет журнал доставок (alert).

Порядок шагов:

  1. отобрать события под проверку — select_pending_events (crud)
  2. найти совпавший тип по keywords — detect_event_type (может не найтись —
     это больше не повод пропустить событие, см. ниже)
  3. найти подходящие правила — load_routing_rules (crud): по (тип,
     приоритет), если тип распознан, ПЛЮС по одному приоритету; наложение
     схлопывается — см. _merge_rule_overlap
  4. собрать строки alert — build_alert_rows
  5. записать пачкой (ON CONFLICT DO NOTHING) — insert_alerts (crud)
  5.5. доставить instant+(email|telegram) из РЕАЛЬНО вставленных строк —
       send_email/send_telegram, пометить исход через mark_alert_result
       (crud): queued -> sent/failed
  6. пометить все проверенные — mark_checked (crud), НЕЗАВИСИМО от результата

Порог значимости — не хардкод «только П1/П2»: значим тот, для кого в
routing_rule нашлась строка. Правило «расширение» осознанно заведено на
П3 — подтверждает, что порог живёт в справочнике, а не в коде (см.
src/bp5/BP5_README.md). Правило БЕЗ типа события (`event_type_id IS NULL`)
срабатывает на любое событие нужного приоритета независимо от заголовка —
выражает базовое требование ТЗ «слать все события приоритета П1», которое
через ключевые слова не выразить (см.
openspec/changes/add-priority-only-routing). Событие, для которого тип НЕ
распознан, больше не отбрасывается сразу: оно всё равно проверяется на
правила по приоритету — алерт может создаться и без распознанного типа.

Счётчик `matched` в сводке прогона — по-прежнему число событий, для которых
detect_event_type нашёл тип (как и до этого изменения). Он НЕ означает
«создан алерт»: событие может matched=True и не дать алерта (нет правила ни
по типу, ни по приоритету), и наоборот — matched=False, но алерт создастся
по правилу без типа. Это два независимых сигнала: «распознан тип» и
«отправлен алерт» (последний — в `alerts`).

Доставка: email/telegram + instant отправляются по-настоящему через
core.mail/core.telegram — пойманное исключение переводит alert в failed
с error_message, успех в sent. Digest-режим в этой итерации намеренно
остаётся queued (заберёт джоба-сводка).

Адресация (кому реально уходит письмо/сообщение) управляется
settings.true_alerting — но, в отличие от прежней версии, флаг больше НЕ
включает/выключает саму отправку, а выбирает ТОЛЬКО адресата:
  false -> settings.test_email / settings.test_tg (песочница);
  true  -> recipient.email / recipient.telegram_id (реальный получатель).
Сама попытка отправки происходит всегда, пока не передан deliver=False.

deliver=False (использует сидер, core/scripts/stages/bp5.py) отключает
попытку отправки целиком, независимо от true_alerting: строки инстант-
доставки сразу помечаются sent без единого обращения к сети — сидеру нужны
только правдоподобные демо-данные в alert, а не реальная рассылка.

Две точки входа: sync_alerts(session) — шаги 1-6 в ЧУЖОЙ сессии, без commit
(используется сидером); run_bp5() — самостоятельный прогон со своей сессией
и commit.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import AsyncSessionLocal
from core.enums import AlertStatus, DeliveryMode
from core.mail import send_email
from core.telegram import send_telegram
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
    matched_type_id: int | None,
    rules: Sequence[RoutingRule],
) -> list[dict]:
    """Подошедшие правила → строки под запись в alert.

    Одна строка правила — одна строка алерта: несколько получателей и/или
    каналов на одно событие дают несколько строк alert, это и есть
    множественная доставка одного события (ТЗ п. BP-5).

    matched_type_id пишется в КАЖДУЮ строку как есть, независимо от того,
    какое конкретно правило её породило (с типом или по приоритету): если
    тип распознан — это полезная информация в журнале в любом случае; если
    не распознан (None) — запись честно остаётся без типа, а не с
    подставленным значением (см. design.md изменения
    add-priority-only-routing, Decisions).

    priority снимаем с САМОГО события (не с правила): это «приоритет на
    момент алерта», а правило меняется независимо от факта.

    Все строки уходят как queued/без sent_at — реальный исход доставки
    (sent/failed) решается позже, после insert_alerts, попыткой отправки.
    """
    priority = PRIORITY_FROM_DISPLAY[event.priority]
    return [
        {
            'showcase_event_id': event.id,
            'event_type_id': matched_type_id,
            'priority': priority,
            'user_id': rule.user_id,
            'channel_id': rule.channel_id,
            'mode': rule.mode,
            'status': AlertStatus.queued,
            'sent_at': None,
        }
        for rule in rules
    ]


def merge_rule_overlap(
    typed_rules: Sequence[RoutingRule],
    priority_rules: Sequence[RoutingRule],
) -> list[RoutingRule]:
    """Схлопнуть наложение правила по типу и правила по приоритету.

    Если на одно событие сработали и правило с указанным типом, и правило
    без типа с тем же получателем и каналом — остаётся только типовое: оно
    точнее объясняет, почему сработал алерт. Полагаться на UNIQUE(событие,
    канал, получатель) в самом alert нельзя — какая из двух строк уцелеет,
    определялось бы порядком вставки в пачке, а от этого зависит тип,
    записанный в журнал (см. design.md изменения add-priority-only-routing,
    Decisions).
    """
    typed_pairs = {(rule.user_id, rule.channel_id) for rule in typed_rules}
    extra = [
        rule
        for rule in priority_rules
        if (rule.user_id, rule.channel_id) not in typed_pairs
    ]
    return [*typed_rules, *extra]


# ============================================================================
#  Сборка текста письма
# ============================================================================


def build_email_content(event: ShowcaseEvent) -> tuple[str, str]:
    """Тема + тело письма из полей витрины. Чистая функция — без сети/БД."""
    subject = f'[KODIK] {event.priority} — {event.category}: {event.title}'
    body = (
        f'Приоритет: {event.priority}\n'
        f'Категория: {event.category}\n'
        f'Регион: {event.region or "—"} ({event.macro_region or "—"})\n'
        f'Конкурент/объект: {event.competitor or "—"}\n\n'
        f'{event.title}\n\n'
        f'Требуемое действие: {event.action or "—"}\n'
        f'Срок реакции: '
        f'{event.deadline.isoformat() if event.deadline else "—"}\n'
        f'Ответственный отдел: {event.department or "—"}\n\n'
        f'Источник: {event.source_url or "—"}\n'
        f'Опубликовано: '
        f'{event.published_at.isoformat() if event.published_at else "—"}'
    )
    return subject, body


def build_telegram_content(event: ShowcaseEvent) -> str:
    """Текст telegram-сообщения — переиспользует сборку email-контента:
    единый источник текста алерта для обоих каналов."""
    subject, body = build_email_content(event)
    return f'{subject}\n\n{body}'


# ============================================================================
#  Оркестратор — весь конвейер BP-5 в один прогон (шаги помечены ниже)
# ============================================================================


async def sync_alerts(session: AsyncSession, *, deliver: bool = True) -> dict:
    """Синхронизировать алерты в переданной сессии (без commit).

    Вынесено отдельно от run_bp5, чтобы прогон можно было выполнить внутри
    чужой транзакции — так его вызывает сидер (core/scripts/seed_all.py),
    не открывая вторую сессию и не коммитя посреди своей.

    deliver=False — не делать НИ ОДНОЙ попытки реальной отправки (email или
    telegram), независимо от settings.true_alerting; instant-строки сразу
    помечаются sent. Используется сидером (core/scripts/stages/bp5.py),
    которому нужны только правдоподобные демо-статусы в alert, а не реальная
    рассылка на каждый пересид демоданных.

    Возвращает сводку прогона: сколько событий проверено, сколько из них
    оказались значимыми (нашёлся event_type), сколько строк alert записано.
    """
    crud = Bp5Crud(session)
    now = datetime.now(UTC)

    # Справочники — грузим все разом один раз на весь прогон
    event_types = await crud.load_event_types()
    routing_rules = await crud.load_routing_rules()
    channels = await crud.load_channels()
    users = await crud.load_users()

    # Шаг 1 — отобрать события под проверку
    pending = await crud.select_pending_events()
    events_by_id = {event.id: event for event in pending}

    rows: list[dict] = []
    matched = 0
    checked_ids: list[int] = []
    for event in pending:
        checked_ids.append(event.id)

        # Шаг 2 — найти совпавший тип по keywords. Не найден — событие
        # больше НЕ отбрасывается здесь: оно всё ещё может подойти под
        # правило по приоритету (шаг 3).
        matched_type_id = detect_event_type(event.title, event_types)
        if matched_type_id is not None:
            matched += 1

        # Шаг 3 — найти подходящие правила: по (тип, приоритет), если тип
        # распознан, плюс по одному приоритету; наложение схлопывается.
        priority = PRIORITY_FROM_DISPLAY[event.priority]
        typed_rules = (
            routing_rules.by_type.get((matched_type_id, priority), [])
            if matched_type_id is not None
            else []
        )
        priority_rules = routing_rules.by_priority.get(priority, [])
        rules = merge_rule_overlap(typed_rules, priority_rules)
        if not rules:
            continue

        # Шаг 4 — собрать строки alert
        rows.extend(build_alert_rows(event, matched_type_id, rules))

    # Шаг 5 — записать пачкой (идемпотентно), получить РЕАЛЬНО вставленные
    inserted_rows = await crud.insert_alerts(rows)

    # Шаг 5.5 — доставить instant+(email|telegram) из вставленных в этом
    # прогоне строк. digest-режим остаётся queued (заберёт джоба-сводка).
    for row in inserted_rows:
        if row['mode'] != DeliveryMode.instant:
            continue
        channel_name = channels.get(row['channel_id'])
        if channel_name not in ('email', 'telegram'):
            continue

        if not deliver:
            await crud.mark_alert_result(
                row['id'], AlertStatus.sent, datetime.now(UTC), None
            )
            continue

        event = events_by_id[row['showcase_event_id']]
        recipient = users[row['user_id']]
        try:
            if channel_name == 'email':
                to = (
                    recipient.email
                    if settings.true_alerting
                    else settings.test_email
                )
                subject, body = build_email_content(event)
                await send_email(to, subject, body)
            else:
                chat_id = (
                    recipient.telegram_id
                    if settings.true_alerting
                    else settings.test_tg
                )
                await send_telegram(chat_id, build_telegram_content(event))
        except Exception as exc:  # сбой доставки (сеть/аутентификация)
            await crud.mark_alert_result(
                row['id'], AlertStatus.failed, None, str(exc)
            )
        else:
            await crud.mark_alert_result(
                row['id'], AlertStatus.sent, datetime.now(UTC), None
            )

    # Шаг 6 — пометить ВСЕ проверенные, независимо от результата
    await crud.mark_checked(checked_ids, now)

    return {
        'pending': len(pending),
        'matched': matched,
        'alerts': len(inserted_rows),
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


# if __name__ == '__main__':
#     import asyncio

#     result = asyncio.run(run_bp5())
#     print(result)
