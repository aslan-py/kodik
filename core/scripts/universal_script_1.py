"""Полу-реальный прогон конвейера BP-1…BP-5 с двумя заглушками + сервер API.

Показывает, как выглядит пайплайн, пока парсинг (BP-1) и LLM-категоризация
(BP-3) ещё не готовы: эти два этапа заполняются фейковыми, но правдоподобными
данными (теми же, что использует core/scripts/seed_all.py — никакой новый
набор здесь не придумывается), а BP-2/BP-4/BP-5 прогоняются НАСТОЯЩИМИ
конвейерами — теми же функциями, что пойдут в бой (src/bp2/pipeline.py,
src/bp4/pipeline.py, src/bp5/pipeline.py).

Запуск (одна команда, из корня проекта, внутри venv):
    python -m core.scripts.universal_script_1

Делает по порядку:
  1. pip install -r requirements.txt -r requirements-dev.txt
  2. alembic upgrade head
  3. Справочники (core/scripts/stages/dictionaries) — идемпотентно
  4. Очистка данных предыдущего прогона (BP-1…BP-6), справочники не трогает
  5. BP-1 — ЗАГЛУШКА (парсинга ещё нет): core/scripts/stages/bp1.seed()
  6. BP-2 — РЕАЛЬНЫЙ конвейер: src.bp2.pipeline.run_bp2()
  7. BP-3 — ЗАГЛУШКА (LLM ещё нет): core/scripts/stages/bp3.seed()
  8. BP-4 — РЕАЛЬНЫЙ конвейер: src.bp4.pipeline.run_bp4()
  9. BP-5 — РЕАЛЬНЫЙ конвейер (детект + маршрутизация). Перед этим шагом
     скрипт спросит в терминале, слать ли алерты по-настоящему на этом
     прогоне:
       - «нет» (по умолчанию) — core/scripts/stages/bp5.seed() вызывает
         sync_alerts(deliver=False): сеть не трогаем вообще, таблица alert
         заполняется для отчёта, но ничего никуда не уходит;
       - «да» — sync_alerts(deliver=True): реально стучимся в SMTP/
         Telegram Bot API. КУДА уйдёт письмо/сообщение, решает
         TRUE_ALERTING из .env (скрипт его НЕ трогает и НЕ переключает —
         только объясняет, что при текущем значении произойдёт):
           TRUE_ALERTING=False → всё уходит на ОДИН адрес — TEST_EMAIL/
             TEST_TG из твоего .env, независимо от email/telegram_id
             демо-получателей;
           TRUE_ALERTING=True → уходит на email/telegram_id КАЖДОГО
             демо-получателя (Иванов Пётр, Петрова Анна, Сидоров Олег) —
             по умолчанию там заглушки (ivanov@kodik.example и т.п.), и
             скрипт предложит подставить вместо них настоящие контакты.
  10. Поднимает uvicorn (api.main:app) и открывает /docs в браузере

Требует поднятой БД (`docker-compose up -d`) и настроенного `.env`
(см. `.env.example`) — их сам не проверяет и не создаёт. Для реальной
отправки email нужны рабочие MAIL_*-настройки в `.env`; для telegram —
рабочий TELEGRAM_BOT_TOKEN И получатель должен САМ первым написать боту
/start — Telegram API не разрешает ботам писать первыми.
"""

import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from core.config import settings


def _find_project_root(start: Path) -> Path:
    """Корень проекта = ближайший наверх каталог с alembic.ini.

    Не привязываемся к тому, на сколько уровней вложен сам этот файл
    (core/scripts/universal_script_1.py) — pip install/alembic upgrade
    ниже должны запускаться из корня репозитория, а не из core/scripts.
    """
    for parent in (start, *start.parents):
        if (parent / 'alembic.ini').exists():
            return parent
    raise RuntimeError(
        'Не найден корень проекта (alembic.ini) выше '
        f'{start} — переместил кто-то файлы?'
    )


ROOT = _find_project_root(Path(__file__).resolve().parent)
HOST = settings.api_host
PORT = settings.api_port
DOCS_URL = f'http://{HOST}:{PORT}/docs'

sys.stdout.reconfigure(encoding='utf-8')


def install_dependencies() -> None:
    print('=== [1/5] Устанавливаю зависимости ===')
    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'install',
            '-r',
            'requirements.txt',
            '-r',
            'requirements-dev.txt',
        ],
        cwd=ROOT,
        check=True,
    )


