from __future__ import annotations

import asyncio
import json
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rich.console import Console

from gh_stars_organizer.config import AppConfig, load_config, save_config
from gh_stars_organizer.github_client import GitHubCLIError, GitHubClient
from gh_stars_organizer.insights import (
    category_distribution,
    detect_archived,
    detect_duplicates,
    detect_inactive,
    technology_distribution,
)
from gh_stars_organizer.organizer import StarsOrganizer

# ─── App bootstrap ────────────────────────────────────────────────────────────

app = FastAPI(title="GH Stars Organizer", docs_url=None, redoc_url=None)
_organizer: StarsOrganizer | None = None
_config: AppConfig | None = None
_null_console = Console(quiet=True)


def _get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _get_organizer() -> StarsOrganizer:
    global _organizer
    if _organizer is None:
        _organizer = StarsOrganizer(_get_config(), console=_null_console)
    return _organizer


# ─── Static files ─────────────────────────────────────────────────────────────

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return (_static_dir / "index.html").read_text()


# ─── Status ───────────────────────────────────────────────────────────────────


@app.get("/api/status")
async def api_status():
    cfg = _get_config()
    org = _get_organizer()
    repos = org.cache.list_repositories()
    classifications = org.cache.all_classifications(cfg.model)
    last_sync = org.cache.get_last_sync()
    lang_counter: Counter = Counter()
    for r in repos:
        if r.primary_language:
            lang_counter[r.primary_language] += 1
    return {
        "total_repos": len(repos),
        "classified_count": len(classifications),
        "last_sync": last_sync.isoformat() if last_sync else None,
        "categories_count": len(cfg.categories),
        "top_languages": [{"name": k, "count": v} for k, v in lang_counter.most_common(5)],
    }


# ─── Repos ────────────────────────────────────────────────────────────────────


@app.get("/api/repos")
async def api_repos(
    category: str | None = Query(None),
    language: str | None = Query(None),
    search: str | None = Query(None),
    archived: bool | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("stars"),
):
    org = _get_organizer()
    cfg = _get_config()
    repos = org.cache.list_repositories()
    classifications = org.cache.all_classifications(cfg.model)

    if category:
        repos = [r for r in repos if classifications.get(r.id) == category]
    if language:
        repos = [r for r in repos if r.primary_language.lower() == language.lower()]
    if archived is not None:
        repos = [r for r in repos if r.archived == archived]
    if search:
        q = search.lower()
        repos = [
            r for r in repos
            if q in r.full_name.lower() or q in r.description.lower() or any(q in t.lower() for t in r.topics)
        ]

    sort_key = {
        "stars": lambda r: r.stargazer_count,
        "name": lambda r: r.full_name.lower(),
        "updated": lambda r: r.updated_at,
    }.get(sort, lambda r: r.stargazer_count)
    repos.sort(key=sort_key, reverse=(sort != "name"))

    total = len(repos)
    start = (page - 1) * per_page
    page_repos = repos[start : start + per_page]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "repos": [
            {
                "id": r.id,
                "full_name": r.full_name,
                "description": r.description,
                "language": r.primary_language,
                "stars": r.stargazer_count,
                "topics": r.topics[:5],
                "url": r.url,
                "archived": r.archived,
                "is_fork": r.is_fork,
                "updated_at": r.updated_at.isoformat(),
                "category": classifications.get(r.id),
            }
            for r in page_repos
        ],
    }


# ─── Categories ───────────────────────────────────────────────────────────────


@app.get("/api/categories")
async def api_categories():
    org = _get_organizer()
    cfg = _get_config()
    repos = org.cache.list_repositories()
    classifications = org.cache.all_classifications(cfg.model)
    cat_counts = category_distribution(classifications)
    return {
        "categories": [
            {"name": cat, "count": cat_counts.get(cat, 0)}
            for cat in cfg.categories
        ],
        "total_classified": len(classifications),
        "total_repos": len(repos),
    }


# ─── Insights ─────────────────────────────────────────────────────────────────


@app.get("/api/insights")
async def api_insights():
    org = _get_organizer()
    cfg = _get_config()
    repos = org.cache.list_repositories()
    if not repos:
        return {"error": "No repos cached. Run sync first."}
    classifications = org.cache.all_classifications(cfg.model)
    cat_counts = category_distribution(classifications)
    tech_counts = technology_distribution(repos)
    archived = detect_archived(repos)
    inactive = detect_inactive(repos, inactive_months=cfg.inactive_months)
    duplicates = detect_duplicates(repos)
    return {
        "total_repos": len(repos),
        "category_distribution": [
            {"name": k, "count": v} for k, v in cat_counts.most_common()
        ],
        "tech_distribution": [
            {"name": k, "count": v} for k, v in tech_counts.most_common(20)
        ],
        "archived_count": len(archived),
        "inactive_count": len(inactive),
        "duplicate_count": sum(len(g) for g in duplicates),
        "archived_repos": [
            {"full_name": r.full_name, "url": r.url} for r in archived[:30]
        ],
        "inactive_repos": [
            {"full_name": r.full_name, "url": r.url, "updated_at": r.updated_at.isoformat()}
            for r in inactive[:30]
        ],
        "duplicate_groups": [
            [{"full_name": r.full_name, "url": r.url} for r in group]
            for group in duplicates[:20]
        ],
    }


