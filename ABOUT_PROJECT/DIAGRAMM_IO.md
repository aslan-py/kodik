# Модель данных для dbdiagram.io

Полная схема БД в формате DBML. Скопируйте содержимое блока целиком и
вставьте в редактор на [dbdiagram.io](https://dbdiagram.io) — сайт не
связан с репозиторием, изменения нужно переносить вручную при каждом
обновлении схемы (см. `ABOUT.md`, где описаны решения по каждому BP).

```dbml
Project "Кодик - конкурентная разведка" {
  database_type: 'PostgreSQL'
  Note: 'ПРОЕКТ: Кодик - конкурентная разведка\n\nBP-1: слой сырых данных и справочников сбора.\nBP-2: нормализация, фильтрация, дедупликация -> normalized_item + справочники фильтрации.\nBP-3: LLM-категоризация -> categorized_event + справочники разметки.\nBP-4: витрина showcase_event - ФИЗИЧЕСКАЯ плоская таблица под BI, инкрементальный UPSERT поверх normalized_item + categorized_event + ссылка на raw_item (вариант с VIEW отклонён: BI нужны индексы и стабильный контракт колонок).\nBP-5: детектор значимых событий -> alert. Watermark showcase_event.alerted_at (не журнал alert - там легитимны события с нулём алертов). Адресат - user (конкретный человек), НЕ department: список получателей курируется вручную и может не совпадать со штатом отдела.'
}

enum raw_item_status {
  new
  changed
  error
}

// ============================================================================
//  BP-1 — СБОР ДАННЫХ (СПРАВОЧНИКИ ЗАДАЧ + СЫРЬЁ)
// ============================================================================

// 1. Чистый справочник конкурентов (Только имена)
Table competitor {
  id int [pk, increment, note: "Уникальный ID конкурента"]
  name varchar [not null, unique, note: "Название компании (например, Бегемот, Рога и Копыта). Уникально — не допускаем дублей в справочнике"]
  inn varchar [null, unique, note: "ИНН конкурента (опционально). Для поиска по гос-реестрам ЮЛ. Уникально — no duplication в БД"]
  is_active boolean [not null, default: true, note: "Мягкое выключение справочника (ActiveMixin), не удаляя из БД"]
}

// 2. Чистый справочник источников
Table source {
  id int [pk, increment, note: "Уникальный ID источника"]
  name varchar [not null, unique, note: "Имя сайта/ресурса (например, hh.ru, авито, судебный_реестр). Уникально — не допускаем дублей в справочнике"]
  is_active boolean [not null, default: true, note: "Мягкое выключение справочника (ActiveMixin), не удаляя из БД"]
}

// 3. Чистый справочник триггеров (Общие ключевые слова)
Table trigger {
  id int [pk, increment, note: "Уникальный ID ключевого слова"]
  keyword varchar [not null, unique, note: "Само поисковое слово/навык (например, Юрист, Python, Django, Суд). Уникально — не допускаем дублей в справочнике"]
  is_active boolean [not null, default: true, note: "Мягкое выключение справочника (ActiveMixin), не удаляя из БД"]
}

// 4. Матрица задач (Many-to-Many связующая таблица конфигурации)
Table search_task {
  id int [pk, increment, note: "ID конкретной настроенной задачи на парсинг. Используется как КЛЮЧ в Redis (значение = последний хэш)"]
  competitor_id int [not null, ref: > competitor.id, note: "ОБЯЗАТЕЛЬНО: Какого конкурента ищем. **FK ON DELETE RESTRICT**: нельзя удалить конкурента, пока есть задачи (историю не рушим, справочник гасим is_active)"]
  source_id int [not null, ref: > source.id, note: "ОБЯЗАТЕЛЬНО: На каком источнике ищем. **FK ON DELETE RESTRICT** — см. competitor_id"]
  trigger_id int [null, ref: > trigger.id, note: "НЕОБЯЗАТЕЛЬНО: По какому слову. Если NULL - парсим источник 'в лоб' без ключевых слов. **FK ON DELETE RESTRICT** — триггер не удаляем, а гасим is_active"]
  is_active boolean [not null, default: true, note: "Активна ли задача. Celery Beat берёт в перебор только активные строки. Выключаем флагом, не удаляя (иначе теряем FK-историю в raw_item)"]

  indexes {
    (competitor_id, source_id, trigger_id) [unique, note: "Не плодить дубли конфигов. ВНИМАНИЕ: в Postgres NULL != NULL, поэтому строки с trigger_id=NULL этот индекс НЕ защитит от дублей — см. отдельный partial unique index ниже"]
    (competitor_id, source_id) [unique, name: "uq_search_task_no_trigger", note: "Partial unique index (WHERE trigger_id IS NULL) — реализован в src/bp1/models.py: закрывает дыру индекса выше именно для строк без триггера"]
  }

  Note: "Служебная таблица конфигурации: связывает кто, где и что ищет. На неё опирается Celery Beat при старте. id строки = ключ в Redis."
}

// 5. Таблица хранения результатов сбора (Твоя основная модель для BP-1)
Table raw_item {
  id int [pk, increment, note: "Уникальный ID записи сырого материала. Одна строка = одна выгрузка (снимок)"]
  search_task_id int [not null, ref: > search_task.id, note: "СТРОГО ОБЯЗАТЕЛЬНО: Ссылка на задачу конфигурации. Через неё вытягиваем конкурента, источник и триггер. **FK ON DELETE RESTRICT** — сырьё не должно терять привязку к задаче"]
  status raw_item_status [not null, default: "new", note: "Статус СНИМКА на момент вставки. new/changed = новая строка; error = сбой сбора. При совпадении хэша новую строку НЕ создаём и статус НЕ трогаем, обновляем только updated_at у последней. Статус после вставки не перезаписываем"]

  // Поля контента - NULLABLE, т.к. при status=error парсинг не дал ни HTML, ни JSON, ни хэша
  content_hash varchar [null, note: "Хэш от JSON контента для сверки через Redis. NULL при status=error"]
  raw_data jsonb [null, note: "Сырой извлечённый контент страницы в формате JSON. NULL при status=error"]
  html_file_path varchar [null, note: "Путь к сохранённому слепку HTML на диске/S3 для истории. NULL при status=error"]
  source_request_url varchar [null, note: "Ссылка на оригинальный веб-запрос парсера. Заполняется для успешных выгрузок; может быть NULL при ранней ошибке"]

  // Техническое уведомление о сбое (ТЗ BP-1: 'при сбое формируется техническое уведомление')
  error_message varchar [null, note: "Текст ошибки при status=error. NULL для успешных выгрузок"]

  created_at timestamp [not null, default: `now()`, note: "Время первой фиксации этого снимка в системе"]
  updated_at timestamp [not null, default: `now()`, note: "Время последней СВЕРКИ. При совпадении хэша обновляем ТОЛЬКО это поле у последней строки (status не трогаем) — видно, когда последний раз проверяли актуальность"]

  Note: "Центральное хранилище сырых материалов (BP-1). Хранит метаданные задачи, обе ссылки (сеть и диск) и сам сырой JSON. new/changed добавляют новую строку (история версий); при совпадении хэша строку не создаём и статус не трогаем, обновляем только updated_at; error пишет строку с пустым контентом и error_message."
}

// ============================================================================
//  BP-2 — СПРАВОЧНИКИ НОРМАЛИЗАЦИИ И ФИЛЬТРАЦИИ
// ============================================================================

// 6. Справочник регионов (нормализация: сырое имя -> красивое имя). Зона разработчика
Table region {
  id           int     [pk, increment, note: "Уникальный ID региона"]
  name_display varchar [not null, unique, note: "Каноническое имя для витрины и карты: 'Волгоград'. По нему группируем в дашборде"]
  name_aliases varchar[] [null, note: "Варианты написания в нижнем регистре: ['волгоград', 'г. волгоград', 'г волгоград']. Lookup: lower(:raw) = ANY(name_aliases). GIN-индекс ix_region_name_aliases. Тип как у event_type.keywords — оба через ARRAY(String) в коде"]
  macro_region varchar [null, note: "Федеральный округ: Сибирский, Южный и т.д."]
  latitude     float   [null, note: "Широта центра региона (WGS-84), для карты рынка"]
  longitude    float   [null, note: "Долгота центра региона (WGS-84), для карты рынка"]

  indexes {
    name_aliases [type: gin, name: "ix_region_name_aliases", note: "Быстрый поиск по ANY(name_aliases)"]
  }
}

// 7. Справочник чёрных доменов (публикаторы, которых выкидываем целиком). Зона аналитика
Table black_domain {
  id int [pk, increment, note: "Уникальный ID записи"]
  domain varchar [not null, unique, note: "Домен ПУБЛИКАТОРА новости (напр. kompromat.ru). НЕ путать с source - это НЕ то, что мы парсим, а откуда пришёл контент"]
  reason varchar [null, note: "Почему в списке: заказной / компрометирующий ресурс"]
  is_active boolean [not null, default: true, note: "Выключаем флагом, не удаляя"]
  created_at timestamp [not null, default: `now()`]
}

// 8. Стоп-слова / стоп-темы / ложные срабатывания (одна универсальная таблица по type). Зона аналитика
enum stop_type {
  stop_word
  stop_topic
  false_positive
}
Table stop_word {
  id int [pk, increment, note: "Уникальный ID записи"]
  phrase varchar [not null, note: "Слово или тема для отсева"]
  type stop_type [not null, note: "stop_word - стоп-слово; stop_topic - стоп-тема; false_positive - ложное срабатывание ключевого слова"]
  is_active boolean [not null, default: true]
  note varchar [null, note: "Пояснение для аналитика"]

  indexes {
    (phrase, type) [unique, note: "Не дублировать одну фразу в одном типе"]
  }
}

// 9. Лимиты анти-шума (АГГРЕГАТНЫЙ фильтр: одна группа не должна занимать непропорц. долю). Зона аналитика
enum limit_scope {
  competitor
  source
  media
  region
}
enum limit_window {
  run
  day
  week
}
Table topic_limit {
  id int [pk, increment, note: "Уникальный ID правила"]
  scope limit_scope [not null, note: "По какой группе считаем долю: конкурент / источник / СМИ / регион"]
  max_count int [not null, note: "Максимум событий на ОДНУ группу за окно; сверх -> rejected(noise_limit)"]
  window limit_window [not null, default: "week", note: "Окно подсчёта: прогон / день / неделя"]
  is_active boolean [not null, default: true]
  note varchar [null, note: "Напр.: 'СКС занимает ~40% отчёта 5 недель подряд'"]
}

// ============================================================================
//  BP-2 — ВЫХОД: НОРМАЛИЗОВАННЫЕ СОБЫТИЯ (silver-слой)
// ============================================================================

enum norm_status {
  ok
  rejected
}
enum reject_reason_t {
  black_domain
  stop_word
  stop_topic
  false_positive
  noise_limit
  parse_error
}

// 10. Нормализованные события — отдельные строки, только ФАКТЫ
Table normalized_item {
  id int [pk, increment, note: "Уникальный ID события"]
  raw_item_id int [not null, ref: > raw_item.id, note: "Ссылка НАЗАД на сырьё (drill-down, требование прозрачности ТЗ)"]
  competitor_id int [null, ref: > competitor.id, note: "Конкурент / Объект. NULL если из текста однозначно не вытащили"]
  region_id int [null, ref: > region.id, note: "Регион после lookup в region. NULL если не определён"]
  source_id int [null, ref: > source.id, note: "С какого источника собрано. Денормализовано из raw_item -> search_task -> source, чтобы не джойнить в два прыжка. Закрывает атрибут 'источник' из ТЗ и антишум scope='source'"]

  // ---- ФАКТЫ со страницы (зона BP-2) ----
  published_at date [null, note: "Дата события, нормализована к ISO"]
  title varchar [not null, note: "Заголовок"]
  media_name varchar [null, note: "СМИ-публикатор: 'Big-news.ru, Москва'"]
  media_domain varchar [null, note: "Домен публикатора — для сверки с black_domain"]
  url varchar [null, note: "Ссылка на событие"]
  text varchar [null, note: "Тело события: описание вакансии / текст новости. Вход для стоп-слов в BP-2 и для промпта LLM в BP-3"]
  extra jsonb [null, note: "Источник-специфичные факты, которым не место в общих колонках. Напр. для вакансий: {salary_from: 150000, salary_to: 200000, currency: RUB}"]

  dedup_key varchar [not null, unique, note: "Бизнес-ключ события. Лучше URL; иначе хэш(конкурент+заголовок+регион). Уникальный индекс = дедуп через INSERT ... ON CONFLICT"]
  status norm_status [not null, default: "ok", note: "ok -> идут в BP-3; rejected -> лежат помеченными, не удаляем"]
  reject_reason reject_reason_t [null, note: "Причина отсева. NULL для status=ok"]
  created_at timestamp [not null, default: `now()`]

  Note: "Silver-слой BP-2: отдельные события с ФАКТАМИ (дата, заголовок, СМИ, регион, конкурент, url). Атрибуты СМЫСЛА добавляет BP-3 в categorized_event."
}

// ============================================================================
//  BP-3 — СПРАВОЧНИКИ РАЗМЕТКИ + РЕЗУЛЬТАТ LLM-КАТЕГОРИЗАЦИИ (gold-слой)
// ============================================================================

// 11. Справочник категорий событий (контролируемый словарь для LLM). Зона аналитика
Table category {
  id int [pk, increment, note: "Уникальный ID категории"]
  name varchar [not null, unique, note: "Напр.: надзорная санкция и юр.риск; репутационный риск; PR-активность; системная проблема; признание качества; косвенное упоминание; инфошум"]
  note varchar [null, note: "Определение категории для аналитика: что под неё подпадает (напр. 'Любое действие госорганов ... которое создаёт материальные финансовые потери или угрозу остановки/изменения бизнес-модели конкурента')"]
  is_active boolean [not null, default: true]
}

// 12. Справочник отделов (маршрутизация ответственного). Зона аналитика
Table department {
  id int [pk, increment, note: "Уникальный ID отдела"]
  name varchar [not null, unique, note: "Напр.: PR, Юристы, Аналитика, Маркетинг"]
  note varchar [null, note: "Зона ответственности отдела: какие категории он ведёт (напр. Юристы — 'Держат санкции и иски')"]
  is_active boolean [not null, default: true]
}

enum priority_level {
  p1  // П1 — реагировать немедленно, срок 48ч
  p2  // П2 — отслеживать, срок 1 неделя
  p3  // П3 — к сведению
  p4  // П4 — игнорировать (шум)
}
enum tonality_level {
  positive
  neutral
  negative
  alarming
  irrelevant
}

// 13. Результат LLM-категоризации — СМЫСЛЫ (1:1 к normalized_item)
Table categorized_event {
  id int [pk, increment, note: "Уникальный ID разметки"]
  normalized_item_id int [not null, unique, ref: > normalized_item.id, note: "1:1 ссылка на факты события. UNIQUE = одна разметка на событие"]

  // ---- атрибуты СМЫСЛА от LLM ----
  priority priority_level [not null, note: "Приоритет П1–П4"]
  category_id int [not null, ref: > category.id, note: "Категория события из справочника"]
  tonality tonality_level [not null, note: "Тональность"]
  media_index numeric [null, note: "Медиаиндекс (охват/заметность), если применимо"]
  action varchar [null, note: "Требуемое действие"]
  deadline date [null, note: "Срок реакции"]
  department_id int [null, ref: > department.id, note: "Ответственный отдел (маршрутизация)"]
  comment varchar [null, note: "Комментарий от LLM"]

  // ---- метаданные прогона LLM (для перекатегоризации и аудита) ----
  llm_model varchar [null, note: "Какая модель разметила"]
  prompt_version varchar [null, note: "Версия промпта/правил"]
  categorized_at timestamp [not null, default: `now()`, note: "Когда разметили. По этой отметке BP-4 находит переразмеченные события: categorized_at > showcase_event.updated_at"]

  indexes {
    categorized_at [name: "ix_categorized_event_categorized_at", note: "Под отбор переразмеченных событий в BP-4"]
  }

  Note: "Gold-слой BP-3: смысловые атрибуты. Факты берутся из normalized_item по FK. Перекатегоризация = UPDATE этой строки, факты не трогаются."
}

// ============================================================================
//  BP-4 — ВИТРИНА (плоская таблица под BI, слой представления)
// ============================================================================

// 14. Плоская витрина: одна широкая строка на событие (денормализовано, под BI)
Table showcase_event {
  id int [pk, increment, note: "Уникальный ID строки витрины"]
  categorized_event_id int [not null, unique, ref: > categorized_event.id, note: "Ключ для инкрементального UPSERT: одна строка витрины на размеченное событие"]
  raw_item_id int [not null, ref: > raw_item.id, note: "Drill-down до сырья (требование прозрачности ТЗ: из строки витрины -> к исходнику)"]

  // ---- ФАКТЫ (денормализовано: id из слоёв заменены на ИМЕНА через справочники) ----
  published_at date [null, note: "Дата"]
  title varchar [not null, note: "Заголовок"]
  media varchar [null, note: "СМИ"]
  region varchar [null, note: "Регион (region.name_display)"]
  macro_region varchar [null, note: "Федеральный округ"]
  latitude float [null, note: "Широта центра региона (WGS-84) из region.latitude — метка на карте рынка. Лежит в витрине, а НЕ берётся джойном к region: BI читает одну таблицу"]
  longitude float [null, note: "Долгота центра региона (WGS-84) из region.longitude — метка на карте рынка"]
  competitor varchar [null, note: "Конкурент / Объект (competitor.name)"]
  source_url varchar [null, note: "Ссылка на событие"]

  // ---- СМЫСЛЫ (денормализовано) ----
  priority varchar [not null, note: "П1..П4"]
  category varchar [not null, note: "Категория (category.name)"]
  tonality varchar [not null, note: "Тональность"]
  media_index numeric [null, note: "МедиаИндекс"]
  action varchar [null, note: "Требуемое действие"]
  deadline date [null, note: "Срок реакции"]
  department varchar [null, note: "Ответственный отдел (department.name)"]
  comment varchar [null, note: "Комментарий"]

  updated_at timestamp [not null, default: `now()`, note: "Когда строку последний раз собрали. Инкрементальный UPSERT, без полной перезагрузки. ВАЖНО: ставится временем Python (datetime.now(UTC)), а НЕ now() — в Postgres now() отдаёт время начала транзакции, и при сборке в одной транзакции с BP-3 строка навсегда осталась бы 'устаревшей'"]
  alerted_at timestamp [null, note: "BP-5: когда детектор последний раз проверял строку на значимость — НЕЗАВИСИМО от результата. Отбор BP-5: alerted_at IS NULL OR updated_at > alerted_at. Не по журналу alert — там легитимны события с нулём алертов (проверили, не значимо), и по нему нельзя отличить 'ещё не проверено' от 'проверено, но не сработало'"]

  indexes {
    published_at [name: "ix_showcase_event_published_at", note: "Лента событий по датам"]
    competitor [name: "ix_showcase_event_competitor", note: "Паспорт конкурента"]
    priority [name: "ix_showcase_event_priority", note: "Срез по приоритетам"]
    category [name: "ix_showcase_event_category", note: "Срез по категориям"]
  }

  Note: "Плоская витрина BP-4 под BI. Денормализована: id из слоёв заменены на читаемые имена через справочники, enum'ы — на подписи ('p1' -> 'П1', 'positive' -> 'позитивная'). РЕАЛИЗОВАНА физической таблицей с UPSERT по categorized_event_id (вариант с VIEW отклонён: BI нужны индексы и стабильный контракт колонок). Отбор инкрементальный: строки нет в витрине ИЛИ categorized_at > updated_at (перекатегоризация BP-3 доезжает сама). Витрина — ПРОИЗВОДНАЯ таблица: руками не редактируется, любая правка будет затёрта следующим UPSERT'ом, источник правды — categorized_event. raw_item_id обеспечивает drill-down к исходнику."
}

// ============================================================================
//  BP-5 — ДЕТЕКТОР ЗНАЧИМЫХ СОБЫТИЙ + АЛЕРТИНГ + МАРШРУТИЗАЦИЯ
// ============================================================================

// 15. Типы значимых событий + слова-маркеры для детекции. Зона аналитика
Table event_type {
  id int [pk, increment, note: "Уникальный ID типа значимого события"]
  name varchar [not null, unique, note: "судебный/надзорный риск, выигранный тендер, активный наём, расширение, M&A, закрытие объекта"]
  keywords varchar[] [not null, note: "Слова-маркеры: ['прокуратура', 'суд', 'иск', 'нарушения']. По ним детектор матчит title события (вхождение подстроки). Массив, не CSV-строка — по образцу region.name_aliases"]
  is_active boolean [not null, default: true]

  indexes {
    keywords [type: gin, name: "ix_event_type_keywords", note: "Быстрый поиск вхождений, тот же приём что ix_region_name_aliases"]
  }
}

// 16. Каналы доставки. Зона аналитика/админа
Table channel {
  id int [pk, increment, note: "Уникальный ID канала"]
  name varchar [not null, unique, note: "telegram, email, dashboard"]
  is_active boolean [not null, default: true]
}

enum user_role {
  pending  // только что зарегистрировался, доступа нет (кроме GET /users/me)
  viewer   // читает витрину/свои задачи, править не может
  analyst  // правит витрину, подтверждает pending -> viewer/analyst
  admin    // + управление пользователями/справочниками
}

// 17. Получатели алертов — конкретные люди, НЕ отделы. Также пользователь API
// (логин по email+паролю). Зона аналитика/админа
Table user {
  id int [pk, increment, note: "Уникальный ID получателя"]
  full_name varchar [null, note: "ФИО — для читаемости в админке, не критично"]
  department_id int [null, ref: > department.id, note: "В каком отделе числится. СПРАВОЧНО для маршрутизации BP-5 (см. routing_rule.user_id), но ЗНАЧИМО для видимости в BP-6: viewer видит только action_item своего отдела"]
  email varchar [not null, unique, note: "Адрес для канала email, он же логин API"]
  telegram_id bigint [null, unique, note: "Числовой chat_id для канала telegram (sendMessage требует id, не @username). NULL, пока пользователь не привязал telegram — на момент self-service регистрации по email он неизвестен"]
  password_hash varchar [not null, note: "bcrypt-хэш пароля для логина в API"]
  role user_role [not null, default: "pending", note: "Уровень доступа к API (не отдел): pending/viewer/analyst/admin"]
  is_active boolean [not null, default: true, note: "Уволен/в отпуске — гасим флагом, не удаляем (иначе потеряется история alert через FK RESTRICT)"]

  Note: "Список получателей курируется вручную и может не совпадать со штатом отдела (сегодня трое, завтра один) — поэтому department НЕ годится источником рассылки, только user."
}

// 17.1 Код сброса пароля (6 цифр), отправляется на email. Эфемерные данные —
// не audit-история, ondelete=CASCADE: удаление вместе с пользователем ничего
// не теряет. Один активный код на пользователя (старые удаляются при новом
// запросе, см. api/crud/users.py)
Table password_reset_code {
  id int [pk, increment, note: "Уникальный ID кода"]
  user_id int [not null, ref: > user.id, note: "Кому принадлежит код. ON DELETE CASCADE"]
  code_hash varchar [not null, note: "bcrypt-хэш 6-значного кода (тот же hash_password/verify_password, что и у пароля)"]
  expires_at timestamp [not null, note: "Когда код перестаёт быть валиден (password_reset_code_expire_minutes от создания)"]
  used_at timestamp [null, note: "Когда код использован (успешно или исчерпаны попытки)"]
  attempts int [not null, default: 0, note: "Число неверных попыток ввода — защита от перебора, максимум 5"]
  created_at timestamp [not null, default: `now()`, note: "Когда код сгенерирован"]
}

enum delivery_mode {
  instant  // немедленно — шлём сразу по событию (П1)
  digest   // сводка — копим и отправляем пакетом по расписанию (П2)
}
enum alert_status {
  queued   // строка заведена, доставка ещё не выполнена
  sent     // доставлено
  failed   // доставка сорвалась, см. error_message
}

// 18. Матрица маршрутизации: тип + приоритет -> получатель + канал + режим. Зона аналитика
Table routing_rule {
  id int [pk, increment, note: "Уникальный ID правила маршрутизации"]
  event_type_id int [not null, ref: > event_type.id, note: "Для какого типа значимого события"]
  priority priority_level [not null, note: "Для какого приоритета срабатывает правило. Порог значимости — не константа в коде, а сам факт наличия строки здесь"]
  user_id int [not null, ref: > user.id, note: "Кому конкретно отправлять (НЕ department_id — см. Table user)"]
  channel_id int [not null, ref: > channel.id, note: "В какой канал доставляем"]
  mode delivery_mode [not null, note: "instant (П1) | digest (П2)"]
  is_active boolean [not null, default: true]

  indexes {
    (event_type_id, priority, channel_id, user_id) [unique, note: "Несколько получателей и/или каналов на (тип,приоритет) = несколько строк — добавить/убрать адресата = добавить/деактивировать строку"]
  }
}

// 19. Журнал алертов: что/кому/куда отправлено. История + защита от повторной отправки
Table alert {
  id int [pk, increment, note: "Уникальный ID алерта"]
  showcase_event_id int [not null, ref: > showcase_event.id, note: "По какому событию витрины сработал алерт"]
  event_type_id int [not null, ref: > event_type.id, note: "Какой тип значимого события распознан"]
  priority priority_level [not null, note: "Приоритет события на момент алерта (снимок)"]
  user_id int [not null, ref: > user.id, note: "Кому ушло (снимок — правило/отдел человека завтра поменяют, история остаётся)"]
  channel_id int [not null, ref: > channel.id, note: "Каким каналом"]
  mode delivery_mode [not null, note: "Снимок режима из правила: instant | digest. По нему джоба-сводка находит свои алерты"]
  status alert_status [not null, default: "queued", note: "queued -> sent / failed"]
  error_message varchar [null, note: "Текст ошибки при status=failed"]
  created_at timestamp [not null, default: `now()`]
  sent_at timestamp [null, note: "Когда фактически доставлено"]

  indexes {
    (showcase_event_id, channel_id, user_id) [unique, note: "Один алерт на событие+канал+получателя — не слать дважды одному человеку"]
  }

  Note: "Журнал алертинга BP-5. Значимость решается поиском строки в routing_rule (тип+приоритет), она же даёт маршрут (user+channel+mode); сюда пишется факт и статус доставки."
}

// ============================================================================
//  BP-6 — ПЛАН ДЕЙСТВИЙ (единственная запись-часть; дашборды — в DataLens)
// ============================================================================

enum action_status {
  open         // открыта
  in_progress  // в работе
  done         // закрыта
}

// 20. План действий: по событию П1/П2 человек заводит задачу, отдел меняет статус.
//     Поля строго из ТЗ: задача -> отдел -> срок -> ожидаемый результат -> статус.
Table action_item {
  id int [pk, increment, note: "Уникальный ID задачи"]
  showcase_event_id int [not null, ref: > showcase_event.id, note: "По какому событию витрины заведена задача"]
  task varchar [not null, note: "Задача: что конкретно сделать (решение человека)"]
  department_id int [not null, ref: > department.id, note: "Ответственный отдел — ведущее поле для видимости (viewer видит только свой отдел)"]
  assigned_user_id int [null, ref: > user.id, note: "Кому конкретно назначена (адресат алерта BP-5, если задачу завёл AI-ассистент). NULL — задача отдела в целом, без привязки к человеку"]
  deadline date [null, note: "Срок"]
  expected_result varchar [null, note: "Ожидаемый результат"]
  status action_status [not null, default: "open", note: "Статус: open -> in_progress -> done. Меняют отделы через веб-форму"]
  created_at timestamp [not null, default: `now()`]
  updated_at timestamp [not null, default: `now()`, note: "Обновляется при смене статуса"]

  Note: "BP-6: план действий. Единственная часть BP-6 с записью — заполняется человеком через веб-форму (не DataLens). DataLens читает эту таблицу для дашборда 'план действий'."
}

// ============================================================================
//  BP-7 — АГЕНТ РАСШИРЕНИЯ ИСТОЧНИКОВ (админка = CRUD над существующими справочниками)
// ============================================================================

enum source_candidate_status {
  new        // ещё не переносился (или переносился, но не прошёл по score/порогу)
  promoted   // перенесён в source
}

// 21. Очередь кандидатов в новые источники.
//     Агент (следующая итерация) пишет domain/url/competitor_id/score.
//     Когда score строго больше настраиваемого порога (core.config.settings.
//     source_candidate_score_threshold, env SOURCE_CANDIDATE_SCORE_THRESHOLD,
//     по умолчанию 0.5) — SourceCandidatePromoter (src/bp7/pipeline.py)
//     переносит domain в source (is_active=true) и ставит status=promoted.
Table source_candidate {
  id int [pk, increment, note: "Уникальный ID кандидата"]
  domain varchar [not null, unique, note: "Найденный домен-кандидат. UNIQUE — не предлагать дважды"]
  competitor_id int [null, ref: > competitor.id, note: "По какому конкуренту/запросу нашли"]
  url varchar [null, note: "Url найденного кандидата к парсингу"]
  score decimal [null, note: "Оценка релевантности от LLM, 0.00–1.00"]
  status source_candidate_status [not null, default: "new", note: "new -> promoted. Индекс — отбор на перенос без JOIN/NOT EXISTS с source"]
  is_active boolean [not null, default: true, note: "false — снять кандидата с рассмотрения, не удаляя строку"]
  created_at timestamp [not null, default: `now()`, note: "Когда кандидат добавлен"]

  Note: "BP-7: очередь кандидатов в источники. Перенос в source — автоматический, по порогу score (не ручная модерация): см. src/bp7/pipeline.py::SourceCandidatePromoter и src/bp7/BP7_README.md. Порог настраивается через .env, без правки кода. status=promoted проставляется в момент переноса, чтобы при росте таблицы не пересматривать уже обработанные строки."
}

// ============================================================================
//  ГРУППЫ ДЛЯ ВИЗУАЛА В dbdiagram.io
//  Рисуют подписанные рамки вокруг таблиц каждого BP на холсте.
//  Названия таблиц в БД НЕ меняются — это только визуальная разметка.
// ============================================================================

TableGroup "BP-1 — Сбор данных" {
  trigger
  competitor
  source
  search_task
  raw_item
}

TableGroup "BP-2 — Нормализация и фильтрация" {
  region
  black_domain
  stop_word
  topic_limit
  normalized_item
}

TableGroup "BP-3 — LLM-категоризация" {
  category
  department
  categorized_event
}

TableGroup "BP-4 — Витрина (BI)" {
  showcase_event
}

TableGroup "BP-5 — Алертинг и маршрутизация" {
  event_type
  channel
  user
  password_reset_code
  routing_rule
  alert
}

TableGroup "BP-6 — План действий" {
  action_item
}

TableGroup "BP-7 — Расширение источников" {
  source_candidate
}
```
