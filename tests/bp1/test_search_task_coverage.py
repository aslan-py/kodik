"""Тесты автоматического покрытия задачами сбора BP-1."""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from src.bp1.models import Competitor, SearchTask, Source, Trigger
from src.bp1.search_task_coverage import sync_search_task_coverage
from src.bp3.modules import save_results_module
from src.bp7.models import SourceCandidate
from src.bp7.pipeline import SourceCandidatePromoter


def unique_name(prefix: str) -> str:
    return f'__coverage-{prefix}-{uuid4().hex}__'


async def test_sync_creates_only_active_pairs_and_is_idempotent(session):
    active_competitor = Competitor(name=unique_name('competitor-active'))
    inactive_competitor = Competitor(
        name=unique_name('competitor-inactive'), is_active=False
    )
    active_source = Source(name=unique_name('source-active'))
    inactive_source = Source(
        name=unique_name('source-inactive'), is_active=False
    )
    session.add_all(
        [
            active_competitor,
            inactive_competitor,
            active_source,
            inactive_source,
        ]
    )
    await session.flush()

    first_created = await sync_search_task_coverage(session)
    second_created = await sync_search_task_coverage(session)

    task = await session.scalar(
        select(SearchTask).where(
            SearchTask.competitor_id == active_competitor.id,
            SearchTask.source_id == active_source.id,
            SearchTask.trigger_id.is_(None),
        )
    )
    assert first_created >= 1
    assert second_created == 0
    assert task is not None
    assert task.is_active is True
    inactive_competitor_tasks = (
        await session.scalars(
            select(SearchTask).where(
                SearchTask.competitor_id == inactive_competitor.id
            )
        )
    ).all()
    inactive_source_tasks = (
        await session.scalars(
            select(SearchTask).where(SearchTask.source_id == inactive_source.id)
        )
    ).all()
    assert not inactive_competitor_tasks
    assert not inactive_source_tasks


async def test_trigger_task_does_not_cover_triggerless_pair(session):
    competitor = Competitor(name=unique_name('competitor-trigger'))
    source = Source(name=unique_name('source-trigger'))
    trigger = Trigger(keyword=unique_name('trigger'))
    session.add_all([competitor, source, trigger])
    await session.flush()
    session.add(
        SearchTask(
            competitor_id=competitor.id,
            source_id=source.id,
            trigger_id=trigger.id,
        )
    )
    await session.flush()

    await sync_search_task_coverage(session)

    tasks = (
        await session.scalars(
            select(SearchTask).where(
                SearchTask.competitor_id == competitor.id,
                SearchTask.source_id == source.id,
            )
        )
    ).all()
    assert {task.trigger_id for task in tasks} == {None, trigger.id}


async def test_inactive_task_is_preserved_as_existing_coverage(session):
    competitor = Competitor(name=unique_name('competitor-disabled'))
    source = Source(name=unique_name('source-disabled'))
    session.add_all([competitor, source])
    await session.flush()
    task = SearchTask(
        competitor_id=competitor.id,
        source_id=source.id,
        trigger_id=None,
        is_active=False,
    )
    session.add(task)
    await session.flush()
    task_id = task.id

    await sync_search_task_coverage(session)
    await sync_search_task_coverage(session)

    tasks = (
        await session.scalars(
            select(SearchTask).where(
                SearchTask.competitor_id == competitor.id,
                SearchTask.source_id == source.id,
                SearchTask.trigger_id.is_(None),
            )
        )
    ).all()
    assert [(item.id, item.is_active) for item in tasks] == [(task_id, False)]


async def test_new_source_gets_tasks_for_every_active_competitor(session):
    await sync_search_task_coverage(session)
    source = Source(name=unique_name('new-source'))
    session.add(source)
    await session.flush()

    created = await sync_search_task_coverage(session)
    active_competitors = await session.scalar(
        select(func.count())
        .select_from(Competitor)
        .where(Competitor.is_active.is_(True))
    )
    source_tasks = await session.scalar(
        select(func.count())
        .select_from(SearchTask)
        .where(
            SearchTask.source_id == source.id,
            SearchTask.trigger_id.is_(None),
        )
    )

    assert created == active_competitors
    assert source_tasks == active_competitors


async def test_new_competitor_gets_tasks_for_every_active_source(session):
    await sync_search_task_coverage(session)
    competitor = Competitor(name=unique_name('new-competitor'))
    session.add(competitor)
    await session.flush()

    created = await sync_search_task_coverage(session)
    active_sources = await session.scalar(
        select(func.count())
        .select_from(Source)
        .where(Source.is_active.is_(True))
    )
    competitor_tasks = await session.scalar(
        select(func.count())
        .select_from(SearchTask)
        .where(
            SearchTask.competitor_id == competitor.id,
            SearchTask.trigger_id.is_(None),
        )
    )

    assert created == active_sources
    assert competitor_tasks == active_sources


async def test_inactive_source_is_ignored_then_existing_task_resumes(session):
    competitor = Competitor(name=unique_name('toggle-competitor'))
    source = Source(name=unique_name('toggle-source'), is_active=False)
    session.add_all([competitor, source])
    await session.flush()

    await sync_search_task_coverage(session)
    task = await session.scalar(
        select(SearchTask).where(
            SearchTask.competitor_id == competitor.id,
            SearchTask.source_id == source.id,
            SearchTask.trigger_id.is_(None),
        )
    )
    assert task is None

    source.is_active = True
    await session.flush()
    await sync_search_task_coverage(session)
    task = await session.scalar(
        select(SearchTask).where(
            SearchTask.competitor_id == competitor.id,
            SearchTask.source_id == source.id,
            SearchTask.trigger_id.is_(None),
        )
    )
    assert task is not None
    assert task.is_active is True

    source.is_active = False
    await session.flush()
    assert await sync_search_task_coverage(session) == 0
    assert task.is_active is True

    source.is_active = True
    await session.flush()
    assert await sync_search_task_coverage(session) == 0


async def test_bp3_candidate_promoted_by_bp7_is_covered_by_bp1(
    session, monkeypatch
):
    competitor = Competitor(name=unique_name('promoted-competitor'))
    session.add(competitor)
    await session.flush()
    domain = unique_name('promoted-source')

    class ExistingSessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    async def flush_instead_of_commit():
        await session.flush()

    monkeypatch.setattr(
        save_results_module, 'AsyncSessionLocal', ExistingSessionContext
    )
    monkeypatch.setattr(session, 'commit', flush_instead_of_commit)
    await save_results_module._save(
        {},
        set(),
        {},
        {
            competitor.id: {
                'sources': [
                    {
                        'domain': domain,
                        'url': 'https://example.test/news',
                        'score': Decimal('0.99'),
                    }
                ]
            }
        },
    )
    candidate = await session.scalar(
        select(SourceCandidate).where(SourceCandidate.domain == domain)
    )

    promotion = await SourceCandidatePromoter(session).promote()
    created = await sync_search_task_coverage(session)
    source = await session.scalar(select(Source).where(Source.name == domain))
    task = await session.scalar(
        select(SearchTask).where(
            SearchTask.competitor_id == competitor.id,
            SearchTask.source_id == source.id,
            SearchTask.trigger_id.is_(None),
        )
    )

    assert promotion['promoted'] == 1
    assert candidate is not None
    assert created >= 1
    assert task is not None
