## 1. Миграция

- [x] 1.1 Сгенерировать пустую ревизию Alembic (`down_revision='d8be5a20d9b1'`, текущий head)
- [x] 1.2 `upgrade()`: raw SQL `INSERT` с полями `full_name='Admin'`, `email='admin@admin.ru'`, `role='admin'`, `password_hash=hash_password('Admin123')` — с `ON CONFLICT (email) DO NOTHING`. `department_id`/`telegram_id` не указаны (остаются `NULL` по умолчанию колонки); `created_at` в задаче упомянут ошибочно — у `user` такой колонки нет (проверено по `information_schema.columns`), в реализации не используется
- [x] 1.3 `downgrade()`: `DELETE FROM "user" WHERE email = 'admin@admin.ru'` (таблица `user` — зарезервированное слово Postgres, экранирована кавычками)
- [x] 1.4 Комментарий в начале файла миграции — почему данные заводятся здесь, а не в `core/scripts/stages/dictionaries.py` (см. design.md, Decisions), и что пароль дефолтный, подлежит смене

## 2. Применение и проверка

- [x] 2.1 Применить миграцию (`alembic upgrade head`) на локальной БД
- [x] 2.2 Проверить в БД: ровно одна строка `user` с `email='admin@admin.ru'`, `role='admin'`, `is_active=true` (id=232, department_id/telegram_id NULL)
- [x] 2.3 Войти в `/admin` под `admin@admin.ru` / `Admin123` — проверено вызовом `UserAdmin.authenticate()` напрямую: возвращает id пользователя; с неверным паролем — `None`
- [x] 2.4 Идемпотентность подтверждена на уровне SQL: строка вручную заведена с `full_name='Someone Else'`, `role='analyst'`, другим паролем — повторный `INSERT ... ON CONFLICT (email) DO NOTHING` (тот же, что в `upgrade()`) её не тронул, дубль не создан
- [x] 2.5 `alembic downgrade -1` → строка удалена (count=0) → `alembic upgrade head` → строка создана заново чисто (count=1). После — состояние БД восстановлено вручную до `admin@admin.ru`/`Admin123`/`admin` (после теста 2.4 в БД временно был левый "Someone Else"/analyst)

## 3. Уборка за собой

- [x] 3.1 Сменить пароль администратора через `/admin` (кнопка смены пароля у `UserAdmin`) на средах, где к репозиторию есть посторонний доступ — захардкоженный `Admin123` не должен оставаться боевым паролем
