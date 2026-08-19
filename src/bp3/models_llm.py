"""Базовые классы и схемы данных для модулей пайплайна."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

SYSTEM_PROMPT_PATH = Path(__file__).parent / 'prompts' / 'system_prompt.txt'


# ========== Контекст проекта ==========
class ProjectContext(BaseModel):
    """Содержит контекст проекта — поля заполняются по
    мере выполнения модулей в пайплайне."""

    # Входные данные
    news: list[dict] | None = None
    manual_cat: list[dict] | None = None
    manual_dept: list[dict] | None = None
    news_stats: dict[int, dict[str, int]] | None = None
    count_sources: int | None = None
    domains: list[str] | None = None
    competitors: list[dict] | None = None

    # Категоризация
    category_news: list[dict] | None = None

    # Приоритет, дедлайн, отдел
    priority: list[dict] | None = None
    deadline: list[dict] | None = None
    department: list[dict] | None = None

    # Тональность
    tone_of_news: list[dict] | None = None

    # Комментарии и действия
    comments: list[dict] | None = None
    actions: list[dict] | None = None

    # Расчет медиа активности
    media_activity_index: list[dict] | None = None

    # Формирование задач
    tasks: list[dict] | None = None

    # Ожидаемый результат
    expected_result: list[dict] | None = None

    # Добавление новых ресурсов
    domains_to_add: dict[int, dict] | None = None


# ========== Базовые классы модулей ==========
class BaseModule(ABC):
    """Базовый класс для всех модулей пайплайна."""

    @abstractmethod
    def process(self, ctx: ProjectContext) -> ProjectContext:
        """Выполняет свой шаг и возвращает дополненные данные."""
        pass


class LLMModule(BaseModule):
    """Базовый класс для модулей, которые обращаются к LLM."""

    def __init__(self, llm: ChatOpenAI):
        """Сохраняет клиент LLM."""
        self.llm = llm

    def invoke_llm(self, prompt: str, ctx: ProjectContext):
        """Отправляет запрос в LLM: общий системный промпт + промпт шага.

        `ctx` пока не используется — оставлен на будущее, чтобы можно было
        подставлять в системный промпт данные из контекста.
        """
        system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding='utf-8')
        return self.structured_llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]
        )


# ========== Конвейер ==========
class Pipeline:
    """Запускает модули один за другим."""

    def __init__(self, modules: list[BaseModule]):
        """Сохраняет список модулей в порядке выполнения."""
        self.modules = modules

    def run(self) -> ProjectContext:
        """Прогоняет данные через все модули и возвращает результат."""
        ctx = ProjectContext()
        for module in self.modules:
            print(f'Запуск модуля: {module.__class__.__name__}')
            ctx = module.process(ctx)
        return ctx


# ========== Pydantic‑схемы для structured output ==========
class CategorizedItem(BaseModel):
    """Определяет вид ответа с категорией для каждой новости."""

    id: int
    category: str | None = None


class CategorizedResponse(BaseModel):
    """Определяет вид ответа LLM: категории для всех новостей."""

    items: list[CategorizedItem] = Field(
        description='Результат категоризации: по элементу на каждую новость'
    )


ToneLevel = Literal['positive', 'negative', 'alarming', 'neutral', 'irrelevant']


class ToneItem(BaseModel):
    """Определяет вид ответа с тональностью для каждой новости."""

    id: int
    tone_of_news: ToneLevel


class ToneResponse(BaseModel):
    """Определяет вид ответа LLM: тональность для всех новостей."""

    items: list[ToneItem] = Field(
        description='Тональность: по одному элементу на каждую новость'
    )


class CommentActionItem(BaseModel):
    """Определяет вид ответа с комментарием и рекомендацией для каждой
    новости."""

    id: int
    comments: str = Field(
        description='Краткий комментарий: что произошло и почему это важно'
    )
    actions: str = Field(description='Рекомендация по действию для компании')


class CommentActionResponse(BaseModel):
    """Определяет вид ответа LLM: комментарии и рекомендации."""

    items: list[CommentActionItem] = Field(
        description='Комментарии и рекомендации: по элементу на каждую новость'
    )


class GenerationTaskItem(BaseModel):
    """Определяет вид ответа со списком задач для каждой новости."""

    id: int
    tasks: list[str] = Field(
        ...,
        description=(
            'Список из 1–3 конкретных, измеримых и практических задач, '
            'которые необходимо выполнить для реализации рекомендации '
            '(действия) по данной новости'
        ),
    )


class GenerationTaskResponse(BaseModel):
    """Определяет вид ответа LLM: задачи для всех новостей."""

    items: list[GenerationTaskItem] = Field(
        ..., description='Список элементов для каждой новости'
    )


class ExpectedResultItem(BaseModel):
    """Определяет вид ответа с ожидаемым результатом для каждой новости."""

    id: int
    expected_result: str = Field(
        description=(
            'Ожидаемый измеримый результат, '
            'к которому приведёт выполнение задач по данной новости'
        ),
    )


class ExpectedResultResponse(BaseModel):
    """Определяет вид ответа LLM: ожидаемые результаты."""

    items: list[ExpectedResultItem] = Field(
        ..., description='Список элементов для каждой новости'
    )
