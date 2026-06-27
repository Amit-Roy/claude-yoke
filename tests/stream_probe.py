"""Exercise ClaudeClient.stream() against a fake CLI (no API cost)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_tui.core.claude_client import ClaudeClient  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_cli.py"


class FakeClient(ClaudeClient):
    """Routes ``stream()`` at the fake CLI instead of the real one."""

    def _build_args(self, model, permission_mode, resume):
        return [sys.executable, str(FAKE)]


async def run() -> None:
    client = FakeClient(sys.executable, str(Path.cwd()))
    events = [event async for event in client.stream("hi")]
    types = [e.get("type") for e in events]

    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"  {'✓' if cond else '✗'} {label}")
        ok = ok and cond

    print("== real subprocess streaming ==")
    check("received three events", len(events) == 3)
    check("event order is system→assistant→result",
          types == ["system", "assistant", "result"])
    check("assistant text parsed",
          events[1]["message"]["content"][0]["text"] == "hello from the fake cli")
    check("result carries cost", events[2].get("total_cost_usd") == 0.0002)
    check("process cleaned up", not client.is_running)

    if not ok:
        sys.exit(1)
    print("\nSTREAMING OK")


if __name__ == "__main__":
    asyncio.run(run())
