"""Минимальная заглушка этапа 1 пайплайна: raw_item.

В отличие от `core/scripts/stages/bp1.py` (полный демо-датасет — ~49
конкурентов, 100+ новостей, нужен для наполнения BI и демонстрации
фильтров BP-2), эта заглушка заливает ФИКСИРОВАННЫЙ минимальный набор:
один конкурент, один снимок, шесть новостей со спроектированными
исходами по всему конвейеру (см. `openspec/changes/add-simple-test-
dictionaries/design.md` за точным раскладом и обоснованием):

- №1 (`test1-alert-source.ru`) — однозначный сигнал категории «надзорная
  санкция и юридический риск» (прокуратура, проверка, нарушения),
  доходит до BP-3 с приоритетом П1 и содержит маркер-слово для
  алертинга BP-5;
- №2 (`compromat-test.ru`) — домен в чёрном списке, отсеивается в BP-2;
- №3 (`test3-source.ru`) — содержит стоп-слово «промокод», отсеивается
  в BP-2;
- №4, №5, №6 (`shared-site-test.ru`, один и тот же домен) — под антишум
  BP-2 (`topic_limit`, `max_count=1`): ровно одна выживает, две
  отклоняются. На практике (два прогона подряд) стабильно выживает
  №4 — первая по порядку вставки в этом снимке; не гарантировано
  спецификацией SQL (см. design.md, Risks), но воспроизводится.

Итог после BP-2: из 6 новостей до `status=ok` доходят ровно 2, одна из
них (№1) — гарантированно с приоритетом П1 после BP-3.

Справочники под этот сценарий (чёрный домен, стоп-слово, лимит
антишума, тип события, маршрутизация) заливает отдельный скрипт
`core/scripts/stages/simple_dictionaries.py` — запускать до этой
заглушки.

`clear()` сносит сырьё (`raw_item`) и всё, что на нём построено, но
НЕ трогает саму задачу сбора (`search_task`) — это конфигурация,
которую ведёт аналитик через админку/API, а не данные конвейера.
`seed()` переиспользует подходящую существующую задачу, если она уже
заведена, и создаёт свою только при её отсутствии.

Нужна для дешёвой сквозной проверки этапов 2-7 через пайплайн/админку —
LLM-модули BP-3 и Tavily-поиск BP-3/BP-7 стоят реальных токенов и
лимитов внешних API, гонять их на полном датасете (~49 конкурентов)
при обычной проверке «пайплайн в принципе работает» неоправданно
дорого. `bp1.py` эта заглушка не переиспользует и не заменяет — обе
команды сосуществуют, каждая под свою задачу.

Конкурент берётся ЛЮБОЙ активный из уже залитого справочника (не
конкретное имя из демо-датасета) — справочники в реальном проекте
курируются вручную и состав конкурентов может не совпадать с полным
демо-набором (`core/scripts/stages/dictionaries.py`). Текст новостей —
синтетический, не привязан к конкретному конкуренту из
`news_data.py`/CSV, чтобы стаб не зависел от того, какие именно
конкуренты сейчас есть в БД.

Запуск (как самостоятельный сидер):
    python -m core.scripts.stages.bp1_stub

Через реестр пайплайна дёргается из `core/pipeline/registry.py`
(заглушка этапа 1).
"""

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import RawItemStatus
from core.scripts.stages.cascade import clear_from
from core.scripts.stages.dictionaries import SOURCE_NAME
from src.bp1.models import Competitor, RawItem, SearchTask, Source

# Шесть синтетических новостей — каждая со спроектированным исходом в
# BP-2/BP-3 (см. докстринг модуля). title/text содержат «{competitor}» —
# заголовок/текст форматируются с именем конкурента динамически (_item()),
# сами новости не привязаны к конкретному конкуренту из демо-датасета.
STUB_NEWS = (
    {
        # №1 — «надзорная санкция и юридический риск» → П1, алертинг.
        'title': 'Прокуратура начала проверку «{competitor}» из-за нарушений',
        'text': (
            'Прокуратура региона начала внеплановую проверку компании '
            '«{competitor}» после жалоб клиентов. По предварительным '
            'данным, в ходе проверки выявлены нарушения в работе сервиса, '
            'материалы переданы в надзорные органы.'
        ),
        'published_at': '2026-06-01',
        'region': None,
        'media_name': 'Test1 Alert Source',
        'url': 'https://test1-alert-source.ru/news/stub-1',
    },
    {
        # №2 — домен в чёрном списке (compromat-test.ru) → отсев в BP-2.
        'title': 'Партнёрство «{competitor}» с логистическим оператором',
        'text': (
            'Компания «{competitor}» объявила о партнёрстве с крупным '
            'логистическим оператором. Стороны рассчитывают расширить '
            'географию поставок и ускорить доставку заказов.'
        ),
        'published_at': '2026-06-02',
        'region': None,
        'media_name': 'Compromat Test',
        'url': 'https://compromat-test.ru/news/stub-2',
    },
    {
        # №3 — стоп-слово «промокод» → отсев в BP-2.
        'title': 'Специальный промокод на скидку от партнёра «{competitor}»',
        'text': (
            'Партнёр компании «{competitor}» запустил акцию с промокодом '
            'на скидку для новых клиентов. Промокод действует ограниченное '
            'время и распространяется на весь ассортимент.'
        ),
        'published_at': '2026-06-03',
        'region': None,
        'media_name': 'Test3 Source',
        'url': 'https://test3-source.ru/news/stub-3',
    },
    {
        # №4 — общий домен с №5/№6 → антишум (max_count=1) отсеет две из трёх.
        'title': '«{competitor}» представила обновление продукта',
        'text': (
            'Компания «{competitor}» выпустила обновление флагманского '
            'продукта с новыми функциями. Разработчики отмечают рост '
            'производительности и улучшенный интерфейс.'
        ),
        'published_at': '2026-06-04',
        'region': None,
        'media_name': 'Shared Site Test',
        'url': 'https://shared-site-test.ru/news/stub-4',
    },
    {
        # №5 — общий домен с №4/№6 → антишум.
        'title': 'Сотрудники «{competitor}» выступили на конференции',
        'text': (
            'Представители «{competitor}» выступили с докладами на '
            'отраслевой конференции. Они поделились опытом внедрения '
            'новых технологий и планами развития.'
        ),
        'published_at': '2026-06-05',
        'region': None,
        'media_name': 'Shared Site Test',
        'url': 'https://shared-site-test.ru/news/stub-5',
    },
    {
        # №6 — общий домен с №4/№5 → антишум.
        'title': '«{competitor}» подвела итоги квартала',
        'text': (
            'Компания «{competitor}» опубликовала итоги очередного '
            'квартала. Показатели выручки и клиентской базы продолжают '
            'расти.'
        ),
        'published_at': '2026-06-06',
        'region': None,
        'media_name': 'Shared Site Test',
        'url': 'https://shared-site-test.ru/news/stub-6',
    },
)