# ─── Search ───────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


@app.post("/api/search")
async def api_search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    org = _get_organizer()
    try:
        results = org.search(req.query, top_k=req.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "results": [
            {
                "full_name": r.repository.full_name,
                "description": r.repository.description,
                "url": r.repository.url,
                "stars": r.repository.stargazer_count,
                "language": r.repository.primary_language,
                "score": round(r.score, 4),
                "category": r.category,
            }
            for r in results
        ]
    }


# ─── Config ───────────────────────────────────────────────────────────────────


@app.get("/api/config")
async def api_get_config():
    cfg = _get_config()
    return {
        "model": cfg.model,
        "embedding_model": cfg.embedding_model,
        "api_base_url": cfg.api_base_url,
        "api_key_env": cfg.api_key_env,
        "categories": cfg.categories,
        "inactive_months": cfg.inactive_months,
        "llm_requests_per_minute": cfg.llm_requests_per_minute,
        "github_requests_per_minute": cfg.github_requests_per_minute,
    }


class ConfigUpdate(BaseModel):
    model: str | None = None
    embedding_model: str | None = None
    api_base_url: str | None = None
    api_key_env: str | None = None
    categories: list[str] | None = None
    inactive_months: int | None = None
    llm_requests_per_minute: int | None = None
    github_requests_per_minute: int | None = None


@app.post("/api/config")
async def api_save_config(update: ConfigUpdate):
    global _config, _organizer
    cfg = _get_config()
    data = update.model_dump(exclude_none=True)
    updated = cfg.model_copy(update=data)
    save_config(updated)
    _config = updated
    _organizer = None  # force re-init with new config
    return {"ok": True}


# ─── Lists ────────────────────────────────────────────────────────────────────


@app.get("/api/lists")
async def api_get_lists():
    org = _get_organizer()
    try:
        lists_map = org.github.get_starred_lists()  # {name: id}
        result = []
        for name, list_id in lists_map.items():
            result.append({"id": list_id, "name": name})
        return {"lists": result}
    except GitHubCLIError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/lists/{list_id}/repos")
async def api_get_list_repos(list_id: str):
    org = _get_organizer()
    try:
        repos = org.github.get_list_repositories(list_id)
        return {"repos": repos}
    except GitHubCLIError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


class ListRename(BaseModel):
    name: str


@app.put("/api/lists/{list_id}")
async def api_rename_list(list_id: str, body: ListRename):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    org = _get_organizer()
    try:
        org.github.rename_list(list_id, body.name.strip())
        return {"ok": True}
    except GitHubCLIError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.delete("/api/lists/{list_id}")
async def api_delete_list(list_id: str):
    org = _get_organizer()
    try:
        org.github.delete_list(list_id)
        return {"ok": True}
    except GitHubCLIError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


class CreateListBody(BaseModel):
    name: str


@app.post("/api/lists")
async def api_create_list(body: CreateListBody):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    org = _get_organizer()
    try:
        list_id = org.github.create_starred_list(body.name.strip())
        return {"ok": True, "id": list_id, "name": body.name.strip()}
    except GitHubCLIError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ─── SSE helpers ──────────────────────────────────────────────────────────────


def _sse_event(data: Any) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _run_in_thread_with_sse(fn, *args) -> StreamingResponse:
    """Run fn(*args, status_callback) in a thread; stream SSE events."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def callback(msg: str):
        asyncio.run_coroutine_threadsafe(queue.put({"type": "progress", "message": msg}), loop)

    def thread_target():
        try:
            result = fn(*args, callback)
            asyncio.run_coroutine_threadsafe(queue.put({"type": "done", "result": result}), loop)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(queue.put({"type": "error", "message": str(exc)}), loop)

    threading.Thread(target=thread_target, daemon=True).start()

    async def generator():
        while True:
            event = await queue.get()
            yield _sse_event(event)
            if event["type"] in ("done", "error"):
                break

    return StreamingResponse(generator(), media_type="text/event-stream")


# ─── SSE endpoints ────────────────────────────────────────────────────────────


@app.post("/api/sync")
async def api_sync():
    org = _get_organizer()
    return _run_in_thread_with_sse(org.sync)


@app.post("/api/classify")
async def api_classify():
    org = _get_organizer()

    def run_classify(cb):
        repos = org.cache.list_repositories()
        return org.classify_repositories(repos, status_callback=cb)

    return _run_in_thread_with_sse(run_classify)


@app.post("/api/organize")
async def api_organize():
    org = _get_organizer()
    return _run_in_thread_with_sse(org.organize)


# ─── Launch helper ────────────────────────────────────────────────────────────


def launch(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    uvicorn.run(
        "gh_stars_organizer.web_app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
