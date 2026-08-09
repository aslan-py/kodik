"""Конвейер BP-2: сырьё raw_item → факты normalized_item.

Очистка, нормализация, дедупликация и фильтрация шума. BP-2 сам читает
raw_data (отвязка от BP-1: то же сырьё можно переразобрать новыми правилами).

Порядок шагов:

  1. отобрать свежие необработанные снимки — select_pending_raw_items (crud)
  2. разбить снимок на события + предочистка — split_items → clean_text
  3. провалидировать событие (типы, парс даты) — RawEventIn (schemas)
  4. имена справочников → id, посчитать dedup_key — normalize_item
  5. отсев по чёрным доменам — is_black_domain
  6. отсев по стоп-словам — match_stop_word (5-6 применяет apply_filters)
  7. записать пачку с дедупом (ON CONFLICT) — upsert_normalized_items (crud)
  8. антишум: лишнее сверх лимита → rejected — reject_over_limit (antinoise)

Оркестратор run_bp2 открывает сессию, один раз грузит справочники и
прогоняет шаги 1-8 в одной транзакции.

Соседние модули: crud.py — БД; schemas.py — валидация; dedup.py — dedup_key;
constants.py — таблицы очистки текста, antinoise.py - валидация шума.

Для простоты ориентации по коду, переходи сразу на  async def run_bp2()
    и внутри данного оркестратора двигайся сверху вниз.
"""

import asyncio
import html
import re
import sys
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime

from core.database import AsyncSessionLocal
from core.enums import NormStatus, RejectReason
from src.bp1.models import Competitor
from src.bp2.antinoise import reject_over_limit
from src.bp2.constants import TextCleanup
from src.bp2.crud import Bp2Crud
from src.bp2.dedup import make_dedup_key
from src.bp2.models import Region, StopWord
from src.bp2.schemas import TITLE_PLACEHOLDER, RawEventIn

# ============================================================================
#  Предочистка текстового поля (вспомогательная)
# ============================================================================


def clean_text(value: object) -> str | None:
    """Предочистка одного текстового поля (гигиена, без потери смысла).

    Сырьё с веб-страниц приходит «грязным»: обрывки HTML-тегов и скриптов,
    HTML-сущности (&nbsp;, &laquo;), управляющие и невидимые символы,
    неразрывные пробелы, табы и переводы строк. Приводим к чистому виду:

    1. вырезаем <script>/<style> вместе с содержимым, затем прочие теги;
    2. декодируем HTML-сущности (&nbsp; → пробел, &laquo; → «);
    3. NFKC — складываем совместимые формы (fullwidth, лигатуры, пробелы);
    4. срезаем управляющие/невидимые символы, экзотические пробелы → \\x20;
    5. схлопываем пробелы/переводы строк в один и обрезаем края.

    Типографику (кавычки, тире) сохраняем: поле идёт в витрину и в промпт
    LLM. Унификация под дедуп/стоп-слова — отдельный слой (norm()).

    Пустой результат (только пробелы / None) → None, чтобы в БД лежал
    честный NULL, а не строка из пробелов. Принимает object: в сыром
    JSON поле может быть числом или None.
    """
    if value is None:
        return None
    s = TextCleanup.HTML_SCRIPT_STYLE.sub(' ', str(value))
    s = TextCleanup.HTML_TAG.sub(' ', s)
    s = html.unescape(s)
    s = unicodedata.normalize('NFKC', s)
    s = s.translate(TextCleanup.CLEAN_TABLE)
    s = re.sub(r'\s+', ' ', s).strip()
    return s or None


# ============================================================================
#  Разбор снимка на события + предочистка
# ============================================================================


