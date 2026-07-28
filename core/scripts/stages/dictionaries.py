"""Этап «справочники»: настроечные таблицы, на которых стоит весь конвейер.

Система data-driven — поведение задаётся данными справочников, а не кодом:
кого ищем (competitor), где (source), по каким словам (trigger), что
отсеиваем (black_domain, stop_word, topic_limit), какими категориями и
отделами размечаем (category, department), куда шлём алерты (event_type,
channel, routing_rule). Без них не запустится ни один этап пайплайна.

Запуск:
    python -m core.scripts.stages.dictionaries

ВНИМАНИЕ: clear() здесь сносит СНАЧАЛА все данные пайплайна, и только потом
сами справочники — иначе FK не дадут удалить конкурента, на которого
ссылается задача сбора. То есть это самая разрушительная очистка в проекте.

Регионы (1100+ строк) грузятся из src/bp2/files/cities.json.
"""

import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import DeliveryMode, PriorityLevel, StopType
from core.scripts.stages.cascade import (
    DICTIONARY_ORDER,
    PIPELINE_ORDER,
    clear_from,
)
from src.bp1.models import Competitor, Source, Trigger
from src.bp2.models import BlackDomain, Region, StopWord, TopicLimit
from src.bp3.models import Category, Department
from src.bp5.models import Channel, EventType, RoutingRule

PROJECT_ROOT = Path(__file__).parents[3]
CITIES_FILE = PROJECT_ROOT / 'src' / 'bp2' / 'files' / 'cities.json'

# Единственный источник демо — новостной агрегатор (его «парсим»).
# name источника = URL, откуда парсим (а не человекочитаемое имя).
# Импортируется этапом bp1 — там он нужен для search_task и raw_data.meta.
SOURCE_NAME = 'https://newssearch.yandex.ru'

# ============================================================================
#  Данные справочников
# ============================================================================

COMPETITORS = [
    {'name': 'Топ-Сервис'},
    {'name': 'МУП «Школьное питание»'},
    {'name': 'Виво Маркет'},
    {'name': 'Комбинат питания Иркутска'},
    {'name': 'Комбинат школьного питания Сургута'},
    {'name': 'Деп. продовольствия и соцпитания Казани'},
    {'name': 'Комбинат соц. питания «Охта»'},
    {'name': 'Мусороуборочная компания'},
    {'name': 'СКС'},
]

TRIGGERS = [
    {'keyword': 'школьное питание'},
    {'keyword': 'тендер'},
    {'keyword': 'прокуратура'},
]

# domain = полный ХОСТ как в ссылке, БЕЗ схемы (https://) и пути — именно
# так его отдаёт urlparse(items[].url).netloc, по которому идёт сверка в BP-2.
# С поддоменом, если публикатор сидит на поддомене (напр. spb.bezformata.com).
BLACK_DOMAINS = [
    {'domain': 'critics24.com', 'reason': 'Заказной/компрометирующий (Киев)'},
    {'domain': 'kompromat.ru', 'reason': 'Компрометирующий ресурс'},
]

STOP_WORDS = [
    {
        'phrase': 'гороскоп',
        'type': StopType.stop_topic,
        'note': 'Инфошум — не относится к деятельности конкурентов',
    },
    {
        'phrase': 'реклама',
        'type': StopType.stop_word,
        'note': 'Рекламные материалы',
    },
    {
        'phrase': 'бегемот в зоопарке',
        'type': StopType.false_positive,
        'note': 'Ложное срабатывание по конкуренту «Бегемот» (животное)',
    },
]

TOPIC_LIMITS = [
    {
        'scope': 'competitor',
        'max_count': 5,
        'window': 'week',
        'note': 'Один конкурент не должен занимать непропорц. долю за неделю',
    },
    {
        'scope': 'media',
        'max_count': 10,
        'window': 'week',
        'note': 'Одно СМИ не должно доминировать в выборке',
    },
]

CATEGORIES = [
    'надзорная санкция и юридический риск',
    'репутационный риск',
    'PR-активность конкурента',
    'системная проблема (возможность для входа)',
    'признание качества и конкурсы',
    'косвенное упоминание',
    'информационный шум',
]

DEPARTMENTS = ['PR', 'Тендеры', 'Юристы', 'Аналитика', 'Маркетинг']

EVENT_TYPES = [
    {
        'name': 'судебный/надзорный риск',
        'keywords': 'прокуратура, суд, иск, нарушения, надзор',
    },
    {
        'name': 'выигранный тендер',
        'keywords': 'тендер, контракт, закупка, аукцион',
    },
    {'name': 'активный наём', 'keywords': 'вакансия, наём, набор персонала'},
    {
        'name': 'расширение',
        'keywords': 'расширение, открытие, новый объект, реконструкция',
    },
    {
        'name': 'закрытие объекта',
        'keywords': 'закрытие, банкротство, ликвидация',
    },
]

CHANNELS = ['telegram', 'email']

