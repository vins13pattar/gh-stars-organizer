from __future__ import annotations

import json
import os
import re

import httpx

from gh_stars_organizer.models import Repository
from gh_stars_organizer.utils import RateLimiter, retry


class RepositoryClassifier:
    def __init__(
        self,
        api_base_url: str,
        model: str,
        categories: list[str],
        api_key_env: str = "OPENAI_API_KEY",
        requests_per_minute: int = 60,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.model = model
        self.categories = categories
        self.api_key = os.getenv(api_key_env, "")
        self.client = httpx.Client(timeout=30.0, transport=transport)
        self.rate_limiter = RateLimiter(requests_per_minute)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _prompt(self, repo: Repository) -> str:
        categories_text = "\n".join(f"- {category}" for category in self.categories)
        return (
            "You are a GitHub repository classifier.\n\n"
            "Based on the repository information choose the most appropriate category from the provided list.\n\n"
            "Return JSON only.\n\n"
            '{\n  "category": "category_name"\n}\n\n'
            f"Allowed categories:\n{categories_text}\n\n"
            f"Repository name: {repo.full_name}\n"
            f"Description: {repo.description}\n"
            f"Topics: {', '.join(repo.topics)}\n"
            f"Primary language: {repo.primary_language}\n"
        )

    def _extract_json(self, content: str) -> dict:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model output")
        return json.loads(match.group(0))

    @retry(max_attempts=3, base_delay=1.0)
    def _request_category(self, repo: Repository) -> str:
        self.rate_limiter.wait()
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": self._prompt(repo)}],
            "response_format": {"type": "json_object"},
        }
        response = self.client.post(f"{self.api_base_url}/chat/completions", headers=self._headers(), json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = self._extract_json(content)
        category = str(parsed.get("category", "other")).strip()
        if category not in self.categories:
            return "other" if "other" in self.categories else self.categories[0]
        return category

    def classify(self, repo: Repository) -> str:
        try:
            return self._request_category(repo)
        except Exception:
            return self._fallback_category(repo)

    def _fallback_category(self, repo: Repository) -> str:
        text = f"{repo.full_name} {repo.description} {' '.join(repo.topics)} {repo.primary_language}".lower()
        rules = {
            "genai-llm-agents": ["llm", "langchain", "agent", "openai", "gpt"],
            "rag-search-embeddings": ["rag", "embedding", "vector", "retrieval"],
            "backend-api-frameworks": ["api", "backend", "fastapi", "django", "flask"],
            "frontend-ui-frameworks": ["frontend", "react", "vue", "next.js", "ui"],
            "mobile-react-native": ["mobile", "react-native", "android", "ios"],
            "databases-vector-search": ["database", "postgres", "mysql", "mongodb", "redis"],
            "cloud-devops-infra": ["kubernetes", "docker", "cloud", "terraform", "devops"],
            "developer-tools": ["cli", "tooling", "linter", "formatter", "testing"],
            "ai-learning-resources": ["awesome", "tutorial", "course", "learn"],
            "software-architecture": ["architecture", "design-pattern", "system-design"],
            "product-ideas": ["saas", "boilerplate", "startup", "product"],
        }
        for category, keywords in rules.items():
            if category in self.categories and any(word in text for word in keywords):
                return category
        return "other" if "other" in self.categories else self.categories[0]

    def close(self) -> None:
        self.client.close()

