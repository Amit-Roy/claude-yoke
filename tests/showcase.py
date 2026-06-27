"""Drive the app to a realistic mid-session state and save showcase.svg.

This is what the docs screenshot is rendered from: a fresh app shows empty
instruments, which doesn't reveal the design. Here we light up the gauge, the
agent status lights, and the full message colour language.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import Select  # noqa: E402

from claude_tui.app import ClaudeTUI  # noqa: E402

MODEL = "claude-opus-4-8"


async def run() -> None:
    app = ClaudeTUI()
    async with app.run_test(size=(146, 44)) as pilot:
        await pilot.pause()
        app.query_one("#model-select", Select).value = MODEL
        chat, tokens, agents = app.chat, app.tokens, app.agents

        chat.clear()
        chat.add_user(
            "Make the result event authoritative for output tokens, and add a "
            "thinking renderer to the transcript."
        )
        chat.add_thinking(
            "Per-step assistant usage under-counts output (8+8 vs 42 in my test "
            "call) — the result event's usage is the only reliable total. I'll "
            "commit on result and show a live chars/4 estimate while streaming."
        )
        chat.add_assistant(
            "Here's the plan:\n\n"
            "1. Treat `result.usage.output_tokens` as authoritative.\n"
            "2. Add a `thinking` block renderer (dim italic).\n"
            "3. Keep a live ~chars/4 estimate while a turn streams."
        )
        chat.add_tool_use("Read", {"file_path": "claude_tui/widgets/info_panels.py"})
        chat.add_tool_result("class TokensPanel(Vertical): …  (268 lines)")
        chat.add_tool_use(
            "Task", {"subagent_type": "Explore", "description": "find token usages"}
        )
        chat.add_assistant("Wiring it up now — the gauge reads from `update_context`.")
        chat.add_footer(input_tokens=144_000, output_tokens=8_858, cost_usd=0.1183)

        # Light the token gauge into the amber zone (~72%) and set readouts.
        tokens.update_context(
            {
                "input_tokens": 18_000,
                "cache_read_input_tokens": 122_000,
                "cache_creation_input_tokens": 4_000,
            },
            MODEL,
        )
        tokens.commit_turn(8_858, 0.1183)
        tokens.stats.context_tokens = 144_000
        tokens.stats.last_in = 144_000
        tokens.refresh_body()

        # Two live status lights: the main turn and an Explore subagent.
        agents.start_main(MODEL)
        agents.add_agent("t1", "Explore", "find token usages")

        await pilot.pause()
        out = Path(__file__).resolve().parent.parent / "showcase.svg"
        app.save_screenshot(str(out))
        print(f"saved {out.name} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(run())
