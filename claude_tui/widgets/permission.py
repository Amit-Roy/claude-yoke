"""Modal that surfaces a tool-permission request from the agent.

When Claude wants to use a tool that needs approval, the CLI sends a
``can_use_tool`` control request; we pop this dialog so the user can Allow it
once, allow that tool for the rest of the session, or Deny it. The choice is
returned via ``dismiss`` as one of ``"allow"`` / ``"allow_session"`` /
``"deny"``.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..theme import AMBER, ICE, MUTED, NOMINAL

# The argument worth showing per tool, so the prompt reads like the action.
_KEY_ARG = {
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "NotebookEdit": "notebook_path",
    "WebFetch": "url",
    "WebSearch": "query",
    "Task": "description",
}


def _summarize(tool: str, tool_input: dict) -> str:
    key = _KEY_ARG.get(tool)
    value = tool_input.get(key) if isinstance(tool_input, dict) and key else None
    if value is None and isinstance(tool_input, dict) and tool_input:
        # Fall back to the first scalar argument.
        for k, v in tool_input.items():
            if isinstance(v, (str, int, float)):
                key, value = k, v
                break
    if value is None:
        return ""
    text = str(value).strip().replace("\n", " ")
    if len(text) > 300:
        text = text[:300].rstrip() + " …"
    return text


class PermissionScreen(ModalScreen):
    """Approve or deny one tool call. Returns the decision via ``dismiss``."""

    BINDINGS = [
        Binding("a", "allow", "Allow once"),
        Binding("s", "allow_session", "Allow for session"),
        Binding("d", "deny", "Deny"),
        Binding("escape", "deny", "Deny"),
    ]

    def __init__(self, tool: str, tool_input: dict, description: str = "") -> None:
        self._tool = tool or "tool"
        self._input = tool_input if isinstance(tool_input, dict) else {}
        self._description = description
        super().__init__()

    def compose(self) -> ComposeResult:
        summary = _summarize(self._tool, self._input)
        with Vertical(id="perm-box"):
            yield Static(
                f"[{AMBER}]▍[/] [bold {AMBER}]Permission required[/]", id="perm-title"
            )
            yield Static(
                f"Claude wants to use [bold {NOMINAL}]{self._tool}[/].", id="perm-tool"
            )
            if summary:
                yield Static(f"[{MUTED}]{summary}[/]", id="perm-summary")
            elif self._description:
                yield Static(f"[{MUTED}]{self._description}[/]", id="perm-summary")
            with Horizontal(id="perm-buttons"):
                yield Button("Allow once  (a)", id="perm-allow", variant="success")
                yield Button("Allow session  (s)", id="perm-session", variant="primary")
                yield Button("Deny  (d)", id="perm-deny", variant="error")
            yield Static(
                f"[{ICE}]a[/] allow once   [{ICE}]s[/] allow this tool all session   "
                f"[{ICE}]d[/]/esc deny",
                id="perm-hint",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "perm-allow":
            self.action_allow()
        elif event.button.id == "perm-session":
            self.action_allow_session()
        elif event.button.id == "perm-deny":
            self.action_deny()

    def action_allow(self) -> None:
        self.dismiss("allow")

    def action_allow_session(self) -> None:
        self.dismiss("allow_session")

    def action_deny(self) -> None:
        self.dismiss("deny")
