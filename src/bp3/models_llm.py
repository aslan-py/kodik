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
    text: str | None = None
    category: str | None = None


class CategorizedResponse(BaseModel):
    items: list[CategorizedItem] = Field(
        description='Результат категоризации: по элементу на каждую новость'
    )


ToneCategory = Literal[
    'Позитивная', 'Негативная', 'Тревожная', 'Нейтральная', 'Нерелевантно'
]


class ToneItem(BaseModel):
    id: int
    tone_of_news: ToneCategory


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
