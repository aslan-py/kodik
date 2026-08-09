"""Асинхронное подключение к БД для BP-3 — отдельный engine с `NullPool`.

BP-3 гоняет `Pipeline.run()` в отдельном потоке со своим event loop —
каждый прогон создаёт и закрывает свой (см.
`src/bp3/pipeline.py::_run_pipeline_in_thread`). Общий `core.database.engine`
пулит соединения и привязывает пул к ПЕРВОМУ event loop'у, который его
коснулся: при повторном прогоне BP-3 (новый поток => новый loop) это либо
падает (`AttributeError` на уже закрытый прокси — если старый loop успел
закрыться), либо виснет намертво (если старый loop ещё жив, но не крутится
в текущем потоке — обращение к его соединению никогда не получит ответ).

`NullPool` не держит соединения между чекаутами — каждый запрос открывает
и закрывает своё, привязки к конкретному loop'у не остаётся, кросс-loop
конфликта нет (тот же приём, что уже применяется в `tests/conftest.py`
ровно для этого класса проблем с asyncpg). Отдельный engine, а не
`poolclass=NullPool` на общем `core.database.engine` — чтобы не убирать
пулинг соединений для всего остального проекта (API/админка), которому
он нужен для производительности.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings

engine = create_async_engine(settings.database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
