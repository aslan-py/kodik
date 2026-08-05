"""Этап BP-1: задачи сбора (search_task) и сырьё (raw_item).

Заливает то, что в бою производит парсер: снимки страниц новостного
агрегатора. Один raw_item = одна выгрузка по одной задаче сбора.

Запуск:
    python -m core.scripts.stages.bp1

После него можно прогонять BP-2:
    python -c "import asyncio; from src.bp2.pipeline import run_bp2; \\
               print(asyncio.run(run_bp2()))"

Контент снимков берётся из демо-набора новостей (stages/news_data.py):
здесь описан только СЦЕНАРИЙ выгрузок — какой конкурент, какой статус,
когда снят снимок и какие новости (по id строки CSV) в нём лежат. Тексты
перед укладкой намеренно «пачкаются» (dirty): HTML-сущности, обрывки тегов,
неразрывные пробелы, три разных формата даты, регион в произвольном
регистре — ровно то, что чистит BP-2.

Набор данных решает две задачи сразу — поэтому он один, а не два разных:

1. ДЕМО. Новости по 49 конкурентам (разработчики LLM/ML-решений и смежных
   ИИ-продуктов): пройдя весь конвейер, они дают наполненную витрину, на
   которую не стыдно посмотреть в BI.
2. КРАЙНИЕ СЛУЧАИ. В него вплетены все сценарии, которые должен пережить
   отбор BP-2 и его фильтры — сосредоточены на десятке конкурентов с
   несколькими новостями, чтобы сценарии были наглядными:

   - пары new → changed (в нормализацию идёт только свежий снимок) —
     «Октагон Дата», «ДатаСинтез»;
   - unchanged: снимок с поднятым updated_at (хэш совпал, данные те же) —
     «Праймтех»;
   - тай-брейк: пара с ОДИНАКОВЫМ created_at — побеждает больший id —
     «ДатаСинтез»;
   - два сбоя сбора (status=error, без контента) — «Интеллект-Системс»,
     «СловоГен»;
   - события под каждый фильтр BP-2: чёрный домен, стоп-слово (x2),
     стоп-тема, ложное срабатывание, пустой заголовок (parse_error) —
     сосредоточены на «СмартАналитика» (стоп-слова/false_positive/
     black_domain), «Кодариум» (стоп-тема) и «Праймтех» (parse_error);
   - перебор лимита антишума: у «СмартАналитика» шесть чистых событий за
     неделю при лимите 5 — самое незначительное уходит в
     rejected(noise_limit) на шаге антишума.

Остальные ~38 конкурентов (по 1-2 новости каждый) заливаются одним плоским
снимком на конкурента — генерируется автоматически внизу файла, чтобы не
раздувать этот список однотипными записями и не забыть никого из
справочника (bp2 иначе молча пропустит новости конкурента без search_task).

Справочники должны быть залиты заранее (stages/dictionaries).
"""

from datetime import UTC, date, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import RawItemStatus
from core.scripts.stages.cascade import clear_from
from core.scripts.stages.dictionaries import SOURCE_NAME
from core.scripts.stages.news_data import NEWS, News, by_ids
from src.bp1.models import Competitor, RawItem, SearchTask, Source

# Месяцы в родительном падеже — для формата даты «26 июня 2026»,
# который умеет разбирать parse_ru_date (src/bp2/schemas.py).
RU_MONTHS = (
    'января',
    'февраля',
    'марта',
    'апреля',
    'мая',
    'июня',
    'июля',
    'августа',
    'сентября',
    'октября',
    'ноября',
    'декабря',
)


def dt(day: int, hour: int = 9, minute: int = 0, second: int = 0) -> datetime:
    """Момент времени в июне 2026 — чтобы снимки шли в заданном порядке."""
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


# ============================================================================
#  Порча текста: чистая новость → то, что реально приходит со страницы
# ============================================================================
#  Вид артефакта выбирается по номеру события в снимке — так в наборе
#  встречаются все варианты, а результат остаётся воспроизводимым. Все они
#  обратимы: clean_text (BP-2) возвращает ровно исходную строку из CSV.


def dirty(text: str, index: int) -> str:
    """Внести в текст артефакты вёрстки — то, что чистит BP-2.

    0 — HTML-сущности вместо кавычек-ёлочек (&laquo; / &raquo;);
    1 — неразрывный пробел, табуляция и лишние пробелы по краям;
    2 — обёртка в HTML-тег.
    """
    kind = index % 3
    if kind == 0:
        return text.replace('«', '&laquo;').replace('»', '&raquo;')
    if kind == 1:
        return f'  {text.replace(" ", "&nbsp;", 1)}\t'
    return f'<p>{text}</p>'


def dirty_date(day: date, index: int) -> str:
    """Дата в одном из трёх форматов, которые встречаются в источниках."""
    kind = index % 3
    if kind == 0:
        return f'{day.day:02d}.{day.month:02d}.{day.year}'
    if kind == 1:
        return f'{day.day} {RU_MONTHS[day.month - 1]} {day.year}'
    return day.isoformat()


