from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from gh_stars_organizer.config import AppConfig, default_config_path, load_config, save_config
from gh_stars_organizer.organizer import StarsOrganizer

app = typer.Typer(help="Organize GitHub starred repositories into intelligent lists.")
console = Console()


def _load(path: Path | None) -> AppConfig:
    return load_config(path)


@app.command()
def sync(config_path: Path | None = typer.Option(None, "--config", "-c")) -> None:
    cfg = _load(config_path)
    organizer = StarsOrganizer(cfg, console=console)
    try:
        organizer.sync()
    finally:
        organizer.close()


@app.command()
def preview(
    limit: int = typer.Option(100, "--limit", "-n"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    cfg = _load(config_path)
    organizer = StarsOrganizer(cfg, console=console)
    try:
        rows = organizer.preview(limit=limit)
        table = Table(title="Predicted Categories")
        table.add_column("Repository")
        table.add_column("Category")
        for repo, category in rows:
            table.add_row(repo.full_name, category)
        console.print(table)
    finally:
        organizer.close()


@app.command()
def organize(config_path: Path | None = typer.Option(None, "--config", "-c")) -> None:
    cfg = _load(config_path)
    organizer = StarsOrganizer(cfg, console=console)
    try:
        summary = organizer.organize()
        if not summary.get("star_lists_supported", True):
            console.print(f"[yellow]{summary.get('message', 'GitHub Star Lists API unavailable.')}[/yellow]")
            return
        console.print(
            f"[green]Done.[/green] Created {summary['lists_created']} lists and processed "
            f"{summary['repos_processed']} repository assignments."
        )
    finally:
        organizer.close()


@app.command()
def insights(config_path: Path | None = typer.Option(None, "--config", "-c")) -> None:
    cfg = _load(config_path)
    organizer = StarsOrganizer(cfg, console=console)
    try:
        report = organizer.insights()
        console.print(f"[green]Insights written to:[/green] {report}")
    finally:
        organizer.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Semantic search query."),
    top_k: int = typer.Option(10, "--top-k", "-k"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    cfg = _load(config_path)
    organizer = StarsOrganizer(cfg, console=console)
    try:
        results = organizer.search(query, top_k=top_k)
        if not results:
            console.print("[yellow]No matches found.[/yellow]")
            return
        table = Table(title=f"Search Results for: {query}")
        table.add_column("Repository")
        table.add_column("Score")
        table.add_column("Category")
        table.add_column("URL")
        for item in results:
            table.add_row(
                item.repository.full_name,
                f"{item.score:.3f}",
                item.category or "-",
                item.repository.url,
            )
        console.print(table)
    finally:
        organizer.close()


@app.command()
def config(
    init: bool = typer.Option(False, "--init", help="Create default config if missing."),
    show: bool = typer.Option(False, "--show", help="Show active configuration."),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    path = config_path or default_config_path()
    if init or not path.exists():
        target = save_config(AppConfig(), path)
        console.print(f"[green]Config created:[/green] {target}")
        return
    if show:
        cfg = load_config(path)
        console.print(cfg.model_dump_json(indent=2))
        return
    console.print(f"Config file: {path}")


@app.command()
def tui(config_path: Path | None = typer.Option(None, "--config", "-c")) -> None:
    cfg = _load(config_path)
    from gh_stars_organizer.tui_app import launch_tui

    launch_tui(cfg)


if __name__ == "__main__":
    app()
