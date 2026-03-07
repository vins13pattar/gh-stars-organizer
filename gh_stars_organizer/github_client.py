from __future__ import annotations

import json
import subprocess
from datetime import datetime

from gh_stars_organizer.models import Repository
from gh_stars_organizer.utils import RateLimiter, retry


class GitHubCLIError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, page_size: int = 100, requests_per_minute: int = 120) -> None:
        self.page_size = min(max(page_size, 1), 100)
        self.rate_limiter = RateLimiter(requests_per_minute)

    @retry(max_attempts=3, base_delay=1.0)
    def _graphql(self, query: str, variables: dict[str, str | int | None] | None = None) -> dict:
        self.rate_limiter.wait()
        cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
        for key, value in (variables or {}).items():
            if value is None:
                continue
            cmd.extend(["-F", f"{key}={value}"])
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise GitHubCLIError(proc.stderr.strip() or "gh api graphql failed")
        payload = json.loads(proc.stdout)
        if payload.get("errors"):
            raise GitHubCLIError(str(payload["errors"]))
        return payload["data"]

    def fetch_starred_repositories(self) -> list[Repository]:
        query = """
        query($first: Int!, $after: String) {
          viewer {
            starredRepositories(first: $first, after: $after, orderBy: {field: STARRED_AT, direction: DESC}) {
              nodes {
                id
                name
                nameWithOwner
                description
                url
                stargazerCount
                updatedAt
                isArchived
                isFork
                owner { login }
                primaryLanguage { name }
                repositoryTopics(first: 20) {
                  nodes {
                    topic { name }
                  }
                }
              }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
        """
        repos: list[Repository] = []
        cursor: str | None = None
        while True:
            data = self._graphql(query, {"first": self.page_size, "after": cursor})
            edge = data["viewer"]["starredRepositories"]
            for node in edge["nodes"]:
                repos.append(
                    Repository(
                        id=node["id"],
                        name=node["name"],
                        owner=node["owner"]["login"],
                        full_name=node["nameWithOwner"],
                        description=node["description"] or "",
                        topics=[item["topic"]["name"] for item in node["repositoryTopics"]["nodes"]],
                        primary_language=(node.get("primaryLanguage") or {}).get("name", ""),
                        stargazer_count=node["stargazerCount"],
                        url=node["url"],
                        updated_at=datetime.fromisoformat(node["updatedAt"].replace("Z", "+00:00")),
                        archived=node["isArchived"],
                        is_fork=node["isFork"],
                    )
                )
            page_info = edge["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
        return repos

    def get_starred_lists(self) -> dict[str, str]:
        query = """
        query {
          viewer {
            starredRepositoryLists(first: 100) {
              nodes { id name }
            }
          }
        }
        """
        data = self._graphql(query)
        return {item["name"]: item["id"] for item in data["viewer"]["starredRepositoryLists"]["nodes"]}

    def create_starred_list(self, name: str) -> str:
        mutation = """
        mutation($name: String!) {
          createStarredRepositoryList(input: {name: $name}) {
            starredRepositoryList { id name }
          }
        }
        """
        data = self._graphql(mutation, {"name": name})
        return data["createStarredRepositoryList"]["starredRepositoryList"]["id"]

    def add_repository_to_list(self, list_id: str, repo_id: str) -> None:
        mutation = """
        mutation($listId: ID!, $repoId: ID!) {
          addStarredRepositoryToList(input: {starredRepositoryListId: $listId, starrableId: $repoId}) {
            clientMutationId
          }
        }
        """
        try:
            self._graphql(mutation, {"listId": list_id, "repoId": repo_id})
        except GitHubCLIError as exc:
            if "already" not in str(exc).lower():
                raise

