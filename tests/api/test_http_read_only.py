"""HTTP-проверки read-only API этапов конвейера и кандидатов BP-7."""

from decimal import Decimal

from sqlalchemy import select

from core.enums import (
    AlertStatus,
    DeliveryMode,
    PriorityLevel,
    SourceCandidateStatus,
    UserRole,
)
from src.bp3.models import CategorizedEvent
from src.bp5.models import Alert, Channel
from src.bp7.models import SourceCandidate
from tests.api.test_action_items import make_showcase_event


async def test_pipeline_read_only_lists_and_details(
    client, session, users_by_role, auth_headers
):
    showcase = await make_showcase_event(session)
    raw_id = showcase.raw_item_id
    categorized_id = showcase.categorized_event_id
    categorized = await session.scalar(
        select(CategorizedEvent).where(CategorizedEvent.id == categorized_id)
    )
    normalized_id = categorized.normalized_item_id
    headers = auth_headers(users_by_role[UserRole.admin])

    for path, item_id in (
        ('/raw-items', raw_id),
        ('/normalized-items', normalized_id),
        ('/categorized-events', categorized_id),
    ):
        listed = await client.get(path, headers=headers)
        detail = await client.get(f'{path}/{item_id}', headers=headers)
        assert item_id in {item['id'] for item in listed.json()}
        assert detail.status_code == 200

    assert (
        await client.get(
            '/raw-items', headers=headers, params={'status': 'new'}
        )
    ).status_code == 200
    assert (
        await client.get(
            '/normalized-items', headers=headers, params={'title': 'Событие'}
        )
    ).status_code == 200
    assert (
        await client.get(
            '/categorized-events', headers=headers, params={'priority': 'p1'}
        )
    ).status_code == 200


async def test_alert_list_detail_and_filters(
    client, session, users_by_role, auth_headers
):
    showcase = await make_showcase_event(session, title='Alert HTTP event')
    channel = Channel(name='http-alert-channel')
    session.add(channel)
    await session.flush()
    user = users_by_role[UserRole.viewer]
    alert = Alert(
        showcase_event_id=showcase.id,
        event_type_id=None,
        priority=PriorityLevel.p1,
        user_id=user.id,
        channel_id=channel.id,
        mode=DeliveryMode.instant,
        status=AlertStatus.queued,
    )
    session.add(alert)
    await session.flush()
    headers = auth_headers(users_by_role[UserRole.admin])

    listed = await client.get(
        '/alerts',
        headers=headers,
        params={'status': 'queued', 'user_id': user.id, 'priority': 'p1'},
    )
    detail = await client.get(f'/alerts/{alert.id}', headers=headers)

    assert alert.id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200


async def test_source_candidates_are_read_only_and_filterable(
    client, session, users_by_role, auth_headers
):
    candidate = SourceCandidate(
        domain='http-api-candidate.example.com',
        score=Decimal('0.80'),
        status=SourceCandidateStatus.new,
    )
    session.add(candidate)
    await session.flush()
    headers = auth_headers(users_by_role[UserRole.analyst])
    listed = await client.get(
        '/source-candidates', headers=headers, params={'domain': 'candidate'}
    )
    detail = await client.get(
        f'/source-candidates/{candidate.id}', headers=headers
    )

    assert candidate.id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200
    assert (
        await client.post('/source-candidates', headers=headers, json={})
    ).status_code == 405
