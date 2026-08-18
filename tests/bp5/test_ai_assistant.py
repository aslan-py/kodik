"""Тесты AI-ассистента BP-6 (src/bp5/ai_assistant.py).

DeepSeek-вызов (_ask_deepseek) мокается (autouse) — тесты не должны
стучаться в реальный DeepSeek, тот же приём, что и mock_send_email в
tests/bp5/test_crud.py. Фикстуры цепочки до витрины скопированы оттуда же
(competitor/source/raw_item/category/department/user/make_showcase) —
в проекте фикстуры BP-тестов не централизуются в conftest, каждый файл
самодостаточен (см. tests/bp5/test_crud.py, tests/bp5/test_pipeline.py).
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from core.enums import (
    ActionStatus,
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
from src.bp5.ai_assistant import DEFAULT_TASK_TEMPLATE, generate_action_items
from src.bp5.models import Alert, Channel, EventType, User
from src.bp6.models import ActionItem


@pytest.fixture(autouse=True)
def mock_ask_deepseek(monkeypatch):
    mock = AsyncMock(return_value='Тестовый результат')
    monkeypatch.setattr('src.bp5.ai_assistant._ask_deepseek', mock)
    return mock


# ============================================================================
#  Фикстуры — цепочка до витрины + справочники (см. tests/bp5/test_crud.py)
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
async def event_type(session):
    et = EventType(name=f'__тест-тип-{uuid4().hex[:8]}__', keywords=['x'])
    session.add(et)
    await session.flush()
    return et


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


async def make_showcase(
    session,
    raw_item,
    competitor,
    category,
    department,
    *,
    title,
    priority=PriorityLevel.p1,
    action=None,
    deadline=None,
):
    """Полная цепочка normalized_item -> categorized_event -> showcase_event
    (см. tests/bp5/test_crud.py::make_showcase — тот же контракт полей).

    action/deadline — то, что в проде определяет BP-3 (сейчас заглушка,
    в конечном счёте LLM-агент) и что ai_assistant переиспользует как есть
    для task/deadline, не генерируя их заново."""
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
        action=action,
        deadline=deadline,
    )
    session.add(sc)
    await session.flush()
    return sc


async def make_alert(
    session,
    *,
    showcase_event,
    event_type,
    user,
    channel,
    priority=PriorityLevel.p1,
    mode=DeliveryMode.instant,
    status=AlertStatus.sent,
):
    alert = Alert(
        showcase_event_id=showcase_event.id,
        event_type_id=event_type.id,
        priority=priority,
        user_id=user.id,
        channel_id=channel.id,
        mode=mode,
        status=status,
        sent_at=datetime.now(UTC) if status == AlertStatus.sent else None,
    )
    session.add(alert)
    await session.flush()
    return alert


# ============================================================================
#  generate_action_items
# ============================================================================


class TestGenerateActionItems:
    async def test_creates_item_from_queued_digest_alert(
        self,
        session,
        raw_item,
        competitor,
        category,
        department,
        channel,
        event_type,
        user,
    ):
        """Ключевой сценарий из обсуждения: П2/digest-алерт НИКОГДА не
        доходит до status=sent (нет джобы-сводки) — триггер должен
        сработать всё равно, по самому факту существования alert.
        task/deadline переиспользуются из showcase_event (BP-3), не
        генерируются DeepSeek заново."""
        event = await make_showcase(
            session,
            raw_item,
            competitor,
            category,
            department,
            title='Событие П2',
            priority=PriorityLevel.p2,
            action='Согласовать позицию с юристами',
            deadline=date(2026, 7, 1),
        )
        await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=user,
            channel=channel,
            priority=PriorityLevel.p2,
            mode=DeliveryMode.digest,
            status=AlertStatus.queued,
        )

        await generate_action_items(session)

        item = await session.scalar(
            select(ActionItem).where(ActionItem.showcase_event_id == event.id)
        )
        assert item is not None
        assert item.assigned_user_id == user.id
        assert item.department_id == department.id
        assert item.task == 'Согласовать позицию с юристами'
        assert item.deadline == date(2026, 7, 1)
        assert item.expected_result == 'Тестовый результат'

    async def test_event_without_alerts_is_skipped(
        self, session, raw_item, competitor, category, department
    ):
        event = await make_showcase(
            session,
            raw_item,
            competitor,
            category,
            department,
            title='Без алертов',
        )

        await generate_action_items(session)

        item = await session.scalar(
            select(ActionItem).where(ActionItem.showcase_event_id == event.id)
        )
        assert item is None

    async def test_existing_action_item_not_duplicated(
        self,
        session,
        raw_item,
        competitor,
        category,
        department,
        channel,
        event_type,
        user,
    ):
        event = await make_showcase(
            session,
            raw_item,
            competitor,
            category,
            department,
            title='Уже есть задача',
        )
        await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=user,
            channel=channel,
        )
        session.add(
            ActionItem(
                showcase_event_id=event.id,
                task='Ранее заведённая задача',
                department_id=department.id,
                status=ActionStatus.open,
            )
        )
        await session.flush()

        await generate_action_items(session)

        items = (
            (
                await session.execute(
                    select(ActionItem).where(
                        ActionItem.showcase_event_id == event.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(items) == 1
        assert items[0].task == 'Ранее заведённая задача'

    async def test_priority_p3_event_is_still_processed(
        self,
        session,
        raw_item,
        competitor,
        category,
        department,
        channel,
        event_type,
        user,
    ):
        """Приоритет больше не фильтруется в ai_assistant — значимость уже
        решена самим фактом наличия alert (routing_rule сработал), П3/П4
        не исключение."""
        event = await make_showcase(
            session,
            raw_item,
            competitor,
            category,
            department,
            title='Событие П3',
            priority=PriorityLevel.p3,
        )
        await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=user,
            channel=channel,
            priority=PriorityLevel.p3,
        )

        await generate_action_items(session)

        item = await session.scalar(
            select(ActionItem).where(ActionItem.showcase_event_id == event.id)
        )
        assert item is not None

    async def test_missing_action_falls_back_to_default_task(
        self,
        session,
        raw_item,
        competitor,
        category,
        department,
        channel,
        event_type,
        user,
    ):
        """Если BP-3 (сейчас заглушка) не заполнил action — task берёт
        тот же фолбэк, что и сидер core/scripts/stages/bp6.py."""
        event = await make_showcase(
            session,
            raw_item,
            competitor,
            category,
            department,
            title='Событие без action',
        )
        await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=user,
            channel=channel,
        )

        await generate_action_items(session)

        item = await session.scalar(
            select(ActionItem).where(ActionItem.showcase_event_id == event.id)
        )
        assert item.task == DEFAULT_TASK_TEMPLATE.format(title=event.title)
        assert item.deadline is None

    async def test_user_without_department_is_skipped(
        self,
        session,
        raw_item,
        competitor,
        category,
        department,
        channel,
        event_type,
    ):
        orphan_user = User(
            full_name='Без отдела',
            department_id=None,
            email=f'{uuid4().hex[:8]}@test.ru',
            telegram_id=uuid4().int % 1_000_000_000,
            password_hash='test-hash',
        )
        session.add(orphan_user)
        await session.flush()

        event = await make_showcase(
            session, raw_item, competitor, category, department, title='X'
        )
        await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=orphan_user,
            channel=channel,
        )

        await generate_action_items(session)

        item = await session.scalar(
            select(ActionItem).where(ActionItem.showcase_event_id == event.id)
        )
        assert item is None

    async def test_earliest_alert_wins_when_multiple_recipients(
        self,
        session,
        raw_item,
        competitor,
        category,
        department,
        channel,
        event_type,
        user,
    ):
        other_department = Department(name=f'__тест-отдел2-{uuid4().hex[:8]}__')
        session.add(other_department)
        await session.flush()
        other_user = User(
            full_name='Другой пользователь',
            department_id=other_department.id,
            email=f'{uuid4().hex[:8]}@test.ru',
            telegram_id=uuid4().int % 1_000_000_000,
            password_hash='test-hash',
        )
        session.add(other_user)
        await session.flush()

        event = await make_showcase(
            session, raw_item, competitor, category, department, title='X'
        )
        first_alert = await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=user,
            channel=channel,
        )
        await make_alert(
            session,
            showcase_event=event,
            event_type=event_type,
            user=other_user,
            channel=channel,
        )
        assert first_alert.id  # первый вставленный = меньший id

        await generate_action_items(session)

        item = await session.scalar(
            select(ActionItem).where(ActionItem.showcase_event_id == event.id)
        )
        assert item.assigned_user_id == user.id
        assert item.department_id == department.id
