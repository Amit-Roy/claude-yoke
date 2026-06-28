"""The right half: model/permission toolbar, transcript log, and composer."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, RichLog, Select

from .. import render
from ..config import MODELS, PERMISSION_MODES


class ChatPanel(Vertical):
    """Owns the conversation view and the user input controls."""

    class PromptSubmitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    class PromptChanged(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal(id="chat-toolbar"):
            yield Select(
                MODELS, value="default", allow_blank=False, id="model-select"
            )
            yield Select(
                PERMISSION_MODES,
                value="default",
                allow_blank=False,
                id="perm-select",
            )
            yield Button("New", id="new-chat", variant="primary")
            yield Button("Stop", id="stop-chat", variant="error", disabled=True)
        yield RichLog(
            id="chat-log", highlight=False, markup=True, wrap=True, auto_scroll=True
        )
        with Horizontal(id="composer"):
            yield Input(placeholder="Message Claude…  (Enter to send)", id="prompt")
            yield Button("Send", id="send", variant="success")

    def on_mount(self) -> None:
        self.show_welcome()
        self.query_one("#prompt", Input).focus()

    # -- input plumbing --------------------------------------------------- #
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt":
            self._submit()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "prompt":
            self.post_message(self.PromptChanged(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            self._submit()

    def _submit(self) -> None:
        prompt_input = self.query_one("#prompt", Input)
        text = prompt_input.value.strip()
        if not text:
            return
        prompt_input.value = ""
        self.post_message(self.PromptSubmitted(text))

    # -- state ------------------------------------------------------------ #
    @property
    def model(self) -> str:
        return str(self.query_one("#model-select", Select).value)

    @property
    def permission_mode(self) -> str:
        return str(self.query_one("#perm-select", Select).value)

    def set_busy(self, busy: bool) -> None:
        self.query_one("#stop-chat", Button).disabled = not busy
        self.query_one("#send", Button).disabled = busy
        self.query_one("#prompt", Input).disabled = busy

    # -- log writers ------------------------------------------------------ #
    @property
    def transcript(self) -> RichLog:
        return self.query_one("#chat-log", RichLog)

    def clear(self) -> None:
        self.transcript.clear()

    def show_welcome(self) -> None:
        self.transcript.write(
            render.banner(
                [
                    "Welcome to Claude Yoke.",
                    "Pick a session on the left to resume it, or just type below to",
                    "start a new conversation. Subagents appear in the Agents panel,",
                    "live token usage in the Tokens panel.",
                ]
            )
        )

    def add_user(self, text: str) -> None:
        self.transcript.write(render.user_message(text))

    def add_assistant(self, text: str) -> None:
        self.transcript.write(render.assistant_message(text))

    def add_thinking(self, text: str) -> None:
        self.transcript.write(render.thinking_message(text))

    def add_tool_use(self, name: str, tool_input: dict) -> None:
        self.transcript.write(render.tool_call(name, tool_input))

    def add_tool_result(self, text: str, *, is_error: bool = False) -> None:
        self.transcript.write(render.tool_result(text, is_error=is_error))

    def add_system(self, text: str, *, error: bool = False) -> None:
        self.transcript.write(render.system_message(text, error=error))

    def add_footer(
        self, *, input_tokens: int, output_tokens: int, cost_usd, thinking_tokens: int = 0
    ) -> None:
        self.transcript.write(
            render.turn_footer(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                thinking_tokens=thinking_tokens,
            )
        )
