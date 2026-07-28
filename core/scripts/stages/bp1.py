"""Этап BP-1: задачи сбора (search_task) и сырьё (raw_item).

Заливает то, что в бою производит парсер: снимки страниц новостного
агрегатора. Один raw_item = одна выгрузка по одной задаче сбора.

Запуск:
    python -m core.scripts.stages.bp1

После него можно прогонять BP-2:
    python -c "import asyncio; from src.bp2.pipeline import run_bp2; \\
               print(asyncio.run(run_bp2()))"

Набор данных решает две задачи сразу — поэтому он один, а не два разных:

1. ДЕМО. Настоящие новости по девяти конкурентам: пройдя весь конвейер, они
   дают осмысленную витрину, на которую не стыдно посмотреть в BI.
2. КРАЙНИЕ СЛУЧАИ. В него вплетены все сценарии, которые должен пережить
   отбор BP-2 и его фильтры:

   - пары new → changed (в нормализацию идёт только changed);
   - unchanged: снимок с поднятым updated_at (хэш совпал, данные те же);
   - две строки error (raw_data = NULL, в отбор не попадают);
   - тай-брейк: пара с ОДИНАКОВЫМ created_at — побеждает больший id;
   - события под каждый фильтр: чёрный домен, стоп-слово, стоп-тема,
     ложное срабатывание, пустой заголовок (parse_error);
   - перебор лимита антишума по конкуренту (у Иркутска событий больше 5).

Справочники должны быть залиты заранее (stages/dictionaries).
"""

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import RawItemStatus
from core.scripts.stages.cascade import clear_from
from core.scripts.stages.dictionaries import SOURCE_NAME
from src.bp1.models import Competitor, RawItem, SearchTask, Source


def dt(day: int, hour: int = 9, minute: int = 0, second: int = 0) -> datetime:
    """Момент времени в июне 2026 — чтобы снимки шли в заданном порядке."""
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


def item(url, title, text, published_at, region, media_name, extra=None):
    """Один сырой объект raw_data.items[] (ключи = колонкам normalized_item).

    Тексты намеренно ГРЯЗНЫЕ — с HTML-сущностями, обрывками тегов, лишними
    пробелами и разными форматами даты: ровно то, что чистит BP-2.
    """
    return {
        'url': url,
        'title': title,
        'text': text,
        'published_at': published_at,
        'region': region,
        'media_name': media_name,
        'extra': extra or {},
    }


# ============================================================================
#  Снимки: (конкурент, статус, момент съёма, события) + опции
# ============================================================================
#  Порядок в списке = порядок вставки: у снимка, объявленного ниже, id больше.
#  Это важно для пары с одинаковым created_at (тай-брейк по id DESC).

