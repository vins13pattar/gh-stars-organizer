from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import httpx

from gh_stars_organizer.utils import RateLimiter, retry


class EmbeddingClient:
    def __init__(
        self,
        api_base_url: str,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        requests_per_minute: int = 60,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.model = model
        self.api_key = os.getenv(api_key_env, "")
        self.client = httpx.Client(timeout=30.0, transport=transport)
        self.rate_limiter = RateLimiter(requests_per_minute)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _local_embedding(self, text: str, dim: int = 256) -> list[float]:
        vector = [0.0] * dim
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @retry(max_attempts=3, base_delay=1.0)
    def _request_embedding(self, text: str) -> list[float]:
        self.rate_limiter.wait()
        payload = {"model": self.model, "input": text}
        response = self.client.post(f"{self.api_base_url}/embeddings", headers=self._headers(), json=payload)
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]

    def embed_text(self, text: str) -> list[float]:
        if not self.api_key:
            return self._local_embedding(text)
        try:
            return self._request_embedding(text)
        except Exception:
            return self._local_embedding(text)

    def close(self) -> None:
        self.client.close()


class FaissSimilarityIndex:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.ids_path = Path(f"{index_path}.ids.json")

    def build(self, vectors: dict[str, list[float]]) -> None:
        if not vectors:
            return
        import faiss
        import numpy as np

        ids = list(vectors.keys())
        matrix = np.array([vectors[repo_id] for repo_id in ids], dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        self.ids_path.write_text(json.dumps(ids))

    def search(self, query_vector: list[float], top_k: int = 10) -> list[tuple[str, float]]:
        if not self.index_path.exists() or not self.ids_path.exists():
            return []
        import faiss
        import numpy as np

        index = faiss.read_index(str(self.index_path))
        ids = json.loads(self.ids_path.read_text())
        query = np.array([query_vector], dtype="float32")
        faiss.normalize_L2(query)
        distances, indices = index.search(query, min(top_k, len(ids)))
        results: list[tuple[str, float]] = []
        for score, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            results.append((ids[idx], float(score)))
        return results

