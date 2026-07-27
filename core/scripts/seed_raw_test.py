"""Тест-сид для BP-2: пересоздаёт search_task и наполняет raw_item.

Самоочищается: перед вставкой чистит normalized_item → raw_item → search_task
(справочники competitor/source/region/black_domain/stop_word НЕ трогает).
Можно перезапускать сколько угодно:

    python -m core.scripts.seed_raw_test

Сценарии (что должен сделать BP-2 с каждой ЗАДАЧЕЙ):
  new only            одиночный new                    → берём
  new → changed       старый new + новый changed       → берём changed
  new → changed (=CR) new и changed с ОДИНАКОВЫМ        → берём changed
                      created_at (тай-брейк по id DESC)
  unchanged           new с поднятым updated_at         → берём (статус тот же)
  error               raw_data NULL                     → пропускаем

changed всегда идёт ПОСЛЕ new на той же задаче (иначе changed бессмыслен).
created_at у снимков разные (≥1 c), кроме нарочного тай-кейса.

В контент отобранных снимков подложены события под все фильтры:
ok / black_domain / stop_word / stop_topic / false_positive / parse_error.
"""

import asyncio
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import delete, select

from core.database import AsyncSessionLocal
from core.enums import RawItemStatus
from src.bp1.models import Competitor, RawItem, SearchTask
from src.bp2.models import NormalizedItem

SOURCE_ID = 1
SOURCE_NAME = 'https://newssearch.yandex.ru'


def dt(day, hour=9, minute=0, second=0):
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


def item(url, title, text, published_at, region, media_name):
    """Один сырой объект raw_data.items[] (ключи = контракту)."""
    return {
        'url': url,
        'title': title,
        'text': text,
        'published_at': published_at,
        'region': region,
        'media_name': media_name,
        'extra': {},
    }


def raw_data(task_id, competitor, items):
    return {
        'meta': {
            'search_task_id': task_id,
            'source': SOURCE_NAME,
            'competitor': competitor,
            'trigger': None,
        },
        'items': items,
    }