SNAPSHOTS: list[dict] = [
    # ---- Топ-Сервис: new → changed, побеждает changed ----
    {
        'competitor': 'Топ-Сервис',
        'status': RawItemStatus.new,
        'created': dt(22, 10),
        'items': [
            item(
                'https://big-news.ru/kaluga/old',
                'Первая версия заметки',
                'Черновой текст, позже обновлён.',
                '22.06.2026',
                'Калуга',
                'Big-news.ru, Москва',
            ),
        ],
    },
    {
        'competitor': 'Топ-Сервис',
        'status': RawItemStatus.changed,
        'created': dt(25, 10),
        'items': [
            item(
                'https://big-news.ru/kaluga/12045',
                '  Калужской транспортной прокуратурой выявлены\t'
                'нарушения закона о защите прав пассажиров ',
                '<p>Проверка показала&nbsp;нарушения. '
                '&laquo;Топ-Сервис&raquo; получил представление.</p>',
                '25.06.2026',
                'Калуга',
                'Big-news.ru, Москва',
            ),
            item(
                'https://big-news.ru/kaluga/12046',
                '…нарушения законодательства о защите прав '
                'пассажиров ж/д транспорта',
                'Продолжение темы&mdash;прокуратура выявила '
                'нарушения у перевозчика.',
                '25 июня 2026 г.',
                '  калуга ',
                'Big-news.ru, Москва',
            ),
            item(
                'https://www.cnews.ru/news/2026/06/24/conf',
                'Конференция CNews &laquo;Оптимизация цифровой '
                'инфраструктуры 2026&raquo;',
                'Топ-Сервис выступил партнёром конференции.',
                '24.06.2026',
                'Москва',
                'CNews.ru',
            ),
        ],
    },
    # ---- МУП «Школьное питание»: unchanged (updated_at поднят) ----
    {
        'competitor': 'МУП «Школьное питание»',
        'status': RawItemStatus.new,
        'created': dt(24, 8),
        'updated': dt(27, 8),  # хэш совпал — обновили только отметку сверки
        'items': [
            item(
                'https://news.rambler.ru/incident/54321',
                'Бывшему вице-мэру Нефтеюганска второй&nbsp;раз '
                'смягчили меру пресечения',
                'Суд смягчил меру пресечения фигуранту, связанному '
                'с МУП &laquo;Школьное питание&raquo;.',
                '25.06.2026',
                'Нефтеюганск',
                'Рамблер/новости',
            ),
        ],
    },
    # ---- Виво Маркет: демо + стоп-слово + пустой заголовок ----
    {
        'competitor': 'Виво Маркет',
        'status': RawItemStatus.new,
        'created': dt(27, 9),
        'items': [
            item(
                'https://v1.ru/text/business/2026/06/25/social',
                'Как волгоградские  предприниматели развивают '
                'социальный бизнес',
                'Среди участников — сеть &laquo;Виво Маркет&raquo;.',
                '25.06.2026',
                'Волгоград',
                'V1.ru, Волгоград',
            ),
            item(
                'https://www.forbes.ru/biznes/456-den',
                'День широко распахнутых дверей и кешбэк во&nbsp;благо',
                '<b>Виво Маркет</b> провёл акцию для покупателей.',
                '27.06.2026',
                'ВОЛГОГРАД',
                'Forbes, Москва',
            ),
            item(
                'https://volgaprom.expert/news/789',
                'VR-очки, дегустация, карта желаний: ярмарка '
                'вакансий Волгограда',
                'Виво Маркет представил стенд на ярмарке.',
                '23.06.2026',
                'г. Волгоград',
                'ВолгаПромЭксперт',
            ),
            # → stop_word «реклама»
            item(
                'https://volgaprom.expert/news/790',
                'Скидки недели в магазинах сети',
                'Это реклама акции для покупателей.',
                '26.06.2026',
                'Волгоград',
                'ВолгаПромЭксперт',
            ),
            # → parse_error: заголовка нет вообще
            item(
                'https://v1.ru/text/business/2026/06/26/noname',
                '',
                'Текст без заголовка — парсер не смог достать title.',
                '26.06.2026',
                'Волгоград',
                'V1.ru, Волгоград',
            ),
        ],
    },
    # ---- Комбинат питания Иркутска: new → changed, перебор антишума ----
    {
        'competitor': 'Комбинат питания Иркутска',
        'status': RawItemStatus.new,
        'created': dt(21, 8),
        'items': [
            item(
                'https://irksib.ru/2026/06/20/old',
                'Старая версия материала',
                'Позже заменена обновлённой выгрузкой.',
                '20.06.2026',
                'Иркутск',
                'Irksib.ru',
            ),
        ],
    },
    {
        'competitor': 'Комбинат питания Иркутска',
        'status': RawItemStatus.changed,
        'created': dt(26, 8),
        'items': [
            item(
                'https://argumenti.ru/irkutsk/2026/06/35let',
                '35 лет со вкусом и качеством от Комбината питания',
                'Предприятие отмечает юбилей.',
                '24.06.2026',
                'Иркутск',
                'Аргументы недели',
            ),
            item(
                'https://www.kp.ru/irkutsk/recipe',
                'Поделитесь рецептом',
                'Комбинат питания запустил конкурс рецептов.',
                '23.06.2026',
                'иркутск',
                'КП-Иркутск',
            ),
            item(
                'https://irksib.ru/2026/06/22/kuhnya',
                'Детская молочная кухня Иркутска: роботизация '
                'и поставки с сентября',
                'Модернизация производства детского питания.',
                '2026-06-22',
                'Иркутск ',
                'Irksib.ru',
            ),
            item(
                'https://dairynews.today/irkutsk/assort',
                'Детская молочная кухня Иркутска расширяет ассортимент',
                'В линейке появились новые позиции.',
                '22.06.26',
                'Иркутск',
                'ДэйриНьюс',
            ),
            item(
                'https://tokmedia.ru/tn-angara',
                'Иркутское предприятие ТН-Ангара внедрит бережливые технологии',
                'Оптимизация процессов на производстве.',
                '26 июня 2026',
                'Иркутск',
                'Ток Медиа',
            ),
            # → stop_topic «гороскоп»
            item(
                'https://www.kp.ru/irkutsk/goroskop',
                'Гороскоп на неделю для жителей Иркутска',
                'Что обещают звёзды.',
                '24.06.2026',
                'Иркутск',
                'КП-Иркутск',
            ),
            # Шестое ЧИСТОЕ событие конкурента при лимите 5/неделю —
            # именно оно уходит в rejected(noise_limit) на шаге антишума.
            item(
                'https://irksib.ru/2026/06/25/postavki',
                'Комбинат питания заключил договор на поставку овощей',
                'Расширение пула поставщиков к новому учебному году.',
                '25.06.2026',
                'Иркутск',
                'Irksib.ru',
            ),
        ],
    },
    # ---- Сургут: new → changed с разными датами съёма ----
    {
        'competitor': 'Комбинат школьного питания Сургута',
        'status': RawItemStatus.new,
        'created': dt(21, 9, 30),
        'items': [
            item(
                'https://ugra-news.ru/surgut/old',
                'Старая заметка о питании',
                'Заменена свежей выгрузкой.',
                '21.06.2026',
                'Сургут',
                'Сургутская трибуна',
            ),
        ],
    },
    {
        'competitor': 'Комбинат школьного питания Сургута',
        'status': RawItemStatus.changed,
        'created': dt(23, 9, 30, 15),
        'items': [
            item(
                'https://ugra-news.ru/surgut/reforma',
                'Сургут готовит реформу школьного питания: '
                '55%&nbsp;еды выбрасывается',
                'Власти обсуждают проблему пищевых отходов.',
                '23.06.2026',
                'Сургут',
                'Сургутская трибуна',
            ),
            item(
                'https://siapress.ru/news/pitanie',
                'В школах Сургута хотят изменить систему питания',
                'Обсуждается новая модель организации питания.',
                '23.06.2026',
                'Сургут ',
                'СИА-Пресс',
            ),
        ],
    },
    # ---- Казань: new → changed + ложное срабатывание ----
    {
        'competitor': 'Деп. продовольствия и соцпитания Казани',
        'status': RawItemStatus.new,
        'created': dt(20, 12),
        'items': [
            item(
                'https://www.kzn.ru/meta/news/old',
                'Прошлая новость департамента',
                'Устарела.',
                '20.06.2026',
                'Казань',
                'kzn.ru',
            ),
        ],
    },
    {
        'competitor': 'Деп. продовольствия и соцпитания Казани',
        'status': RawItemStatus.changed,
        'created': dt(26, 12),
        'items': [
            item(
                'https://www.kzn.ru/meta/news/600',
                'С начала года свыше 600 школьников посетили '
                'городские предприятия',
                'Экскурсии организованы департаментом питания.',
                '22.06.2026',
                'Казань',
                'kzn.ru',
            ),
            # → false_positive «бегемот в зоопарке»
            item(
                'https://www.kzn.ru/meta/news/zoo',
                'Бегемот в зоопарке Казани отметил день рождения',
                'К деятельности конкурента отношения не имеет.',
                '22.06.2026',
                'Казань',
                'kzn.ru',
            ),
        ],
    },
    # ---- Охта: ТАЙ-БРЕЙК — одинаковый created_at, побеждает больший id ----
    {
        'competitor': 'Комбинат соц. питания «Охта»',
        'status': RawItemStatus.new,
        'created': dt(23, 15),
        'items': [
            item(
                'https://spb.bezformata.com/draft',
                'Черновик материала о столовых',
                'Черновой текст.',
                '23.06.2026',
                'СПб',
                'БезФормата СПб',
            ),
        ],
    },
    {
        'competitor': 'Комбинат соц. питания «Охта»',
        'status': RawItemStatus.changed,
        'created': dt(23, 15),  # ТОТ ЖЕ момент, что у new выше
        'items': [
            item(
                'https://spb.bezformata.com/stolovye',
                'В Петербурге определили лучшие школьные столовые',
                'Комбинат &laquo;Охта&raquo; вошёл в число лучших.',
                '23.06.2026',
                'СПб',
                'БезФормата СПб',
            ),
        ],
    },
    # ---- Мусороуборочная компания: чёрный домен + сбой сбора ----
    {
        'competitor': 'Мусороуборочная компания',
        'status': RawItemStatus.error,
        'created': dt(24, 11),
        'items': [],
        'error': 'ConnectionTimeout: источник не ответил за 30 с. '
        'Исчерпаны все 3 попытки.',
    },
    {
        'competitor': 'Мусороуборочная компания',
        'status': RawItemStatus.new,
        'created': dt(25, 11),
        'items': [
            # → black_domain critics24.com; регион «Украина» не резолвится
            item(
                'https://critics24.com/kiev/gubernator',
                '&laquo;Ночной губернатор&raquo; вызван на допрос',
                'Скандальная публикация о деятельности компании.',
                '22.06.2026',
                'Украина',
                'critics24.com (Киев)',
            ),
        ],
    },
    # ---- СКС: сбой + три демо-новости ----
    {
        'competitor': 'СКС',
        'status': RawItemStatus.error,
        'created': dt(24, 11, 10),
        'items': [],
        'error': 'HTTP 403 от источника: сработала защита от парсинга.',
    },
    {
        'competitor': 'СКС',
        'status': RawItemStatus.new,
        'created': dt(25, 11, 10),
        'items': [
            item(
                'https://samadm.ru/news/rekonstrukciya',
                'Глава Самары проверил ход реконструкции коммунальных сетей',
                'Работы ведёт СКС.',
                '25.06.2026',
                'Самара',
                'samadm.ru',
            ),
            item(
                'https://63.ru/text/gorod/2026/06/23/torez',
                'В Самаре закрыто движение по ул. Мориса Тореза',
                'Причина — ремонт сетей СКС.',
                '23.06.2026',
                'самара',
                '63.ru',
            ),
            item(
                'https://samara450.ru/dolg',
                'Более 1,5 млрд руб. долга накопили жители Самары за воду',
                'Задолженность перед ресурсником СКС.',
                '25.06.2026',
                'Самара',
                'Самара 450',
            ),
        ],
    },
]


