from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import re
from pathlib import Path

from rich.console import Console

from gh_stars_organizer.cache import SQLiteCache
from gh_stars_organizer.classifier import RepositoryClassifier
from gh_stars_organizer.config import AppConfig
from gh_stars_organizer.embeddings import EmbeddingClient, FaissSimilarityIndex
from gh_stars_organizer.github_client import GitHubCLIError, GitHubClient
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

    def sync(self, status_callback: Callable[[str], None] | None = None) -> list[Repository]:
        def emit(message: str) -> None:
            if status_callback:
                status_callback(message)
            self.console.print(f"[bold cyan]{message}[/bold cyan]")

        emit("Fetching starred repositories...")
        repositories = self.github.fetch_starred_repositories(
            progress_callback=lambda page, total: emit(f"Fetching stars... page {page}, repos {total}")
        )
        emit("Caching repositories locally...")
        self.cache.upsert_repositories(repositories)
        self.cache.set_last_sync()
        emit(f"Fetched {len(repositories)} repositories.")
        return repositories

    def _ensure_repositories(self) -> list[Repository]:
        repositories = self.cache.list_repositories()
        if repositories:
            return repositories
        return self.sync()

    def classify_repositories(
        self,
        repositories: list[Repository],
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, str]:
        def emit(message: str) -> None:
            if status_callback:
                status_callback(message)

        self.console.print("[bold cyan]Classifying repositories...[/bold cyan]")
        classifications = self.cache.all_classifications(self.config.model)
        missing = [repo for repo in repositories if repo.id not in classifications]
        total_missing = len(missing)
        processed = 0
        if total_missing:
            emit(f"Classifying repositories... 0/{total_missing}")
        for repo in repositories:
            if repo.id in classifications:
                continue
            category = self.classifier.classify(repo)
            self.cache.set_classification(repo.id, self.config.model, category)
            classifications[repo.id] = category
            processed += 1
            if processed % 10 == 0 or processed == total_missing:
                emit(f"Classifying repositories... {processed}/{total_missing}")
            self.console.print(f"[dim]{repo.full_name}[/dim] -> [yellow]{category}[/yellow]")
        if not total_missing:
            emit("Classification cache is up to date.")
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

    def preview(
        self,
        limit: int = 100,
        status_callback: Callable[[str], None] | None = None,
    ) -> list[tuple[Repository, str]]:
        repositories = self._ensure_repositories()
        classifications = self.classify_repositories(repositories, status_callback=status_callback)
        preview_rows: list[tuple[Repository, str]] = []
        for repo in repositories[:limit]:
            preview_rows.append((repo, classifications.get(repo.id, "other")))
        return preview_rows

    def _write_local_lists(self, grouped: dict[str, list[Repository]]) -> tuple[Path, int]:
        output_dir = self.config.local_lists_path
        output_dir.mkdir(parents=True, exist_ok=True)
        index_lines = ["# Local Star Lists", ""]
        created = 0
        for category, repos in sorted(grouped.items()):
            slug = re.sub(r"[^a-z0-9-]+", "-", category.lower()).strip("-") or "other"
            path = output_dir / f"{slug}.md"
            lines = [f"# {category}", "", f"Total repositories: {len(repos)}", ""]
            for repo in sorted(repos, key=lambda item: item.full_name.lower()):
                lines.append(f"- [{repo.full_name}]({repo.url})")
            path.write_text("\n".join(lines) + "\n")
            index_lines.append(f"- [{category}]({path.name}) ({len(repos)} repos)")
            created += 1
        (output_dir / "index.md").write_text("\n".join(index_lines) + "\n")
        return output_dir, created

    def organize(self, status_callback: Callable[[str], None] | None = None) -> dict[str, int | bool | str]:
        repositories = self._ensure_repositories()
        classifications = self.classify_repositories(repositories, status_callback=status_callback)
        grouped: dict[str, list[Repository]] = defaultdict(list)
        for repo in repositories:
            grouped[classifications.get(repo.id, "other")].append(repo)

        try:
            existing_lists = self.github.get_starred_lists()
        except GitHubCLIError as exc:
            message = str(exc)
            if ("Field 'lists' doesn't exist on type 'User'" in message) or (
                "starredRepositoryLists" in message and "doesn't exist on type 'User'" in message
            ):
                output_dir, created = self._write_local_lists(grouped)
                if status_callback:
                    status_callback(
                        "GitHub Star Lists API unavailable. Generated local categorized lists at "
                        f"{output_dir}."
                    )
                return {
                    "lists_created": 0,
                    "repos_processed": len(repositories),
                    "star_lists_supported": False,
                    "local_lists_generated": True,
                    "local_lists_created": created,
                    "local_lists_path": str(output_dir),
                    "message": f"GitHub Star Lists API unavailable. Local categorized lists generated at {output_dir}.",
                }
            if "INSUFFICIENT_SCOPES" in message or "requires one of the following scopes: ['user']" in message:
                output_dir, created = self._write_local_lists(grouped)
                if status_callback:
                    status_callback(
                        "GitHub list APIs need 'user' scope. Run: gh auth refresh -s user. "
                        f"Generated local categorized lists at {output_dir}."
                    )
                return {
                    "lists_created": 0,
                    "repos_processed": len(repositories),
                    "star_lists_supported": False,
                    "local_lists_generated": True,
                    "local_lists_created": created,
                    "local_lists_path": str(output_dir),
                    "message": (
                        "GitHub list APIs require 'user' scope. Run: gh auth refresh -s user. "
                        f"Local categorized lists generated at {output_dir}."
                    ),
                }
            raise
        created = 0
        added = 0
        for category, repos in grouped.items():
            list_name = category
            list_id = existing_lists.get(list_name)
            if not list_id:
                if status_callback:
                    status_callback(f"Creating GitHub list: {list_name}")
                self.console.print(f"[cyan]Creating list:[/cyan] {list_name}")
                try:
                    list_id = self.github.create_starred_list(list_name)
                except GitHubCLIError as exc:
                    message = str(exc)
                    if ("createUserList" in message and "doesn't exist" in message) or (
                        "createStarredRepositoryList" in message and "doesn't exist" in message
                    ):
                        output_dir, local_created = self._write_local_lists(grouped)
                        if status_callback:
                            status_callback(
                                "GitHub list-creation API unavailable. Generated local categorized lists at "
                                f"{output_dir}."
                            )
                        return {
                            "lists_created": created,
                            "repos_processed": len(repositories),
                            "star_lists_supported": False,
                            "local_lists_generated": True,
                            "local_lists_created": local_created,
                            "local_lists_path": str(output_dir),
                            "message": f"GitHub list-creation API unavailable. Local categorized lists generated at {output_dir}.",
                        }
                    if "INSUFFICIENT_SCOPES" in message or "requires one of the following scopes: ['user']" in message:
                        output_dir, local_created = self._write_local_lists(grouped)
                        if status_callback:
                            status_callback(
                                "GitHub list APIs need 'user' scope. Run: gh auth refresh -s user. "
                                f"Generated local categorized lists at {output_dir}."
                            )
                        return {
                            "lists_created": created,
                            "repos_processed": len(repositories),
                            "star_lists_supported": False,
                            "local_lists_generated": True,
                            "local_lists_created": local_created,
                            "local_lists_path": str(output_dir),
                            "message": (
                                "GitHub list APIs require 'user' scope. Run: gh auth refresh -s user. "
                                f"Local categorized lists generated at {output_dir}."
                            ),
                        }
                    raise
                existing_lists[list_name] = list_id
                created += 1
            for repo in repos:
                try:
                    self.github.add_repository_to_list(list_id, repo.id)
                except GitHubCLIError as exc:
                    message = str(exc)
                    if ("updateUserListsForItem" in message and "doesn't exist" in message) or (
                        "addStarredRepositoryToList" in message and "doesn't exist" in message
                    ):
                        output_dir, local_created = self._write_local_lists(grouped)
                        if status_callback:
                            status_callback(
                                "GitHub add-to-list API unavailable. Generated local categorized lists at "
                                f"{output_dir}."
                            )
                        return {
                            "lists_created": created,
                            "repos_processed": len(repositories),
                            "star_lists_supported": False,
                            "local_lists_generated": True,
                            "local_lists_created": local_created,
                            "local_lists_path": str(output_dir),
                            "message": f"GitHub add-to-list API unavailable. Local categorized lists generated at {output_dir}.",
                        }
                    if "INSUFFICIENT_SCOPES" in message or "requires one of the following scopes: ['user']" in message:
                        output_dir, local_created = self._write_local_lists(grouped)
                        if status_callback:
                            status_callback(
                                "GitHub list APIs need 'user' scope. Run: gh auth refresh -s user. "
                                f"Generated local categorized lists at {output_dir}."
                            )
                        return {
                            "lists_created": created,
                            "repos_processed": len(repositories),
                            "star_lists_supported": False,
                            "local_lists_generated": True,
                            "local_lists_created": local_created,
                            "local_lists_path": str(output_dir),
                            "message": (
                                "GitHub list APIs require 'user' scope. Run: gh auth refresh -s user. "
                                f"Local categorized lists generated at {output_dir}."
                            ),
                        }
                    raise
                added += 1
                if status_callback and added % 25 == 0:
                    status_callback(f"Assigning repositories to lists... {added}/{len(repositories)}")
        return {
            "lists_created": created,
            "repos_processed": added,
            "star_lists_supported": True,
            "message": "Organization completed.",
        }

    def insights(self, status_callback: Callable[[str], None] | None = None) -> str:
        repositories = self._ensure_repositories()
        classifications = self.classify_repositories(repositories, status_callback=status_callback)
        if status_callback:
            status_callback("Generating markdown insights report...")
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
