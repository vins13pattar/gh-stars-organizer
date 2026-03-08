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


def test_get_starred_lists_uses_user_lists(monkeypatch):
    client = GitHubClient(page_size=1)

    def fake_graphql(query, variables=None):
        assert "viewer" in query
        assert "lists(first: 100)" in query
        return {
            "viewer": {
                "lists": {
                    "nodes": [
                        {"id": "L_1", "name": "genai-llm-agents"},
                        {"id": "L_2", "name": "developer-tools"},
                    ]
                }
            }
        }

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    lists = client.get_starred_lists()
    assert lists["genai-llm-agents"] == "L_1"
    assert lists["developer-tools"] == "L_2"


def test_add_repository_to_list_uses_update_user_lists(monkeypatch):
    client = GitHubClient(page_size=1)
    captured = {}

    def fake_graphql(query, variables=None):
        captured["query"] = query
        captured["variables"] = variables
        return {"updateUserListsForItem": {"clientMutationId": None}}

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    client.add_repository_to_list("L_1", "R_1")
    assert "updateUserListsForItem" in captured["query"]
    assert captured["variables"] == {"repoId": "R_1", "listIds": ["L_1"]}
