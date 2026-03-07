from __future__ import annotations

import json
import sqlite3
from array import array
from datetime import UTC, datetime
from pathlib import Path

from gh_stars_organizer.models import Repository


class SQLiteCache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS repositories (
                repo_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                description TEXT NOT NULL,
                topics_json TEXT NOT NULL,
                primary_language TEXT NOT NULL,
                stargazer_count INTEGER NOT NULL,
                url TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived INTEGER NOT NULL,
                is_fork INTEGER NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS classifications (
                repo_id TEXT NOT NULL,
                model TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (repo_id, model)
            );
            CREATE TABLE IF NOT EXISTS embeddings (
                repo_id TEXT NOT NULL,
                model TEXT NOT NULL,
                dim INTEGER NOT NULL,
                vector BLOB NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (repo_id, model)
            );
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def upsert_repositories(self, repositories: list[Repository]) -> None:
        now = datetime.now(UTC).isoformat()
        rows = [
            (
                repo.id,
                repo.owner,
                repo.name,
                repo.full_name,
                repo.description,
                json.dumps(repo.topics),
                repo.primary_language,
                repo.stargazer_count,
                repo.url,
                repo.updated_at.isoformat(),
                int(repo.archived),
                int(repo.is_fork),
                now,
            )
            for repo in repositories
        ]
        self.conn.executemany(
            """
            INSERT INTO repositories (
                repo_id, owner, name, full_name, description, topics_json,
                primary_language, stargazer_count, url, updated_at, archived, is_fork, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_id) DO UPDATE SET
                owner = excluded.owner,
                name = excluded.name,
                full_name = excluded.full_name,
                description = excluded.description,
                topics_json = excluded.topics_json,
                primary_language = excluded.primary_language,
                stargazer_count = excluded.stargazer_count,
                url = excluded.url,
                updated_at = excluded.updated_at,
                archived = excluded.archived,
                is_fork = excluded.is_fork,
                last_seen_at = excluded.last_seen_at
            """,
            rows,
        )
        self.conn.commit()

    def list_repositories(self) -> list[Repository]:
        rows = self.conn.execute("SELECT * FROM repositories ORDER BY full_name ASC").fetchall()
        repositories: list[Repository] = []
        for row in rows:
            repositories.append(
                Repository(
                    id=row["repo_id"],
                    owner=row["owner"],
                    name=row["name"],
                    full_name=row["full_name"],
                    description=row["description"],
                    topics=json.loads(row["topics_json"]),
                    primary_language=row["primary_language"],
                    stargazer_count=row["stargazer_count"],
                    url=row["url"],
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    archived=bool(row["archived"]),
                    is_fork=bool(row["is_fork"]),
                )
            )
        return repositories

    def set_classification(self, repo_id: str, model: str, category: str) -> None:
        self.conn.execute(
            """
            INSERT INTO classifications (repo_id, model, category, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(repo_id, model) DO UPDATE SET
                category = excluded.category,
                created_at = excluded.created_at
            """,
            (repo_id, model, category, datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

    def get_classification(self, repo_id: str, model: str) -> str | None:
        row = self.conn.execute(
            "SELECT category FROM classifications WHERE repo_id = ? AND model = ?",
            (repo_id, model),
        ).fetchone()
        return row["category"] if row else None

    def all_classifications(self, model: str) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT repo_id, category FROM classifications WHERE model = ?",
            (model,),
        ).fetchall()
        return {row["repo_id"]: row["category"] for row in rows}

    def set_embedding(self, repo_id: str, model: str, vector: list[float]) -> None:
        arr = array("f", vector)
        self.conn.execute(
            """
            INSERT INTO embeddings (repo_id, model, dim, vector, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(repo_id, model) DO UPDATE SET
                dim = excluded.dim,
                vector = excluded.vector,
                updated_at = excluded.updated_at
            """,
            (repo_id, model, len(vector), arr.tobytes(), datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

    def get_embedding(self, repo_id: str, model: str) -> list[float] | None:
        row = self.conn.execute(
            "SELECT vector FROM embeddings WHERE repo_id = ? AND model = ?",
            (repo_id, model),
        ).fetchone()
        if not row:
            return None
        arr = array("f")
        arr.frombytes(row["vector"])
        return list(arr)

    def all_embeddings(self, model: str) -> dict[str, list[float]]:
        rows = self.conn.execute(
            "SELECT repo_id, vector FROM embeddings WHERE model = ?",
            (model,),
        ).fetchall()
        vectors: dict[str, list[float]] = {}
        for row in rows:
            arr = array("f")
            arr.frombytes(row["vector"])
            vectors[row["repo_id"]] = list(arr)
        return vectors

    def set_last_sync(self, timestamp: datetime | None = None) -> None:
        ts = (timestamp or datetime.now(UTC)).isoformat()
        self.conn.execute(
            """
            INSERT INTO metadata (key, value)
            VALUES ('last_sync', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (ts,),
        )
        self.conn.commit()

    def get_last_sync(self) -> datetime | None:
        row = self.conn.execute("SELECT value FROM metadata WHERE key = 'last_sync'").fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["value"])

    def close(self) -> None:
        self.conn.close()

