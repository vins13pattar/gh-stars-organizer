from gh_stars_organizer.github_client import GitHubClient


def test_fetch_starred_repositories_pagination(monkeypatch):
    client = GitHubClient(page_size=1)
    calls = {"count": 0}

    def fake_graphql(query, variables=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "viewer": {
                    "starredRepositories": {
                        "nodes": [
                            {
                                "id": "1",
                                "name": "repo1",
                                "nameWithOwner": "a/repo1",
                                "description": "desc",
                                "url": "https://github.com/a/repo1",
                                "stargazerCount": 1,
                                "updatedAt": "2024-01-01T00:00:00Z",
                                "isArchived": False,
                                "isFork": False,
                                "owner": {"login": "a"},
                                "primaryLanguage": {"name": "Python"},
                                "repositoryTopics": {"nodes": [{"topic": {"name": "cli"}}]},
                            }
                        ],
                        "pageInfo": {"hasNextPage": True, "endCursor": "CURSOR"},
                    }
                }
            }
        return {
            "viewer": {
                "starredRepositories": {
                    "nodes": [],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    repos = client.fetch_starred_repositories()
    assert len(repos) == 1
    assert repos[0].full_name == "a/repo1"
    assert calls["count"] == 2

