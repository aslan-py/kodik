"""Интеграционные тесты BP-5 CRUD и sync_alerts — требуют реальной БД.

Сессия из conftest не делает commit — данные откатываются после каждого
теста. Цепочка до витрины та же, что в tests/bp4/test_crud.py, плюс
справочники детектора: event_type, channel, user, routing_rule.

sync_alerts реально пытается слать email (core.mail.send_email) и telegram
(core.telegram.send_telegram) для instant-строк — во всех тестах ниже обе
функции подменяются моками (AsyncMock), чтобы не зависеть от сети и от
TRUE_ALERTING в окружении. Адресация (test_email/test_tg против реального
recipient.email/recipient.telegram_id) выбирается settings.true_alerting —
см. test_routing_uses_test_address_when_true_alerting_is_false и парный
тест ниже.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.config import settings
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


@pytest.fixture(autouse=True)
def mock_send_email(monkeypatch):
    """sync_alerts не должен реально стучаться в SMTP ни в одном тесте.

    autouse — иначе забытый тест без мока либо реально уйдёт в сеть (при
    TRUE_ALERTING=true в окружении разработчика), либо будет молча
    считаться "sent" при поломанной логике доставки (при false).
    """
    mock = AsyncMock()
    monkeypatch.setattr('src.bp5.pipeline.send_email', mock)
    return mock


@pytest.fixture(autouse=True)
def mock_send_telegram(monkeypatch):
    """Telegram-аналог mock_send_email — тот же смысл, тот же autouse."""
    mock = AsyncMock()
    monkeypatch.setattr('src.bp5.pipeline.send_telegram', mock)
    return mock


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
    """'email' — тот самый канал, что реально сидируется в проде
    (core/scripts/stages/dictionaries.py: CHANNELS).

    БД не изолирована от уже закоммиченных справочников (тот же нюанс,
    что и у фикстуры event_type ниже) — если 'email' уже существует,
    переиспользуем, иначе создаём. Имя должно быть ровно 'email': иначе
    sync_alerts не распознает канал как email-доставляемый (см.
    src/bp5/pipeline.py, шаг 5.5) и mock send_email ни разу не вызовется.
    """
    existing = await session.scalar(
        select(Channel).where(Channel.name == 'email')
    )
    if existing is not None:
        return existing
    c = Channel(name='email')
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def channel_telegram(session):
    """'telegram' — второй реально сидируемый канал (см. фикстуру channel
    выше). Имя должно быть ровно 'telegram', иначе sync_alerts не
    распознает канал как telegram-доставляемый."""
    existing = await session.scalar(
        select(Channel).where(Channel.name == 'telegram')
    )
    if existing is not None:
        return existing
    c = Channel(name='telegram')
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def user(session, department):
    u = User(
        full_name='Тестовый Пользователь',
        department_id=department.id,
        email=f'{uuid4().hex[:8]}@test.ru',
        telegram_id=uuid4().int % 1_000_000_000,
        password_hash='test-hash',
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


@pytest.fixture
async def routing_rule_by_priority(session, user, channel):
    """Правило БЕЗ типа события — срабатывает на любое событие П1,
    независимо от заголовка (add-priority-only-routing)."""
    rule = RoutingRule(
        event_type_id=None,
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
    groups = await crud.load_routing_rules()
    key = (routing_rule.event_type_id, routing_rule.priority)
    assert key in groups.by_type
    assert routing_rule.id in [r.id for r in groups.by_type[key]]
    assert groups.by_priority == {}


async def test_load_routing_rules_groups_rule_without_type_by_priority(
    session, routing_rule_by_priority
):
    crud = Bp5Crud(session)
    groups = await crud.load_routing_rules()
    assert routing_rule_by_priority.priority in groups.by_priority
    assert routing_rule_by_priority.id in [
        r.id for r in groups.by_priority[routing_rule_by_priority.priority]
    ]
    assert groups.by_type == {}


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

    assert inserted_again == []
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


async def test_insert_alerts_empty_list_returns_empty(session):
    crud = Bp5Crud(session)
    assert await crud.insert_alerts([]) == []


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
    mock_send_email,
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
    assert alert.status == AlertStatus.sent  # instant + email, отправка ок
    assert alert.sent_at is not None
    mock_send_email.assert_awaited_once()


async def test_matched_event_marks_failed_when_send_raises(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
    mock_send_email,
):
    mock_send_email.side_effect = RuntimeError('SMTP недоступен')

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
    assert alert.status == AlertStatus.failed
    assert alert.sent_at is None
    assert alert.error_message == 'SMTP недоступен'


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
        telegram_id=uuid4().int % 1_000_000_000,
        password_hash='test-hash',
    )
    u2 = User(
        full_name='Получатель Два',
        department_id=department.id,
        email=f'{uuid4().hex[:8]}@test.ru',
        telegram_id=uuid4().int % 1_000_000_000,
        password_hash='test-hash',
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


async def test_no_match_marks_checked_and_not_repicked(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
):
    """Ни тип, ни правило по приоритету не подошли — событие помечается
    проверенным и повторный прогон его не поднимает (openspec/changes/
    add-priority-only-routing, spec.md: 'Событие без распознанного типа
    при отсутствии правил по приоритету')."""
    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title='Обычная новость без триггеров',
    )
    first = await sync_alerts(session)
    await session.flush()
    assert first['alerts'] == 0

    crud = Bp5Crud(session)
    pending = await crud.select_pending_events()
    assert sc.id not in [e.id for e in pending]


