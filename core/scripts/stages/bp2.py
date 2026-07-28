"""Этап BP-2: нормализованные события (normalized_item) — ФАКТЫ.

Кладёт готовый silver-слой, минуя конвейер очистки. Нужен, когда работаешь
со СЛЕДУЮЩИМ процессом (BP-3 или витриной) и не хочешь каждый раз гонять
BP-2: залил факты одной командой и занимаешься разметкой.

Запуск:
    python -m core.scripts.stages.bp2

Альтернатива — получить те же факты по-настоящему, из сырья:
    python -m core.scripts.stages.bp1
    python -c "import asyncio; from src.bp2.pipeline import run_bp2; \\
               print(asyncio.run(run_bp2()))"

Набор курируемый: восемь чистых событий (status=ok) плюс по одной строке
на КАЖДУЮ причину отсева — чтобы было видно, как выглядит отбракованное
и что оно не уходит дальше по конвейеру. Плюс событие без региона:
region_id = NULL проверяет, что LEFT JOIN в витрине не роняет сборку.

Требует залитых справочников (stages/dictionaries) и сырья (stages/bp1):
каждая строка ссылается на raw_item — это drill-down до исходника.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import NormStatus, RejectReason
from core.scripts.stages.cascade import clear_from
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.dedup import make_dedup_key
from src.bp2.models import NormalizedItem, Region

# ============================================================================
#  Данные: одно событие = одна строка silver-слоя
# ============================================================================
#  region указывается КАНОНИЧЕСКИМ именем (name_display) — по нему берётся
#  region_id. None означает «регион не определён», это валидный случай.

NORMALIZED: list[dict] = [
    # ---- чистые события (идут в BP-3) ----
    {
        'competitor': 'Топ-Сервис',
        'region': 'Калуга',
        'published_at': '2026-06-25',
        'title': 'Калужской транспортной прокуратурой выявлены нарушения '
        'закона о защите прав пассажиров',
        'media_name': 'Big-news.ru, Москва',
        'media_domain': 'big-news.ru',
        'url': 'https://big-news.ru/kaluga/12045',
        'text': 'Проверка показала нарушения. «Топ-Сервис» получил '
        'представление.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'Виво Маркет',
        'region': 'Волгоград',
        'published_at': '2026-06-27',
        'title': 'День широко распахнутых дверей и кешбэк во благо',
        'media_name': 'Forbes, Москва',
        'media_domain': 'forbes.ru',
        'url': 'https://www.forbes.ru/biznes/456-den',
        'text': 'Виво Маркет провёл акцию для покупателей.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'Комбинат питания Иркутска',
        'region': 'Иркутск',
        'published_at': '2026-06-24',
        'title': '35 лет со вкусом и качеством от Комбината питания',
        'media_name': 'Аргументы недели',
        'media_domain': 'argumenti.ru',
        'url': 'https://argumenti.ru/irkutsk/2026/06/35let',
        'text': 'Предприятие отмечает юбилей.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'Комбинат школьного питания Сургута',
        'region': 'Сургут',
        'published_at': '2026-06-23',
        'title': 'Сургут готовит реформу школьного питания: '
        '55% еды выбрасывается',
        'media_name': 'Сургутская трибуна',
        'media_domain': 'ugra-news.ru',
        'url': 'https://ugra-news.ru/surgut/reforma',
        'text': 'Власти обсуждают проблему пищевых отходов.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'Деп. продовольствия и соцпитания Казани',
        'region': 'Казань',
        'published_at': '2026-06-22',
        'title': 'С начала года свыше 600 школьников посетили '
        'городские предприятия',
        'media_name': 'kzn.ru',
        'media_domain': 'kzn.ru',
        'url': 'https://www.kzn.ru/meta/news/600',
        'text': 'Экскурсии организованы департаментом питания.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'Комбинат соц. питания «Охта»',
        'region': 'Санкт-Петербург',
        'published_at': '2026-06-23',
        'title': 'В Петербурге определили лучшие школьные столовые',
        'media_name': 'БезФормата СПб',
        'media_domain': 'spb.bezformata.com',
        'url': 'https://spb.bezformata.com/stolovye',
        'text': 'Комбинат «Охта» вошёл в число лучших.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'СКС',
        'region': 'Самара',
        'published_at': '2026-06-25',
        'title': 'Глава Самары проверил ход реконструкции коммунальных сетей',
        'media_name': 'samadm.ru',
        'media_domain': 'samadm.ru',
        'url': 'https://samadm.ru/news/rekonstrukciya',
        'text': 'Работы ведёт СКС.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    {
        'competitor': 'СКС',
        'region': 'Самара',
        'published_at': '2026-06-25',
        'title': 'Более 1,5 млрд руб. долга накопили жители Самары за воду',
        'media_name': 'Самара 450',
        'media_domain': 'samara450.ru',
        'url': 'https://samara450.ru/dolg',
        'text': 'Задолженность перед ресурсником СКС.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    # ---- событие без региона: region_id = NULL (валидный случай) ----
    {
        'competitor': 'МУП «Школьное питание»',
        'region': None,
        'published_at': '2026-06-25',
        'title': 'Бывшему вице-мэру второй раз смягчили меру пресечения',
        'media_name': 'Рамблер/новости',
        'media_domain': 'news.rambler.ru',
        'url': 'https://news.rambler.ru/incident/54321',
        'text': 'Суд смягчил меру пресечения фигуранту, связанному с МУП.',
        'status': NormStatus.ok,
        'reject_reason': None,
    },
    # ---- отсев: по одной строке на каждую причину ----
    {
        'competitor': 'Мусороуборочная компания',
        'region': None,
        'published_at': '2026-06-22',
        'title': '«Ночной губернатор» вызван на допрос',
        'media_name': 'critics24.com (Киев)',
        'media_domain': 'critics24.com',
        'url': 'https://critics24.com/kiev/gubernator',
        'text': 'Скандальная публикация о деятельности компании.',
        'status': NormStatus.rejected,
        'reject_reason': RejectReason.black_domain,
    },
    {
        'competitor': 'Виво Маркет',
        'region': 'Волгоград',
        'published_at': '2026-06-26',
        'title': 'Скидки недели в магазинах сети',
        'media_name': 'ВолгаПромЭксперт',
        'media_domain': 'volgaprom.expert',
        'url': 'https://volgaprom.expert/news/790',
        'text': 'Это реклама акции для покупателей.',
        'status': NormStatus.rejected,
        'reject_reason': RejectReason.stop_word,
    },
    {
        'competitor': 'Комбинат питания Иркутска',
        'region': 'Иркутск',
        'published_at': '2026-06-24',
        'title': 'Гороскоп на неделю для жителей Иркутска',
        'media_name': 'КП-Иркутск',
        'media_domain': 'www.kp.ru',
        'url': 'https://www.kp.ru/irkutsk/goroskop',
        'text': 'Что обещают звёзды.',
        'status': NormStatus.rejected,
        'reject_reason': RejectReason.stop_topic,
    },
    {
        'competitor': 'Деп. продовольствия и соцпитания Казани',
        'region': 'Казань',
        'published_at': '2026-06-22',
        'title': 'Бегемот в зоопарке Казани отметил день рождения',
        'media_name': 'kzn.ru',
        'media_domain': 'kzn.ru',
        'url': 'https://www.kzn.ru/meta/news/zoo',
        'text': 'К деятельности конкурента отношения не имеет.',
        'status': NormStatus.rejected,
        'reject_reason': RejectReason.false_positive,
    },
    {
        'competitor': 'Виво Маркет',
        'region': 'Волгоград',
        'published_at': '2026-06-26',
        'title': 'без заголовка',
        'media_name': 'V1.ru, Волгоград',
        'media_domain': 'v1.ru',
        'url': 'https://v1.ru/text/business/2026/06/26/noname',
        'text': 'Текст без заголовка — парсер не смог достать title.',
        'status': NormStatus.rejected,
        'reject_reason': RejectReason.parse_error,
    },
    {
        'competitor': 'Комбинат питания Иркутска',
        'region': 'Иркутск',
        'published_at': '2026-06-26',
        'title': 'Иркутское предприятие ТН-Ангара внедрит '
        'бережливые технологии',
        'media_name': 'Ток Медиа',
        'media_domain': 'tokmedia.ru',
        'url': 'https://tokmedia.ru/tn-angara',
        'text': 'Оптимизация процессов на производстве.',
        'status': NormStatus.rejected,
        'reject_reason': RejectReason.noise_limit,
    },
]


# ============================================================================
#  Этап
# ============================================================================


async def seed(session: AsyncSession) -> int:
    """Залить нормализованные события.

    Каждая строка привязывается к первому НЕ-error снимку своего конкурента
    (drill-down до сырья). dedup_key считается той же формулой, что и в
    конвейере — make_dedup_key из src/bp2/dedup.py, чтобы фабрикованные
    строки и настоящий прогон BP-2 не создавали дублей друг для друга.
    """
    competitors = {
        c.name: c.id
        for c in (await session.execute(select(Competitor))).scalars()
    }
    regions = {
        r.name_display: r.id
        for r in (await session.execute(select(Region))).scalars()
    }
    source_id = await session.scalar(select(Source.id).limit(1))

    # первый успешный снимок каждого конкурента
    raw_by_competitor: dict[int, int] = {}
    rows = await session.execute(
        select(SearchTask.competitor_id, RawItem.id)
        .join(RawItem, RawItem.search_task_id == SearchTask.id)
        .where(RawItem.raw_data.is_not(None))
        .order_by(RawItem.id)
    )
    for competitor_id, raw_id in rows:
        raw_by_competitor.setdefault(competitor_id, raw_id)

    if not raw_by_competitor:
        raise RuntimeError(
            'Нет сырья — не к чему привязать факты. '
            'Сначала: python -m core.scripts.stages.bp1'
        )

    added = 0
    for row in NORMALIZED:
        competitor_id = competitors.get(row['competitor'])
        raw_item_id = raw_by_competitor.get(competitor_id)
        if raw_item_id is None:
            continue
        session.add(
            NormalizedItem(
                raw_item_id=raw_item_id,
                competitor_id=competitor_id,
                region_id=regions.get(row['region']),
                source_id=source_id,
                published_at=date.fromisoformat(row['published_at']),
                title=row['title'],
                media_name=row['media_name'],
                media_domain=row['media_domain'],
                url=row['url'],
                text=row['text'],
                extra=None,
                dedup_key=make_dedup_key(
                    row['competitor'],
                    row['title'],
                    row['published_at'],
                    row['region'],
                ),
                status=row['status'],
                reject_reason=row['reject_reason'],
            )
        )
        added += 1

    await session.flush()
    return added


async def clear(session: AsyncSession) -> int:
    """Снести факты и всё, что на них построено (разметку, витрину, алерты)."""
    return await clear_from(session, NormalizedItem)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-2 (факты)', clear, seed)
