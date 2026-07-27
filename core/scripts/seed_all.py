"""Единый сидинг тестовых данных по всему пайплайну BP-1…BP-6.

Запуск (из любого места):
    python -m core.scripts.seed_all
"""

import asyncio
import hashlib
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from core.enums import (  # noqa: E402
    ActionStatus,
    AlertStatus,
    DeliveryMode,
    NormStatus,
    PriorityLevel,
    RawItemStatus,
    RejectReason,
    StopType,
    TonalityLevel,
)
from src.bp1.models import (  # noqa: E402
    Competitor,
    RawItem,
    SearchTask,
    Source,
    Trigger,
)
from src.bp2.dedup import make_dedup_key  # noqa: E402
from src.bp2.models import (  # noqa: E402
    BlackDomain,
    NormalizedItem,
    Region,
    StopWord,
    TopicLimit,
)
from src.bp3.models import (  # noqa: E402
    CategorizedEvent,
    Category,
    Department,
)
from src.bp4.models import ShowcaseEvent  # noqa: E402
from src.bp5.models import (  # noqa: E402
    Alert,
    Channel,
    EventType,
    RoutingRule,
)
from src.bp6.models import ActionItem  # noqa: E402

CITIES_FILE = PROJECT_ROOT / 'src' / 'bp2' / 'files' / 'cities.json'

# Единственный источник демо — новостной агрегатор (его «парсим»).
# name источника = URL, откуда парсим (а не человекочитаемое имя).
SOURCE_NAME = 'https://newssearch.yandex.ru'

# ============================================================================
#  СПРАВОЧНИКИ — статические данные
# ============================================================================

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

TRIGGERS = [
    {'keyword': 'школьное питание'},
    {'keyword': 'тендер'},
    {'keyword': 'прокуратура'},
]

# domain = полный ХОСТ как в ссылке, БЕЗ схемы (https://) и пути — именно
# так его отдаёт urlparse(items[].url).netloc, по которому идёт сверка в BP-2.
# С поддоменом, если публикатор сидит на поддомене (напр. spb.bezformata.com).
BLACK_DOMAINS = [
    {'domain': 'critics24.com', 'reason': 'Заказной/компрометирующий (Киев)'},
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
        'phrase': 'бегемот в зоопарке',
        'type': StopType.false_positive,
        'note': 'Ложное срабатывание по конкуренту «Бегемот» (животное)',
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
    'надзорная санкция и юридический риск',
    'репутационный риск',
    'PR-активность конкурента',
    'системная проблема (возможность для входа)',
    'признание качества и конкурсы',
    'косвенное упоминание',
    'информационный шум',
]

DEPARTMENTS = ['PR', 'Тендеры', 'Юристы', 'Аналитика', 'Маркетинг']

EVENT_TYPES = [
    {
        'name': 'судебный/надзорный риск',
        'keywords': 'прокуратура, суд, иск, нарушения, надзор',
    },
    {
        'name': 'выигранный тендер',
        'keywords': 'тендер, контракт, закупка, аукцион',
    },
    {'name': 'активный наём', 'keywords': 'вакансия, наём, набор персонала'},
    {
        'name': 'расширение',
        'keywords': 'расширение, открытие, новый объект, реконструкция',
    },
    {
        'name': 'закрытие объекта',
        'keywords': 'закрытие, банкротство, ликвидация',
    },
]

CHANNELS = ['telegram', 'email']

# (тип, приоритет, отдел, канал, режим)
ROUTING = [
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Юристы',
        'telegram',
        DeliveryMode.instant,
    ),
    (
        'судебный/надзорный риск',
        PriorityLevel.p1,
        'Юристы',
        'email',
        DeliveryMode.instant,
    ),
    (
        'выигранный тендер',
        PriorityLevel.p2,
        'Тендеры',
        'email',
        DeliveryMode.digest,
    ),
    ('расширение', PriorityLevel.p3, 'Аналитика', 'email', DeliveryMode.digest),
]


