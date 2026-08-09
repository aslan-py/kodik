"""Узкий сидер справочников под сквозную ручную проверку пайплайна.

В отличие от `core/scripts/stages/dictionaries.py` (полный демо-набор
справочников — десятки конкурентов, категорий, пользователей), этот
скрипт заливает ФИКСИРОВАННЫЙ узкий набор, согласованный с шестью
новостями заглушки этапа 1 (`core/scripts/stages/bp1_stub.py`):

- один конкурент («ДатаСинтез») и один источник (переиспользует
  `SOURCE_NAME` из `dictionaries.py`);
- чёрный домен под новость №2, стоп-слово «промокод» под новость №3,
  лимит антишума (`scope=media, max_count=1`) под новости №4-6;
- два канала доставки (email, telegram), один тип значимого события
  (ловит новость №1 по слову «прокуратура») и один тестовый
  пользователь-получатель с маршрутизацией на П1 в оба канала.

При каждом запуске (в т.ч. повторном) сначала сносит весь пайплайн
(FK RESTRICT не даст удалить конкурента/источник, на которые ссылается
`search_task`), затем управляемые этим скриптом справочники, и
заливает их заново — идемпотентно, как остальные сидеры проекта.

ВНИМАНИЕ: сносит ВСЕХ конкурентов/источники — рассчитан на то, что в
БД к моменту запуска нет других конкурентов/источников, кроме залитых
им самим. Не трогает `Category`/`Department`/`Region` — они приходят
из `dictionaries.py` (запускать до этого скрипта).

Порядок использования: полная очистка БД → `dictionaries.py` → этот
скрипт → `bp1_stub.py` → пайплайн через админку начиная с этапа 1.

Запуск:
    python -m core.scripts.stages.simple_dictionaries
"""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import hash_password
from core.enums import (
    DeliveryMode,
    LimitScope,
    LimitWindow,
    PriorityLevel,
    StopType,
)
from core.scripts.stages.cascade import PIPELINE_ORDER, clear_from
from core.scripts.stages.dictionaries import DEMO_USER_PASSWORD, SOURCE_NAME
from src.bp1.models import Competitor, Source
from src.bp2.models import BlackDomain, StopWord, TopicLimit
from src.bp5.models import Channel, EventType, RoutingRule, User

COMPETITOR_NAME = 'ДатаСинтез'
BLACK_DOMAIN = 'compromat-test.ru'  # под новость №2
STOP_PHRASE = 'промокод'  # под новость №3
EVENT_TYPE_NAME = 'судебный/надзорный риск'  # по образцу demo BP-5
EVENT_TYPE_KEYWORDS = ['прокуратура']  # под новость №1
CHANNEL_NAMES = ['email', 'telegram']

# telegram_id — числовая заглушка для NOT NULL/unique в БД, не пересекается
# с демо-пользователями dictionaries.py (100000001-100000003).
TEST_USER = {
    'full_name': 'Тестовый Получатель',
    'email': 'test-recipient@kodik.example',
    'telegram_id': 900000001,
}

# Порядок удаления управляемых справочников: дети → родители (FK RESTRICT).
MANAGED_ORDER = (
    RoutingRule,
    User,
    EventType,
    Channel,
    TopicLimit,
    StopWord,
    BlackDomain,
    Source,
    Competitor,
)


async def seed(session: AsyncSession) -> int:
    """Залить узкий набор справочников под тестовый сценарий bp1_stub."""
    competitor = Competitor(name=COMPETITOR_NAME)
    source = Source(name=SOURCE_NAME)
    black_domain = BlackDomain(
        domain=BLACK_DOMAIN,
        reason='Тестовый чёрный домен под новость №2 (simple_dictionaries)',
    )
    stop_word = StopWord(
        phrase=STOP_PHRASE,
        type=StopType.stop_word,
        note='Тестовое стоп-слово под новость №3 (simple_dictionaries)',
    )
    topic_limit = TopicLimit(
        scope=LimitScope.media,
        max_count=1,
        window=LimitWindow.run,
        note='Тестовый лимит антишума под новости №4-6 (simple_dictionaries)',
    )
    event_type = EventType(name=EVENT_TYPE_NAME, keywords=EVENT_TYPE_KEYWORDS)
    channels = [Channel(name=name) for name in CHANNEL_NAMES]
    session.add_all(
        [
            competitor,
            source,
            black_domain,
            stop_word,
            topic_limit,
            event_type,
            *channels,
        ]
    )
    await session.flush()

    user = User(
        full_name=TEST_USER['full_name'],
        department_id=None,
        email=TEST_USER['email'],
        telegram_id=TEST_USER['telegram_id'],
        password_hash=hash_password(DEMO_USER_PASSWORD),
    )
    session.add(user)
    await session.flush()

    channel_by_name = {c.name: c.id for c in channels}
    routing_rules = [
        RoutingRule(
            event_type_id=event_type.id,
            priority=PriorityLevel.p1,
            user_id=user.id,
            channel_id=channel_by_name[name],
            mode=DeliveryMode.instant,
        )
        for name in CHANNEL_NAMES
    ]
    session.add_all(routing_rules)
    await session.flush()

    return 6 + len(channels) + 1 + len(routing_rules)


async def clear(session: AsyncSession) -> int:
    """Снести справочники simple_dictionaries вместе со всем пайплайном.

    Сначала весь пайплайн (FK RESTRICT не даст удалить конкурента/
    источник, на которые ссылается search_task), затем управляемые этим
    скриптом справочники в порядке MANAGED_ORDER (дети → родители).
    """
    total = await clear_from(session, PIPELINE_ORDER[-1])
    for model in MANAGED_ORDER:
        result = await session.execute(delete(model))
        total += result.rowcount
    return total


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('simple_dictionaries (тестовые справочники)', clear, seed)