def _item(news: dict, competitor_name: str) -> dict:
    """Один объект `raw_data.items[]` — title/text форматируются именем
    конкурента, чтобы BP-3/детекторы ниже по конвейеру видели осмысленный
    текст."""
    return {
        'url': news['url'],
        'title': news['title'].format(competitor=competitor_name),
        'text': news['text'].format(competitor=competitor_name),
        'published_at': news['published_at'],
        'region': news['region'],
        'media_name': news['media_name'],
        'extra': {},
    }


async def seed(session: AsyncSession) -> int:
    """Задача сбора (переиспользуется, если уже есть) + один `raw_item`
    с шестью новостями.

    Конкурент — первый попавшийся активный из справочника (не жёстко
    заданное имя): справочники курируются вручную, состав конкурентов
    в конкретной БД может не совпадать с полным демо-набором.

    Задача сбора ищется по (competitor_id, source_id, trigger_id=None) —
    ровно тому натуральному ключу, что защищён partial unique index
    `uq_search_task_no_trigger` (src/bp1/models.py). Слепая вставка на
    повторный запуск упала бы на этом индексе теперь, когда clear() ниже
    задачу сбора больше не сносит.
    """
    competitor = await session.scalar(
        select(Competitor).where(Competitor.is_active).limit(1)
    )
    source_id = await session.scalar(
        select(Source.id).where(Source.name == SOURCE_NAME)
    )
    if competitor is None or source_id is None:
        raise RuntimeError(
            'Справочники не залиты — нет активного конкурента/источника. '
            'Сначала: python -m core.scripts.stages.dictionaries'
        )

    task = await session.scalar(
        select(SearchTask).where(
            SearchTask.competitor_id == competitor.id,
            SearchTask.source_id == source_id,
            SearchTask.trigger_id.is_(None),
        )
    )
    if task is None:
        task = SearchTask(
            competitor_id=competitor.id, source_id=source_id, trigger_id=None
        )
        session.add(task)
        await session.flush()

    created = datetime.now(UTC)
    raw_data = {
        'meta': {
            'search_task_id': task.id,
            'source': SOURCE_NAME,
            'competitor': competitor.name,
            'trigger': None,
            'source_request_url': f'{SOURCE_NAME}/?text={competitor.name}',
            'fetched_at': created.isoformat(),
        },
        'items': [_item(news, competitor.name) for news in STUB_NEWS],
    }
    session.add(
        RawItem(
            search_task_id=task.id,
            status=RawItemStatus.new,
            content_hash=sha256(
                f'{competitor.name}:{created.isoformat()}'.encode()
            ).hexdigest(),
            raw_data=raw_data,
            html_file_path=f'/snapshots/{task.id}/{created:%Y-%m-%dT%H-%M}.html',
            source_request_url=f'{SOURCE_NAME}/?text={competitor.name}',
        )
    )
    return 1


async def clear(session: AsyncSession) -> int:
    """Снести сырьё и всё, что на нём построено — НЕ задачу сбора.

    Задача сбора (`search_task`) — конфигурация, которую ведёт аналитик
    через админку/API, а не данные конвейера: снести её значило бы
    потерять чужую ручную настройку при каждом запуске заглушки.
    `clear_from(session, RawItem)` сносит сырьё и все слои, построенные
    на нём (normalized_item, categorized_event, showcase_event, alert,
    action_item), оставляя search_task нетронутым.
    """
    return await clear_from(session, RawItem)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-1 stub (минимальная заглушка raw_item)', clear, seed)
