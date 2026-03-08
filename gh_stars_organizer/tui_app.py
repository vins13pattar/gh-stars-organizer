from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.work import work
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from gh_stars_organizer.config import AppConfig
from gh_stars_organizer.organizer import StarsOrganizer


class StarsOrganizerTUI(App):
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        layout: vertical;
    }
    #controls {
        height: auto;
        padding: 1;
    }
    #status {
        height: 3;
        padding: 0 1;
    }
    DataTable {
        height: 1fr;
    }
    #search-box {
        width: 1fr;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.organizer = StarsOrganizer(config)
        self.preview_limit = 300
        self.preview_initialized = False
        self.search_initialized = False
        self.busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="controls"):
            yield Button("Sync", id="sync", variant="primary")
            yield Button("Preview", id="preview")
            yield Button("Organize", id="organize", variant="success")
            yield Button("Insights", id="insights")
            yield Input(placeholder="Search repositories semantically...", id="search-box")
            yield Button("Search", id="search", variant="warning")
        with Vertical():
            yield Static("Ready.", id="status")
            yield DataTable(id="preview-table")
            yield DataTable(id="search-table")
        yield Footer()

    def on_mount(self) -> None:
        preview_table = self.query_one("#preview-table", DataTable)
        search_table = self.query_one("#search-table", DataTable)
        if not self.preview_initialized:
            preview_table.add_columns("Repository", "Category", "Language", "Stars")
            self.preview_initialized = True
        if not self.search_initialized:
            search_table.add_columns("Repository", "Score", "Category", "URL")
            self.search_initialized = True
        self._status("Ready. Press Sync or Preview to load repositories.")

    def on_unmount(self) -> None:
        self.organizer.close()

    def _status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button_id in ("sync", "preview", "organize", "insights", "search"):
            self.query_one(f"#{button_id}", Button).disabled = busy
        self.query_one("#search-box", Input).disabled = busy

    def _load_preview(self) -> None:
        table = self.query_one("#preview-table", DataTable)
        rows = self.organizer.preview(limit=self.preview_limit)
        table.clear(columns=not self.preview_initialized)
        for repo, category in rows:
            table.add_row(repo.full_name, category, repo.primary_language or "-", str(repo.stargazer_count))
        self._status(f"Loaded preview for {len(rows)} repositories.")

    def _run_search(self, query: str) -> None:
        table = self.query_one("#search-table", DataTable)
        results = self.organizer.search(query, top_k=15)
        table.clear(columns=not self.search_initialized)
        for result in results:
            table.add_row(
                result.repository.full_name,
                f"{result.score:.3f}",
                result.category or "-",
                result.repository.url,
            )
        self._status(f"Search complete: {len(results)} results.")

    @work(thread=True, exclusive=True)
    def _sync_task(self) -> None:
        try:
            repos = self.organizer.sync()
            self.call_from_thread(self._status, f"Synced {len(repos)} repositories. Refreshing preview...")
            self.call_from_thread(self._load_preview)
        except Exception as exc:
            self.call_from_thread(self._status, f"Error: {exc}")
        finally:
            self.call_from_thread(self._set_busy, False)

    @work(thread=True, exclusive=True)
    def _preview_task(self) -> None:
        try:
            self.call_from_thread(self._load_preview)
        except Exception as exc:
            self.call_from_thread(self._status, f"Error: {exc}")
        finally:
            self.call_from_thread(self._set_busy, False)

    @work(thread=True, exclusive=True)
    def _organize_task(self) -> None:
        try:
            summary = self.organizer.organize()
            self.call_from_thread(
                self._status,
                f"Organize done. Created {summary['lists_created']} lists, "
                f"processed {summary['repos_processed']} assignments.",
            )
        except Exception as exc:
            self.call_from_thread(self._status, f"Error: {exc}")
        finally:
            self.call_from_thread(self._set_busy, False)

    @work(thread=True, exclusive=True)
    def _insights_task(self) -> None:
        try:
            report = self.organizer.insights()
            self.call_from_thread(self._status, f"Insights written to {report}")
        except Exception as exc:
            self.call_from_thread(self._status, f"Error: {exc}")
        finally:
            self.call_from_thread(self._set_busy, False)

    @work(thread=True, exclusive=True)
    def _search_task(self, query: str) -> None:
        try:
            self.call_from_thread(self._status, f"Searching for: {query}")
            self.call_from_thread(self._run_search, query)
        except Exception as exc:
            self.call_from_thread(self._status, f"Error: {exc}")
        finally:
            self.call_from_thread(self._set_busy, False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.busy:
            self._status("Working... please wait.")
            return
        button_id = event.button.id
        if button_id == "sync":
            self._set_busy(True)
            self._status("Syncing starred repositories...")
            self._sync_task()
        elif button_id == "preview":
            self._set_busy(True)
            self._status("Refreshing preview...")
            self._preview_task()
        elif button_id == "organize":
            self._set_busy(True)
            self._status("Organizing starred lists...")
            self._organize_task()
        elif button_id == "insights":
            self._set_busy(True)
            self._status("Generating insights report...")
            self._insights_task()
        elif button_id == "search":
            query = self.query_one("#search-box", Input).value.strip()
            if not query:
                self._status("Enter a query to search.")
                return
            self._set_busy(True)
            self._search_task(query)


def launch_tui(config: AppConfig) -> None:
    app = StarsOrganizerTUI(config)
    app.run()