async def main():
    async with AsyncSessionLocal() as session:
        # --- самоочистка (FK-safe: сначала дети, потом родители) ---
        await session.execute(delete(NormalizedItem))
        await session.execute(delete(RawItem))
        await session.execute(delete(SearchTask))
        await session.flush()

        comp = {
            c.name: c.id
            for c in (await session.execute(select(Competitor))).scalars()
        }

        # --- search_task: по одной задаче на конкурента ---
        used = [
            'Топ-Сервис',  # new only
            'Виво Маркет',  # new only
            'МУП «Школьное питание»',  # unchanged
            'Комбинат питания Иркутска',  # new → changed
            'Комбинат школьного питания Сургута',  # new → changed
            'Деп. продовольствия и соцпитания Казани',  # new → changed
            'Комбинат соц. питания «Охта»',  # new → changed (=CR)
            'Мусороуборочная компания',  # error
            'СКС',  # error
        ]
        tasks = {
            name: SearchTask(
                competitor_id=comp[name], source_id=SOURCE_ID, trigger_id=None
            )
            for name in used
        }
        session.add_all(tasks.values())
        await session.flush()
        tid = {name: t.id for name, t in tasks.items()}

        raws: list[RawItem] = []

        def add(name, status, items, created, updated=None, *, error=None):
            data = None if error else raw_data(tid[name], name, items)
            raws.append(
                RawItem(
                    search_task_id=tid[name],
                    status=status,
                    content_hash=None
                    if error
                    else sha256(
                        f'{name}:{created.isoformat()}'.encode()
                    ).hexdigest(),
                    raw_data=data,
                    html_file_path=None,
                    source_request_url=SOURCE_NAME,
                    error_message=error,
                    created_at=created,
                    updated_at=updated or created,
                )
            )

        # ---- NEW only (2): берём ----
        add(
            'Топ-Сервис',
            RawItemStatus.new,
            [
                item(
                    'https://big-news.ru/kaluga/1',
                    'Прокуратура выявила нарушения',
                    'Проверка показала нарушения.',
                    '25.06.2026',
                    'Калуга',
                    'Big-news.ru',
                ),
                item(
                    'https://critics24.com/kiev/2',
                    'Компромат на компанию',
                    'Заказная публикация.',
                    '25 июня 2026',
                    'Калуга',
                    'critics24.com',
                ),  # чёрный домен → black_domain
            ],
            dt(25, 10, 0, 0),
        )
        add(
            'Виво Маркет',
            RawItemStatus.new,
            [
                item(
                    'https://forbes.ru/1',
                    'Акция магазина',
                    'Это реклама скидок.',
                    '27.06.2026',
                    'Волгоград',
                    'Forbes',
                ),  # stop_word
                item(
                    'https://v1.ru/2',
                    '',
                    'Текст без заголовка.',
                    '27.06.2026',
                    'Волгоград',
                    'V1.ru',
                ),  # пустой title → parse_error
            ],
            dt(25, 10, 0, 7),
        )

        # ---- UNCHANGED (1): new с поднятым updated_at → берём ----
        add(
            'МУП «Школьное питание»',
            RawItemStatus.new,
            [
                item(
                    'https://mos.ru/1',
                    'Новое меню в школах',
                    'Обновили рацион.',
                    '24.06.2026',
                    'Москва',
                    'mos.ru',
                ),
            ],
            dt(24, 8, 0, 0),
            dt(27, 8, 0, 0),
        )  # updated_at > created_at

        # ---- NEW → CHANGED (3), разные created_at: берём changed ----
        add(
            'Комбинат питания Иркутска',
            RawItemStatus.new,
            [
                item(
                    'https://irk.ru/old',
                    'Старая версия',
                    'Старый текст.',
                    '22.06.2026',
                    'Иркутск',
                    'Ирк.ру',
                ),
            ],
            dt(22, 8, 0, 0),
        )
        add(
            'Комбинат питания Иркутска',
            RawItemStatus.changed,
            [
                item(
                    'https://irk.ru/new',
                    '35 лет со вкусом',
                    'Юбилей.',
                    '24.06.2026',
                    'Иркутск',
                    'Аргументы',
                ),
                item(
                    'https://irk.ru/goro',
                    'Гороскоп на неделю',
                    'Звёзды.',
                    '24.06.2026',
                    'Иркутск',
                    'Ирк.ру',
                ),  # stop_topic
            ],
            dt(24, 8, 0, 0),
        )

        add(
            'Комбинат школьного питания Сургута',
            RawItemStatus.new,
            [
                item(
                    'https://ugra.ru/old',
                    'Старая заметка',
                    'Старьё.',
                    '21.06.2026',
                    'Сургут',
                    'Югра',
                ),
            ],
            dt(21, 9, 30, 0),
        )
        add(
            'Комбинат школьного питания Сургута',
            RawItemStatus.changed,
            [
                item(
                    'https://ugra-news.ru/surgut',
                    'Реформа школьного питания',
                    'Обсуждают отходы.',
                    '2026-06-23',
                    'Сургут',
                    'Сургутская трибуна',
                ),
            ],
            dt(23, 9, 30, 15),
        )

        add(
            'Деп. продовольствия и соцпитания Казани',
            RawItemStatus.new,
            [
                item(
                    'https://kzn.ru/old',
                    'Старая новость',
                    'Было.',
                    '20.06.2026',
                    'Казань',
                    'kzn.ru',
                ),
            ],
            dt(20, 12, 0, 0),
        )
        add(
            'Деп. продовольствия и соцпитания Казани',
            RawItemStatus.changed,
            [
                item(
                    'https://kzn.ru/1',
                    'Экскурсии для школьников',
                    'Провели экскурсии.',
                    '22.06.2026',
                    'Казань',
                    'kzn.ru',
                ),
                item(
                    'https://kzn.ru/2',
                    'Бегемот в зоопарке Казани',
                    'Не про конкурента.',
                    '22.06.2026',
                    'Казань',
                    'kzn.ru',
                ),  # false_pos
            ],
            dt(26, 12, 0, 0),
        )

        # ---- NEW → CHANGED с ОДИНАКОВЫМ created_at: тай-брейк по id DESC ----
        # new вставляем ПЕРВЫМ → у changed id больше → он и побеждает.
        add(
            'Комбинат соц. питания «Охта»',
            RawItemStatus.new,
            [
                item(
                    'https://spb.ru/old',
                    'Черновик',
                    'Черновой текст.',
                    '23.06.2026',
                    'Санкт-Петербург',
                    'СПб.ру',
                ),
            ],
            dt(23, 15, 0, 0),
        )
        add(
            'Комбинат соц. питания «Охта»',
            RawItemStatus.changed,
            [
                item(
                    'https://spb.bezformata.com/1',
                    'Лучшие школьные столовые',
                    'Охта в числе лучших.',
                    '23.06.2026',
                    'Санкт-Петербург',
                    'БезФормата СПб',
                ),
            ],
            dt(23, 15, 0, 0),
        )  # ТОТ ЖЕ момент, что у new выше

        # ---- ERROR (2): raw_data NULL → пропускаем ----
        add(
            'Мусороуборочная компания',
            RawItemStatus.error,
            [],
            dt(25, 11, 0),
            error='Таймаут парсера после ретраев',
        )
        add(
            'СКС',
            RawItemStatus.error,
            [],
            dt(25, 11, 0, 10),
            error='403 от источника',
        )

        session.add_all(raws)
        await session.commit()

        by_status: dict[str, int] = {}
        for r in raws:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        print(f'search_task: +{len(tasks)}   raw_item: +{len(raws)}')
        print('по статусам:', by_status)


if __name__ == '__main__':
    asyncio.run(main())
