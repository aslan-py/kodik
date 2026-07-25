"""Сидинг тестовых данных для BP-1 (новостной контур).

Заполняет справочники и raw_item реалистичным «грязным» сырьём — новостями
о конкурентах (сфера: питание/ЖКХ/соцобъекты), собранными через новостной
агрегатор. Данные намеренно НЕ причёсаны: обрывки HTML-тегов, HTML-сущности
(&laquo;, &nbsp;, &mdash;), неразрывные пробелы, табы, разнобой регистра,
дат и написания регионов. Это вход для BP-2, который должен всё вычистить.

Порядок вставки:
  1. competitor, source, trigger  — справочники
  2. search_task                  — матрица задач (зависит от п.1)
  3. raw_item                     — сырые снимки (зависит от п.2)

Идемпотентен: справочники и search_task вставляются с проверкой на дубли,
raw_item — с проверкой count (повторный запуск не плодит строки).

Запуск (из любого места):
    python src/bp1/scripts/seed_bp1.py
    python -m src.bp1.scripts.seed_bp1
"""

import asyncio
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from src.bp1.models import (  # noqa: E402
    Competitor,
    RawItem,
    RawItemStatus,
    SearchTask,
    Source,
    Trigger,
)

# ---------------------------------------------------------------------------
# Справочники
# ---------------------------------------------------------------------------

# Единственный источник демо — новостной агрегатор (его «парсим»).
# Конкретное СМИ-публикатор лежит в items[].media, не тут.
SOURCE_NAME = 'Яндекс.Новости'

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

SOURCES = [
    {'name': SOURCE_NAME},
]

TRIGGERS = [
    {'keyword': 'школьное питание'},
    {'keyword': 'тендер'},
    {'keyword': 'прокуратура'},
]


# ---------------------------------------------------------------------------
# Сырые новости по конкурентам (грязные — как пришли с парсинга).
# Один конкурент = один поисковый прогон = один raw_item с items[].
# ---------------------------------------------------------------------------

