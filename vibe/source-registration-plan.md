# План: Регистрация источника в БД отдельным методом пакета adaptive

## Задача

Добавить в пакет `src/bp1/adaptive` отдельный метод, который позволяет пользователю
зарегистрировать новый источник, передав ссылку на сайт. Метод выполняет цепочку:

1. **Обработка ссылки** — полный URL нормализуется до вида `scheme://hostname/`
   (например `https://www.lenta.ru/news/...` → `https://lenta.ru/`). Для классификации
   и Redis-ключа дополнительно выделяется hostname (`lenta.ru`).
2. **Классификация** — через [`SourceClassifier`](kodik/src/bp1/adaptive/strategies/classifier.py)
   по hostname определяется тип сайта (news/registry/api/spa/unknown), сложность,
   антибот/CAPTCHA/SPA и рекомендованная стратегия.
3. **Добавление в БД** — запись `Source` (модель [`src/bp1/models.py`](kodik/src/bp1/models.py:90))
   создаётся с **полным URL** (`https://lenta.ru/`), только если такого имени ещё нет
   (идемпотентность).
4. **Сохранение классификации в хранилище** — результат `SourceClassification` кладётся в
   Redis через [`UnifiedCache.set_classification`](kodik/src/bp1/adaptive/core/cache.py:107)
   (ключ `bp1:classification:{hostname}`, TTL 7 дней) для повторного использования.

**Согласованный формат имени источника:** полный URL, как хранится в БД/`source.csv`
(например `https://lenta.ru/`). Так как [`AdaptiveRunner.run_task`](kodik/src/bp1/adaptive/integration/runner.py:207)
сейчас строит URL как `https://{source_name}/search?...`, при полном URL получился бы битый
адрес `https://https://lenta.ru//search?...`. Поэтому `AdaptiveRunner` дорабатывается: поисковый
URL строится из hostname, извлечённого из `source_name`.

## Этапы выполнения

### Stage 1: Создать модуль регистрации источника (хелперы + сервис + схема)
**What to add/implement:**
*   Создать `src/bp1/adaptive/integration/sources.py`.
*   Функция `extract_host(url_or_domain: str) -> str`: возвращает hostname в нижнем регистре
    без ведущего `www.`. Принимает и полный URL, и голый домен. Если hostname пуст — поднимает
    `ValueError('Некорректная ссылка на сайт')`.
*   Функция `normalize_source_url(url: str) -> str`: возвращает `scheme://hostname/`
    (`https://www.lenta.ru/news/1` → `https://lenta.ru/`). Используется для `Source.name`.
*   Функция `build_search_url(source_name: str, search_param: str) -> str`: извлекает hostname из
    `source_name` (полный URL или домен) и возвращает
    `f'https://{host}/search?q={search_param}'`.
*   Класс `SourceRegistrationService`:
    *   метод `classify(url: str) -> SourceClassification` — вызывает `SourceClassifier.classify`
        с `source_name=extract_host(url)` и `source_url=url`;
    *   метод `async register(url: str, session: AsyncSession, redis_client) -> SourceRegistrationResult`:
        1. `source_name = normalize_source_url(url)`; `host = extract_host(url)`;
        2. `classification = await self.classify(url)`;
        3. если `Source` с `name == source_name` уже есть (SELECT) — `created=False`,
           `source_id` из найденного;
        4. иначе создаёт `Source(name=source_name)`, `session.add`, `session.flush`, `created=True`;
        5. `await UnifiedCache(redis_client).set_classification(host, classification)`;
        6. возвращает результат.
*   Добавить pydantic-схему `SourceRegistrationResult` в `src/bp1/adaptive/schemas.py`:
    `host: str`, `source_name: str`, `created: bool`, `source_id: int | None`,
    `classification: SourceClassification`.

**Files to edit/create:**
*   `kodik/src/bp1/adaptive/integration/sources.py` — новый модуль.
*   `kodik/src/bp1/adaptive/schemas.py` — добавить `SourceRegistrationResult`.
*   `kodik/src/bp1/adaptive/integration/__init__.py` — экспорт `SourceRegistrationService`.

**Examples in existing code:**
*   `kodik/src/bp1/adaptive/strategies/classifier.py` — `SourceClassifier.classify`.
*   `kodik/src/bp1/adaptive/core/cache.py` — `UnifiedCache.set_classification`.
*   `kodik/src/bp1/adaptive/integration/runner.py` — паттерн session/redis.

