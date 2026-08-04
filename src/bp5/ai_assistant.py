"""AI-ассистент BP-6: авто-создание action_item из алертов BP-5.

Изолированный модуль — НЕ трогает src/bp5/pipeline.py и src/bp5/crud.py,
только читает их результат (Alert). Коллега параллельно пишет свою версию
этого же модуля — весь код нарочно самодостаточен в одном файле.

Триггер — сам факт существования строки `alert` для события (ЛЮБОЙ
status/mode), а не `status == sent`. Причины:
  1. digest-режим (mode=digest, сейчас это П2) в sync_alerts никогда не
     доходит до sent — шаг 5.5 в pipeline.py доставляет только instant,
     digest-строки остаются queued навсегда (джоба-сводка, которая
     собирала бы их раз в неделю, ещё не написана — независимый от этого
     модуля пробел BP-5). Если бы триггер требовал sent, для П2 задачи
     никогда бы не создавались.
  2. instant/digest — это данные (routing_rule.mode), не хардкод в коде;
     успешность реальной доставки письма/telegram — вопрос SMTP/API,
     отдельный от того, нужна ли человеку задача.

task/deadline НЕ генерируются заново — берутся готовыми из showcase_event
(BP-3 их уже определил: сейчас скрипт-заглушка, в проде — LLM-агент,
но контракт поля `action`/`deadline` тот же, см. src/bp4/models.py). Тот
же приём, что и в сидере core/scripts/stages/bp6.py (`task=event.action or
f'Отработать событие: {title}'`). DeepSeek здесь дозаписывает только
`expected_result` — единственное, что реально требует интерпретации
события, а не дублирования того, что BP-3 уже посчитал.

Упрощение MVP: если событие разошлось алертами в НЕСКОЛЬКО разных
отделов/пользователей, заводится только ОДНА задача — по самому раннему
(меньший Alert.id) алерту. Это осознанное упрощение, не то, что диктует
ТЗ («задача → отдел» без уточнения множественной маршрутизации).

Запуск:
    python -m src.bp5.ai_assistant
"""

import json
import logging
from collections.abc import Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Регистрирует ВСЕ модели в Base.metadata: без этого SQLAlchemy не резолвит
# FK на таблицы модулей, которые этот файл не импортирует напрямую (здесь —
# 'department', на который ссылается ActionItem.department_id), и flush
# падает с NoReferencedTableError. Тот же приём в api/main.py, alembic/env.py.
import src.db_registry  # noqa: F401
from core.config import settings
from core.database import AsyncSessionLocal
from core.enums import ActionStatus
from src.bp4.models import ShowcaseEvent
from src.bp5.models import Alert, User
from src.bp6.models import ActionItem

logger = logging.getLogger(__name__)

# ============================================================================
#  Промпты DeepSeek — правьте текст здесь, логику вызова ниже трогать не надо
# ============================================================================

SYSTEM_PROMPT = (
    'Ты помощник аналитика конкурентной разведки. По событию витрины и уже '
    'поставленной задаче сформулируй ожидаемый результат — измеримый итог, '
    'по которому понятно, что задача закрыта. Верни СТРОГО JSON без '
    'пояснений вне него: {"expected_result": "..."}. Пиши по-русски, '
    '1-2 предложения, конкретно и измеримо.'
)

USER_PROMPT_TEMPLATE = (
    'Событие: {title}\n'
    'Приоритет: {priority}\n'
    'Категория: {category}\n'
    'Регион: {region}\n'
    'Конкурент/объект: {competitor}\n'
    'Задача: {task}\n'
    'Комментарий аналитика: {comment}'
)

# Фолбэк, если BP-3 не определил action — тот же текст, что и в сидере
# core/scripts/stages/bp6.py, чтобы поведение не разъезжалось.
DEFAULT_TASK_TEMPLATE = 'Отработать событие: {title}'


# ============================================================================
#  DeepSeek-клиент
# ============================================================================


