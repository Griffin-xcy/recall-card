from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class TextMaterialInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=20, max_length=500_000)


class UrlMaterialInput(BaseModel):
    url: HttpUrl


class CardUpdate(BaseModel):
    topic: str | None = Field(default=None, min_length=1, max_length=60)
    kind: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    question: str | None = Field(default=None, max_length=2_000)
    answer: str | None = Field(default=None, min_length=1, max_length=10_000)
    tags: list[str] | None = None


class ModelSettingsInput(BaseModel):
    base_url: str = Field(min_length=10, max_length=500)
    api_key: str = Field(default="", max_length=500)
    model: str = Field(min_length=1, max_length=200)


class GeneratedCard(BaseModel):
    topic: str = "其他"
    kind: str = "知识点"
    title: str
    question: str = ""
    answer: str
    tags: list[str] = Field(default_factory=list)


class TopicInput(BaseModel):
    name: str = Field(min_length=1, max_length=30)


class KindInput(BaseModel):
    name: str = Field(min_length=1, max_length=30)


class ReviewInput(BaseModel):
    state: Literal["new", "known", "again"]


class BulkUpdateInput(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    review_state: Literal["new", "known", "again"] | None = None
    topic: str | None = Field(default=None, min_length=1, max_length=60)
    kind: str | None = Field(default=None, min_length=1, max_length=30)


class BulkIdsInput(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