# ============================================================================
#  Этап
# ============================================================================


def make_raw_data(task_id: int, competitor: str, items: list[dict]) -> dict:
    """Контейнер выгрузки: meta (контекст задачи) + items (события)."""
    return {
        'meta': {
            'search_task_id': task_id,
            'source': SOURCE_NAME,
            'competitor': competitor,
            'trigger': None,
            'source_request_url': (f'{SOURCE_NAME}/?text={competitor}'),
            'fetched_at': '2026-06-27T09:00:00Z',
        },
        'items': items,
    }


async def seed(session: AsyncSession) -> int:
    """Создать задачи сбора и залить снимки.

    По одной search_task на конкурента (без триггера — парсим агрегатор
    «в лоб»). Снимки вставляются в порядке объявления SNAPSHOTS: у более
    позднего в списке id больше, на этом держится сценарий тай-брейка.
    """
    competitors = {
        c.name: c.id
        for c in (await session.execute(select(Competitor))).scalars()
    }
    source_id = await session.scalar(
        select(Source.id).where(Source.name == SOURCE_NAME)
    )
    if source_id is None:
        raise RuntimeError(
            'Справочники не залиты — нет источника. '
            'Сначала: python -m core.scripts.stages.dictionaries'
        )

    # --- по одной задаче сбора на каждого конкурента из набора ---
    names = list(dict.fromkeys(s['competitor'] for s in SNAPSHOTS))
    tasks = {
        name: SearchTask(
            competitor_id=competitors[name],
            source_id=source_id,
            trigger_id=None,
        )
        for name in names
    }
    session.add_all(tasks.values())
    await session.flush()

    # --- снимки ---
    for snap in SNAPSHOTS:
        name = snap['competitor']
        task_id = tasks[name].id
        created = snap['created']
        failed = snap['status'] == RawItemStatus.error
        session.add(
            RawItem(
                search_task_id=task_id,
                status=snap['status'],
                # У сбоя контента нет вообще: ни хэша, ни JSON, ни HTML.
                content_hash=None
                if failed
                else sha256(
                    f'{name}:{created.isoformat()}'.encode()
                ).hexdigest(),
                raw_data=None
                if failed
                else make_raw_data(task_id, name, snap['items']),
                html_file_path=None
                if failed
                else f'/snapshots/{task_id}/{created:%Y-%m-%dT%H-%M}.html',
                source_request_url=f'{SOURCE_NAME}/?text={name}',
                error_message=snap.get('error'),
                created_at=created,
                updated_at=snap.get('updated') or created,
            )
        )
        # flush на КАЖДОМ шаге: id должны расти в порядке объявления, иначе
        # сценарий тай-брейка (одинаковый created_at) не воспроизведётся.
        await session.flush()

    return len(SNAPSHOTS)


async def clear(session: AsyncSession) -> int:
    """Снести сырьё, задачи сбора и всё, что на них построено."""
    return await clear_from(session, SearchTask)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-1 (сырьё)', clear, seed)