# ============================================================================
#  ДАННЫЕ — сырьё BP-1 (грязные новости по конкурентам)
# ============================================================================

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
                'published_at': '25.06.2026',
                'region': 'Калуга',
                'media_name': 'Big-news.ru, Москва',
            },
            {
                'url': 'https://big-news.ru/kaluga/12046',
                'title': '…нарушения законодательства о защите прав '
                'пассажиров ж/д транспорта',
                'text': 'Продолжение темы&mdash;прокуратура выявила '
                'нарушения у перевозчика.',
                'published_at': '25 июня 2026 г.',
                'region': '  калуга ',
                'media_name': 'Big-news.ru, Москва',
            },
            {
                'url': 'https://www.cnews.ru/news/2026/06/24/conf',
                'title': 'Конференция CNews &laquo;Оптимизация цифровой '
                'инфраструктуры 2026&raquo;',
                'text': 'Топ-Сервис выступил партнёром конференции.',
                'published_at': '24.06.2026',
                'region': 'Москва',
                'media_name': 'CNews.ru',
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
                'published_at': '25.06.2026',
                'region': 'Нефтеюганск',
                'media_name': 'Рамблер/новости',
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
                'published_at': '25.06.2026',
                'region': 'Волгоград',
                'media_name': 'V1.ru, Волгоград',
            },
            {
                'url': 'https://www.forbes.ru/biznes/456-den',
                'title': 'День широко распахнутых дверей '
                'и кешбэк во&nbsp;благо',
                'text': '<b>Виво Маркет</b> провёл акцию для покупателей.',
                'published_at': '27.06.2026',
                'region': 'ВОЛГОГРАД',
                'media_name': 'Forbes, Москва',
            },
            {
                'url': 'https://volgaprom.expert/news/789',
                'title': 'VR-очки, дегустация, карта желаний: ярмарка '
                'вакансий Волгограда',
                'text': 'Виво Маркет представил стенд на ярмарке.',
                'published_at': '23.06.2026',
                'region': 'г. Волгоград',
                'media_name': 'ВолгаПромЭксперт',
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
                'published_at': '24.06.2026',
                'region': 'Иркутск',
                'media_name': 'Аргументы недели',
            },
            {
                'url': 'https://www.kp.ru/irkutsk/recipe',
                'title': 'Поделитесь рецептом',
                'text': 'Комбинат питания запустил конкурс рецептов.',
                'published_at': '23.06.2026',
                'region': 'иркутск',
                'media_name': 'КП-Иркутск',
            },
            {
                'url': 'https://irksib.ru/2026/06/22/kuhnya',
                'title': 'Детская молочная кухня Иркутска: роботизация '
                'и поставки с сентября',
                'text': 'Модернизация производства детского питания.',
                'published_at': '2026-06-22',
                'region': 'Иркутск ',
                'media_name': 'Irksib.ru',
            },
            {
                'url': 'https://dairynews.today/irkutsk/assort',
                'title': 'Детская молочная кухня Иркутска расширяет '
                'ассортимент',
                'text': 'В линейке появились новые позиции.',
                'published_at': '22.06.26',
                'region': 'Иркутск',
                'media_name': 'ДэйриНьюс',
            },
            {
                'url': 'https://tokmedia.ru/tn-angara',
                'title': 'Иркутское предприятие ТН-Ангара внедрит '
                'бережливые технологии',
                'text': 'Оптимизация процессов на производстве.',
                'published_at': '26 июня 2026',
                'region': 'Иркутск',
                'media_name': 'Ток Медиа',
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
                'published_at': '23.06.2026',
                'region': 'Сургут',
                'media_name': 'Сургутская трибуна',
            },
            {
                'url': 'https://siapress.ru/news/pitanie',
                'title': 'В школах Сургута хотят изменить систему питания',
                'text': 'Обсуждается новая модель организации питания.',
                'published_at': '23.06.2026',
                'region': 'Сургут ',
                'media_name': 'СИА-Пресс',
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
                'published_at': '22.06.2026',
                'region': 'Казань',
                'media_name': 'kzn.ru',
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
                'published_at': '23.06.2026',
                'region': 'СПб',
                'media_name': 'БезФормата СПб',
            },
        ],
    ),
    (
        'Мусороуборочная компания',
        [
            # critics24.com (Киев) — заказной/компрометирующий ресурс,
            # он же в black_domain. Регион «Украина» не резолвится.
            {
                'url': 'https://critics24.com/kiev/gubernator',
                'title': '&laquo;Ночной губернатор&raquo; вызван на допрос',
                'text': 'Скандальная публикация о деятельности компании.',
                'published_at': '22.06.2026',
                'region': 'Украина',
                'media_name': 'critics24.com (Киев)',
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
                'published_at': '25.06.2026',
                'region': 'Самара',
                'media_name': 'samadm.ru',
            },
            {
                'url': 'https://63.ru/text/gorod/2026/06/23/torez',
                'title': 'В Самаре закрыто движение по ул. Мориса Тореза',
                'text': 'Причина — ремонт сетей СКС.',
                'published_at': '23.06.2026',
                'region': 'самара',
                'media_name': '63.ru',
            },
            {
                'url': 'https://samara450.ru/dolg',
                'title': 'Более 1,5 млрд руб. долга накопили жители '
                'Самары за воду',
                'text': 'Задолженность перед ресурсником СКС.',
                'published_at': '25.06.2026',
                'region': 'Самара',
                'media_name': 'Самара 450',
            },
        ],
    ),
]


