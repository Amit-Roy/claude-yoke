"""Turn messages and tool calls into Rich renderables for the chat log.

Shared by both the live streaming path and the saved-transcript loader so a
replayed session looks identical to a live one. The colour language follows
the cockpit identity: the agent (claude) speaks in amber, the operator (you)
in ice, tool telemetry in green, trouble in red.
"""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .theme import AMBER, DANGER, ICE, LABEL, MUTED, NOMINAL, RULE

# A compact, human-readable hint of the most important argument per tool.
_TOOL_KEY_ARG = {
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "Glob": "pattern",
    "Grep": "pattern",
    "Task": "description",
    "WebFetch": "url",
    "WebSearch": "query",
    "TodoWrite": "todos",
}


def _truncate(text: str, limit: int = 240) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


def user_message(text: str) -> RenderableType:
    return Panel(
        Text(text, style=LABEL),
        title=f"[{ICE}]you[/]",
        title_align="left",
        border_style=ICE,
        padding=(0, 1),
    )


def assistant_message(text: str) -> RenderableType:
    return Panel(
        Markdown(text),
        title=f"[{AMBER}]claude[/]",
        title_align="left",
        border_style=AMBER,
        padding=(0, 1),
    )


def thinking_message(text: str) -> RenderableType:
    return Panel(
        Text(text.strip(), style=f"italic {MUTED}"),
        title="[dim]thinking[/dim]",
        title_align="left",
        border_style=RULE,
        padding=(0, 1),
    )


def system_message(text: str, *, error: bool = False) -> RenderableType:
    style = DANGER if error else MUTED
    label = "error" if error else "system"
    return Text.assemble((f"  {label}  ", f"bold {style}"), (text, style))


def tool_call(name: str, tool_input: dict) -> RenderableType:
    key = _TOOL_KEY_ARG.get(name)
    summary = ""
    if key and isinstance(tool_input, dict) and key in tool_input:
        value = tool_input[key]
        summary = _truncate(value if isinstance(value, str) else str(value), 200)
    elif tool_input:
        summary = _truncate(", ".join(f"{k}={v}" for k, v in tool_input.items()), 200)

    marker = "agent" if name == "Task" else "tool"
    body = Text()
    body.append(f"{marker} ", style=f"dim {NOMINAL}")
    body.append(name, style=f"bold {NOMINAL}")
    if summary:
        body.append("  ")
        body.append(summary, style=MUTED)
    return Panel(body, border_style=NOMINAL, padding=(0, 1), expand=True)


def tool_result(text: str, *, is_error: bool = False) -> RenderableType:
    # Borderless on purpose: the result is secondary telemetry, so it stays a
    # quiet indented line rather than another box competing with the turn.
    style = DANGER if is_error else MUTED
    label = "error" if is_error else "result"
    snippet = _truncate(text, 300) or "(empty)"
    body = Text()
    body.append(f"  └ {label}  ", style=f"dim {style}")
    body.append(snippet, style=style)
    return body


def turn_footer(*, input_tokens: int, output_tokens: int, cost_usd: float | None) -> RenderableType:
    parts = Text()
    parts.append("  ── turn complete", style=MUTED)
    parts.append(f"   ↑{input_tokens:,}", style=ICE)
    parts.append(f" ↓{output_tokens:,}", style=AMBER)
    if cost_usd is not None:
        parts.append(f"   ${cost_usd:.4f}", style=AMBER)
    return parts


def banner(lines: list[str]) -> RenderableType:
    body = Group(
        Text(lines[0], style=f"bold {AMBER}") if lines else Text(),
        *[Text(line, style=MUTED) for line in lines[1:]],
    )
    return Panel(body, border_style=RULE, padding=(0, 1))
