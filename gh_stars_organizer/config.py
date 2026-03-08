from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CATEGORIES = [
    "genai-llm-agents",
    "rag-search-embeddings",
    "backend-api-frameworks",
    "frontend-ui-frameworks",
    "mobile-react-native",
    "databases-vector-search",
    "cloud-devops-infra",
    "developer-tools",
    "ai-learning-resources",
    "software-architecture",
    "product-ideas",
    "other",
]


class AppConfig(BaseModel):
    model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    api_base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    categories: list[str] = Field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    github_page_size: int = 100
    cache_db_path: Path = Path("~/.gh-stars-organizer/cache.db").expanduser()
    faiss_index_path: Path = Path("~/.gh-stars-organizer/embeddings.index").expanduser()
    local_lists_path: Path = Path("~/.gh-stars-organizer/lists").expanduser()
    insights_report_path: Path = Path("stars-insights.md")
    inactive_months: int = 18
    llm_requests_per_minute: int = 60
    github_requests_per_minute: int = 120


def default_config_path() -> Path:
    return Path("~/.gh-stars-organizer/config.yaml").expanduser()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or default_config_path()
    if not config_path.exists():
        cfg = AppConfig()
        save_config(cfg, config_path)
        return cfg
    raw = yaml.safe_load(config_path.read_text()) or {}
    cfg = AppConfig.model_validate(raw)
    ensure_parent(cfg.cache_db_path)
    ensure_parent(cfg.faiss_index_path)
    cfg.local_lists_path.mkdir(parents=True, exist_ok=True)
    return cfg


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    ensure_parent(target)
    ensure_parent(config.cache_db_path)
    ensure_parent(config.faiss_index_path)
    data = config.model_dump()
    data["cache_db_path"] = str(config.cache_db_path)
    data["faiss_index_path"] = str(config.faiss_index_path)
    data["local_lists_path"] = str(config.local_lists_path)
    data["insights_report_path"] = str(config.insights_report_path)
    config.local_lists_path.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, sort_keys=False))
    return target
