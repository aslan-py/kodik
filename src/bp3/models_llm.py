from abc import ABC, abstractmethod
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# ========== Контекст проекта ==========
class ProjectContext(BaseModel):
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
    @abstractmethod
    def process(self, ctx: ProjectContext) -> ProjectContext:
        pass


class LLMModule(BaseModule):
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm


# ========== Конвейер ==========
class Pipeline:
    def __init__(self, modules: list[BaseModule]):
        self.modules = modules

    def run(self) -> ProjectContext:
        ctx = ProjectContext()
        for module in self.modules:
            print(f'Запуск модуля: {module.__class__.__name__}')
            ctx = module.process(ctx)
        return ctx


# ========== Pydantic‑схемы для structured output ==========
class CategorizedItem(BaseModel):
    id: int
    category: str | None = None


class CategorizedResponse(BaseModel):
    items: list[CategorizedItem] = Field(
        description='Результат категоризации: по элементу на каждую новость'
    )


ToneLevel = Literal['positive', 'negative', 'alarming', 'neutral', 'irrelevant']


class ToneItem(BaseModel):
    id: int
    tone_of_news: ToneLevel


class ToneResponse(BaseModel):
    items: list[ToneItem] = Field(
        description='Тональность: по одному элементу на каждую новость'
    )


class CommentActionItem(BaseModel):
    id: int
    comments: str = Field(
        description='Краткий комментарий: что произошло и почему это важно'
    )
    actions: str = Field(description='Рекомендация по действию для компании')


class CommentActionResponse(BaseModel):
    items: list[CommentActionItem] = Field(
        description='Комментарии и рекомендации: по элементу на каждую новость'
    )


class GenerationTaskItem(BaseModel):
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
    items: list[GenerationTaskItem] = Field(
        ..., description='Список элементов для каждой новости'
    )


class ExpectedResultItem(BaseModel):
    id: int
    expected_result: str = Field(
        description=(
            'Ожидаемый измеримый результат, '
            'к которому приведёт выполнение задач по данной новости'
        ),
    )


class ExpectedResultResponse(BaseModel):
    items: list[ExpectedResultItem] = Field(
        ..., description='Список элементов для каждой новости'
    )