# ============================================================================
#  ДАННЫЕ — курируемый silver-слой (normalized_item)
# ============================================================================

NORMALIZED: list[dict] = [
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
    # --- Пример отсева по чёрному домену (critics24.com) ---
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
]


# ============================================================================
#  ДАННЫЕ — разметка ok-событий (gold-слой). Ключ — url из NORMALIZED.
# ============================================================================

MARKUP: dict[str, dict] = {
    'https://big-news.ru/kaluga/12045': {
        'priority': PriorityLevel.p1,
        'category': 'надзорная санкция и юридический риск',
        'tonality': TonalityLevel.negative,
        'department': 'Юристы',
        'action': 'Подготовить юридическую позицию и оценить риски',
        'comment': 'Надзорный риск: представление прокуратуры',
    },
    'https://www.forbes.ru/biznes/456-den': {
        'priority': PriorityLevel.p2,
        'category': 'PR-активность конкурента',
        'tonality': TonalityLevel.positive,
        'department': 'PR',
        'action': 'Подготовить ответный PR-кейс',
        'comment': 'Активная промо-акция конкурента',
    },
    'https://argumenti.ru/irkutsk/2026/06/35let': {
        'priority': PriorityLevel.p3,
        'category': 'PR-активность конкурента',
        'tonality': TonalityLevel.positive,
        'department': 'PR',
        'action': None,
        'comment': 'Юбилейная активность, к сведению',
    },
    'https://ugra-news.ru/surgut/reforma': {
        'priority': PriorityLevel.p2,
        'category': 'системная проблема (возможность для входа)',
        'tonality': TonalityLevel.negative,
        'department': 'Аналитика',
        'action': 'Оценить возможность входа на рынок Сургута',
        'comment': 'Системная проблема у конкурента — окно возможностей',
    },
    'https://www.kzn.ru/meta/news/600': {
        'priority': PriorityLevel.p3,
        'category': 'косвенное упоминание',
        'tonality': TonalityLevel.neutral,
        'department': 'Аналитика',
        'action': None,
        'comment': 'Косвенное упоминание, фоновая активность',
    },
    'https://spb.bezformata.com/stolovye': {
        'priority': PriorityLevel.p3,
        'category': 'признание качества и конкурсы',
        'tonality': TonalityLevel.positive,
        'department': 'PR',
        'action': None,
        'comment': 'Признание качества конкурента',
    },
    'https://samadm.ru/news/rekonstrukciya': {
        'priority': PriorityLevel.p3,
        'category': 'PR-активность конкурента',
        'tonality': TonalityLevel.neutral,
        'department': 'Аналитика',
        'action': None,
        'comment': 'Инфраструктурная активность',
    },
    'https://samara450.ru/dolg': {
        'priority': PriorityLevel.p2,
        'category': 'репутационный риск',
        'tonality': TonalityLevel.negative,
        'department': 'PR',
        'action': 'Мониторить репутационный фон конкурента',
        'comment': 'Рост задолженности — репутационный риск',
    },
}

DEFAULT_MARKUP = {
    'priority': PriorityLevel.p3,
    'category': 'косвенное упоминание',
    'tonality': TonalityLevel.neutral,
    'department': 'Аналитика',
    'action': None,
    'comment': 'Фоновая активность (дефолтная разметка)',
}

LLM_MODEL = 'gpt-4o-mini'
PROMPT_VERSION = 'v1.0'

# Enum'ы слоёв → готовые к показу подписи витрины / обратный маппинг.
PRIORITY_DISPLAY = {
    PriorityLevel.p1: 'П1',
    PriorityLevel.p2: 'П2',
    PriorityLevel.p3: 'П3',
    PriorityLevel.p4: 'П4',
}
PRIORITY_FROM_DISPLAY = {v: k for k, v in PRIORITY_DISPLAY.items()}
TONALITY_DISPLAY = {
    TonalityLevel.positive: 'позитивная',
    TonalityLevel.neutral: 'нейтральная',
    TonalityLevel.negative: 'негативная',
}


