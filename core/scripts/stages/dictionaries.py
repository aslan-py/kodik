"""Этап «справочники»: настроечные таблицы, на которых стоит весь конвейер.

Система data-driven — поведение задаётся данными справочников, а не кодом:
кого ищем (competitor), где (source), по каким словам (trigger), что
отсеиваем (black_domain, stop_word, topic_limit), какими категориями и
отделами размечаем (category, department), кому и куда шлём алерты
(event_type, channel, user, routing_rule). Без них не запустится ни один
этап пайплайна.

Запуск:
    python -m core.scripts.stages.dictionaries

ВНИМАНИЕ: clear() здесь сносит СНАЧАЛА все данные пайплайна, и только потом
сами справочники — иначе FK не дадут удалить конкурента, на которого
ссылается задача сбора. То есть это самая разрушительная очистка в проекте.

Регионы (1100+ строк) грузятся из core/scripts/scripts_data/cities.json.
Список конкурентов не дублируется руками — он выводится из демо-набора
новостей (core/scripts/stages/news_data.py): кого упоминает CSV, тот и
попадает в справочник.
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
from core.scripts.stages.news_data import NEWS
from src.bp1.models import Competitor, Source, Trigger
from src.bp2.models import BlackDomain, Region, StopWord, TopicLimit
from src.bp3.models import Category, Department
from src.bp5.models import Channel, EventType, RoutingRule, User

SCRIPTS_DATA = Path(__file__).parents[1] / 'scripts_data'
CITIES_FILE = SCRIPTS_DATA / 'cities.json'

# Единственный источник демо — новостной агрегатор (его «парсим»).
# name источника = URL, откуда парсим (а не человекочитаемое имя).
# Импортируется этапом bp1 — там он нужен для search_task и raw_data.meta.
SOURCE_NAME = 'https://newssearch.yandex.ru'

# ============================================================================
#  Данные справочников
# ============================================================================

# Кого отслеживаем — разработчики LLM/ML-продуктов из демо-набора новостей.
# Список НЕ дублируется руками: имена берутся из CSV в порядке первого
# упоминания, поэтому новая компания в новостях сама попадает в справочник.
COMPETITORS = [
    {'name': name} for name in dict.fromkeys(news.competitor for news in NEWS)
]

TRIGGERS = [
    {'keyword': 'искусственный интеллект'},
    {'keyword': 'языковая модель'},
    {'keyword': 'утечка данных'},
    {'keyword': 'тендер'},
]

# domain = полный ХОСТ как в ссылке, БЕЗ схемы (https://) и пути — именно
# так его отдаёт urlparse(items[].url).netloc, по которому идёт сверка в BP-2.
# С поддоменом, если публикатор сидит на поддомене (напр. spb.bezformata.com).
BLACK_DOMAINS = [
    {
        'domain': 'insider-leaks.info',
        'reason': 'Анонимный слив без проверяемых источников',
    },
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
        'phrase': 'скидка',
        'type': StopType.stop_word,
        'note': 'Промо-рассылки и продающие тексты',
    },
    {
        'phrase': 'крейсер',
        'type': StopType.false_positive,
        'note': 'Ложное срабатывание по конкуренту «Аврора Интеллект»',
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
    {
        'name': 'надзорная санкция и юридический риск',
        'note': (
            'Любое действие госорганов (проверка, предписание, штраф, иск, '
            'блокировка сервисов) или судебное разбирательство, которое '
            'создаёт материальные финансовые потери или угрозу остановки/'
            'изменения бизнес-модели конкурента.'
        ),
    },
    {
        'name': 'репутационный риск',
        'note': (
            'Информационный инцидент, который не имеет прямого юридического '
            'или финансового исчисления на данный момент, но снижает доверие '
            'стейкхолдеров (клиентов, партнёров, инвесторов) к бренду, '
            'угрожая будущему оттоку аудитории.'
        ),
    },
    {
        'name': 'PR-активность конкурента',
        'note': (
            'Целенаправленные публичные действия конкурента по формированию '
            'позитивного имиджа, не связанные с выходом нового продукта. '
            'Это «продажа воздуха»: спикерство на форумах, спонсорство, '
            'ESG-отчёты, наймы звёздных менеджеров.'
        ),
    },
    {
        'name': 'системная проблема (возможность для входа)',
        'note': (
            'Повторяющиеся (2+ раза за период) жалобы клиентов или '
            'экспертов на функциональные/технические сбои или неудобство '
            'сервиса конкурента, которые он не может или не хочет исправить.'
        ),
    },
    {
        'name': 'признание качества и конкурсы',
        'note': (
            'Объективная фиксация успеха через внешние авторитетные '
            'источники (например, рейтинги агентств), победа в отраслевых '
            'премиях, получение патентов, положительная экспертиза от '
            'лидеров мнений.'
        ),
    },
    {
        'name': 'косвенное упоминание',
        'note': (
            'Новость, где конкурент не является главным субъектом '
            '(упоминается в одном абзаце или списке), но контекст важен '
            'для понимания трендов (например, упоминание в законе, отчёте '
            'ЦБ, в новости о партнёре конкурента).'
        ),
    },
    {
        'name': 'информационный шум',
        'note': (
            'Фоновые, малозначимые новости без конкретики и последствий. '
            'Перепечатки старых материалов, формальные отчёты по GAAP/МСФО '
            '(без отклонений), смена второстепенных менеджеров средней '
            'руки, общие слова о «цифровизации».'
        ),
    },
]

DEPARTMENTS = [
    {
        'name': 'Юристы',
        'note': 'Держат санкции и иски.',
    },
    {
        'name': 'PR',
        'note': 'Держат имиджевые риски и активность конкурентов в медиа.',
    },
    {
        'name': 'Аналитика',
        'note': (
            'Держит рыночные возможности (системные сбои) и тренды '
            '(косвенные упоминания).'
        ),
    },
    {
        'name': 'Маркетинг',
        'note': (
            'Держит успехи конкурентов (признание) и корректирует свою '
            'коммуникацию.'
        ),
    },
]

# keywords ищутся как ПОДСТРОКА заголовка (detect_event_type, BP-5), поэтому
# коротких форм вроде «иск» здесь нет: они срабатывали бы на «риск», «поиск».
EVENT_TYPES = [
    {
        'name': 'судебный/надзорный риск',
        'keywords': [
            'прокуратура',
            'роскомнадзор',
            'фас ',
            'штраф',
            'предписание',
            'суд ',
        ],
    },
    {
        'name': 'выигранный тендер',
        'keywords': ['тендер', 'контракт', 'закупка', 'аукцион'],
    },
    {
        'name': 'активный наём',
        'keywords': ['вакансия', 'наём', 'набор ', 'стажировк'],
    },
    {
        'name': 'расширение',
        'keywords': [
            'центр разработки',
            'расширение',
            'новый офис',
            'дата-центр',
        ],
    },
    {
        'name': 'уход с рынка',
        'keywords': ['закрытие', 'банкротство', 'ликвидация', 'уход с рынка'],
    },
]

CHANNELS = ['telegram', 'email']

# Получатели алертов — конкретные люди, не абстрактный «отдел». department —
# справочно (в каком отделе числится), резолвится в department_id при
# заливке. email/telegram_id обязательны — это и есть адрес доставки.
# telegram_id — фейковые числовые id (не настоящие chat_id): сидер работает
# с deliver=False (src/bp5/pipeline.py), в сеть не стучится, поэтому эти
# значения нужны только чтобы удовлетворить NOT NULL/unique в БД.
USERS = [
    {
        'full_name': 'Иванов Пётр',
        'department': 'Юристы',
        'email': 'ivanov@kodik.example',
        'telegram_id': 100000001,
    },
    {
        'full_name': 'Петрова Анна',
        'department': 'Юристы',
        'email': 'petrova@kodik.example',
        'telegram_id': 100000002,
    },
    {
        'full_name': 'Сидоров Олег',
        'department': 'Аналитика',
        'email': 'sidorov@kodik.example',
        'telegram_id': 100000003,
    },
]

# (тип события, приоритет, получатель, канал, режим доставки)
# Получатель — user.full_name, НЕ отдел: список курируется вручную и может
# не совпадать со штатом отдела. Пример ниже — у «судебного риска» на П1
# ДВА получателя, и у одного из них ДВА канала: три строки под одну пару
# (тип, приоритет) дают три алерта на одно и то же событие.
ROUTING = [
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Иванов Пётр',
        'telegram',
        DeliveryMode.instant,
    ),
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Иванов Пётр',
        'email',
        DeliveryMode.instant,
    ),
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Петрова Анна',
        'telegram',
        DeliveryMode.instant,
    ),
    (
        'выигранный тендер',
        PriorityLevel.p2,
        'Сидоров Олег',
        'email',
        DeliveryMode.digest,
    ),
    (
        'расширение',
        PriorityLevel.p3,
        'Сидоров Олег',
        'email',
        DeliveryMode.digest,
    ),
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


async def _key_to_id(session: AsyncSession, model, key_column) -> dict:
    """{значение key_column: id} — для резолва связей (routing_rule, user).

    key_column передаётся явно (Department.name, User.full_name, ...),
    а не берётся по умолчанию как model.name — у User естественный ключ
    называется full_name, не name.
    """
    rows = await session.execute(select(key_column, model.id))
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
    added += await _insert(session, Category, CATEGORIES, 'name')
    added += await _insert(session, Department, DEPARTMENTS, 'name')
    added += await _insert(session, EventType, EVENT_TYPES, 'name')
    added += await _insert(
        session, Channel, [{'name': n} for n in CHANNELS], 'name'
    )

    # --- без натурального UNIQUE: заливаем только в пустую таблицу ---
    if await _is_empty(session, TopicLimit):
        added += await _insert(session, TopicLimit, TOPIC_LIMITS)
    await session.flush()

    # user: email И telegram_id по отдельности unique (не пара), поэтому
    # обычный _insert с ON CONFLICT по двум колонкам сразу не подходит —
    # тот же count-guard, что и у routing_rule. department_id резолвится
    # из уже залитых Department.
    if await _is_empty(session, User):
        dept = await _key_to_id(session, Department, Department.name)
        session.add_all(
            User(
                full_name=u['full_name'],
                department_id=dept[u['department']],
                email=u['email'],
                telegram_id=u['telegram_id'],
            )
            for u in USERS
        )
        added += len(USERS)
    await session.flush()

    if await _is_empty(session, RoutingRule):
        etype = await _key_to_id(session, EventType, EventType.name)
        channel = await _key_to_id(session, Channel, Channel.name)
        user = await _key_to_id(session, User, User.full_name)
        session.add_all(
            RoutingRule(
                event_type_id=etype[etype_name],
                priority=priority,
                user_id=user[full_name],
                channel_id=channel[chan_name],
                mode=mode,
            )
            for etype_name, priority, full_name, chan_name, mode in ROUTING
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