def run_migrations() -> None:
    print('\n=== [2/5] Прогоняю миграции (alembic upgrade head) ===')
    subprocess.run(
        [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
        cwd=ROOT,
        check=True,
    )


def _ask_yes_no(prompt: str) -> bool:
    """input() с безопасным дефолтом «нет», если стоит не-интерактивно."""
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in ('y', 'yes', 'д', 'да')


def seed_pipeline() -> None:
    """Справочники → заглушки BP-1/BP-3 → реальные конвейеры BP-2/BP-4/BP-5.

    Импорты — только здесь: до install_dependencies() зависимостей может не
    быть вообще (свежий venv у другого разработчика), импортировать их на
    уровне модуля до установки нельзя.
    """
    import asyncio

    from sqlalchemy import select

    from core.config import settings
    from core.database import AsyncSessionLocal
    from core.scripts.stages import bp1 as bp1_stage
    from core.scripts.stages import bp3 as bp3_stage
    from core.scripts.stages import bp5 as bp5_stage
    from core.scripts.stages import dictionaries
    from core.scripts.stages.cascade import (
        DICTIONARY_ORDER,
        PIPELINE_ORDER,
        count_rows,
    )
    from src.bp2.pipeline import run_bp2
    from src.bp4.pipeline import run_bp4
    from src.bp5.models import User
    from src.bp5.pipeline import sync_alerts

    async def edit_demo_contacts() -> None:
        """Заменить заглушки (ivanov@kodik.example и т.п.) на настоящие
        email/telegram chat_id для демо-получателей — по одному на строку.

        Работает, только когда TRUE_ALERTING=True: только в этом режиме
        BP-5 вообще смотрит на email/telegram_id получателя (см.
        prepare_bp5_delivery).
        """
        async with AsyncSessionLocal() as session:
            for demo in dictionaries.USERS:
                user = (
                    await session.execute(
                        select(User).where(User.email == demo['email'])
                    )
                ).scalar_one_or_none()
                if user is None:
                    continue
                print(
                    f'\n{demo["full_name"]} — сейчас: '
                    f'{user.email}, telegram_id={user.telegram_id}'
                )
                email = input(
                    '  Реальный email (пусто — оставить как есть): '
                ).strip()
                tg = input(
                    '  Реальный telegram chat_id (пусто — оставить как есть): '
                ).strip()

                # email/telegram_id уникальны на всю таблицу user — её
                # делят демо-получатели и настоящие API-аккаунты, поэтому
                # уже занятое значение (например, свой же email из другого
                # теста) нужно поймать заранее, а не ловить IntegrityError.
                if email:
                    taken = (
                        await session.execute(
                            select(User).where(
                                User.email == email, User.id != user.id
                            )
                        )
                    ).scalar_one_or_none()
                    if taken is not None:
                        print(
                            f'    email {email} уже занят пользователем '
                            f'id={taken.id} — оставляю {user.email}'
                        )
                    else:
                        user.email = email
                if tg:
                    tg_id = int(tg)
                    taken = (
                        await session.execute(
                            select(User).where(
                                User.telegram_id == tg_id, User.id != user.id
                            )
                        )
                    ).scalar_one_or_none()
                    if taken is not None:
                        print(
                            f'    telegram_id {tg_id} уже занят '
                            f'пользователем id={taken.id} — оставляю '
                            f'{user.telegram_id}'
                        )
                    else:
                        user.telegram_id = tg_id
            await session.commit()

    async def prepare_bp5_delivery() -> bool:
        """Спрашивает, слать ли BP-5 реально на этом прогоне, и честно
        объясняет, куда уйдёт письмо/telegram при ТЕКУЩЕМ TRUE_ALERTING
        из .env — сам его не меняет и не подменяет.

        Возвращает True, если нужно вызвать sync_alerts(deliver=True)
        вместо безопасной заглушки bp5_stage.seed() (deliver=False).
        """
        wants_real = _ask_yes_no(
            '\nПротестировать РЕАЛЬНУЮ отправку алертов (email/telegram) '
            'на этом прогоне?\n'
            'Для telegram получатель должен САМ первым написать боту '
            '/start — иначе Bot API откажет.\n'
            'Да/нет [y/N]: '
        )
        if not wants_real:
            return False

        if not settings.true_alerting:
            print(
                '\nВ .env стоит TRUE_ALERTING=False — значит ВСЕ алерты '
                'реально уйдут на ОДИН адрес: email='
                f'{settings.test_email!r}, telegram chat_id='
                f'{settings.test_tg!r} (твои TEST_EMAIL/TEST_TG). '
                'Настоящие email/telegram_id демо-получателей при этом не '
                'используются вообще — вводить их незачем.'
            )
            return True

        print(
            '\nВ .env стоит TRUE_ALERTING=True — значит алерты уйдут на '
            'email/telegram_id КАЖДОГО демо-получателя из таблицы user. '
            'Сейчас там заглушки (ivanov@kodik.example и т.п.) — реальная '
            'отправка на них не пройдёт (упадёт безопасно, '
            'alert.status=failed).'
        )
        if _ask_yes_no(
            'Ввести настоящие email/telegram chat_id для демо-получателей? '
            '[y/N]: '
        ):
            await edit_demo_contacts()
        return True

    async def print_summary(session) -> None:
        print('\nСтрок в таблицах:')
        for model in reversed(DICTIONARY_ORDER + PIPELINE_ORDER):
            count = await count_rows(session, model)
            print(f'  {model.__tablename__:22} {count}')

    async def run() -> None:
        async with AsyncSessionLocal() as session:
            print('  Справочники (идемпотентно)...')
            added = await dictionaries.seed(session)
            print(f'    +{added}')

            print('  Очищаю данные предыдущего прогона (BP-1…BP-6)...')
            deleted = await bp1_stage.clear(session)
            print(f'    -{deleted}')

            print(
                '  BP-1 — ЗАГЛУШКА (парсинга ещё нет): фейковое сырьё '
                'raw_item...'
            )
            added = await bp1_stage.seed(session)
            print(f'    +{added}')

            await session.commit()

        print('  BP-2 — РЕАЛЬНЫЙ конвейер: raw_item -> normalized_item...')
        summary = await run_bp2()
        print(f'    {summary}')

        async with AsyncSessionLocal() as session:
            print(
                '  BP-3 — ЗАГЛУШКА (LLM ещё нет): фейковая разметка '
                'categorized_event...'
            )
            added = await bp3_stage.seed(session)
            await session.commit()
            print(f'    +{added}')

        print(
            '  BP-4 — РЕАЛЬНЫЙ конвейер: разметка -> витрина showcase_event...'
        )
        summary = await run_bp4()
        print(f'    {summary}')

        real_delivery = await prepare_bp5_delivery()

        if real_delivery:
            print(
                '  BP-5 — РЕАЛЬНЫЙ конвейер (детект + маршрутизация + '
                f'РЕАЛЬНАЯ отправка, TRUE_ALERTING='
                f'{settings.true_alerting} из .env)...'
            )
            async with AsyncSessionLocal() as session:
                summary = await sync_alerts(session, deliver=True)
                await session.commit()
            added = summary['alerts']
        else:
            print(
                '  BP-5 — РЕАЛЬНЫЙ конвейер (детект + маршрутизация, БЕЗ '
                'реальной отправки email/telegram)...'
            )
            async with AsyncSessionLocal() as session:
                added = await bp5_stage.seed(session)
                await session.commit()
        print(f'    +{added} алертов')

        async with AsyncSessionLocal() as session:
            await print_summary(session)

    print('\n=== [3/5] Заполняю пайплайн (справочники + BP-1…BP-5) ===')
    asyncio.run(run())


def _wait_and_open_browser() -> None:
    for _ in range(60):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(DOCS_URL, timeout=1)
        except urllib.error.URLError:
            continue
        webbrowser.open(DOCS_URL)
        return


def serve() -> None:
    import uvicorn

    print(f'\n=== [4/5] Поднимаю uvicorn на {DOCS_URL} ===')
    threading.Thread(target=_wait_and_open_browser, daemon=True).start()

    print(
        '=== [5/5] Открываю документацию в браузере, как только сервер '
        'ответит ==='
    )
    uvicorn.run('api.main:app', host=HOST, port=PORT)


def main() -> None:
    install_dependencies()
    run_migrations()
    seed_pipeline()
    serve()


if __name__ == '__main__':
    main()