def split_items(raw_data: dict) -> list[dict]:
    """Разбить raw_data на список отдельных событий с предочисткой.

    raw_data устроен как {"meta": {...}, "items": [ {...}, ... ]}.
    На каждый объект из items[] переносим контекст из meta (конкурент,
    источник, триггер, id задачи) — дальше по конвейеру он нужен для
    lookup'ов и дедуп-ключа. Текстовые поля прогоняем через clean_text.

    Возвращает список плоских dict'ов (по одному на событие). Если items
    пуст или отсутствует — вернётся пустой список.
    """
    meta = raw_data.get('meta') or {}
    items = raw_data.get('items') or []

    result: list[dict] = []
    for item in items:
        result.append(
            {
                # --- контекст из meta (общий для всей выгрузки) ---
                'search_task_id': meta.get('search_task_id'),
                'source': clean_text(meta.get('source')),
                'competitor': clean_text(meta.get('competitor')),
                'trigger': clean_text(meta.get('trigger')),
                # --- поля самого события (предочищены) ---
                'url': clean_text(item.get('url')),
                'title': clean_text(item.get('title')),
                'text': clean_text(item.get('text')),
                'published_at': clean_text(item.get('published_at')),
                'region': clean_text(item.get('region')),
                'media_name': clean_text(item.get('media_name')),
                # extra — сырые источник-специфичные факты (у hh зарплата),
                # не чистим: это структура, разберём при нормализации.
                'extra': item.get('extra') or {},
            }
        )
    return result


# ============================================================================
#  Нормализация: событие + справочники → строка normalized_item
# ============================================================================


def build_competitor_map(competitors: Sequence[Competitor]) -> dict[str, int]:
    """{имя в нижнем регистре → competitor_id} для lookup по названию."""
    return {c.name.lower(): c.id for c in competitors}


def build_region_map(regions: Sequence[Region]) -> dict[str, int]:
    """{alias → region_id}: разворачиваем name_aliases каждого региона."""
    return {
        alias.lower(): r.id for r in regions for alias in (r.name_aliases or [])
    }


def normalize_item(
    event: RawEventIn,
    *,
    raw_item_id: int,
    competitor_map: dict[str, int],
    region_map: dict[str, int],
    source_map: dict[int, int],
) -> dict:
    """Собрать одну строку normalized_item из события (только ФАКТЫ).

    Сырые имена превращаем в id по готовым картам (competitor/region/source),
    считаем dedup_key единой формулой из dedup.py. По умолчанию status=ok;
    безымянное событие (title == TITLE_PLACEHOLDER) сразу помечаем
    rejected/parse_error. Фильтры (чёрные домены, стоп-слова) — отдельные
    шаги ПОСЛЕ и могут переопределить status.

    Возвращает dict под upsert_normalized_items (created_at/id — на БД).
    """
    published = event.published_at.isoformat() if event.published_at else ''

    status = NormStatus.ok
    reject_reason = None
    if event.title == TITLE_PLACEHOLDER:
        status = NormStatus.rejected
        reject_reason = RejectReason.parse_error

    return {
        'raw_item_id': raw_item_id,
        'competitor_id': competitor_map.get((event.competitor or '').lower()),
        'region_id': region_map.get((event.region or '').lower()),
        'source_id': source_map.get(event.search_task_id),
        'published_at': event.published_at,
        'title': event.title,
        'media_name': event.media_name,
        'media_domain': event.media_domain,
        'url': event.url,
        'text': event.text,
        'extra': event.extra,
        'dedup_key': make_dedup_key(
            event.competitor, event.title, published, event.region
        ),
        'status': status,
        'reject_reason': reject_reason,
    }


# ============================================================================
#  Фильтры отсева (чёрные домены → стоп-слова)
# ============================================================================
#  Предикаты (сработало/нет) + apply_filters, который проставляет status.
#  Короткое замыкание: уже отклонённое дальше не проверяем, сработавший
#  чёрный домен отменяет проверку стоп-слов (см. ABOUT.md, BP-2 п.2-3).


def is_black_domain(media_domain: str | None, black_domains: set[str]) -> bool:
    """Домен публикатора в чёрном списке?"""
    return bool(media_domain) and media_domain in black_domains


