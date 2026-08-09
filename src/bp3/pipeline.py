"""Точка входа BP-3: normalized_item -> categorized_event (через LLM-конвейер).

Та же сборка `Pipeline([...])` из 9 модулей, что и в корневом `main.py` —
он не тронут и остаётся отдельным скриптом для ручной отладки. Здесь —
переиспользуемая функция по контракту `run_bp2`/`run_bp4`/`run_bp5`
(`async def -> dict`), чтобы BP-3 можно было вызвать так же, как остальные
этапы конвейера (см. core/pipeline/registry.py).

`Pipeline.run()` внутри синхронный (LangChain/Tavily-клиенты — sync) —
оборачиваем в `async def` только ради единого контракта с остальными
этапами, само выполнение блокирующее.

Запуск:
    python -m src.bp3.pipeline
"""

import os

from dotenv import load_dotenv

from src.bp3.config import get_llm
from src.bp3.models_llm import Pipeline
from src.bp3.modules.action_planning_module import ActionPlanningModule
from src.bp3.modules.categorized_module import CategorizedModule
from src.bp3.modules.comment_action_module import CommentActionModule
from src.bp3.modules.generation_task_module import GenerationTaskModule
from src.bp3.modules.input_data_module import InputDataModule
from src.bp3.modules.media_activity_module import MediaActivityModule
from src.bp3.modules.save_results_module import SaveResultsModule
from src.bp3.modules.source_finder_module import SourceFinderModule
from src.bp3.modules.tone_analysis_module import ToneAnalysisModule


async def run_bp3() -> dict:
    """Один прогон конвейера BP-3: normalized_item -> categorized_event.

    Возвращает сводку прогона (сколько новостей обработано/размечено).
    """
    load_dotenv()
    if not os.getenv('OPENROUTER_API_KEY'):
        raise RuntimeError('OPENROUTER_API_KEY не задан')
    if not os.getenv('TAVILY_API_KEY'):
        raise RuntimeError('TAVILY_API_KEY не задан')

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
            SourceFinderModule(),
            SaveResultsModule(),
        ]
    )
    result = pipeline.run()

    return {
        'news_processed': len(result.news or []),
        'categorized': len(result.category_news or []),
        'domains_found': len(result.domains_to_add or []),
    }


if __name__ == '__main__':
    import asyncio

    print(asyncio.run(run_bp3()))
