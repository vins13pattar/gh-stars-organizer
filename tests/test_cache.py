from datetime import UTC, datetime
from pathlib import Path

from gh_stars_organizer.cache import SQLiteCache
from gh_stars_organizer.models import Repository


def _repo(repo_id: str) -> Repository:
    return Repository(
        id=repo_id,
        name="repo",
        owner="owner",
        full_name="owner/repo",
        description="test",
        topics=["python"],
        primary_language="Python",
        stargazer_count=1,
        url="https://github.com/owner/repo",
        updated_at=datetime.now(UTC),
    )


def test_cache_repository_and_classification(tmp_path: Path):
    cache = SQLiteCache(tmp_path / "cache.db")
    repo = _repo("R_1")
    cache.upsert_repositories([repo])
    repos = cache.list_repositories()
    assert len(repos) == 1
    cache.set_classification("R_1", "model", "developer-tools")
    assert cache.get_classification("R_1", "model") == "developer-tools"


def test_cache_embeddings_roundtrip(tmp_path: Path):
    cache = SQLiteCache(tmp_path / "cache.db")
    vector = [0.1, 0.2, 0.3]
    cache.set_embedding("R_1", "emb-model", vector)
    restored = cache.get_embedding("R_1", "emb-model")
    assert restored is not None
    assert len(restored) == len(vector)
    assert abs(restored[1] - 0.2) < 1e-6

