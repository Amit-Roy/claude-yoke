"""The Claude TUI application: layout, wiring, and the streaming turn loop."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    Button,
    ContentSwitcher,
    DirectoryTree,
    Footer,
    Header,
    Select,
)

from . import config, render
from .theme import COCKPIT
from .core.claude_client import ClaudeClient
from .core.sessions import SessionMeta, load_transcript
from .widgets.activity_bar import ActivityBar
from .widgets.chat import ChatPanel
from .widgets.editor import EditorScreen
from .widgets.files_tree import FilesTree
from .widgets.info_panels import AgentsPanel, TokensPanel
from .widgets.permission import PermissionScreen
from .widgets.sessions_list import SessionsList
from .widgets.splitter import Splitter


class ClaudeTUI(App):
    """A multi-pane terminal front-end for the ``claude`` CLI."""

    TITLE = "Claude Yoke"
    SUB_TITLE = "a terminal UI for Claude Code"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+n", "new_session", "New chat"),
        ("ctrl+r", "reload_sessions", "Reload"),
        ("escape", "stop_turn", "Stop"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.register_theme(COCKPIT)
        self.theme = "cockpit"
        self.cwd = Path.cwd()
        cli = config.find_claude_cli()
        self.client = ClaudeClient(cli_path=cli or "claude", cwd=str(self.cwd))
        self._cli_available = cli is not None
        self._task_ids: set[str] = set()
        # Authoritative "a turn is in flight" flag, tied to the worker's
        # lifecycle rather than to subprocess bookkeeping — so the composer can
        # never get permanently wedged if the process state goes sideways.
        self._turn_active = False
        # Tools the user approved for the rest of this session (skip re-asking).
        self._allowed_tools: set[str] = set()

    # --------------------------------------------------------------------- #
    #  Composition
    # --------------------------------------------------------------------- #
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="body"):
            yield ActivityBar(id="activity-bar")
            with Vertical(id="left-column"):
                with ContentSwitcher(initial="sessions", id="sidebar-host"):
                    yield SessionsList(config.project_dir_for(self.cwd), id="sessions")
                    yield FilesTree(self.cwd, id="files")
                yield TokensPanel(id="tokens-panel")
                yield AgentsPanel(id="agents-panel")
            yield Splitter("left-column", axis="x", min_size=30, sibling_min=44, id="main-splitter")
            yield ChatPanel(id="main")
        yield Footer()

    def on_mount(self) -> None:
        if not self._cli_available:
            self.chat.add_system(
                "claude CLI not found on PATH. Set CLAUDE_TUI_CLI to its full path. "
                "Browsing sessions still works; sending messages will not.",
                error=True,
            )

    # -- handy accessors -------------------------------------------------- #
    @property
    def chat(self) -> ChatPanel:
        return self.query_one("#main", ChatPanel)

    @property
    def tokens(self) -> TokensPanel:
        return self.query_one("#tokens-panel", TokensPanel)

    @property
    def agents(self) -> AgentsPanel:
        return self.query_one("#agents-panel", AgentsPanel)

    # --------------------------------------------------------------------- #
    #  Sidebar: view switching, sessions, files
    # --------------------------------------------------------------------- #
    @on(ActivityBar.ViewSelected)
    def _switch_view(self, message: ActivityBar.ViewSelected) -> None:
        self.query_one("#sidebar-host", ContentSwitcher).current = message.view_id

    @on(SessionsList.SessionChosen)
    def _open_session(self, message: SessionsList.SessionChosen) -> None:
        self._load_session(message.meta)

    @on(DirectoryTree.FileSelected)
    def _edit_file(self, message: DirectoryTree.FileSelected) -> None:
        self.push_screen(EditorScreen(Path(message.path)))

    @on(Select.Changed, "#model-select")
    def _model_changed(self, message: Select.Changed) -> None:
        self.tokens.set_model(str(message.value))

    # --------------------------------------------------------------------- #
    #  Toolbar buttons
    # --------------------------------------------------------------------- #
    @on(Button.Pressed, "#new-chat")
    def _new_chat_button(self) -> None:
        self.action_new_session()

    @on(Button.Pressed, "#stop-chat")
    def _stop_button(self) -> None:
        self.action_stop_turn()

    # --------------------------------------------------------------------- #
    #  Actions
    # --------------------------------------------------------------------- #
    def action_new_session(self) -> None:
        self.client.cancel()
        self.client.session_id = None
        self._turn_active = False
        self._task_ids.clear()
        self._allowed_tools.clear()
        self.chat.clear()
        self.chat.show_welcome()
        self.chat.add_system("Started a new session.")
        self.tokens.reset()
        self.agents.clear_all()
        self.chat.set_busy(False)
        self.query_one("#prompt").focus()

    def action_reload_sessions(self) -> None:
        self.query_one("#sessions", SessionsList).reload()

    def action_stop_turn(self) -> None:
        if self.client.cancel():
            self.chat.add_system("Stopping current turn…")
            self.agents.stop_main(ok=False)

    # --------------------------------------------------------------------- #
    #  Sending a message
    # --------------------------------------------------------------------- #
    @on(ChatPanel.PromptChanged)
    def _prompt_changed(self, message: ChatPanel.PromptChanged) -> None:
        self.tokens.set_pending(message.text)

    @on(ChatPanel.PromptSubmitted)
    def _prompt_submitted(self, message: ChatPanel.PromptSubmitted) -> None:
        if not self._cli_available:
            self.chat.add_system("Cannot send: claude CLI not found.", error=True)
            return
        if self._turn_active:
            self.chat.add_system("A turn is already running — Stop it first.", error=True)
            return
        self._turn_active = True
        self.chat.add_user(message.text)
        self._run_turn(message.text)

    @work(exclusive=True, group="turn")
    async def _run_turn(self, prompt: str) -> None:
        chat, tokens, agents = self.chat, self.tokens, self.agents
        model = chat.model
        chat.set_busy(True)
        tokens.set_model(model)
        tokens.set_pending("")
        agents.start_main(model if model != "default" else "claude")
        ok = True
        try:
            async for event in self.client.stream(
                prompt,
                model=model,
                permission_mode=chat.permission_mode,
                resume=self.client.session_id,
            ):
                if event.get("type") == "_permission":
                    await self._handle_permission(event.get("request") or {})
                    continue
                ok = self._handle_event(event) and ok
        except Exception as exc:  # noqa: BLE001 — surface anything to the UI
            chat.add_system(f"stream error: {exc}", error=True)
            ok = False
        finally:
            self._turn_active = False
            agents.stop_main(ok=ok)
            chat.set_busy(False)
            self.query_one("#prompt").focus()

    async def _handle_permission(self, ctrl: dict) -> None:
        """Surface a ``can_use_tool`` request and answer it over the wire."""
        req = ctrl.get("request") or {}
        request_id = str(ctrl.get("request_id", ""))
        tool = str(req.get("tool_name", "tool"))
        tool_input = req.get("input") or {}
        description = str(req.get("description", ""))

        # Honour an earlier "allow for session" choice without re-asking.
        if tool in self._allowed_tools:
            await self.client.respond_permission(
                request_id, allow=True, updated_input=tool_input
            )
            return

        decision = await self.push_screen_wait(
            PermissionScreen(tool, tool_input, description)
        )
        if decision in ("allow", "allow_session"):
            if decision == "allow_session":
                self._allowed_tools.add(tool)
            await self.client.respond_permission(
                request_id, allow=True, updated_input=tool_input
            )
            note = f"approved {tool}"
            self.chat.add_system(note + (" · session" if decision == "allow_session" else ""))
        else:
            await self.client.respond_permission(
                request_id, allow=False, message="Denied by the user in Claude Yoke."
            )
            self.chat.add_system(f"denied {tool}", error=True)

    def _handle_event(self, event: dict) -> bool:
        """Dispatch one CLI event to the panels. Returns False on error events."""
        etype = event.get("type")

        if etype == "system":
            sid = event.get("session_id")
            if sid:
                self.client.session_id = sid
            if event.get("subtype") == "init":
                tools = event.get("tools") or []
                self.chat.add_system(
                    f"session {str(sid)[:8]} · {event.get('model', '?')} · "
                    f"{len(tools)} tools · perm={event.get('permissionMode', '?')}"
                )
            return True

        if etype == "assistant":
            self._handle_assistant(event.get("message") or {})
            return True

        if etype == "user":
            self._handle_user(event.get("message") or {})
            return True

        if etype == "result":
            return self._handle_result(event)

        if etype == "_spawn-error":
            self.chat.add_system(
                f"could not launch claude CLI: {event.get('error')}", error=True
            )
            return False

        if etype == "_error":
            detail = event.get("stderr") or f"exit code {event.get('returncode')}"
            self.chat.add_system(detail[:500], error=True)
            return False

        if etype == "_stdout":
            self.chat.add_system(event.get("text", "")[:300])
            return True

        return True

    def _handle_assistant(self, message: dict) -> None:
        model = message.get("model", "")
        usage = message.get("usage")
        if usage:
            self.tokens.update_context(usage, model)
        content = message.get("content")
        if isinstance(content, str):
            if content.strip():
                self.chat.add_assistant(content)
                self.tokens.note_stream_text(content)
            return
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and block.get("text", "").strip():
                self.chat.add_assistant(block["text"])
                self.tokens.note_stream_text(block["text"])
            elif btype == "thinking" and block.get("thinking", "").strip():
                self.chat.add_thinking(block["thinking"])
                self.tokens.note_stream_text(block["thinking"])
            elif btype == "tool_use":
                name = block.get("name", "tool")
                tool_input = block.get("input", {}) or {}
                self.chat.add_tool_use(name, tool_input)
                if name == "Task":
                    tid = block.get("id", "")
                    self._task_ids.add(tid)
                    self.agents.add_agent(
                        tid,
                        str(tool_input.get("subagent_type", "agent")),
                        str(tool_input.get("description")
                            or tool_input.get("prompt", ""))[:60],
                    )

    def _handle_user(self, message: dict) -> None:
        content = message.get("content")
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = self._stringify(block.get("content"))
            self.chat.add_tool_result(text, is_error=bool(block.get("is_error")))
            tid = block.get("tool_use_id", "")
            if tid in self._task_ids:
                self.agents.finish_agent(tid, ok=not block.get("is_error"))

    def _handle_result(self, event: dict) -> bool:
        cost = event.get("total_cost_usd")
        cost = float(cost) if isinstance(cost, (int, float)) else None
        usage = event.get("usage") or {}
        out = int(usage.get("output_tokens", 0) or 0)
        self.tokens.commit_turn(out, cost)
        self.chat.add_footer(
            input_tokens=self.tokens.stats.context_tokens,
            output_tokens=out or self.tokens.stats.last_out,
            cost_usd=cost,
        )
        return event.get("subtype") != "error"

    @staticmethod
    def _stringify(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return "" if content is None else str(content)

    # --------------------------------------------------------------------- #
    #  Loading a saved transcript
    # --------------------------------------------------------------------- #
    def _load_session(self, meta: SessionMeta) -> None:
        self.client.cancel()
        messages, fresh = load_transcript(meta.path)
        self.client.session_id = meta.session_id
        self._task_ids.clear()
        self.chat.clear()
        self.chat.transcript.write(
            render.banner(
                [
                    f"Resumed session {meta.session_id[:8]}  ·  {fresh.short_model}",
                    f"{fresh.message_count} messages · {fresh.size_str} · "
                    f"{fresh.duration_str}",
                    "Type below to continue this conversation.",
                ]
            )
        )
        for msg in messages:
            if msg.role == "user":
                self.chat.add_user(msg.text)
            elif msg.role == "assistant":
                self.chat.add_assistant(msg.text)
            elif msg.role == "tool_use":
                self.chat.add_tool_use(msg.tool_name, msg.tool_input)
            elif msg.role == "tool_result":
                self.chat.add_tool_result(msg.text, is_error=msg.is_error)
        self.tokens.seed(fresh.context_tokens, fresh.output_tokens, fresh.model)
        self.agents.clear_all()
        self.query_one("#prompt").focus()


def main() -> None:
    ClaudeTUI().run()


if __name__ == "__main__":
    main()
