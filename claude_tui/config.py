"""Paths, CLI discovery, and static option lists shared across the app."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Models offered in the toolbar dropdown. "default" lets the CLI decide.
MODELS: list[tuple[str, str]] = [
    ("Default", "default"),
    ("Opus 4.8", "claude-opus-4-8"),
    ("Sonnet 4.6", "claude-sonnet-4-6"),
    ("Haiku 4.5", "claude-haiku-4-5"),
]

# Permission modes passed straight through to ``claude --permission-mode``.
# "default" is the safe choice: tools needing approval are auto-denied in
# headless mode rather than running unattended.
PERMISSION_MODES: list[tuple[str, str]] = [
    ("Perm: default", "default"),
    ("Perm: acceptEdits", "acceptEdits"),
    ("Perm: plan", "plan"),
    ("Perm: bypass", "bypassPermissions"),
]

# Rough $/Mtok used only for the *estimate* shown in the tokens panel. The
# authoritative cost comes from the CLI's own ``result.total_cost_usd``.
PRICING: dict[str, tuple[float, float]] = {
    # model substring : (input $/Mtok, output $/Mtok)
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}


def find_claude_cli() -> str | None:
    """Locate the ``claude`` executable.

    Honors ``CLAUDE_TUI_CLI`` first, then ``PATH``, then the winget install
    location used on Windows.
    """
    override = os.environ.get("CLAUDE_TUI_CLI")
    if override and Path(override).exists():
        return override

    for name in ("claude", "claude.exe", "claude.cmd"):
        found = shutil.which(name)
        if found:
            return found

    winget = (
        HOME
        / "AppData/Local/Microsoft/WinGet/Packages"
    )
    if winget.exists():
        for exe in winget.glob("Anthropic.ClaudeCode_*/claude.exe"):
            return str(exe)
    return None


def encode_project_dir(cwd: Path | str) -> str:
    """Mirror Claude Code's project-folder encoding.

    Every character that is not alphanumeric, ``-`` or ``_`` becomes ``-``,
    so ``F:\\workspace\\repos\\all-in-one-claude-tui`` maps to
    ``F--workspace-repos-all-in-one-claude-tui``.
    """
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(cwd))


def project_dir_for(cwd: Path | str) -> Path:
    """Return the ``~/.claude/projects/<encoded>`` folder for *cwd*."""
    return PROJECTS_DIR / encode_project_dir(cwd)


def price_for_model(model: str | None) -> tuple[float, float]:
    """Best-effort (input, output) $/Mtok for a model id."""
    if model:
        low = model.lower()
        for key, price in PRICING.items():
            if key in low:
                return price
    return PRICING["sonnet"]