ARTICLES: list[tuple[str, list[dict]]] = [
    (
        'Топ-Сервис',
        [
            {
                'url': 'https://big-news.ru/kaluga/12045',
                'title': '  Калужской транспортной прокуратурой выявлены\t'
                'нарушения закона о защите прав пассажиров ',
                'text': '<p>Проверка показала&nbsp;нарушения. '
                '&laquo;Топ-Сервис&raquo; получил представление.</p>',
                'date': '25.06.2026',
                'region': 'Калуга',
                'media': 'Big-news.ru, Москва',
            },
            {
                'url': 'https://big-news.ru/kaluga/12046',
                'title': '…нарушения законодательства о защите прав '
                'пассажиров ж/д транспорта',
                'text': 'Продолжение темы&mdash;прокуратура выявила '
                'нарушения у перевозчика.',
                'date': '25 июня 2026 г.',
                'region': '  калуга ',
                'media': 'Big-news.ru, Москва',
            },
            {
                'url': 'https://www.cnews.ru/news/2026/06/24/conf',
                'title': 'Конференция CNews &laquo;Оптимизация цифровой '
                'инфраструктуры 2026&raquo;',
                'text': 'Топ-Сервис выступил партнёром конференции.',
                'date': '24.06.2026',
                'region': 'Москва',
                'media': 'CNews.ru',
            },
        ],
    ),
    (
        'МУП «Школьное питание»',
        [
            {
                'url': 'https://news.rambler.ru/incident/54321',
                'title': 'Бывшему вице-мэру Нефтеюганска второй&nbsp;раз '
                'смягчили меру пресечения',
                'text': 'Суд смягчил меру пресечения фигуранту, связанному '
                'с МУП &laquo;Школьное питание&raquo;.',
                'date': '25.06.2026',
                'region': 'Нефтеюганск',
                'media': 'Рамблер/новости',
            },
        ],
    ),
    (
        'Виво Маркет',
        [
            {
                'url': 'https://v1.ru/text/business/2026/06/25/social',
                'title': 'Как волгоградские  предприниматели развивают '
                'социальный бизнес',
                'text': 'Среди участников — сеть &laquo;Виво Маркет&raquo;.',
                'date': '25.06.2026',
                'region': 'Волгоград',
                'media': 'V1.ru, Волгоград',
            },
            {
                'url': 'https://www.forbes.ru/biznes/456-den',
                'title': 'День широко распахнутых дверей '
                'и кешбэк во&nbsp;благо',
                'text': '<b>Виво Маркет</b> провёл акцию для покупателей.',
                'date': '27.06.2026',
                'region': 'ВОЛГОГРАД',
                'media': 'Forbes, Москва',
            },
            {
                'url': 'https://volgaprom.expert/news/789',
                'title': 'VR-очки, дегустация, карта желаний: ярмарка '
                'вакансий Волгограда',
                'text': 'Виво Маркет представил стенд на ярмарке.',
                'date': '23.06.2026',
                'region': 'г. Волгоград',
                'media': 'ВолгаПромЭксперт',
            },
        ],
    ),
    (
        'Комбинат питания Иркутска',
        [
            {
                'url': 'https://argumenti.ru/irkutsk/2026/06/35let',
                'title': '35 лет со вкусом и качеством от Комбината питания',
                'text': 'Предприятие отмечает юбилей.',
                'date': '24.06.2026',
                'region': 'Иркутск',
                'media': 'Аргументы недели',
            },
            {
                'url': 'https://www.kp.ru/irkutsk/recipe',
                'title': 'Поделитесь рецептом',
                'text': 'Комбинат питания запустил конкурс рецептов.',
                'date': '23.06.2026',
                'region': 'иркутск',
                'media': 'КП-Иркутск',
            },
            {
                'url': 'https://irksib.ru/2026/06/22/kuhnya',
                'title': 'Детская молочная кухня Иркутска: роботизация '
                'и поставки с сентября',
                'text': 'Модернизация производства детского питания.',
                'date': '2026-06-22',
                'region': 'Иркутск ',
                'media': 'Irksib.ru',
            },
            {
                'url': 'https://dairynews.today/irkutsk/assort',
                'title': 'Детская молочная кухня Иркутска расширяет '
                'ассортимент',
                'text': 'В линейке появились новые позиции.',
                'date': '22.06.26',
                'region': 'Иркутск',
                'media': 'ДэйриНьюс',
            },
            {
                'url': 'https://tokmedia.ru/tn-angara',
                'title': 'Иркутское предприятие ТН-Ангара внедрит '
                'бережливые технологии',
                'text': 'Оптимизация процессов на производстве.',
                'date': '26 июня 2026',
                'region': 'Иркутск',
                'media': 'Ток Медиа',
            },
        ],
    ),
    (
        'Комбинат школьного питания Сургута',
        [
            {
                'url': 'https://ugra-news.ru/surgut/reforma',
                'title': 'Сургут готовит реформу школьного питания: '
                '55%&nbsp;еды выбрасывается',
                'text': 'Власти обсуждают проблему пищевых отходов.',
                'date': '23.06.2026',
                'region': 'Сургут',
                'media': 'Сургутская трибуна',
            },
            {
                'url': 'https://siapress.ru/news/pitanie',
                'title': 'В школах Сургута хотят изменить систему питания',
                'text': 'Обсуждается новая модель организации питания.',
                'date': '23.06.2026',
                'region': 'Сургут ',
                'media': 'СИА-Пресс',
            },
        ],
    ),
    (
        'Деп. продовольствия и соцпитания Казани',
        [
            {
                'url': 'https://www.kzn.ru/meta/news/600',
                'title': 'С начала года свыше 600 школьников посетили '
                'городские предприятия',
                'text': 'Экскурсии организованы департаментом питания.',
                'date': '22.06.2026',
                'region': 'Казань',
                'media': 'kzn.ru',
            },
        ],
    ),
    (
        'Комбинат соц. питания «Охта»',
        [
            {
                'url': 'https://spb.bezformata.com/stolovye',
                'title': 'В Петербурге определили лучшие школьные столовые',
                'text': 'Комбинат &laquo;Охта&raquo; вошёл в число лучших.',
                'date': '23.06.2026',
                'region': 'СПб',
                'media': 'БезФормата СПб',
            },
        ],
    ),
    (
        'Мусороуборочная компания',
        [
            # critics24.com (Киев) — заказной/компрометирующий ресурс,
            # кандидат в black_domain. Регион «Украина» не резолвится.
            {
                'url': 'https://critics24.com/kiev/gubernator',
                'title': '&laquo;Ночной губернатор&raquo; вызван на допрос',
                'text': 'Скандальная публикация о деятельности компании.',
                'date': '22.06.2026',
                'region': 'Украина',
                'media': 'critics24.com (Киев)',
            },
        ],
    ),
    (
        'СКС',
        [
            {
                'url': 'https://samadm.ru/news/rekonstrukciya',
                'title': 'Глава Самары проверил ход реконструкции '
                'коммунальных сетей',
                'text': 'Работы ведёт СКС.',
                'date': '25.06.2026',
                'region': 'Самара',
                'media': 'samadm.ru',
            },
            {
                'url': 'https://63.ru/text/gorod/2026/06/23/torez',
                'title': 'В Самаре закрыто движение по ул. Мориса Тореза',
                'text': 'Причина — ремонт сетей СКС.',
                'date': '23.06.2026',
                'region': 'самара',
                'media': '63.ru',
            },
            {
                'url': 'https://samara450.ru/dolg',
                'title': 'Более 1,5 млрд руб. долга накопили жители '
                'Самары за воду',
                'text': 'Задолженность перед ресурсником СКС.',
                'date': '25.06.2026',
                'region': 'Самара',
                'media': 'Самара 450',
            },
        ],
    ),
]


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def make_raw_data(
    search_task_id: int,
    source: str,
    competitor: str,
    trigger: str | None,
    base_url: str,
    items: list[dict],
) -> dict:
    return {
        'meta': {
            'search_task_id': search_task_id,
            'source': source,
            'competitor': competitor,
            'trigger': trigger,
            'source_request_url': base_url,
            'fetched_at': '2026-06-27T09:00:00Z',
        },
        'items': items,
    }


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # --- 1. Справочники ---
        await session.execute(
            insert(Competitor)
            .values(COMPETITORS)
            .on_conflict_do_nothing(index_elements=['name'])
        )
        await session.execute(
            insert(Source)
            .values(SOURCES)
            .on_conflict_do_nothing(index_elements=['name'])
        )
        await session.execute(
            insert(Trigger)
            .values(TRIGGERS)
            .on_conflict_do_nothing(index_elements=['keyword'])
        )
        await session.flush()

        c = {
            r.name: r.id
            for r in (await session.execute(select(Competitor))).scalars()
        }
        s = {
            r.name: r.id
            for r in (await session.execute(select(Source))).scalars()
        }

        # --- 2. search_task (по одной на конкурента, без триггера) ---
        # Идемпотентно: сверяем с уже существующими, вставляем недостающие.
        # (ON CONFLICT здесь не годится: у задач с trigger_id IS NULL дедуп
        # держит partial unique index, который ON CONFLICT не покрывает.)
        existing = {
            (r.competitor_id, r.source_id, r.trigger_id)
            for r in (await session.execute(select(SearchTask))).scalars()
        }
        for comp in (row[0] for row in ARTICLES):
            key = (c[comp], s[SOURCE_NAME], None)
            if key not in existing:
                session.add(
                    SearchTask(
                        competitor_id=c[comp],
                        source_id=s[SOURCE_NAME],
                        trigger_id=None,
                    )
                )
        await session.flush()

        tasks = {
            (r.competitor_id, r.source_id, r.trigger_id): r.id
            for r in (await session.execute(select(SearchTask))).scalars()
        }

        def task_id(comp: str) -> int:
            return tasks[(c[comp], s[SOURCE_NAME], None)]

        # --- 3. raw_item ---
        count = await session.scalar(select(func.count()).select_from(RawItem))
        if count:
            print(f'raw_item уже содержит {count} строк, пропускаем.')
            await session.commit()
            return

        now = datetime.now(UTC)
        raw_items: list[RawItem] = []

        for comp, items in ARTICLES:
            tid = task_id(comp)
            base_url = f'https://newssearch.yandex.ru/?text={comp}'
            raw_items.append(
                RawItem(
                    search_task_id=tid,
                    status=RawItemStatus.new,
                    content_hash=sha256(f'{comp}:{len(items)}'),
                    raw_data=make_raw_data(
                        tid, SOURCE_NAME, comp, None, base_url, items
                    ),
                    html_file_path=f'/snapshots/{tid}/2026-06-27T09-00.html',
                    source_request_url=base_url,
                    created_at=now,
                    updated_at=now,
                )
            )

        # Строка-сбой: парсер исчерпал ретраи (status=error, контент пустой).
        raw_items.append(
            RawItem(
                search_task_id=task_id('Топ-Сервис'),
                status=RawItemStatus.error,
                content_hash=None,
                raw_data=None,
                html_file_path=None,
                source_request_url=None,
                error_message=(
                    'ConnectionTimeout: newssearch.yandex.ru не ответил '
                    'за 30 с. Исчерпаны все 3 попытки.'
                ),
                created_at=now,
                updated_at=now,
            )
        )

        session.add_all(raw_items)
        await session.commit()
        print(f'Добавлено {len(raw_items)} строк в raw_item.')


if __name__ == '__main__':
    asyncio.run(seed())