def dirty_region(region: str | None, index: int) -> str | None:
    """Регион в произвольном регистре и с мусорным пробелом.

    Резолвится он по name_aliases (в справочнике они в нижнем регистре),
    поэтому «НИЖНИЙ НОВГОРОД» и «нижний новгород » дадут тот же region_id.
    """
    if region is None:
        return None
    kind = index % 3
    if kind == 0:
        return region
    if kind == 1:
        return f'{region.lower()} '
    return region.upper()


def item(url, title, text, published_at, region, media_name, extra=None):
    """Один сырой объект raw_data.items[] (ключи = колонкам normalized_item)."""
    return {
        'url': url,
        'title': title,
        'text': text,
        'published_at': published_at,
        'region': region,
        'media_name': media_name,
        'extra': extra or {},
    }


def news_item(news: News, index: int) -> dict:
    """Демо-новость → «грязный» объект items[] сырой выгрузки."""
    return item(
        news.url,
        dirty(news.title, index),
        dirty(news.text, index),
        dirty_date(news.published_at, index),
        dirty_region(news.region, index),
        news.media_name,
    )


def draft_item(url: str, title: str, text: str, snapshot_date: date) -> dict:
    """Черновая версия заметки для ПЕРВОГО снимка пары new → changed.

    В факты такие строки не попадают: BP-2 берёт только свежий снимок задачи,
    а он — второй (changed). Они нужны, чтобы у пары была история версий,
    поэтому и описаны прямо здесь, а не в CSV с настоящими новостями.
    """
    return item(url, title, text, snapshot_date.isoformat(), None, 'Черновик')


# ============================================================================
#  Снимки: (конкурент, статус, момент съёма, id новостей из CSV) + опции
# ============================================================================
#  Порядок в списке = порядок вставки: у снимка, объявленного ниже, id больше.
#  Это важно для пары с одинаковым created_at (тай-брейк по id DESC).

# Конкуренты, для которых сценарий расписан руками ниже — вместе со ВСЕМИ
# id новостей, которые на них ссылаются (сверяется тестом в конце файла).
SCENARIO_COMPETITORS = {
    'Октагон Дата',
    'Праймтех',
    'ДатаСинтез',
    'Интеллект-Системс',
    'СловоГен',
    'СмартАналитика',
    'Кодариум',
    'МодельОн',
    'АлгоМаш',
    'НейроТек',
    'ТехноЛогика',
}

