from __future__ import annotations

from collections import defaultdict

from rich.console import Console

from gh_stars_organizer.cache import SQLiteCache
from gh_stars_organizer.classifier import RepositoryClassifier
from gh_stars_organizer.config import AppConfig
from gh_stars_organizer.embeddings import EmbeddingClient, FaissSimilarityIndex
from gh_stars_organizer.github_client import GitHubClient
from gh_stars_organizer.insights import build_markdown_report
from gh_stars_organizer.models import Repository, SearchResult


class StarsOrganizer:
    def __init__(self, config: AppConfig, console: Console | None = None) -> None:
        self.config = config
        self.console = console or Console()
        self.cache = SQLiteCache(config.cache_db_path)
        self.github = GitHubClient(
            page_size=config.github_page_size,
            requests_per_minute=config.github_requests_per_minute,
        )
        self.classifier = RepositoryClassifier(
            api_base_url=config.api_base_url,
            model=config.model,
            categories=config.categories,
            api_key_env=config.api_key_env,
            requests_per_minute=config.llm_requests_per_minute,
        )
        self.embedding_client = EmbeddingClient(
            api_base_url=config.api_base_url,
            model=config.embedding_model,
            api_key_env=config.api_key_env,
            requests_per_minute=config.llm_requests_per_minute,
        )
        self.index = FaissSimilarityIndex(config.faiss_index_path)

    def sync(self) -> list[Repository]:
        self.console.print("[bold cyan]Fetching starred repositories...[/bold cyan]")
        repositories = self.github.fetch_starred_repositories()
        self.cache.upsert_repositories(repositories)
        self.cache.set_last_sync()
        self.console.print(f"[green]Fetched {len(repositories)} repositories.[/green]")
        return repositories

    def _ensure_repositories(self) -> list[Repository]:
        repositories = self.cache.list_repositories()
        if repositories:
            return repositories
        return self.sync()

    def classify_repositories(self, repositories: list[Repository]) -> dict[str, str]:
        self.console.print("[bold cyan]Classifying repositories...[/bold cyan]")
        classifications = self.cache.all_classifications(self.config.model)
        for repo in repositories:
            if repo.id in classifications:
                continue
            category = self.classifier.classify(repo)
            self.cache.set_classification(repo.id, self.config.model, category)
            classifications[repo.id] = category
            self.console.print(f"[dim]{repo.full_name}[/dim] -> [yellow]{category}[/yellow]")
        return classifications

    def embed_repositories(self, repositories: list[Repository]) -> dict[str, list[float]]:
        self.console.print("[bold cyan]Generating embeddings...[/bold cyan]")
        embeddings = self.cache.all_embeddings(self.config.embedding_model)
        for repo in repositories:
            if repo.id in embeddings:
                continue
            vector = self.embedding_client.embed_text(repo.embedding_text())
            self.cache.set_embedding(repo.id, self.config.embedding_model, vector)
            embeddings[repo.id] = vector
        self.index.build(embeddings)
        return embeddings

    def preview(self, limit: int = 100) -> list[tuple[Repository, str]]:
        repositories = self._ensure_repositories()
        classifications = self.classify_repositories(repositories)
        preview_rows: list[tuple[Repository, str]] = []
        for repo in repositories[:limit]:
            preview_rows.append((repo, classifications.get(repo.id, "other")))
        return preview_rows

    def organize(self) -> dict[str, int]:
        repositories = self._ensure_repositories()
        classifications = self.classify_repositories(repositories)
        grouped: dict[str, list[Repository]] = defaultdict(list)
        for repo in repositories:
            grouped[classifications.get(repo.id, "other")].append(repo)

        existing_lists = self.github.get_starred_lists()
        created = 0
        added = 0
        for category, repos in grouped.items():
            list_name = category
            list_id = existing_lists.get(list_name)
            if not list_id:
                self.console.print(f"[cyan]Creating list:[/cyan] {list_name}")
                list_id = self.github.create_starred_list(list_name)
                existing_lists[list_name] = list_id
                created += 1
            for repo in repos:
                self.github.add_repository_to_list(list_id, repo.id)
                added += 1
        return {"lists_created": created, "repos_processed": added}

    def insights(self) -> str:
        repositories = self._ensure_repositories()
        classifications = self.classify_repositories(repositories)
        report_path = build_markdown_report(
            repositories,
            classifications,
            self.config.insights_report_path,
            inactive_months=self.config.inactive_months,
        )
        return str(report_path)

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        repositories = self._ensure_repositories()
        repo_by_id = {repo.id: repo for repo in repositories}
        classifications = self.cache.all_classifications(self.config.model)
        embeddings = self.embed_repositories(repositories)
        query_vector = self.embedding_client.embed_text(query)

        results = self.index.search(query_vector, top_k=top_k)
        if not results:
            return []
        search_results: list[SearchResult] = []
        for repo_id, score in results:
            repo = repo_by_id.get(repo_id)
            if not repo:
                continue
            search_results.append(
                SearchResult(
                    repository=repo,
                    score=score,
                    category=classifications.get(repo_id),
                )
            )
        return search_results

    def close(self) -> None:
        self.classifier.close()
        self.embedding_client.close()
        self.cache.close()

