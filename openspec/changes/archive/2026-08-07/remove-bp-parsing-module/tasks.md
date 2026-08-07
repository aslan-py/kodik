## 1. Удаление модуля

- [x] 1.1 Удалить директорию `src/bp_parsing/` целиком (включая `__pycache__`): `__init__.py`, `constants.py`, `search.py`, `pipeline.py`, `storage.py`, `BP_PARSING_README.md`.

## 2. Очистка хвостов

- [x] 2.1 В `core/config.py` убрать закомментированный блок `# ===== Parsing (универсальный загрузчик, src/bp_parsing) =====` и три строки под ним (`parsed_pages_dir`/`parsing_headless`/`parsing_timeout_ms`).
- [x] 2.2 В `.gitignore` убрать строку `bp_parsing/`.

## 3. Проверка

- [x] 3.1 `git status` / `git ls-files src/bp_parsing/` — подтвердить, что директория не была отслежена git и что после удаления `git status` не показывает файлы `src/bp_parsing/` как удалённые из индекса. Подтверждено: `git status --short` показывает только `.gitignore`/`core/config.py` как изменённые, `src/bp_parsing/` не фигурирует.
- [x] 3.2 Повторный grep по репозиторию на `bp_parsing`/`parsed_pages` — убедиться, что ссылок не осталось. Подтверждено: единственные совпадения — файлы самого этого изменения (`proposal.md`/`tasks.md`/`README.md`), в коде проекта — ноль.
- [x] 3.3 Импорт `core.config` — убедиться, что удаление комментариев не сломало парсинг конфига. Подтверждено: `from core.config import settings` отрабатывает без ошибок.