def match_stop_word(
    title: str | None,
    text: str | None,
    stop_words: Sequence[StopWord],
) -> RejectReason | None:
    """Первое сработавшее стоп-слово во (title+text) → причина по его type.

    Ищем вхождение фразы (lowercase). reject_reason берём из stop_word.type
    (stop_word / stop_topic / false_positive). Ничего не нашли — None.
    """
    haystack = f'{title or ""} {text or ""}'.lower()
    for sw in stop_words:
        if sw.phrase.lower() in haystack:
            return RejectReason(sw.type.value)
    return None


def apply_filters(
    row: dict,
    *,
    black_domains: set[str],
    stop_words: Sequence[StopWord],
) -> dict:
    """Проставить rejected/reason по фильтрам (мутирует и возвращает row).

    Порядок и короткое замыкание: уже отклонённое (parse_error из
    normalize_item) не трогаем; сработавший чёрный домен отменяет проверку
    стоп-слов. Первая сработавшая причина побеждает.
    """
    if row['status'] == NormStatus.rejected:
        return row
    if is_black_domain(row['media_domain'], black_domains):
        row['status'] = NormStatus.rejected
        row['reject_reason'] = RejectReason.black_domain
        return row
    reason = match_stop_word(row['title'], row['text'], stop_words)
    if reason is not None:
        row['status'] = NormStatus.rejected
        row['reject_reason'] = reason
    return row


# ============================================================================
#  Общая часть конвейера (шаги 2-6): снимки → строки normalized_item
# ============================================================================


def build_normalized_rows(
    raw_items: Sequence,
    *,
    competitor_map: dict[str, int],
    region_map: dict[str, int],
    source_map: dict[int, int],
    black_domains: set[str],
    stop_words: Sequence[StopWord],
) -> list[dict]:
    """Прогнать снимки через split → validate → normalize → filters.

    Общий шаг для run_bp2 в обоих режимах (reparse=False/True) — они
    отличаются только тем, какие raw_items сюда попадают и как
    записывается результат (upsert с update=False/True).
    """
    rows: list[dict] = []
    for raw_item in raw_items:
        for event_dict in split_items(raw_item.raw_data or {}):
            event = RawEventIn.model_validate(event_dict)
            row = normalize_item(
                event,
                raw_item_id=raw_item.id,
                competitor_map=competitor_map,
                region_map=region_map,
                source_map=source_map,
            )
            apply_filters(
                row, black_domains=black_domains, stop_words=stop_words
            )
            rows.append(row)
    return rows


REASONS_COUNTED_BEFORE_WRITE = (
    RejectReason.black_domain,
    RejectReason.stop_word,
    RejectReason.stop_topic,
    RejectReason.false_positive,
    RejectReason.parse_error,
)


def count_rejected_by_reason(rows: Sequence[dict]) -> dict[str, int]:
    """Разбивка отклонённых `rows` по `reject_reason` — для сводки прогона.

    Считает только причины, которые проставляет `normalize_item`/
    `apply_filters` ДО записи в БД. `noise_limit` сюда не входит — это
    отдельный постфактум-проход поверх уже записанных строк (см. run_bp2,
    шаг 8), в `rows` он появиться не может.
    """
    counts = {reason.value: 0 for reason in REASONS_COUNTED_BEFORE_WRITE}
    for row in rows:
        reason = row['reject_reason']
        if reason is not None:
            counts[reason.value] += 1
    return counts


# ============================================================================
#  Оркестратор — весь конвейер BP-2 в один прогон (шаги помечены ниже)
# ============================================================================


