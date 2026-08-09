"""Точка входа BP-3: normalized_item -> categorized_event (через LLM-конвейер).

Единственная сборка `Pipeline([...])` для BP-3 — корневого `main.py` больше
нет, ручная отладка через `python -m src.bp3.pipeline` (см. ниже), как у
остальных BP. Переиспользуемая функция по контракту `run_bp2`/`run_bp4`/
`run_bp5` (`async def -> dict`), чтобы BP-3 можно было вызвать так же, как
остальные этапы конвейера (см. core/pipeline/registry.py).

`Pipeline.run()` внутри синхронный (LangChain/Tavily-клиенты — sync,
модули `process()` не асинхронные) — выполняется в отдельном потоке через
`asyncio.to_thread`. Это не просто формальность: `run_bp3()` вызывается
через `await` из уже работающего event loop (админка/CLI), и если бы
`Pipeline.run()` выполнялся прямо на этом потоке, доступ к БД внутри
модулей (`fetch_data`/сохранение — теперь `AsyncSessionLocal`) не смог бы
сам открыть новый event loop — "RuntimeError: asyncio.run() cannot be
called from a running event loop".

Внутри потока — ОДИН event loop на весь прогон (`_run_pipeline_in_thread`
ниже), а не отдельный `asyncio.run()` на каждый async-вызов внутри
модулей. На Windows (ProactorEventLoop) закрытие loop'а и создание нового
на следующий вызов рвёт пул соединений `core.database.engine` — он
модульный синглтон, и его asyncpg-соединения остаются привязаны к loop'у,
под которым были открыты; повторный `asyncio.run()` в том же потоке
создаёт НОВЫЙ loop, а старые соединения пула ссылаются на уже закрытый —
"AttributeError: 'NoneType' object has no attribute 'send'" при попытке
их переиспользовать. Модули (`input_data_module.py`/`save_results_module.py`)
берут этот единый loop через `asyncio.get_event_loop()` и гоняют корутины
через `loop.run_until_complete(...)`, не создавая свои.

Запуск:
    python -m src.bp3.pipeline
"""

import asyncio

from src.bp3.config import get_llm
from src.bp3.models_llm import Pipeline
from src.bp3.modules.action_planning_module import ActionPlanningModule
from src.bp3.modules.categorized_module import CategorizedModule
from src.bp3.modules.comment_action_module import CommentActionModule
from src.bp3.modules.expected_result_module import ExpectedResultModule
from src.bp3.modules.generation_task_module import GenerationTaskModule
from src.bp3.modules.input_data_module import InputDataModule
from src.bp3.modules.media_activity_module import MediaActivityModule
from src.bp3.modules.save_results_module import SaveResultsModule
from src.bp3.modules.source_finder_module import SourceFinderModule
from src.bp3.modules.tone_analysis_module import ToneAnalysisModule


def _run_pipeline_in_thread(pipeline: Pipeline):
    """Прогнать `Pipeline.run()` под ОДНИМ event loop на весь вызов.

    Выполняется внутри `asyncio.to_thread` — у потока изначально нет
    своего loop'а. Создаём его явно и держим на всё время прогона, чтобы
    все `AsyncSessionLocal`-вызовы внутри модулей шли через один и тот же
    loop (см. докстринг модуля — почему несколько отдельных
    `asyncio.run()` в одном потоке ломают пул соединений на Windows).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return pipeline.run()
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def run_bp3() -> dict:
    """Один прогон конвейера BP-3: normalized_item -> categorized_event.

    Возвращает сводку прогона (сколько новостей обработано/размечено).

    Ключи (`OPENROUTER_API_KEY`/`TAVILY_API_KEY`) проверять здесь не нужно —
    `core.config.Settings` уже провалидировал их обязательность при старте
    приложения (см. core/config.py).
    """
    llm = get_llm()
    pipeline = Pipeline(
        [
            InputDataModule(),
            CategorizedModule(llm),
            ActionPlanningModule(),
            ToneAnalysisModule(llm),
            CommentActionModule(llm),
            MediaActivityModule(),
            GenerationTaskModule(llm),
            ExpectedResultModule(llm),
            SourceFinderModule(),
            SaveResultsModule(),
        ]
    )
    result = await asyncio.to_thread(_run_pipeline_in_thread, pipeline)

    domains_found = sum(
        len(v.get('sources', []))
        for v in (result.domains_to_add or {}).values()
    )
    return {
        'news_processed': len(result.news or []),
        'categorized': len(result.category_news or []),
        'domains_found': domains_found,
    }


if __name__ == '__main__':
    import asyncio

    print(asyncio.run(run_bp3()))
