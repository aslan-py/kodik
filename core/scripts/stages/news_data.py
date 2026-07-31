"""Демо-новости: единый источник контента для этапов BP-1, BP-2 и BP-3.

Раньше один и тот же текст жил в трёх местах: «грязным» в сырье (bp1),
чистым в фактах (bp2) и по url в разметке (bp3) — три списка, которые
приходилось править синхронно. Теперь новость описывается ОДИН раз строкой
в core/scripts/scripts_data/news_dataset.csv, а этапы берут из неё каждый
свою часть:

    bp1 — url, title, text, регион, дата, СМИ (портит их перед укладкой);
    bp2 — те же поля начисто + reject (каким фильтром событие отсеяно);
    bp3 — category, priority, tonality, department, action, comment.

Добавить новость в демо = дописать строку в CSV и упомянуть её id в
снимке SNAPSHOTS (core/scripts/stages/bp1.py). Ничего больше.

Колонки CSV:

    id            номер строки, по нему на новость ссылаются снимки bp1
    competitor    имя конкурента как в справочнике competitor
    region        каноническое имя города (пусто = регион не определён)
    published_at  дата публикации, ISO
    media_name    человекочитаемое имя СМИ
    url           ссылка на публикацию (из неё выводится media_domain)
    title, text   заголовок и текст НАЧИСТО — как их должен отдать BP-2
    category      имя категории из справочника category (пусто у отсеянных)
    priority      p1/p2/p3, tonality — positive/neutral/negative
    department    ответственный отдел, action — что делаем, comment — вывод
    reject        пусто = чистое событие; иначе причина отсева (RejectReason)

Отсеянное фильтрами (чёрный домен, стоп-слова, parse_error) до LLM не
доходит — колонки блока BP-3 у таких строк пустые. Исключение —
reject=noise_limit: само событие нормальное, его вытеснил лимит антишума,
поэтому разметка у него заполнена (настоящий прогон BP-2 может вытеснить
другую строку, и тогда эта пойдёт в BP-3 со своей разметкой).
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from core.enums import PriorityLevel, RejectReason, TonalityLevel

NEWS_FILE = Path(__file__).parents[1] / 'scripts_data' / 'news_dataset.csv'


@dataclass(frozen=True, slots=True)
class News:
    """Одна демо-новость: контент + ожидаемый исход фильтров + разметка."""

    id: int
    competitor: str
    region: str | None
    published_at: date
    media_name: str
    url: str
    title: str
    text: str
    category: str | None
    priority: PriorityLevel | None
    tonality: TonalityLevel | None
    department: str | None
    action: str | None
    comment: str | None
    reject: RejectReason | None

    @property
    def is_clean(self) -> bool:
        """Событие проходит фильтры BP-2 и доходит до разметки."""
        return self.reject is None


def _value(row: dict[str, str], key: str) -> str | None:
    """Значение колонки: пустая ячейка CSV → None (в БД это NULL)."""
    return (row.get(key) or '').strip() or None


def _to_news(row: dict[str, str]) -> News:
    """Строка CSV → News (пустые ячейки → None, enum'ы по значению)."""
    priority = _value(row, 'priority')
    tonality = _value(row, 'tonality')
    reject = _value(row, 'reject')
    return News(
        id=int(row['id']),
        competitor=row['competitor'].strip(),
        region=_value(row, 'region'),
        published_at=date.fromisoformat(row['published_at'].strip()),
        media_name=row['media_name'].strip(),
        url=row['url'].strip(),
        # title пустой ТОЛЬКО у события с parse_error — так и задумано:
        # BP-2 подменит его заглушкой TITLE_PLACEHOLDER.
        title=row['title'].strip(),
        text=row['text'].strip(),
        category=_value(row, 'category'),
        priority=PriorityLevel(priority) if priority else None,
        tonality=TonalityLevel(tonality) if tonality else None,
        department=_value(row, 'department'),
        action=_value(row, 'action'),
        comment=_value(row, 'comment'),
        reject=RejectReason(reject) if reject else None,
    )


def load_news() -> list[News]:
    """Прочитать демо-набор из CSV в порядке строк файла."""
    with open(NEWS_FILE, encoding='utf-8-sig', newline='') as f:
        return [_to_news(row) for row in csv.DictReader(f, delimiter=';')]


# Набор грузится один раз на импорт — файл маленький, а этапы обращаются
# к нему многократно (bp1 по id, bp2/bp3 сплошным проходом).
NEWS: list[News] = load_news()
BY_ID: dict[int, News] = {n.id: n for n in NEWS}


def by_ids(ids: list[int]) -> list[News]:
    """Новости по номерам строк CSV, в порядке переданных id."""
    return [BY_ID[i] for i in ids]
