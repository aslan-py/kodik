"""Подписи витрины BP-4: код enum'а → готовая к показу строка.

Витрина денормализована и отдаёт BI значения, готовые к отображению:
в колонке priority лежит «П1», а не 'p1'; в tonality — «позитивная»,
а не 'positive'. Сами enum'ы (PriorityLevel, TonalityLevel) живут
в core.enums — это слой хранения; здесь только слой представления.

Маппинги вынесены из pipeline.py по образцу src/bp2/constants.py и являются
ЕДИНСТВЕННЫМ источником этих подписей: их переиспользуют сборка витрины
(src/bp4/pipeline.py) и сидер (core/scripts/seed_all.py).

PRIORITY_FROM_DISPLAY — обратный маппинг («П1» → PriorityLevel.p1). Нужен
там, где читают уже собранную витрину и хотят вернуться к enum'у: BP-5
матчит приоритет строки витрины с правилами маршрутизации, где priority —
это enum, а не подпись.
"""

from core.enums import PriorityLevel, TonalityLevel

PRIORITY_DISPLAY: dict[PriorityLevel, str] = {
    PriorityLevel.p1: 'П1',
    PriorityLevel.p2: 'П2',
    PriorityLevel.p3: 'П3',
    PriorityLevel.p4: 'П4',
}

PRIORITY_FROM_DISPLAY: dict[str, PriorityLevel] = {
    v: k for k, v in PRIORITY_DISPLAY.items()
}

TONALITY_DISPLAY: dict[TonalityLevel, str] = {
    TonalityLevel.positive: 'позитивная',
    TonalityLevel.neutral: 'нейтральная',
    TonalityLevel.negative: 'негативная',
}
