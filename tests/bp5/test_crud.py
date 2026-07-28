"""Интеграционные тесты BP-5 CRUD и sync_alerts — требуют реальной БД.

Сессия из conftest не делает commit — данные откатываются после каждого
теста. Цепочка до витрины та же, что в tests/bp4/test_crud.py, плюс
справочники детектора: event_type, channel, user, routing_rule.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from core.enums import (
    AlertStatus,
    DeliveryMode,
    NormStatus,
    PriorityLevel,
    RawItemStatus,
    TonalityLevel,
)
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.constants import PRIORITY_DISPLAY
from src.bp4.models import ShowcaseEvent
from src.bp5.crud import Bp5Crud
from src.bp5.models import Alert, Channel, EventType, RoutingRule, User
from src.bp5.pipeline import sync_alerts

# ============================================================================
#  Вспомогательные фикстуры — цепочка до витрины + справочники детектора
# ============================================================================


@pytest.fixture
async def competitor(session):
    c = Competitor(name=f'__тест-конкурент-{uuid4().hex[:8]}__')
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def source(session):
    s = Source(name=f'__тест-источник-{uuid4().hex[:8]}__')
    session.add(s)
    await session.flush()
    return s


@pytest.fixture
async def raw_item(session, competitor, source):
    task = SearchTask(
        competitor_id=competitor.id, source_id=source.id, trigger_id=None
    )
    session.add(task)
    await session.flush()
    now = datetime.now(UTC)
    raw = RawItem(
        search_task_id=task.id,
        status=RawItemStatus.new,
        raw_data={'meta': {'search_task_id': task.id}, 'items': []},
        created_at=now,
        updated_at=now,
    )
    session.add(raw)
    await session.flush()
    return raw


@pytest.fixture
async def category(session):
    c = Category(name=f'__тест-категория-{uuid4().hex[:8]}__')
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def department(session):
    d = Department(name=f'__тест-отдел-{uuid4().hex[:8]}__')
    session.add(d)
    await session.flush()
    return d


@pytest.fixture
async def channel(session):
    c = Channel(name=f'__тест-канал-{uuid4().hex[:8]}__')
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def user(session, department):
    u = User(
        full_name='Тестовый Пользователь',
        department_id=department.id,
        email=f'{uuid4().hex[:8]}@test.ru',
        telegram_login=f'test_{uuid4().hex[:8]}',
    )
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def event_type(session):
    """Ключевые слова — заведомо уникальная бессмыслица.

    БД не изолирована от реальных сидированных справочников (session из
    conftest откатывает только то, что сделано в рамках теста, но уже
    закоммиченные ранее строки — например, из core.scripts.seed_all —
    остаются видны транзакции по чтению). Настоящий event_type «судебный/
    надзорный риск» тоже ловит «прокуратура» — использовать здесь то же
    слово означало бы, что detect_event_type мог бы поймать ЧУЖОЙ тип,
    а не фикстуру теста. Уникальный маркер это исключает.
    """
    marker = f'ключслово{uuid4().hex[:8]}'
    et = EventType(
        name=f'__тест-тип-{uuid4().hex[:8]}__',
        keywords=[marker],
    )
    session.add(et)
    await session.flush()
    return et


@pytest.fixture
async def routing_rule(session, event_type, user, channel):
    rule = RoutingRule(
        event_type_id=event_type.id,
        priority=PriorityLevel.p1,
        user_id=user.id,
        channel_id=channel.id,
        mode=DeliveryMode.instant,
    )
    session.add(rule)
    await session.flush()
    return rule


async def make_showcase(
    session,
    raw_item,
    competitor,
    category,
    department,
    *,
    title,
    priority=PriorityLevel.p1,
):
    """Полная цепочка normalized_item -> categorized_event -> showcase_event.

    BP-5 работает от витрины, поэтому строим её целиком, а не подделываем
    напрямую — так задействуется тот же контракт полей, что у реального
    BP-4 (в частности, priority хранится строкой-подписью, не enum'ом).
    """
    item = NormalizedItem(
        raw_item_id=raw_item.id,
        competitor_id=competitor.id,
        region_id=None,
        source_id=None,
        published_at=date(2026, 6, 25),
        title=title,
        dedup_key=uuid4().hex,
        status=NormStatus.ok,
    )
    session.add(item)
    await session.flush()

    ce = CategorizedEvent(
        normalized_item_id=item.id,
        priority=priority,
        category_id=category.id,
        tonality=TonalityLevel.neutral,
        department_id=department.id,
        llm_model='test',
        prompt_version='v0',
    )
    session.add(ce)
    await session.flush()

    sc = ShowcaseEvent(
        categorized_event_id=ce.id,
        raw_item_id=raw_item.id,
        title=title,
        priority=PRIORITY_DISPLAY[priority],
        category=category.name,
        tonality='нейтральная',
    )
    session.add(sc)
    await session.flush()
    return sc


# ============================================================================
#  select_pending_events / mark_checked
# ============================================================================


async def test_new_showcase_event_is_pending(
    session, raw_item, competitor, category, department
):
    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title='Прокуратура начала проверку',
    )
    crud = Bp5Crud(session)
    pending = await crud.select_pending_events()
    assert sc.id in [e.id for e in pending]


async def test_checked_event_not_pending(
    session, raw_item, competitor, category, department
):
    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title='Без совпадений',
    )
    crud = Bp5Crud(session)
    await crud.mark_checked([sc.id], datetime.now(UTC))
    await session.flush()

    pending = await crud.select_pending_events()
    assert sc.id not in [e.id for e in pending]


async def test_checked_event_returns_after_update(
    session, raw_item, competitor, category, department
):
    """updated_at сдвинулся (пересборка BP-4) -> событие снова pending."""
    sc = await make_showcase(
        session, raw_item, competitor, category, department, title='Тест'
    )
    crud = Bp5Crud(session)
    checked_at = datetime.now(UTC)
    await crud.mark_checked([sc.id], checked_at)
    await session.flush()

    sc.updated_at = checked_at + timedelta(minutes=5)
    await session.flush()

    pending = await crud.select_pending_events()
    assert sc.id in [e.id for e in pending]


# ============================================================================
#  load_event_types / load_routing_rules
# ============================================================================


async def test_load_event_types_returns_active_only(session, event_type):
    inactive = EventType(
        name=f'__неактивный-{uuid4().hex[:8]}__',
        keywords=['x'],
        is_active=False,
    )
    session.add(inactive)
    await session.flush()

    crud = Bp5Crud(session)
    ids = {t.id for t in await crud.load_event_types()}
    assert event_type.id in ids
    assert inactive.id not in ids


async def test_load_routing_rules_grouped_by_type_and_priority(
    session, routing_rule
):
    crud = Bp5Crud(session)
    grouped = await crud.load_routing_rules()
    key = (routing_rule.event_type_id, routing_rule.priority)
    assert key in grouped
    assert routing_rule.id in [r.id for r in grouped[key]]


# ============================================================================
#  insert_alerts
# ============================================================================


async def test_insert_alerts_duplicate_ignored(
    session, raw_item, competitor, category, department, routing_rule
):
    sc = await make_showcase(
        session, raw_item, competitor, category, department, title='Тест'
    )
    crud = Bp5Crud(session)
    row = {
        'showcase_event_id': sc.id,
        'event_type_id': routing_rule.event_type_id,
        'priority': PriorityLevel.p1,
        'user_id': routing_rule.user_id,
        'channel_id': routing_rule.channel_id,
        'mode': routing_rule.mode,
        'status': AlertStatus.sent,
        'sent_at': datetime.now(UTC),
    }
    await crud.insert_alerts([row])
    inserted_again = await crud.insert_alerts([row])
    await session.flush()

    assert inserted_again == 0
    found = (
        (
            await session.execute(
                select(Alert).where(Alert.showcase_event_id == sc.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(found) == 1


async def test_insert_alerts_empty_list_returns_zero(session):
    crud = Bp5Crud(session)
    assert await crud.insert_alerts([]) == 0


# ============================================================================
#  sync_alerts (оркестратор в чужой сессии)
# ============================================================================


async def test_no_match_gives_no_alert(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
):
    """Заголовок не содержит ключевых слов — алертов нет."""
    await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title='Обычная новость без триггеров',
    )
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['matched'] == 0
    assert summary['alerts'] == 0


async def test_match_without_routing_rule_gives_no_alert(
    session, raw_item, competitor, category, department, event_type
):
    """Тип нашёлся, но правила для этого приоритета нет — алерта нет."""
    await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
        priority=PriorityLevel.p3,  # routing_rule заведён только на p1
    )
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['matched'] == 1
    assert summary['alerts'] == 0


async def test_matched_event_creates_alert(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
):
    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
    )
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['alerts'] == 1
    alert = await session.scalar(
        select(Alert).where(Alert.showcase_event_id == sc.id)
    )
    assert alert is not None
    assert alert.user_id == routing_rule.user_id
    assert alert.status == AlertStatus.sent  # instant


async def test_digest_mode_stays_queued(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    user,
    channel,
):
    session.add(
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel.id,
            mode=DeliveryMode.digest,
        )
    )
    await session.flush()

    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
    )
    await sync_alerts(session)
    await session.flush()

    alert = await session.scalar(
        select(Alert).where(Alert.showcase_event_id == sc.id)
    )
    assert alert.status == AlertStatus.queued
    assert alert.sent_at is None


async def test_multiple_recipients_create_multiple_alerts(
    session, raw_item, competitor, category, department, event_type, channel
):
    u1 = User(
        full_name='Получатель Один',
        department_id=department.id,
        email=f'{uuid4().hex[:8]}@test.ru',
        telegram_login=f't1_{uuid4().hex[:8]}',
    )
    u2 = User(
        full_name='Получатель Два',
        department_id=department.id,
        email=f'{uuid4().hex[:8]}@test.ru',
        telegram_login=f't2_{uuid4().hex[:8]}',
    )
    session.add_all([u1, u2])
    await session.flush()
    session.add_all(
        [
            RoutingRule(
                event_type_id=event_type.id,
                priority=PriorityLevel.p1,
                user_id=u1.id,
                channel_id=channel.id,
                mode=DeliveryMode.instant,
            ),
            RoutingRule(
                event_type_id=event_type.id,
                priority=PriorityLevel.p1,
                user_id=u2.id,
                channel_id=channel.id,
                mode=DeliveryMode.instant,
            ),
        ]
    )
    await session.flush()

    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
    )
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['alerts'] == 2
    alerts = (
        (
            await session.execute(
                select(Alert).where(Alert.showcase_event_id == sc.id)
            )
        )
        .scalars()
        .all()
    )
    assert {a.user_id for a in alerts} == {u1.id, u2.id}


async def test_sync_alerts_is_idempotent(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
):
    await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
    )
    first = await sync_alerts(session)
    await session.flush()
    assert first['alerts'] == 1

    second = await sync_alerts(session)
    await session.flush()
    assert second['pending'] == 0
    assert second['alerts'] == 0
