from unittest.mock import Mock

from src.bp3.models_llm import (
    CategorizedItem,
    CategorizedResponse,
    ProjectContext,
)
from src.bp3.modules.categorized_module import CategorizedModule


def test_categorization_does_not_request_or_depend_on_echoed_article_text():
    """Текст статьи остаётся из входа, а LLM возвращает только категорию."""
    structured_llm = Mock()
    structured_llm.invoke.return_value = CategorizedResponse(
        items=[CategorizedItem(id=10, category='репутационный риск')]
    )
    llm = Mock()
    llm.with_structured_output.return_value = structured_llm

    result = CategorizedModule(llm).process(
        ProjectContext(news=[{'id': 10, 'text': 'Длинный исходный текст'}])
    )

    assert result.category_news == [
        {
            'id': 10,
            'text': 'Длинный исходный текст',
            'category': 'репутационный риск',
        }
    ]
    prompt = structured_llm.invoke.call_args.args[0]
    assert 'Не возвращай text' in prompt
