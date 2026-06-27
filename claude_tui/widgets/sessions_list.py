"""Sidebar view #1: the chat-sessions browser with per-session metadata."""

from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from ..core.sessions import SessionMeta, load_sessions
from ..theme import AMBER, LABEL, MUTED


class SessionItem(ListItem):
    """A single session row carrying its :class:`SessionMeta`."""

    def __init__(self, meta: SessionMeta) -> None:
        self.meta = meta
        super().__init__()

    def compose(self) -> ComposeResult:
        meta = self.meta
        title = Text(meta.title or "(untitled)", style=f"bold {LABEL}")
        title.truncate(40, overflow="ellipsis")

        sep = "  ·  "
        line2 = Text(no_wrap=True, style=MUTED)
        line2.append(f"{meta.short_model}", style=AMBER)
        line2.append(sep)
        line2.append(meta.duration_str)
        line2.append(sep)
        line2.append(meta.size_str)

        line3 = Text(no_wrap=True, style="dim")
        line3.append(f"{meta.message_count} msgs")
        if meta.context_tokens:
            line3.append(f"  ·  {meta.context_tokens // 1000}k ctx")
        line3.append(f"  ·  {meta.updated_str}")

        yield Static(Group(title, line2, line3))


class SessionsList(Vertical):
    """Loads and lists sessions for a project directory."""

    class SessionChosen(Message):
        def __init__(self, meta: SessionMeta) -> None:
            self.meta = meta
            super().__init__()

    def __init__(self, project_dir: Path, **kwargs) -> None:
        self._project_dir = project_dir
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static(
            f"[{AMBER}]▍[/] SESSIONS [dim](this project)[/dim]", id="sessions-header"
        )
        yield ListView(id="sessions-listview")

    def on_mount(self) -> None:
        self.reload()

    def reload(self) -> None:
        """Re-scan the project directory and repopulate the list."""
        listview = self.query_one("#sessions-listview", ListView)
        listview.clear()
        sessions = load_sessions(self._project_dir)
        header = self.query_one("#sessions-header", Static)
        header.update(
            f"[{AMBER}]▍[/] SESSIONS [dim]({len(sessions)} · this project)[/dim]"
        )
        if not sessions:
            listview.append(
                ListItem(Static("[dim]No sessions yet for this project.[/dim]"))
            )
            return
        for meta in sessions:
            listview.append(SessionItem(meta))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, SessionItem):
            self.post_message(self.SessionChosen(event.item.meta))
