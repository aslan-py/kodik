# Итоговая проверка административной навигации

Дата: 2026-08-13.

## Автоматические проверки

- Headless browser: `1 passed` — точный порядок пяти видимых разделов,
  отсутствие старых самостоятельных разделов, скрытие технического
  `PipelineControlMarker`, переходы через меню и прямые URL для всех пяти
  banner-состояний.
- Admin suite: `20 passed, 1 skipped` — browser-тест является opt-in и
  отдельно выполнен с `KODIK_RUN_ADMIN_BROWSER_TESTS=1`.
- Полный suite: `757 passed, 2 skipped`.
- Ruff: без ошибок.
- `node --check api/admin/ui/admin.js`: без ошибок.

Прямые URL проверены для `Competitor`, `Region`, `EventType` и `RawItem`.
Pipeline проверен на корне `#/`. Сохранение widget actions, read-only/CRUD и
прав пользователей покрыто целевыми admin-тестами.

## Визуальная матрица

Проверены светлая и тёмная темы, desktop 1440×1100 и минимальная ширина
768×900, компактное и раскрытое состояние меню. Горизонтальная прокрутка
страницы отсутствует; banner, таблицы и pipeline actions не перекрываются.

| Ширина | Меню | Светлая тема | Тёмная тема |
|---|---|---|---|
| Desktop | Компактное | [PNG](screenshots/desktop-compact-light.png) | [PNG](screenshots/desktop-compact-dark.png) |
| Desktop | Раскрытое | [PNG](screenshots/desktop-expanded-light.png) | [PNG](screenshots/desktop-expanded-dark.png) |
| 768 px | Компактное | [PNG](screenshots/minimum-compact-light.png) | [PNG](screenshots/minimum-compact-dark.png) |
| 768 px | Раскрытое | [PNG](screenshots/minimum-expanded-light.png) | [PNG](screenshots/minimum-expanded-dark.png) |

Визуальный просмотр подтвердил различимые pipeline/settings/final зоны,
контрастный active state, читаемый banner и корректное responsive-поведение.
