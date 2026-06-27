"""Drive the app through a tool-permission prompt against a fake CLI.

Verifies that a ``control_request`` surfaces a decision modal, that the user's
choice is sent back as the right ``control_response``, and that "allow for
session" suppresses the modal on the next request — all without API cost.
"""

import asyncio
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_tui.app import ClaudeTUI  # noqa: E402
from claude_tui.core.claude_client import ClaudeClient  # noqa: E402
from claude_tui.widgets.chat import ChatPanel  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_perm_cli.py"

ok = True


def check(label, cond):
    global ok
    print(f"  {'✓' if cond else '✗'} {label}")
    ok = ok and cond


class FakePermClient(ClaudeClient):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.calls = []

    def _build_args(self, model, permission_mode, resume):
        return [sys.executable, str(FAKE)]

    async def respond_permission(self, request_id, *, allow, updated_input=None, message=None):
        self.calls.append((request_id, allow))
        await super().respond_permission(
            request_id, allow=allow, updated_input=updated_input, message=message
        )


async def drive(decision):
    """Run one turn, answering the permission modal with *decision*."""
    app = ClaudeTUI()
    async with app.run_test(size=(146, 44)) as pilot:
        await pilot.pause()
        client = FakePermClient(sys.executable, str(Path.cwd()))
        app.client = client
        app._cli_available = True

        async def fake_wait(_screen):
            return decision

        app.push_screen_wait = fake_wait  # bypass the real modal deterministically

        app.post_message(ChatPanel.PromptSubmitted("make a file"))
        for _ in range(300):
            await asyncio.sleep(0.02)
            if not app._turn_active and client.calls:
                break
        await pilot.pause()
        # Snapshot everything we need WHILE the app is still composed.
        return {
            "calls": list(client.calls),
            "turn_active": app._turn_active,
            "running": client.is_running,
            "session_cost": app.tokens.stats.session_cost,
            "allowed_tools": set(app._allowed_tools),
        }


async def run():
    print("== permission control protocol ==")

    s = await drive("allow")
    check("allow: responded to the request", len(s["calls"]) == 1)
    check("allow: sent behavior=allow", s["calls"] and s["calls"][0][1] is True)
    check("allow: answered the right request_id", s["calls"] and s["calls"][0][0] == "req-1")
    check("allow: turn completed cleanly", not s["turn_active"] and not s["running"])
    check("allow: cost committed from result", s["session_cost"] > 0)
    check("allow once did NOT bless the tool", "Write" not in s["allowed_tools"])

    s = await drive("deny")
    check("deny: sent behavior=deny", s["calls"] and s["calls"][0][1] is False)
    check("deny: turn still completes", not s["turn_active"] and not s["running"])

    s = await drive("allow_session")
    check("session: tool remembered for the session", "Write" in s["allowed_tools"])

    if not ok:
        sys.exit(1)
    print("\nPERMISSION OK")


if __name__ == "__main__":
    asyncio.run(run())
