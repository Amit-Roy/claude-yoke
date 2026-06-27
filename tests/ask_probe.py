"""Drive the app through an AskUserQuestion prompt against a fake CLI.

Verifies that an AskUserQuestion request surfaces the question modal, that a
submitted answer is fed back as ``updatedInput.answers``, and that skipping
lets the turn finish without answers — all without API cost.
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

FAKE = Path(__file__).resolve().parent / "fake_ask_cli.py"

ok = True


def check(label, cond):
    global ok
    print(f"  {'✓' if cond else '✗'} {label}")
    ok = ok and cond


class FakeAskClient(ClaudeClient):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.calls = []

    def _build_args(self, model, permission_mode, resume):
        return [sys.executable, str(FAKE)]

    async def respond_permission(self, request_id, *, allow, updated_input=None, message=None):
        self.calls.append({"id": request_id, "allow": allow, "input": updated_input})
        await super().respond_permission(
            request_id, allow=allow, updated_input=updated_input, message=message
        )


async def drive(answer):
    app = ClaudeTUI()
    async with app.run_test(size=(146, 44)) as pilot:
        await pilot.pause()
        client = FakeAskClient(sys.executable, str(Path.cwd()))
        app.client = client
        app._cli_available = True

        async def fake_wait(_screen):
            return answer

        app.push_screen_wait = fake_wait

        app.post_message(ChatPanel.PromptSubmitted("ask me something"))
        for _ in range(300):
            await asyncio.sleep(0.02)
            if not app._turn_active and client.calls:
                break
        await pilot.pause()
        return {"calls": list(client.calls), "turn_active": app._turn_active,
                "running": client.is_running}


async def run():
    print("== AskUserQuestion control protocol ==")

    s = await drive({"Tabs or spaces?": "Spaces"})
    call = s["calls"][0] if s["calls"] else {}
    check("answered: one response sent", len(s["calls"]) == 1)
    check("answered: allowed the tool", call.get("allow") is True)
    check("answered: updatedInput carries answers",
          isinstance(call.get("input"), dict) and "answers" in call["input"])
    check("answered: answer value is correct",
          call.get("input", {}).get("answers", {}).get("Tabs or spaces?") == "Spaces")
    check("answered: original questions preserved",
          "questions" in call.get("input", {}))
    check("answered: turn completed", not s["turn_active"] and not s["running"])

    s = await drive(None)  # user skipped
    call = s["calls"][0] if s["calls"] else {}
    check("skipped: still allowed (no hang)", call.get("allow") is True)
    check("skipped: no answers attached",
          "answers" not in (call.get("input") or {}))
    check("skipped: turn completed", not s["turn_active"] and not s["running"])

    if not ok:
        sys.exit(1)
    print("\nASK OK")


if __name__ == "__main__":
    asyncio.run(run())
