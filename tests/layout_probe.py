"""Assert the on-screen geometry matches the requested layout, and save an SVG."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_tui.app import ClaudeTUI  # noqa: E402

W, H = 140, 45
failures: list[str] = []


def check(label: str, cond: bool, extra: str = "") -> None:
    print(f"  {'✓' if cond else '✗'} {label}{('  — ' + extra) if extra else ''}")
    if not cond:
        failures.append(label)


def region(app, selector):
    return app.query_one(selector).region


async def run() -> None:
    app = ClaudeTUI()
    async with app.run_test(size=(W, H)) as pilot:
        await pilot.pause()

        bar = region(app, "#activity-bar")
        left = region(app, "#left-column")
        main = region(app, "#main")
        sidebar = region(app, "#sidebar-host")
        tokens = region(app, "#tokens-panel")
        agents = region(app, "#agents-panel")

        print("== regions (x, y, w, h) ==")
        for name, r in [("activity-bar", bar), ("left-column", left), ("main", main),
                        ("sidebar", sidebar), ("tokens", tokens), ("agents", agents)]:
            print(f"    {name:12} x={r.x:3} y={r.y:2} w={r.width:3} h={r.height:2}")

        print("== layout assertions ==")
        check("activity bar is the leftmost pane", bar.x == 0)
        check("activity bar is a narrow fixed column", 18 <= bar.width <= 28,
              f"w={bar.width}")
        check("left column sits right of the activity bar", left.x == bar.x + bar.width)
        check("main chat is the rightmost pane", main.x == left.x + left.width)
        check("main chat occupies ~the right half",
              abs(main.width - left.width) <= 2, f"main={main.width} left={left.width}")

        # Left side is split vertically: sidebar (top) → tokens → agents (bottom).
        check("sidebar is at the top of the left column", sidebar.y <= tokens.y,
              f"sidebar.y={sidebar.y} tokens.y={tokens.y}")
        check("tokens panel sits above the agents panel", tokens.y < agents.y,
              f"tokens.y={tokens.y} agents.y={agents.y}")
        check("agents panel is at the bottom of the left column",
              agents.y + agents.height >= left.y + left.height - 1,
              f"agents.bottom={agents.y + agents.height} left.bottom={left.y + left.height}")
        check("the three left panes share the left column's width",
              sidebar.width == tokens.width == agents.width == left.width)

        out = Path(__file__).resolve().parent.parent / "screenshot.svg"
        app.save_screenshot(str(out))
        print(f"== saved screenshot -> {out.name} ({out.stat().st_size} bytes) ==")

    if failures:
        print(f"\nFAILED ({len(failures)}): " + "; ".join(failures))
        sys.exit(1)
    print("\nLAYOUT OK")


if __name__ == "__main__":
    asyncio.run(run())