# (тип события, приоритет, отдел, канал, режим доставки)
ROUTING = [
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Юристы',
        'telegram',
        DeliveryMode.instant,
    ),
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Юристы',
        'email',
        DeliveryMode.instant,
    ),
    (
        'выигранный тендер',
        PriorityLevel.p2,
        'Тендеры',
        'email',
        DeliveryMode.digest,
    ),
    ('расширение', PriorityLevel.p3, 'Аналитика', 'email', DeliveryMode.digest),
]


# ============================================================================
#  Хелперы
# ============================================================================


def make_aliases(name: str) -> list[str]:
    """Стандартные псевдонимы города в нижнем регистре."""
    n = name.lower()
    return list(dict.fromkeys([n, f'г. {n}', f'г {n}']))


def build_region_rows() -> list[dict]:
    """Строки справочника регионов из cities.json (без дублей по имени)."""
    with open(CITIES_FILE, encoding='utf-8') as f:
        cities = json.load(f)

    seen: set[str] = set()
    rows: list[dict] = []
    for city in cities:
        name = city['name']
        if name in seen:
            continue
        seen.add(name)
        coords = city.get('coords') or {}
        lat, lon = coords.get('lat'), coords.get('lon')
        # Псевдонимы из файла дополняем стандартными «г. X» / «г X».
        aliases = list(
            dict.fromkeys(city.get('aliases', []) + make_aliases(name))
        )
        rows.append(
            {
                'name_display': name,
                'name_aliases': aliases,
                'macro_region': city.get('district'),
                'latitude': float(lat) if lat else None,
                'longitude': float(lon) if lon else None,
            }
        )
    return rows


async def _insert(session: AsyncSession, model, rows, *unique_cols) -> int:
    """Вставить строки справочника, вернуть число реально вставленных.

    unique_cols — натуральный ключ справочника: по нему ON CONFLICT DO NOTHING
    гасит повторы, и скрипт можно перезапускать. Если ключа нет (topic_limit,
    routing_rule) — колонки не передаются и делается обычный INSERT; от дублей
    там защищает count-guard на стороне вызова.
    """
    if not rows:
        return 0
    stmt = insert(model).values(rows)
    if unique_cols:
        stmt = stmt.on_conflict_do_nothing(index_elements=list(unique_cols))
    result = await session.execute(stmt)
    return result.rowcount


async def _is_empty(session: AsyncSession, model) -> bool:
    """В таблице нет ни одной строки."""
    return await session.scalar(select(model.id).limit(1)) is None


async def _name_to_id(session: AsyncSession, model) -> dict[str, int]:
    """{name: id} справочника — для резолва связей routing_rule."""
    rows = await session.execute(select(model.name, model.id))
    return dict(rows.all())


# ============================================================================
#  Этап
# ============================================================================


async def seed(session: AsyncSession) -> int:
    """Залить все справочники. Идемпотентно: повторный запуск дублей не даст.

    Справочники с натуральным UNIQUE идут через ON CONFLICT DO NOTHING.
    Для topic_limit и routing_rule такого ключа нет (правило описывается
    набором полей, а не именем), поэтому они защищены count-guard'ом:
    заливаем только в пустую таблицу.
    """
    added = 0
    added += await _insert(session, Region, build_region_rows(), 'name_display')
    added += await _insert(session, Competitor, COMPETITORS, 'name')
    added += await _insert(session, Source, [{'name': SOURCE_NAME}], 'name')
    added += await _insert(session, Trigger, TRIGGERS, 'keyword')
    added += await _insert(session, BlackDomain, BLACK_DOMAINS, 'domain')
    added += await _insert(session, StopWord, STOP_WORDS, 'phrase', 'type')
    added += await _insert(
        session, Category, [{'name': n} for n in CATEGORIES], 'name'
    )
    added += await _insert(
        session, Department, [{'name': n} for n in DEPARTMENTS], 'name'
    )
    added += await _insert(session, EventType, EVENT_TYPES, 'name')
    added += await _insert(
        session, Channel, [{'name': n} for n in CHANNELS], 'name'
    )

    # --- без натурального UNIQUE: заливаем только в пустую таблицу ---
    if await _is_empty(session, TopicLimit):
        added += await _insert(session, TopicLimit, TOPIC_LIMITS)
    await session.flush()

    if await _is_empty(session, RoutingRule):
        etype = await _name_to_id(session, EventType)
        channel = await _name_to_id(session, Channel)
        dept = await _name_to_id(session, Department)
        session.add_all(
            RoutingRule(
                event_type_id=etype[etype_name],
                priority=priority,
                department_id=dept[dep_name],
                channel_id=channel[chan_name],
                mode=mode,
            )
            for etype_name, priority, dep_name, chan_name, mode in ROUTING
        )
        added += len(ROUTING)
    await session.flush()
    return added


async def clear(session: AsyncSession) -> int:
    """Снести справочники — вместе со ВСЕМИ данными пайплайна.

    Порядок обязателен: данные ссылаются на справочники через FK RESTRICT,
    поэтому сначала уходит весь пайплайн (PIPELINE_ORDER целиком), и только
    затем сами справочники в порядке DICTIONARY_ORDER.
    """
    total = await clear_from(session, PIPELINE_ORDER[-1])
    for model in DICTIONARY_ORDER:
        result = await session.execute(delete(model))
        total += result.rowcount
    return total


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('справочники', clear, seed)
