"""The left pane: a vertical stack of view-switching buttons.

Adding a future destination is a one-liner: append a :class:`ViewDef` to
``VIEWS`` and mount a matching widget (same ``id``) inside the sidebar's
``ContentSwitcher``. The bar builds its buttons from this registry, so it needs
no further changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static

from ..theme import AMBER, MUTED


@dataclass(frozen=True)
class ViewDef:
    """One destination reachable from the activity bar."""

    id: str
    label: str
    tooltip: str = ""


# The extensible registry. Order here is the order shown in the bar.
VIEWS: list[ViewDef] = [
    ViewDef("sessions", "Chat Sessions", "Browse and resume past sessions"),
    ViewDef("files", ".claude Files", "Open ~/.claude files for editing"),
    # Future: ViewDef("settings", "Settings"), ViewDef("agents", "Agents"), ...
]


class ActivityBar(Vertical):
    """Renders one button per :class:`ViewDef` and announces selections."""

    class ViewSelected(Message):
        """Posted when the user activates a view button."""

        def __init__(self, view_id: str) -> None:
            self.view_id = view_id
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Static(
            f"[{AMBER}]▍[/] [bold {AMBER}]CLAUDE[/] [{MUTED}]tui[/]", id="brand"
        )
        for view in VIEWS:
            button = Button(view.label, id=f"view-{view.id}", classes="view-button")
            if view.tooltip:
                button.tooltip = view.tooltip
            yield button
        yield Static("", classes="spacer")
        yield Static("[dim]ctrl+n  new[/]\n[dim]ctrl+q  quit[/]", id="bar-hint")

    def on_mount(self) -> None:
        self.set_active(VIEWS[0].id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("view-"):
            view_id = event.button.id.removeprefix("view-")
            self.set_active(view_id)
            self.post_message(self.ViewSelected(view_id))

    def set_active(self, view_id: str) -> None:
        for button in self.query(".view-button").results(Button):
            button.set_class(button.id == f"view-{view_id}", "-active")
