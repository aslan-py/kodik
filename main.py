import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

from dotenv import load_dotenv

from src.bp3.config import get_llm
from src.bp3.models_llm import Pipeline
from src.bp3.modules.action_planning_module import ActionPlanningModule
from src.bp3.modules.categorized_module import CategorizedModule
from src.bp3.modules.comment_action_module import CommentActionModule
from src.bp3.modules.input_data_module import InputDataModule
from src.bp3.modules.save_results_module import SaveResultsModule
from src.bp3.modules.tone_analysis_module import ToneAnalysisModule

if __name__ == '__main__':
    load_dotenv()
    api_key = os.getenv('KODIK_API_KEY')
    if not api_key:
        raise ValueError('KODIK_API_KEY не найден')

    llm = get_llm()

    pipeline = Pipeline(
        [
            InputDataModule(),
            CategorizedModule(llm),
            ActionPlanningModule(),
            ToneAnalysisModule(llm),
            CommentActionModule(llm),
            SaveResultsModule(),
        ]
    )

    result = pipeline.run()

    print('\n========== CategorizedModule ==========')
    print(result.category_news)
    print('\n========== ActionPlanningModule ==========')
    print(result.priority)
    print(result.deadline)
    print(result.department)
    print('\n========== ToneAnalysisModule ==========')
    print(result.tone_of_news)
    print('\n========== CommentActionModule ==========')
    print(result.comments)
    print(result.actions)
