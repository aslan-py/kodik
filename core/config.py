"""Конфигурация приложения из переменных окружения (.env).

Загружает и валидирует параметры подключения к Postgres через Pydantic.
Один источник правды для строки подключения: все части (user, password,
host, port, db) берутся из переменных POSTGRES_*, а database_url собирает
из них DSN.

Используется везде: database.py (engine), Alembic (env.py), воркеры.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.enums import SourceSearchDepth


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из .env файла."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # ===== Postgres =====
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = 'localhost'
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """Динамически собирает DSN-строку подключения к БД."""
        return (
            f'postgresql+asyncpg://{self.postgres_user}:'
            f'{self.postgres_password}@{self.postgres_host}:'
            f'{self.postgres_port}/{self.postgres_db}'
        )

    # ===== Redis =====
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def redis_url(self) -> str:
        """Собирает URL для подключения к Redis."""
        if self.redis_password:
            return (
                f'redis://:{self.redis_password}@'
                f'{self.redis_host}:{self.redis_port}/{self.redis_db}'
            )
        return f'redis://{self.redis_host}:{self.redis_port}/{self.redis_db}'

    # ===== Celery =====
    # Отдельные номера БД Redis (не redis_db — та занята под дедуп-хэши
    # BP-1), чтобы очередь/результаты Celery не смешивались с бизнес-данными.
    celery_broker_db: int = 1
    celery_result_backend_db: int = 2
    celery_worker_concurrency: int = 2
    celery_bp1_worker_concurrency: int = 1
    celery_task_soft_time_limit_seconds: int = 900
    celery_task_time_limit_seconds: int = 960
    celery_task_max_retries: int = 3
    celery_task_default_retry_delay_seconds: int = 60
    celery_task_retry_backoff_max_seconds: int = 600

    # ===== Pipeline orchestration =====
    pipeline_schedule_enabled: bool = False
    pipeline_schedule_cron: str = '0 8 * * *'
    pipeline_schedule_timezone: str = 'Europe/Moscow'
    pipeline_schedule_poll_seconds: int = 60
    pipeline_run_stale_timeout_seconds: int = 1800
    grafana_url: str = 'http://localhost:3001'
    flower_basic_auth: str | None = None

    @property
    def celery_broker_url(self) -> str:
        """Собирает URL брокера Celery (Redis)."""
        if self.redis_password:
            return (
                f'redis://:{self.redis_password}@'
                f'{self.redis_host}:{self.redis_port}/{self.celery_broker_db}'
            )
        return (
            f'redis://{self.redis_host}:{self.redis_port}/'
            f'{self.celery_broker_db}'
        )

    @property
    def celery_result_backend_url(self) -> str:
        """Собирает URL result backend Celery (Redis)."""
        if self.redis_password:
            return (
                f'redis://:{self.redis_password}@'
                f'{self.redis_host}:{self.redis_port}/'
                f'{self.celery_result_backend_db}'
            )
        return (
            f'redis://{self.redis_host}:{self.redis_port}/'
            f'{self.celery_result_backend_db}'
        )

    # ===== Пути для хранения данных =====
    # Корневая папка для данных BP-1
    bp1_data_root: str = './src/bp1/data'

    @property
    def bp1_html_dir(self) -> str:
        """Папка для сохранения HTML файлов."""
        return str(Path(self.bp1_data_root) / 'html_pages')

    @property
    def bp1_raw_dir(self) -> str:
        """Папка для сохранения raw данных (JSON)."""
        return str(Path(self.bp1_data_root) / 'raw')

    # ===== Mail =====
    mail_username: str
    mail_password: str
    mail_from: str
    mail_from_name: str = 'Kodik Alerts'
    mail_port: int = 465
    mail_server: str
    mail_starttls: bool = False
    mail_ssl_tls: bool = True
    mail_use_credentials: bool = True
    mail_validate_certs: bool = True

    # ===== Telegram =====
    telegram_bot_token: str
    test_tg: int

    # ===== Alerting =====
    true_alerting: bool = False
    test_email: str

    # ===== Сбор данных (BP-1) =====
    # Флаг реализации этапа 1, НЕ флаг включения/выключения сбора — по
    # тому же принципу, что и true_alerting. False -> заглушка
    # (core/scripts/stages/bp1_stub.py, синтетические новости, без сети и
    # LLM); True -> настоящий адаптивный сбор (src/bp1/pipeline.py).
    true_parsing: bool = True

    # ===== FASTAPI SETTINGS =====
    api_host: str = '127.0.0.1'
    api_port: int
    app_title: str = 'Конкурентная разведка'
    description: str = 'API управлния проектом конкурентная разведка'

    # ===== CORS =====
    # Список разрешённых origin через запятую, например:
    # CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'

    @property
    def cors_origins_list(self) -> list[str]:
        """Разбирает CORS_ORIGINS в список origin для CORSMiddleware."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(',')
            if origin.strip()
        ]

    # ===== JWT =====
    jwt_secret_key: str
    jwt_expire_minutes: int = 60

    # ===== Сброс пароля =====
    password_reset_code_expire_minutes: int = 10

    # ===== BP-3 (LLM-категоризация через OpenRouter, поиск источников Tavily)
    openrouter_api_key: str
    tavily_api_key: str
    bp3_model: str = 'openai/gpt-4o'
    bp3_search_max_results: int = 2
    bp3_search_depth: SourceSearchDepth = SourceSearchDepth.basic
    bp3_search_time_range: str = 'week'
    bp3_llm_base_url: str = 'https://openrouter.ai/api/v1'
    bp3_llm_temperature: float = 0
    bp3_llm_max_tokens: int = 4096

    # ===== AI-ассистент (BP-6, генерация action_item) =====
    deepseek_token: str
    deepseek_base_url: str = 'https://api.deepseek.com'
    deepseek_model: str = 'deepseek-chat'

    # ===== BP-1 Adaptive (LLM-анализ HTML: селекторы, стратегии обхода) =====
    # Ключ и адрес — отдельные поля, не переиспользуют openrouter_api_key/
    # deepseek_token: у проекта три независимых LLM-доступа под разные
    # провайдеры. Опциональны: без ключа адаптивный парсер работает на
    # эвристическом fallback (см. adaptive/processing/llm.py).
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = 'gpt-4o-mini'

    # ===== BP-1 Adaptive (объём и глубина сбора) =====
    # Эксплуатационные ручки: меняются при работе с конкретными источниками,
    # без правки кода. Значения по умолчанию равны прежним константам
    # (adaptive/processing/parser.py, adaptive/strategies/orchestrator.py).
    bp1_max_news_per_source: int = 20
    bp1_min_article_text_length: int = 100
    bp1_min_full_article_text_length: int = 300
    bp1_max_tail_fetch_attempts: int = 3
    # Размер окна (в символах исходного HTML), забираемого с конца документа
    # при докачке обрезанного хвоста статьи (adaptive/processing/parser.py,
    # _extract_missing_tail). Раньше был захардкожен в коде.
    bp1_tail_fetch_chunk_size: int = 12000
    # Эскалировать ли в LLM короткий (100..min_full) CSS/readability-текст,
    # даже если он выглядит завершённым (заканчивается пунктуацией, не
    # обрублен). True — приоритет полноте текста для ML (может увеличить
    # число LLM-вызовов); False — считать такой текст естественно коротким
    # (короткие вакансии/пресс-релизы) и не тратить LLM-вызов.
    bp1_short_text_llm_escalation: bool = True
    bp1_min_content_length: int = 300
    # Верхний предел страниц пагинации на источник за прогон. Раньше
    # _max_pages() возвращал жёстко зашитое 10000 (фактически "без
    # лимита") — единственным тормозом был bp1_max_news_per_source, и его
    # рост напрямую удлинял прогон. Реальный лимит: сколько страниц
    # придётся пройти, чтобы набрать max_news, если на странице мало
    # подходящих ссылок (Шаг 16 плана, kodik/src/bp1/REFACTORING_PLAN.md).
    bp1_max_pagination_pages: int = 10

    # ===== BP-1 Adaptive (релевантность и обогащение, финальный этап) =====
    # Режим фильтрации релевантности: 'off' | 'filter' | 'rank'.
    # 'rank' (не 'filter') — по умолчанию: BP-1 отвечает за сырой сбор
    # (Bronze Layer), а не за решение, что из собранного оставить —
    # это задача этапа нормализации (BP-2, Silver Layer). 'rank' только
    # сортирует/размечает оценку relevance в extra, ничего не отбрасывает
    # (Шаг 15 плана рефакторинга, kodik/src/bp1/REFACTORING_PLAN.md).
    bp1_relevance_mode: str = 'rank'
    # Порог релевантности (0.0-1.0) для режима 'filter'.
    bp1_relevance_threshold: float = 0.6
    # Включает LLM-обогащение событий структурированными полями.
    bp1_enrichment_enabled: bool = True
    # Ограничение длины текста (символов), передаваемого в промпт
    # обогащения (adaptive/processing/_llm/prompt_builders.py,
    # build_enrichment_prompt). Не влияет на сам извлечённый ex_text —
    # только на текст, по которому LLM считает summary/sentiment/keywords.
    bp1_enrichment_snippet_size: int = 12000

    # ===== BP-1 Adaptive (чанкирование длинных страниц для LLM) =====
    # Размер одного чанка HTML (символов) и максимальное число чанков на
    # страницу/статью (adaptive/processing/_llm/constants.py). Чанки сверх
    # bp1_llm_max_chunks отбрасываются (с предупреждением в логах) —
    # потолок длины HTML, из которого можно извлечь текст через LLM:
    # bp1_llm_max_chunks * bp1_llm_max_chunk_size символов.
    #
    # Снижено с 20 до 6 (реальные замеры hh.ru): _chunk_by_chars режет
    # текст строго последовательно по позиции в документе, а основной
    # контент (title/описание вакансии) обычно идёт раньше в DOM, чем
    # "похожие вакансии"/футер. При 20 чанках 60-85% из них у больших
    # страниц (hh.ru: 677-823 КБ HTML) возвращали от LLM пустой ответ
    # (легитимно — там нет текста статьи), но каждый лишний чанк — это
    # ещё один LLM-запрос, и суммарное время ожидания превышало
    # bp1_article_fetch_timeout_seconds. Реальная длина извлечённого
    # текста вакансии (readability/успешный llm) — ~700-2700 символов,
    # с запасом укладывается в 6 чанков по 8000 символов.
    bp1_llm_max_chunk_size: int = 8000
    bp1_llm_max_chunks: int = 6

    # ===== BP-1 Adaptive (сетевые ограничения) =====
    # parse_timeout_ms / max_concurrent_tasks — общие для классического
    # BP-1 (src/bp1/constants.py) и AdaptiveRunner: один параметр эксплуатации
    # управляет обоими потребителями одного и того же смысла.
    bp1_parse_timeout_ms: int = 60000
    bp1_max_concurrent_tasks: int = 5
    # Бюджет на весь _extract_article_text одной статьи, включая полную
    # цепочку деградации (FAST->CRAWL4AI->BROWSER->WAYBACK->STEALTH->HITL).
    # Не должен быть меньше внутреннего таймаута одной стратегии (60000мс,
    # см. AdaptiveParser.__init__/engines.py) — иначе asyncio.wait_for
    # обрывает выполнение посреди единственной попытки, а не даёт ей дойти
    # до конца (см. orchestrator.py::BrowserStrategy.fetch, где именно
    # такой обрыв уже был явно диагностирован как проблема).
    bp1_article_fetch_timeout_seconds: float = 60.0
    bp1_max_concurrent_fetches: int = 5

    # ===== BP-1 Adaptive (время жизни кэшей) =====
    # Три отдельных поля, не одно общее: кэшируются разные вещи с разной
    # ценой промаха (профиль адаптера дорогой, текст статьи дешёвый) — см.
    # design.md изменения centralize-parsing-settings, Decisions.
    bp1_adapter_ttl_seconds: int = 86400 * 7
    bp1_classification_ttl_seconds: int = 86400 * 7
    bp1_article_text_ttl_seconds: int = 86400 * 7
    bp1_probed_url_ttl_seconds: int = 86400 * 7

    # ===== BP-1 Adaptive (RSS/Atom/sitemap-фид) =====
    # Два разных кэша: обнаружение (URL фида или отметка "фида нет" — TTL
    # длинный, как у адаптера) и материалы (уже распарсенные записи фида —
    # TTL короткий, порядка интервала прогона сбора). Без второго кэша
    # каждый конкурент источника заново скачивал бы один и тот же фид
    # (design.md изменения add-rss-sitemap-collection, Decision D5).
    bp1_feed_cache_ttl_seconds: int = 86400 * 7
    bp1_feed_items_cache_ttl_seconds: int = 3600
    # Порог самокоррекции кэша обнаружения — по аналогии с
    # ADAPTER_FAIL_THRESHOLD (adaptive/processing/parser/constants.py):
    # один случайный сбой не должен сразу выбрасывать рабочий фид.
    bp1_feed_fail_threshold: int = 2

    # ===== BP-1 Adaptive (режим прогона AdaptiveRunner) =====
    bp1_adaptive_mode: str = 'adaptive'
    bp1_headless: bool = True

    # ===== Circuit breaker для источников (BP-1 Adaptive) =====
    # Время временной блокировки источника в Redis после полного отказа
    # (all strategies failed), в секундах. По умолчанию 24 часа.
    source_circuit_ttl_seconds: int = 86400
    # Число подряд идущих полных отказов (с промежутком в circuit TTL каждый),
    # после которого источник отключается в БД (is_active=False).
    source_disable_threshold: int = 3

    # ===== BP-1 RPA (прокси, ротация User-Agent, задержки) =====
    # Требование ТЗ для источников с RPA-доступом (эмуляция браузера):
    # прокси не с корпоративных IP, ротация User-Agent, задержки между
    # запросами. Опционально: без ключа провайдера RPA-стратегии работают
    # без прокси (см. src/bp1/network/).
    sx_org_api_key: str | None = None
    sx_org_base_url: str = 'https://api.sx.org'
    # Код страны для подбора прокси (например, 'RU'); пусто — без фильтра.
    bp1_proxy_country: str | None = None
    bp1_proxy_pool_size: int = 20
    # Порог баланса провайдера: выше — создаются/используются собственные
    # порты, ниже — только бесплатные свободные прокси (search_proxies).
    bp1_proxy_min_balance: float = 1.0
    bp1_proxy_pool_ttl_seconds: int = 1800
    # TTL "остывания" адреса, заблокированного конкретным источником —
    # адрес не выбирается повторно для этого источника до истечения TTL.
    bp1_proxy_cooldown_seconds: int = 1800
    # Минимальная пауза между последовательными запросами к одному хосту
    # для RPA-стратегий (поверх лимитов параллелизма bp1_max_concurrent_*).
    bp1_rpa_request_delay_seconds: float = 2.0

    # ===== BP-7 (агент расширения источников) =====
    # Порог score, выше которого source_candidate переносится в source
    # (src/bp7/pipeline.py::SourceCandidatePromoter). Настраивается через
    # .env без правки кода.
    source_candidate_score_threshold: float = 0.5

    # ===== Админка (FastAdmin, монтируется в api/main.py на /admin) =====
    # FastAdmin читает свои настройки напрямую из os.environ на импорте, а не
    # из этого класса — раскладывает их туда api/admin/__init__.py, чтобы
    # единственным источником правды остался .env.
    admin_site_name: str = 'Кодик — админка'
    admin_language: str = 'ru'
    # Секрет подписи сессии админки. Пустой -> берётся jwt_secret_key
    # (см. api/admin/__init__.py), отдельный ключ заводить не обязательно.
    admin_secret_key: str | None = None
    # False — обязательное значение для локального http://localhost: иначе
    # кука сессии ставится только по HTTPS и вход молча не работает.
    # На проде (за TLS) выставить True.
    admin_session_cookie_secure: bool = False


settings = Settings()
