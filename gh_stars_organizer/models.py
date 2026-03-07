from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Repository(BaseModel):
    id: str
    name: str
    owner: str
    full_name: str
    description: str = ""
    topics: list[str] = Field(default_factory=list)
    primary_language: str = ""
    stargazer_count: int = 0
    url: str
    updated_at: datetime
    archived: bool = False
    is_fork: bool = False

    def embedding_text(self) -> str:
        topic_text = ", ".join(self.topics)
        return f"{self.full_name}\n{self.description}\n{topic_text}".strip()


class ClassificationResult(BaseModel):
    repo_id: str
    category: str
    model: str


class SearchResult(BaseModel):
    repository: Repository
    score: float
    category: str | None = None