# ============================================================================
#  Хелперы
# ============================================================================


def make_aliases(name: str) -> list[str]:
    """Стандартные псевдонимы города в нижнем регистре."""
    n = name.lower()
    return list(dict.fromkeys([n, f'г. {n}', f'г {n}']))


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def make_raw_data(
    search_task_id: int,
    competitor: str,
    base_url: str,
    items: list[dict],
) -> dict:
    return {
        'meta': {
            'search_task_id': search_task_id,
            'source': SOURCE_NAME,
            'competitor': competitor,
            'trigger': None,
            'source_request_url': base_url,
            'fetched_at': '2026-06-27T09:00:00Z',
        },
        'items': items,
    }


def compute_deadline(priority: PriorityLevel, published):
    """Срок реакции считает код (ТЗ: П1 = +2 дня, П2 = +7 дней)."""
    if published is None:
        return None
    if priority == PriorityLevel.p1:
        return published + timedelta(days=2)
    if priority == PriorityLevel.p2:
        return published + timedelta(days=7)
    return None


async def _is_empty(session: AsyncSession, model) -> bool:
    count = await session.scalar(select(func.count()).select_from(model))
    return not count


# ============================================================================
#  Сидинг справочников
# ============================================================================


async def seed_dictionaries(session: AsyncSession) -> None:
    # --- region (из cities.json) ---
    with open(CITIES_FILE, encoding='utf-8') as f:
        cities = json.load(f)
    seen: set[str] = set()
    region_rows = []
    for city in cities:
        name = city['name']
        if name in seen:
            continue
        seen.add(name)
        coords = city.get('coords') or {}
        lat = coords.get('lat')
        lon = coords.get('lon')
        json_aliases: list[str] = city.get('aliases', [])
        merged = list(dict.fromkeys(json_aliases + make_aliases(name)))
        region_rows.append(
            {
                'name_display': name,
                'name_aliases': merged,
                'macro_region': city.get('district'),
                'latitude': float(lat) if lat else None,
                'longitude': float(lon) if lon else None,
            }
        )
    await session.execute(
        insert(Region)
        .values(region_rows)
        .on_conflict_do_nothing(index_elements=['name_display'])
    )

    # --- простые справочники (ON CONFLICT DO NOTHING) ---
    await session.execute(
        insert(Competitor)
        .values(COMPETITORS)
        .on_conflict_do_nothing(index_elements=['name'])
    )
    await session.execute(
        insert(Source)
        .values([{'name': SOURCE_NAME}])
        .on_conflict_do_nothing(index_elements=['name'])
    )
    await session.execute(
        insert(Trigger)
        .values(TRIGGERS)
        .on_conflict_do_nothing(index_elements=['keyword'])
    )
    await session.execute(
        insert(BlackDomain)
        .values(BLACK_DOMAINS)
        .on_conflict_do_nothing(index_elements=['domain'])
    )
    await session.execute(
        insert(StopWord)
        .values(STOP_WORDS)
        .on_conflict_do_nothing(index_elements=['phrase', 'type'])
    )
    await session.execute(
        insert(Category)
        .values([{'name': n} for n in CATEGORIES])
        .on_conflict_do_nothing(index_elements=['name'])
    )
    await session.execute(
        insert(Department)
        .values([{'name': n} for n in DEPARTMENTS])
        .on_conflict_do_nothing(index_elements=['name'])
    )
    await session.execute(
        insert(EventType)
        .values(EVENT_TYPES)
        .on_conflict_do_nothing(index_elements=['name'])
    )
    await session.execute(
        insert(Channel)
        .values([{'name': n} for n in CHANNELS])
        .on_conflict_do_nothing(index_elements=['name'])
    )

    # --- справочники без натурального UNIQUE (count-guard) ---
    if await _is_empty(session, TopicLimit):
        await session.execute(insert(TopicLimit).values(TOPIC_LIMITS))
    await session.flush()

    # routing_rule — ids резолвятся в рантайме, поэтому count-guard.
    if await _is_empty(session, RoutingRule):
        etype_map = {
            r.name: r.id
            for r in (await session.execute(select(EventType))).scalars()
        }
        channel_map = {
            r.name: r.id
            for r in (await session.execute(select(Channel))).scalars()
        }
        dep_map = {
            r.name: r.id
            for r in (await session.execute(select(Department))).scalars()
        }
        session.add_all(
            RoutingRule(
                event_type_id=etype_map[etype],
                priority=priority,
                department_id=dep_map[dep],
                channel_id=channel_map[chan],
                mode=mode,
            )
            for etype, priority, dep, chan, mode in ROUTING
        )
    await session.flush()


