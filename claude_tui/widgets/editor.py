"""A modal text editor used to edit files from the ``.claude`` tree."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

MAX_EDIT_BYTES = 2_000_000

# Map a few extensions to TextArea's syntax highlighting languages.
_LANGS = {
    ".py": "python",
    ".json": "json",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".js": "javascript",
    ".ts": "typescript",
}


class EditorScreen(ModalScreen):
    """Edit and save a single file. Esc cancels, Ctrl+S saves."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Close"),
    ]

    def __init__(self, path: Path) -> None:
        self.path = path
        self._error: str | None = None
        self._content = ""
        super().__init__()

    def compose(self) -> ComposeResult:
        try:
            if self.path.stat().st_size > MAX_EDIT_BYTES:
                self._error = "File is too large to edit here."
            else:
                self._content = self.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self._error = "Binary or non-UTF-8 file — not editable here."
        except OSError as exc:
            self._error = f"Cannot open: {exc}"

        display = str(self.path).replace(str(Path.home()), "~")
        with Vertical(id="editor-box"):
            yield Static(f"[b]EDIT[/b]  [dim]{display}[/dim]", id="editor-title")
            if self._error:
                yield Static(f"[red]{self._error}[/red]", id="editor-error")
            else:
                yield TextArea(
                    self._content,
                    id="editor-area",
                    show_line_numbers=True,
                )
            yield Static("", id="editor-status")
            with Horizontal(id="editor-buttons"):
                yield Button("Save  (Ctrl+S)", id="editor-save", variant="success")
                yield Button("Close (Esc)", id="editor-close", variant="default")

    def on_mount(self) -> None:
        if not self._error:
            area = self.query_one("#editor-area", TextArea)
            # Syntax highlighting needs the optional ``textual[syntax]`` extra;
            # apply it only if the language is actually available.
            lang = _LANGS.get(self.path.suffix.lower())
            if lang:
                try:
                    if lang in area.available_languages:
                        area.language = lang
                except Exception:
                    pass
            area.focus()
        else:
            self.query_one("#editor-save", Button).disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "editor-save":
            self.action_save()
        elif event.button.id == "editor-close":
            self.action_cancel()

    def action_save(self) -> None:
        if self._error:
            return
        text = self.query_one("#editor-area", TextArea).text
        try:
            self.path.write_text(text, encoding="utf-8", newline="")
        except OSError as exc:
            self.query_one("#editor-status", Static).update(f"[red]Save failed: {exc}[/red]")
            return
        self.query_one("#editor-status", Static).update("[green]Saved ✓[/green]")
        self.app.bell()

    def action_cancel(self) -> None:
        self.dismiss(None)