# ============================================================================
#  sync_alerts — правила по приоритету (add-priority-only-routing)
# ============================================================================


async def test_priority_only_rule_matches_unrecognized_title(
    session,
    raw_item,
    competitor,
    category,
    department,
    routing_rule_by_priority,
    mock_send_email,
):
    """Заголовок не содержит ключевых слов ни одного типа, но правило по
    приоритету заведено — алерт всё равно создаётся, тип в журнале пуст."""
    sc = await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title='Заголовок без единого ключевого слова из справочника',
    )
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['matched'] == 0
    assert summary['alerts'] == 1
    alert = await session.scalar(
        select(Alert).where(Alert.showcase_event_id == sc.id)
    )
    assert alert is not None
    assert alert.event_type_id is None
    assert alert.status == AlertStatus.sent
    mock_send_email.assert_awaited_once()


async def test_typed_and_priority_rule_overlap_single_delivery(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
    mock_send_email,
):
    """Типовое правило и правило по приоритету с ТЕМ ЖЕ получателем и
    каналом — ровно одна доставка, в журнале запись с типом (типовое
    правило точнее объясняет срабатывание, см. pipeline.py::
    merge_rule_overlap)."""
    session.add(
        RoutingRule(
            event_type_id=None,
            priority=PriorityLevel.p1,
            user_id=routing_rule.user_id,
            channel_id=routing_rule.channel_id,
            mode=DeliveryMode.instant,
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
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['alerts'] == 1
    alert = await session.scalar(
        select(Alert).where(Alert.showcase_event_id == sc.id)
    )
    assert alert.event_type_id == event_type.id
    mock_send_email.assert_awaited_once()


async def test_typed_and_priority_rule_different_recipients_both_alert(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
    channel_telegram,
    mock_send_email,
    mock_send_telegram,
):
    """Наложение с РАЗНЫМИ получателями (typo и по приоритету) — по алерту
    на каждого, ничего не схлопывается."""
    other_user = User(
        full_name='Второй Получатель',
        department_id=department.id,
        email=f'{uuid4().hex[:8]}@test.ru',
        telegram_id=uuid4().int % 1_000_000_000,
        password_hash='test-hash',
    )
    session.add(other_user)
    await session.flush()
    session.add(
        RoutingRule(
            event_type_id=None,
            priority=PriorityLevel.p1,
            user_id=other_user.id,
            channel_id=channel_telegram.id,
            mode=DeliveryMode.instant,
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
    assert {a.user_id for a in alerts} == {routing_rule.user_id, other_user.id}


async def test_duplicate_priority_only_rule_rejected(session, user, channel):
    """Два правила БЕЗ типа с тем же (приоритет, канал, получатель) —
    частичный уникальный индекс uq_routing_rule_no_type_priority_channel_user
    отвергает дубль (обычный UNIQUE его бы не поймал: NULL != NULL)."""
    session.add(
        RoutingRule(
            event_type_id=None,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel.id,
            mode=DeliveryMode.instant,
        )
    )
    await session.flush()

    session.add(
        RoutingRule(
            event_type_id=None,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel.id,
            mode=DeliveryMode.digest,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


# ============================================================================
#  sync_alerts — канал telegram (зеркало email-тестов выше)
# ============================================================================


async def test_telegram_instant_creates_sent_alert(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    user,
    channel_telegram,
    mock_send_telegram,
):
    session.add(
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel_telegram.id,
            mode=DeliveryMode.instant,
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
    summary = await sync_alerts(session)
    await session.flush()

    assert summary['alerts'] == 1
    alert = await session.scalar(
        select(Alert).where(Alert.showcase_event_id == sc.id)
    )
    assert alert.status == AlertStatus.sent
    assert alert.sent_at is not None
    mock_send_telegram.assert_awaited_once()


async def test_telegram_send_failure_marks_failed(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    user,
    channel_telegram,
    mock_send_telegram,
):
    mock_send_telegram.side_effect = RuntimeError('Telegram API недоступен')
    session.add(
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel_telegram.id,
            mode=DeliveryMode.instant,
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
    assert alert.status == AlertStatus.failed
    assert alert.sent_at is None
    assert alert.error_message == 'Telegram API недоступен'


# ============================================================================
#  sync_alerts — адресация по settings.true_alerting
# ============================================================================


async def test_routing_uses_test_address_when_true_alerting_is_false(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
    user,
    channel_telegram,
    mock_send_email,
    mock_send_telegram,
    monkeypatch,
):
    monkeypatch.setattr(settings, 'true_alerting', False)
    monkeypatch.setattr(settings, 'test_email', 'sandbox@example.com')
    monkeypatch.setattr(settings, 'test_tg', 999999999)
    session.add(
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel_telegram.id,
            mode=DeliveryMode.instant,
        )
    )
    await session.flush()

    await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
    )
    await sync_alerts(session)
    await session.flush()

    email_to = mock_send_email.await_args.args[0]
    tg_chat_id = mock_send_telegram.await_args.args[0]
    assert email_to == 'sandbox@example.com'
    assert tg_chat_id == 999999999


async def test_routing_uses_real_recipient_when_true_alerting_is_true(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
    user,
    channel_telegram,
    mock_send_email,
    mock_send_telegram,
    monkeypatch,
):
    monkeypatch.setattr(settings, 'true_alerting', True)
    session.add(
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel_telegram.id,
            mode=DeliveryMode.instant,
        )
    )
    await session.flush()

    await make_showcase(
        session,
        raw_item,
        competitor,
        category,
        department,
        title=f'Новость про {event_type.keywords[0]}',
    )
    await sync_alerts(session)
    await session.flush()

    email_to = mock_send_email.await_args.args[0]
    tg_chat_id = mock_send_telegram.await_args.args[0]
    assert email_to == user.email
    assert tg_chat_id == user.telegram_id


# ============================================================================
#  sync_alerts(deliver=False) — режим сидера, сеть не трогается никогда
# ============================================================================


async def test_sync_alerts_deliver_false_marks_sent_without_network(
    session,
    raw_item,
    competitor,
    category,
    department,
    event_type,
    routing_rule,
    user,
    channel_telegram,
    mock_send_email,
    mock_send_telegram,
    monkeypatch,
):
    # true_alerting=True — если deliver=False не работал бы, это привело
    # бы к попытке реальной отправки на настоящие адреса юзера.
    monkeypatch.setattr(settings, 'true_alerting', True)
    session.add(
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel_telegram.id,
            mode=DeliveryMode.instant,
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
    summary = await sync_alerts(session, deliver=False)
    await session.flush()

    assert summary['alerts'] == 2  # email (routing_rule) + telegram
    mock_send_email.assert_not_awaited()
    mock_send_telegram.assert_not_awaited()

    alerts = (
        (
            await session.execute(
                select(Alert).where(Alert.showcase_event_id == sc.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) == 2
    assert all(a.status == AlertStatus.sent for a in alerts)
    assert all(a.sent_at is not None for a in alerts)