**Verification commands:**
*   `ruff check src/bp1/adaptive/integration/sources.py src/bp1/adaptive/schemas.py`
*   `d:\1_Dev\Work\00_Stagirovka\.venv-kodik\Scripts\python.exe -c "from src.bp1.adaptive.integration.sources import extract_host, normalize_source_url, build_search_url; assert extract_host('https://www.lenta.ru/news/1')=='lenta.ru'; assert normalize_source_url('https://www.lenta.ru/news/1')=='https://lenta.ru/'; assert build_search_url('https://lenta.ru/','x')=='https://lenta.ru/search?q=x'; print('ok')"`

### Stage 2: Доработать AdaptiveRunner — построение поискового URL из hostname
**What to add/implement:**
*   В `AdaptiveRunner.run_task` заменить прямую конструкцию
    `url = f'https://{source_name}/search?q={search_param}'` (строка 207) на вызов
    `build_search_url(source_name, search_param)`.
*   `parser_url` для специализированных RPA-парсеров оставить как `f'https://{source_name}'`,
    но вычислить hostname из `source_name` через `extract_host` (иначе при полном URL
    `https://https://lenta.ru/`).

**Files to edit/create:**
*   `kodik/src/bp1/adaptive/integration/runner.py` — строка 207 и блок построения `parser_url`.

**Examples in existing code:**
*   `kodik/src/bp1/adaptive/integration/runner.py` — текущая строка 206–207.

**Verification commands:**
*   `ruff check src/bp1/adaptive/integration/runner.py`

### Stage 3: Написать тесты регистрации источника
**What to add/implement:**
*   Создать `kodik/tests/bp1/adaptive/test_source_registration.py`.
*   Тест `test_extract_host_variants`: `https://www.lenta.ru/news/1`→`lenta.ru`,
    `https://api.hh.ru/`→`api.hh.ru`, `http://fedresurs.ru:8080/x`→`fedresurs.ru`,
    `https://LENTA.RU`→`lenta.ru`.
*   Тест `test_extract_host_invalid`: не-URL (`'не ссылка'`, `''`) → `ValueError`.
*   Тест `test_normalize_source_url`: полный URL → `scheme://hostname/`.
*   Тест `test_build_search_url`: из полного URL и из голого домена → `https://host/search?q=...`.
*   Тест `test_register_creates_source(session)`: с фейковым Redis — `register(
    'https://www.lenta.ru/news', session, fake_redis)` создаёт `Source(name='https://lenta.ru/')`,
    `created=True`, `classification.source_type == SourceType.NEWS`; в фейковом Redis появился ключ
    `bp1:classification:lenta.ru`.
*   Тест `test_register_is_idempotent(session)`: повторный `register` с тем же URL не создаёт
    вторую запись, `created=False`, `source_id` совпадает.

**Files to edit/create:**
*   `kodik/tests/bp1/adaptive/test_source_registration.py` — новый файл.
*   Фикстура `session` (из `kodik/tests/conftest.py`), фейковый Redis (по образцу
    `_FakeRedis` из `kodik/tests/bp1/adaptive/test_integration.py:31`).

**Examples in existing code:**
*   `kodik/tests/bp1/adaptive/test_classifier.py` — асинхронные тесты.
*   `kodik/tests/bp1/adaptive/test_integration.py` — `_FakeRedis`, `tmp_path`.

**Verification commands:**
*   `d:\1_Dev\Work\00_Stagirovka\.venv-kodik\Scripts\python.exe -m pytest tests/bp1/adaptive/test_source_registration.py -v`
*   `ruff check tests/bp1/adaptive/test_source_registration.py`

### Stage 4: Проверить работу фичи на реальном примере
**What to add/implement:**
*   Прогнать `register('https://www.lenta.ru/', session, real_redis)` на реальной БД и Redis
    через временный скрипт в `kodik/` (удаляется после проверки).
*   Убедиться: в БД появился `Source(name='https://lenta.ru/')`, в Redis ключ
    `bp1:classification:lenta.ru`, классификация `news`/`FAST`.
*   Запустить полный прогон `pytest tests/bp1/adaptive/` и `ruff check` по изменённым файлам.

**Verification commands:**
*   `d:\1_Dev\Work\00_Stagirovka\.venv-kodik\Scripts\python.exe -m pytest tests/bp1/adaptive -v`
*   `ruff check src/bp1/adaptive tests/bp1/adaptive`