async def run_bp2(
    *, reparse: bool = False, raw_item_ids: Sequence[int] | None = None
) -> dict:
    """Один прогон конвейера BP-2: сырьё → normalized_item.

    Открывает сессию, один раз грузит справочники и по каждому событию
    проходит цепочку split_items → RawEventIn → normalize_item →
    apply_filters, копит строки и пишет их одним upsert (дедуп по
    dedup_key). В конце — антишум (reject_over_limit).

    reparse=False (по умолчанию) — обычный инкрементальный прогон: берутся
    только свежие снимки, которых ещё нет в normalized_item
    (select_pending_raw_items), запись идёт с ON CONFLICT DO NOTHING.

    reparse=True — переразбор УЖЕ нормализованных снимков новыми правилами
    (например, поправили стоп-слова или чёрные домены и надо пересчитать
    status/reject_reason без повторного захода на сайт). Берутся все
    свежие снимки или только raw_item_ids (select_reparse_raw_items), запись
    идёт с ON CONFLICT DO UPDATE — существующая строка правится на месте
    (тот же id), дублей и удалений нет. raw_item_ids имеет смысл только
    вместе с reparse=True.

    Антишум (topic_limit) выполняется в обоих режимах, но у него есть
    известное ограничение: reject_over_limit умеет только ОТКЛОНЯТЬ строки
    сверх лимита. Если max_count впоследствии УВЕЛИЧАТ, ранее отклонённые
    (status=rejected, reject_reason=noise_limit) строки автоматически
    обратно в ok не вернутся — операция однонаправленная. Ужесточение
    лимита (max_count уменьшили), наоборот, отработает верно при следующем
    вызове.

    Возвращает сводку прогона: сколько снимков и строк обработано,
    разбивку отклонённых строк по причине (rejected_by_reason —
    black_domain/stop_word/stop_topic/false_positive/parse_error, посчитана
    до записи в БД) и отдельно noise_rejected (постфактум-отсев по лимиту
    шума, см. выше).
    """
    if raw_item_ids is not None and not reparse:
        raise ValueError('raw_item_ids допустим только вместе с reparse=True')

    run_started_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        crud = Bp2Crud(session)

        # Справочники грузим ОДИН раз на весь прогон (не на каждое событие).
        competitor_map = build_competitor_map(await crud.load_competitors())
        region_map = build_region_map(await crud.load_regions())
        source_map = await crud.load_source_ids()
        black_domains = await crud.load_black_domains()
        stop_words = await crud.load_stop_words()
        topic_limits = await crud.load_topic_limits()

        # Шаг 1 — отобрать снимки: свежие необработанные или под переразбор
        if reparse:
            raw_items = await crud.select_reparse_raw_items(raw_item_ids)
        else:
            raw_items = await crud.select_pending_raw_items()

        # Шаги 2-6 — разбить, провалидировать, нормализовать, отфильтровать
        rows = build_normalized_rows(
            raw_items,
            competitor_map=competitor_map,
            region_map=region_map,
            source_map=source_map,
            black_domains=black_domains,
            stop_words=stop_words,
        )

        # Шаг 7 — записать пачку (DO NOTHING на обычном прогоне,
        # DO UPDATE status/reject_reason на переразборе)
        await crud.upsert_normalized_items(rows, update=reparse)
        await session.commit()

        # Шаг 8 — антишум: самые старые сверх лимита → rejected(noise_limit)
        noise_rejected = 0
        if topic_limits:
            noise_rejected = await reject_over_limit(
                session, topic_limits, run_started_at
            )
            await session.commit()

        return {
            'raw_items': len(raw_items),
            'rows': len(rows),
            'rejected_by_reason': count_rejected_by_reason(rows),
            'noise_rejected': noise_rejected,
        }


if __name__ == '__main__':
    # python -m src.bp2.pipeline                  — обычный прогон (только new)
    # python -m src.bp2.pipeline reparse           — переразобрать всё свежее
    # python -m src.bp2.pipeline reparse 157 160   — переразобрать только id
    if len(sys.argv) > 1 and sys.argv[1] == 'reparse':
        ids = [int(x) for x in sys.argv[2:]] or None
        result = asyncio.run(run_bp2(reparse=True, raw_item_ids=ids))
    else:
        result = asyncio.run(run_bp2())
    print(result)