SNAPSHOTS: list[dict] = [
    # ---- Октагон Дата: new → changed, потом ещё один плоский снимок ----
    {
        'competitor': 'Октагон Дата',
        'status': RawItemStatus.new,
        'created': dt(21, 10),
        'drafts': [
            (
                'https://www.rbc.ru/news/oktagon-data-draft',
                'Предварительная информация о проверке «Октагон Дата»',
                'Черновой текст, детали проверки уточняются.',
            ),
        ],
    },
    {
        'competitor': 'Октагон Дата',
        'status': RawItemStatus.changed,
        'created': dt(26, 10),
        'news': [3, 16],
    },
    {
        'competitor': 'Октагон Дата',
        'status': RawItemStatus.new,
        'created': dt(28, 9),
        'news': [28, 33],
    },
    # ---- Праймтех: unchanged (updated_at поднят) + один сбойный довесок ----
    {
        'competitor': 'Праймтех',
        'status': RawItemStatus.new,
        'created': dt(26, 8),
        'updated': dt(27, 8),  # хэш совпал — обновили только отметку сверки
        'news': [4, 13, 29],
    },
    {
        'competitor': 'Праймтех',
        'status': RawItemStatus.new,
        'created': dt(28, 11),
        # 34 — бессвязный текст, 110 — пустой заголовок (parse_error).
        'news': [34, 110],
    },
    # ---- ДатаСинтез: ТАЙ-БРЕЙК — одинаковый created_at, побеждает больший id
    {
        'competitor': 'ДатаСинтез',
        'status': RawItemStatus.new,
        'created': dt(27, 15),
        'drafts': [
            (
                'https://habr.com/ru/news/datasintez-draft',
                'Черновик материала о проверке «ДатаСинтез»',
                'Черновой текст, ждём подтверждения деталей.',
            ),
        ],
    },
    {
        'competitor': 'ДатаСинтез',
        'status': RawItemStatus.changed,
        'created': dt(27, 15),  # ТОТ ЖЕ момент, что у new выше
        'news': [67, 74, 89, 102],
    },
    # ---- Интеллект-Системс: сбой сбора + демо ----
    {
        'competitor': 'Интеллект-Системс',
        'status': RawItemStatus.error,
        'created': dt(24, 11),
        'error': 'ConnectionTimeout: источник не ответил за 30 с. '
        'Исчерпаны все 3 попытки.',
    },
    {
        'competitor': 'Интеллект-Системс',
        'status': RawItemStatus.new,
        'created': dt(25, 11),
        'news': [68, 73, 88, 103],
    },
    # ---- СловоГен: сбой сбора + демо ----
    {
        'competitor': 'СловоГен',
        'status': RawItemStatus.error,
        'created': dt(24, 11, 10),
        'error': 'HTTP 403 от источника: сработала защита от парсинга.',
    },
    {
        'competitor': 'СловоГен',
        'status': RawItemStatus.new,
        'created': dt(26, 11, 10),
        'news': [69, 72, 87, 101],
    },
    # ---- СмартАналитика: new → changed, перебор антишума + все фильтры ----
    {
        'competitor': 'СмартАналитика',
        'status': RawItemStatus.new,
        'created': dt(21, 8),
        'drafts': [
            (
                'https://www.cnews.ru/news/smart-old',
                'Старая версия материала о «СмартАналитика»',
                'Позже заменена обновлённой выгрузкой.',
            ),
        ],
    },
    {
        'competitor': 'СмартАналитика',
        'status': RawItemStatus.changed,
        'created': dt(27, 8),
        # Шесть ЧИСТЫХ событий конкурента при лимите 5/неделю (48, 60, 84,
        # 98, 111, 112) — самое незначительное уходит в rejected(noise_limit)
        # на шаге антишума. Плюс по одному образцу на каждый фильтр BP-2:
        # 105, 106 — стоп-слова (спам/реклама); 108 — ложное срабатывание
        # («крейсер»); 109 — чёрный домен (insider-leaks.info).
        'news': [48, 60, 84, 98, 111, 112, 105, 106, 108, 109],
    },
    # ---- Кодариум: демо + стоп-тема (гороскоп) ----
    {
        'competitor': 'Кодариум',
        'status': RawItemStatus.new,
        'created': dt(25, 13),
        'news': [10, 20, 30, 93, 107],
    },
    # ---- МодельОн ----
    {
        'competitor': 'МодельОн',
        'status': RawItemStatus.new,
        'created': dt(25, 14),
        'news': [11, 21, 31, 104],
    },
    # ---- АлгоМаш ----
    {
        'competitor': 'АлгоМаш',
        'status': RawItemStatus.new,
        'created': dt(26, 13),
        'news': [71, 86, 99, 79],
    },
    # ---- НейроТек ----
    {
        'competitor': 'НейроТек',
        'status': RawItemStatus.new,
        'created': dt(26, 14),
        'news': [70, 85, 100],
    },
    # ---- ТехноЛогика ----
    {
        'competitor': 'ТехноЛогика',
        'status': RawItemStatus.new,
        'created': dt(27, 10),
        'news': [45, 55, 65],
    },
]

# --- проверка: сценарий выше покрывает РОВНО те id, что реально принадлежат
#     перечисленным в SCENARIO_COMPETITORS конкурентам — ни одного не забыли,
#     ни одного не задвоили с автогенерацией ниже.
_scenario_ids = {i for snap in SNAPSHOTS for i in snap.get('news', [])}
_expected_ids = {n.id for n in NEWS if n.competitor in SCENARIO_COMPETITORS}
assert _scenario_ids == _expected_ids, (
    f'SNAPSHOTS расходится с news_dataset.csv: '
    f'потеряно {_expected_ids - _scenario_ids}, '
    f'лишнее {_scenario_ids - _expected_ids}'
)

# ============================================================================
#  Остальные конкуренты (по 1-2 новости) — один плоский снимок на каждого,
#  чтобы никто не выпал из справочника без search_task (иначе BP-2 молча
#  пропустит его новости — raw_by_competitor.get(...) is None).
# ============================================================================

_remaining: dict[str, list[int]] = {}
for _news in NEWS:
    if _news.competitor in SCENARIO_COMPETITORS:
        continue
    _remaining.setdefault(_news.competitor, []).append(_news.id)

for _index, (_competitor, _ids) in enumerate(sorted(_remaining.items())):
    SNAPSHOTS.append(
        {
            'competitor': _competitor,
            'status': RawItemStatus.new,
            # Разносим по разным дням/часам июня, чтобы created_at не
            # совпадал случайно (тай-брейк оставлен только для ДатаСинтез).
            'created': dt(1 + _index % 28, 7 + _index % 10, (_index * 7) % 60),
            'news': _ids,
        }
    )


# ============================================================================
#  Этап
# ============================================================================


def build_items(snapshot: dict) -> list[dict]:
    """События снимка: новости из CSV (по id) плюс черновики, если заданы."""
    items = [
        news_item(news, index)
        for index, news in enumerate(by_ids(snapshot.get('news', [])))
    ]
    items.extend(
        draft_item(url, title, text, snapshot['created'].date())
        for url, title, text in snapshot.get('drafts', [])
    )
    return items


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
                else make_raw_data(task_id, name, build_items(snap)),
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

    run_stage('BP-1 (таблица raw_item)', clear, seed)
