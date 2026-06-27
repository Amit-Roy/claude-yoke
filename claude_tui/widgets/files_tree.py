"""Sidebar view #2: a directory tree of the project for quick editing.

Rooted at the working directory so you can browse and open the actual project
files (not just ``~/.claude``). Click any file to edit it in the modal editor.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DirectoryTree, Static

from ..theme import AMBER


class ProjectDirectoryTree(DirectoryTree):
    """A directory tree that hides build/VCS noise so files stay findable."""

    _HIDE = {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "cache",
        "shell-snapshots",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
    }

    def filter_paths(self, paths):
        return [
            p
            for p in paths
            if p.name not in self._HIDE
            and not p.name.endswith((".lock", ".pyc"))
            and not p.name.endswith(".egg-info")
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
        label = self._root.name or str(self._root)
        yield Static(f"[{AMBER}]▍[/] FILES [dim]{label}[/dim]", id="files-header")
        yield ProjectDirectoryTree(str(self._root), id="claude-dirtree")
