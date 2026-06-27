"""Sidebar view #2: a directory tree of ``~/.claude`` for quick editing."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DirectoryTree, Static

from ..theme import AMBER


class ClaudeDirectoryTree(DirectoryTree):
    """A directory tree that hides noise (caches, git, pycache)."""

    _HIDE = {"__pycache__", ".git", "node_modules", "cache", "shell-snapshots"}

    def filter_paths(self, paths):
        return [
            p
            for p in paths
            if p.name not in self._HIDE and not p.name.endswith(".lock")
        ]


class FilesTree(Vertical):
    """Wraps the directory tree with a small header.

    File selection is surfaced by the inner :class:`DirectoryTree` via its own
    ``FileSelected`` message, which bubbles up to the app.
    """

    def __init__(self, root: Path, **kwargs) -> None:
        self._root = root
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        label = str(self._root).replace(str(Path.home()), "~")
        yield Static(f"[{AMBER}]▍[/] FILES [dim]{label}[/dim]", id="files-header")
        yield ClaudeDirectoryTree(str(self._root), id="claude-dirtree")
