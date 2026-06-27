"""Headless smoke test — verifies the UI builds and events are handled.

Run from the project root with the venv python:

    .venv\\Scripts\\python.exe tests\\smoke_test.py

It mounts the app in Textual's headless test harness, exercises view
switching, feeds synthetic CLI events through the dispatcher, and checks that
real session files parse. It never invokes the ``claude`` CLI.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:  # make non-ASCII check marks/titles printable on a cp1252 console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import (  # noqa: E402
    ContentSwitcher,
    DataTable,
    Input,
    RichLog,
    Select,
)

from claude_tui import config  # noqa: E402
from claude_tui.app import ClaudeTUI  # noqa: E402
from claude_tui.core.sessions import load_sessions  # noqa: E402
from claude_tui.widgets.activity_bar import ActivityBar  # noqa: E402

PASS, FAIL = "✓", "✗"
failures: list[str] = []


def check(label: str, condition: bool) -> None:
    mark = PASS if condition else FAIL
    print(f"  {mark} {label}")
    if not condition:
        failures.append(label)


async def run() -> None:
    print("== parsing real sessions ==")
    sessions = load_sessions(config.project_dir_for(Path.cwd()))
    check(f"found {len(sessions)} session(s) for this project", len(sessions) >= 1)
    if sessions:
        s = sessions[0]
        check("session has a title", bool(s.title))
        check("session has a model", s.model != "?")
        check("session reports a size", s.size_bytes > 0)
        print(f"    e.g. '{s.title}' [{s.short_model}] "
              f"{s.size_str} · {s.duration_str} · {s.message_count} msgs")

    print("== mounting app (headless) ==")
    app = ClaudeTUI()
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()

        for wid in ("#activity-bar", "#sidebar-host", "#tokens-panel",
                    "#agents-panel", "#main", "#chat-log", "#prompt"):
            check(f"widget {wid} present", bool(app.query(wid)))

        # View switching via the activity bar.
        app.query_one(ActivityBar).post_message(ActivityBar.ViewSelected("files"))
        await pilot.pause()
        switcher = app.query_one("#sidebar-host", ContentSwitcher)
        check("switched sidebar to files view", switcher.current == "files")
        app.query_one(ActivityBar).post_message(ActivityBar.ViewSelected("sessions"))
        await pilot.pause()
        check("switched sidebar back to sessions", switcher.current == "sessions")

        # Synthetic CLI event stream.
        app._handle_event({"type": "system", "subtype": "init",
                           "session_id": "abcd1234-0000", "model": "claude-opus-4-8",
                           "tools": ["Read", "Bash"], "permissionMode": "default"})
        check("captured session id from init", app.client.session_id == "abcd1234-0000")

        app._handle_event({"type": "assistant", "message": {
            "model": "claude-opus-4-8",
            "usage": {"input_tokens": 1000, "cache_read_input_tokens": 12000,
                      "cache_creation_input_tokens": 2000, "output_tokens": 500},
            "content": [
                {"type": "text", "text": "Hello, I will help."},
                {"type": "tool_use", "id": "tu_1", "name": "Task",
                 "input": {"subagent_type": "Explore", "description": "scan repo"}},
            ]}})
        await pilot.pause()
        check("tokens panel recorded context", app.tokens.stats.context_tokens == 15000)
        check("live output estimate grew while streaming", app.tokens.stats.live_out > 0)
        check("Task registered as running agent", "tu_1" in app.agents._rows)
        check("agent is marked running", app.agents._rows["tu_1"].running)

        app._handle_event({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": "found 3 files", "is_error": False}]}})
        await pilot.pause()
        check("Task agent marked finished", not app.agents._rows["tu_1"].running)

        ok = app._handle_event({"type": "result", "subtype": "success",
                               "total_cost_usd": 0.0123,
                               "usage": {"output_tokens": 500}})
        check("result event returns ok", ok is True)
        check("session cost accumulated", abs(app.tokens.stats.session_cost - 0.0123) < 1e-9)
        check("authoritative output committed", app.tokens.stats.total_out == 500)
        check("live estimate cleared after result", app.tokens.stats.live_out == 0)

        # Agents table rows mirror the tracked agents (here: just the Task).
        table = app.query_one("#agents-table", DataTable)
        check("agents table rows match tracked agents",
              table.row_count == len(app.agents._rows) and table.row_count >= 1)

        # Starting a main turn adds a row; stopping it keeps it (as finished).
        app.agents.start_main("claude-opus-4-8")
        await pilot.pause()
        check("starting main turn adds a row", "__main__" in app.agents._rows)

        # Error event path.
        bad = app._handle_event({"type": "_error", "returncode": 1, "stderr": "boom"})
        check("error event returns not-ok", bad is False)

        # Toolbar wiring.
        check("model select default", app.query_one("#model-select", Select).value == "default")
        check("chat log is a RichLog", isinstance(app.query_one("#chat-log"), RichLog))
        check("composer input present", isinstance(app.query_one("#prompt"), Input))

    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(run())