# ============================================================================
#  Сидинг данных пайплайна
# ============================================================================


async def seed_pipeline(session: AsyncSession) -> None:
    comp_map = {
        r.name: r.id
        for r in (await session.execute(select(Competitor))).scalars()
    }
    source_id = await session.scalar(
        select(Source.id).where(Source.name == SOURCE_NAME)
    )

    # --- search_task (по одной на конкурента, без триггера) ---
    existing = {
        (r.competitor_id, r.source_id, r.trigger_id)
        for r in (await session.execute(select(SearchTask))).scalars()
    }
    for comp, _ in ARTICLES:
        key = (comp_map[comp], source_id, None)
        if key not in existing:
            session.add(
                SearchTask(
                    competitor_id=comp_map[comp],
                    source_id=source_id,
                    trigger_id=None,
                )
            )
    await session.flush()

    tasks = {
        (r.competitor_id, r.source_id, r.trigger_id): r.id
        for r in (await session.execute(select(SearchTask))).scalars()
    }

    def task_id(comp: str) -> int:
        return tasks[(comp_map[comp], source_id, None)]

    # --- raw_item ---
    if await _is_empty(session, RawItem):
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
                    raw_data=make_raw_data(tid, comp, base_url, items),
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
                error_message=(
                    'ConnectionTimeout: newssearch.yandex.ru не ответил '
                    'за 30 с. Исчерпаны все 3 попытки.'
                ),
                created_at=now,
                updated_at=now,
            )
        )
        session.add_all(raw_items)
        await session.flush()

    # --- normalized_item ---
    if await _is_empty(session, NormalizedItem):
        region_map = {
            r.name_display: r.id
            for r in (await session.execute(select(Region))).scalars()
        }
        raw_by_comp: dict[int, int] = {}
        rows = await session.execute(
            select(SearchTask.competitor_id, RawItem.id)
            .join(RawItem, RawItem.search_task_id == SearchTask.id)
            .where(RawItem.status != 'error')
            .order_by(RawItem.id)
        )
        for competitor_id, raw_id in rows:
            raw_by_comp.setdefault(competitor_id, raw_id)

        items: list[NormalizedItem] = []
        for row in NORMALIZED:
            competitor_id = comp_map.get(row['competitor'])
            raw_item_id = raw_by_comp.get(competitor_id)
            if raw_item_id is None:
                continue
            items.append(
                NormalizedItem(
                    raw_item_id=raw_item_id,
                    competitor_id=competitor_id,
                    region_id=region_map.get(row['region']),
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
        session.add_all(items)
        await session.flush()

    # --- categorized_event ---
    if await _is_empty(session, CategorizedEvent):
        cat_map = {
            r.name: r.id
            for r in (await session.execute(select(Category))).scalars()
        }
        dep_map = {
            r.name: r.id
            for r in (await session.execute(select(Department))).scalars()
        }
        ok_items = (
            await session.execute(
                select(NormalizedItem).where(
                    NormalizedItem.status == NormStatus.ok
                )
            )
        ).scalars()
        events: list[CategorizedEvent] = []
        for item in ok_items:
            m = MARKUP.get(item.url, DEFAULT_MARKUP)
            events.append(
                CategorizedEvent(
                    normalized_item_id=item.id,
                    priority=m['priority'],
                    category_id=cat_map[m['category']],
                    tonality=m['tonality'],
                    media_index=None,
                    action=m['action'],
                    deadline=compute_deadline(m['priority'], item.published_at),
                    department_id=dep_map[m['department']],
                    comment=m['comment'],
                    llm_model=LLM_MODEL,
                    prompt_version=PROMPT_VERSION,
                )
            )
        session.add_all(events)
        await session.flush()

    # --- showcase_event (витрина) ---
    if await _is_empty(session, ShowcaseEvent):
        rows = await session.execute(
            select(
                CategorizedEvent,
                NormalizedItem,
                Category.name,
                Department.name,
                Competitor.name,
                Region.name_display,
                Region.macro_region,
            )
            .join(
                NormalizedItem,
                NormalizedItem.id == CategorizedEvent.normalized_item_id,
            )
            .join(Category, Category.id == CategorizedEvent.category_id)
            .outerjoin(
                Department, Department.id == CategorizedEvent.department_id
            )
            .outerjoin(
                Competitor, Competitor.id == NormalizedItem.competitor_id
            )
            .outerjoin(Region, Region.id == NormalizedItem.region_id)
        )
        showcase: list[ShowcaseEvent] = []
        for ce, ni, cat, dep, comp, region, macro in rows:
            showcase.append(
                ShowcaseEvent(
                    categorized_event_id=ce.id,
                    raw_item_id=ni.raw_item_id,
                    published_at=ni.published_at,
                    title=ni.title,
                    media=ni.media_name,
                    region=region,
                    macro_region=macro,
                    competitor=comp,
                    source_url=ni.url,
                    priority=PRIORITY_DISPLAY[ce.priority],
                    category=cat,
                    tonality=TONALITY_DISPLAY[ce.tonality],
                    media_index=ce.media_index,
                    action=ce.action,
                    deadline=ce.deadline,
                    department=dep,
                    comment=ce.comment,
                )
            )
        session.add_all(showcase)
        await session.flush()

    # --- alert (детекция значимых событий) ---
    if await _is_empty(session, Alert):
        etypes = [
            (r.id, [k.strip().lower() for k in r.keywords.split(',')])
            for r in (await session.execute(select(EventType))).scalars()
        ]
        rules: dict[tuple[int, PriorityLevel], list[RoutingRule]] = {}
        for r in (await session.execute(select(RoutingRule))).scalars():
            rules.setdefault((r.event_type_id, r.priority), []).append(r)

        events = (await session.execute(select(ShowcaseEvent))).scalars()
        now = datetime.now(UTC)
        alerts: list[Alert] = []
        for ev in events:
            title = (ev.title or '').lower()
            priority = PRIORITY_FROM_DISPLAY.get(ev.priority)
            if priority is None:
                continue
            matched_type = next(
                (
                    etype_id
                    for etype_id, kws in etypes
                    if any(kw in title for kw in kws)
                ),
                None,
            )
            if matched_type is None:
                continue
            for rule in rules.get((matched_type, priority), []):
                sent = rule.mode == DeliveryMode.instant
                alerts.append(
                    Alert(
                        showcase_event_id=ev.id,
                        event_type_id=matched_type,
                        priority=priority,
                        department_id=rule.department_id,
                        channel_id=rule.channel_id,
                        mode=rule.mode,
                        status=AlertStatus.sent if sent else AlertStatus.queued,
                        sent_at=now if sent else None,
                    )
                )
        session.add_all(alerts)
        await session.flush()

    # --- action_item (план действий по П1/П2) ---
    if await _is_empty(session, ActionItem):
        events = (
            await session.execute(
                select(ShowcaseEvent).where(
                    ShowcaseEvent.priority.in_({'П1', 'П2'})
                )
            )
        ).scalars()
        dep_map = {
            r.name: r.id
            for r in (await session.execute(select(Department))).scalars()
        }
        tasks_list: list[ActionItem] = []
        for ev in events:
            department_id = dep_map.get(ev.department)
            if department_id is None:
                continue
            tasks_list.append(
                ActionItem(
                    showcase_event_id=ev.id,
                    task=ev.action or f'Отработать событие: {ev.title}',
                    department_id=department_id,
                    deadline=ev.deadline,
                    expected_result=(
                        'Событие отработано, реакция задокументирована'
                    ),
                    status=ActionStatus.open,
                )
            )
        session.add_all(tasks_list)
        await session.flush()


# ============================================================================
#  Точка входа
# ============================================================================


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await seed_dictionaries(session)
        await seed_pipeline(session)
        await session.commit()

        # Итоговая сводка по количеству строк.
        summary = [
            Region,
            Competitor,
            Source,
            Trigger,
            BlackDomain,
            StopWord,
            TopicLimit,
            Category,
            Department,
            EventType,
            Channel,
            RoutingRule,
            SearchTask,
            RawItem,
            NormalizedItem,
            CategorizedEvent,
            ShowcaseEvent,
            Alert,
            ActionItem,
        ]
        print('Готово. Строк в таблицах:')
        for model in summary:
            count = await session.scalar(
                select(func.count()).select_from(model)
            )
            print(f'  {model.__tablename__:22} {count}')


if __name__ == '__main__':
    asyncio.run(seed())