async def _ask_deepseek(event: ShowcaseEvent, task: str) -> str:
    """Просит DeepSeek сгенерировать expected_result по событию и уже
    определённой задаче (task = event.action или фолбэк, см.
    generate_action_items — DeepSeek её не придумывает заново).

    Бросает исключение при сетевой ошибке/невалидном JSON — вызывающий
    код (generate_action_items) ловит и пропускает событие в этом прогоне
    (идемпотентность по showcase_event_id позволяет спокойно повторить
    попытку в следующем прогоне).
    """
    user_content = USER_PROMPT_TEMPLATE.format(
        title=event.title,
        priority=event.priority,
        category=event.category,
        region=event.region or '—',
        competitor=event.competitor or '—',
        task=task,
        comment=event.comment or '—',
    )
    async with httpx.AsyncClient(base_url=settings.deepseek_base_url) as client:
        response = await client.post(
            '/chat/completions',
            headers={'Authorization': f'Bearer {settings.deepseek_token}'},
            json={
                'model': settings.deepseek_model,
                'response_format': {'type': 'json_object'},
                'temperature': 0.3,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_content},
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)['expected_result']


# ============================================================================
#  Отбор кандидатов
# ============================================================================


async def _select_candidate_alerts(session: AsyncSession) -> Sequence[Alert]:
    """Самый ранний Alert (любой status/mode) на каждое событие, для
    которого ещё нет action_item.

    Один SELECT на все alert кандидатов (не N+1) — сортировка по id
    гарантирует, что первое вхождение showcase_event_id в Python-цикле
    ниже (generate_action_items) окажется самым ранним алертом.
    """
    existing = select(ActionItem.showcase_event_id)
    stmt = (
        select(Alert)
        .where(Alert.showcase_event_id.not_in(existing))
        .order_by(Alert.id.asc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def generate_action_items(session: AsyncSession) -> dict:
    """Создать action_item по событиям, уже прошедшим маршрутизацию BP-5.

    Без commit — для встраивания в чужую транзакцию/тесты (по образцу
    sync_alerts, src/bp5/pipeline.py).
    """
    alerts = await _select_candidate_alerts(session)

    first_alert_by_event: dict[int, Alert] = {}
    for alert in alerts:
        first_alert_by_event.setdefault(alert.showcase_event_id, alert)

    if not first_alert_by_event:
        return {'candidates': 0, 'created': 0, 'skipped': 0}

    event_ids = list(first_alert_by_event.keys())
    events = {
        e.id: e
        for e in (
            await session.execute(
                select(ShowcaseEvent).where(ShowcaseEvent.id.in_(event_ids))
            )
        ).scalars()
    }
    user_ids = {a.user_id for a in first_alert_by_event.values()}
    users = {
        u.id: u
        for u in (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars()
    }

    created = 0
    skipped = 0
    for event_id, alert in first_alert_by_event.items():
        event = events.get(event_id)
        if event is None:
            skipped += 1
            continue

        user = users.get(alert.user_id)
        if user is None or user.department_id is None:
            logger.warning(
                'AI-ассистент: пропуск showcase_event_id=%s — у пользователя '
                'user_id=%s нет department_id',
                event_id,
                alert.user_id,
            )
            skipped += 1
            continue

        task = event.action or DEFAULT_TASK_TEMPLATE.format(title=event.title)

        try:
            expected_result = await _ask_deepseek(event, task)
        except Exception:
            logger.exception(
                'AI-ассистент: не удалось сгенерировать expected_result для '
                'showcase_event_id=%s, пропуск (повторится в след. прогоне)',
                event_id,
            )
            skipped += 1
            continue

        session.add(
            ActionItem(
                showcase_event_id=event_id,
                task=task,
                department_id=user.department_id,
                assigned_user_id=user.id,
                deadline=event.deadline,
                expected_result=expected_result,
                status=ActionStatus.open,
            )
        )
        created += 1

    await session.flush()
    return {
        'candidates': len(first_alert_by_event),
        'created': created,
        'skipped': skipped,
    }


async def run_ai_assistant() -> dict:
    """Самостоятельный прогон со своей сессией и commit — по образцу
    run_bp5 (src/bp5/pipeline.py)."""
    async with AsyncSessionLocal() as session:
        summary = await generate_action_items(session)
        await session.commit()
        return summary


if __name__ == '__main__':
    import asyncio

    print(asyncio.run(run_ai_assistant()))
