"""The two stacked left-column instruments: the token gauge and agent lights.

Colour language (see ``theme.py``): ICE = context the agent has *consumed*,
AMBER = output it has *produced* (and its cost), NOMINAL/CAUTION/DANGER =
status. The context gauge is the panel's signature element.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from ..config import price_for_model
from ..theme import AMBER, CAUTION, DANGER, ICE, LABEL, MUTED, NOMINAL, RULE

CONTEXT_WINDOW = 200_000
GAUGE_WIDTH = 22

# Sub-cell eighth blocks, filling left→right, for gauge precision.
_EIGHTHS = "▏▎▍▌▋▊▉"


def _zone(fraction: float) -> str:
    """Instrument zone colour for a fill level: nominal → caution → danger."""
    if fraction < 0.60:
        return NOMINAL
    if fraction < 0.85:
        return AMBER
    return CAUTION


def _k(n: int) -> str:
    n = int(n)
    if n < 1000:
        return str(n)
    if n < 100_000:
        return f"{n / 1000:.1f}k"
    return f"{n // 1000}k"


def _gauge(fraction: float, width: int = GAUGE_WIDTH) -> Text:
    """The signature: a zone-coloured fuel gauge with sub-cell precision.

    The fill is coloured by the *zone it sits in* (green low, amber mid, red
    high), framed by ``▏ ▕`` end-caps over a dim slate track.
    """
    fraction = max(0.0, min(1.0, fraction))
    cells = fraction * width
    full = int(cells)
    partial = cells - full

    bar = Text()
    bar.append("▏", style=RULE)
    for i in range(width):
        zone = _zone((i + 0.5) / width)
        if i < full:
            bar.append("█", style=zone)
        elif i == full and partial > 0:
            idx = int(partial * 8)
            if idx > 0:
                bar.append(_EIGHTHS[idx - 1], style=zone)
            else:
                bar.append("░", style=RULE)
        else:
            bar.append("░", style=RULE)
    bar.append("▕", style=RULE)
    return bar


# --------------------------------------------------------------------------- #
#  Tokens
# --------------------------------------------------------------------------- #
@dataclass
class TokenStats:
    model: str = ""
    context_tokens: int = 0  # window occupancy after the last assistant step
    last_in: int = 0  # input+cache sent on the last step
    last_out: int = 0  # authoritative output of the last finished turn
    total_out: int = 0  # cumulative authoritative output this session
    live_out: int = 0  # rough estimate of the in-flight turn's output
    session_cost: float = 0.0  # authoritative, summed from result events
    pending: int = 0  # estimate of the not-yet-sent composer text

    def estimated_turn_cost(self) -> float:
        in_price, out_price = price_for_model(self.model)
        return (self.last_in / 1e6) * in_price + (self.last_out / 1e6) * out_price


class TokensPanel(Vertical):
    """Live token-usage instrument, updated from CLI ``usage`` events."""

    def __init__(self, **kwargs) -> None:
        self.stats = TokenStats()
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static(f"[{AMBER}]▍[/] TOKENS", classes="panel-title")
        yield Static(id="tokens-body")

    def on_mount(self) -> None:
        self.refresh_body()

    # -- mutations -------------------------------------------------------- #
    def reset(self) -> None:
        self.stats = TokenStats(model=self.stats.model)
        self.refresh_body()

    def set_model(self, model: str) -> None:
        self.stats.model = model
        self.refresh_body()

    def set_pending(self, text: str) -> None:
        # ~4 characters per token is the usual rule of thumb.
        self.stats.pending = max(0, len(text) // 4)
        self.refresh_body()

    def update_context(self, usage: dict, model: str = "") -> None:
        """Update the gauge from an assistant step's input-side usage.

        Output counts here are unreliable (partial per step), so we ignore them
        and rely on the authoritative ``result`` event instead.
        """
        if model:
            self.stats.model = model
        ctx = (
            int(usage.get("input_tokens", 0) or 0)
            + int(usage.get("cache_read_input_tokens", 0) or 0)
            + int(usage.get("cache_creation_input_tokens", 0) or 0)
        )
        if ctx:
            self.stats.context_tokens = ctx
            self.stats.last_in = ctx
        self.refresh_body()

    def note_stream_text(self, text: str) -> None:
        """Add a live ~4-chars/token estimate for streamed assistant output."""
        self.stats.live_out += max(0, len(text) // 4)
        self.refresh_body()

    def commit_turn(self, output_tokens: int, cost_usd: float | None) -> None:
        """Fold an authoritative ``result`` event into the session totals."""
        if output_tokens:
            self.stats.total_out += output_tokens
            self.stats.last_out = output_tokens
        else:
            self.stats.total_out += self.stats.live_out
            self.stats.last_out = self.stats.live_out
        self.stats.live_out = 0
        if cost_usd:
            self.stats.session_cost += max(0.0, cost_usd)
        self.refresh_body()

    def seed(self, context_tokens: int, total_out: int, model: str) -> None:
        """Initialize from a loaded transcript's metadata."""
        self.stats = TokenStats(
            model=model, context_tokens=context_tokens, total_out=total_out
        )
        self.refresh_body()

    # -- rendering -------------------------------------------------------- #
    def refresh_body(self) -> None:
        s = self.stats
        frac = s.context_tokens / CONTEXT_WINDOW
        zone = _zone(frac)
        lines: list[Text] = []

        gauge = _gauge(frac)
        gauge.append("  ")
        gauge.append(f"{frac * 100:4.1f}%", style=f"bold {zone}")
        lines.append(gauge)

        ctx = Text()
        ctx.append(f"{s.context_tokens:,}", style=f"bold {ICE}")
        ctx.append(f"  / {CONTEXT_WINDOW // 1000}k context", style=MUTED)
        lines.append(ctx)

        turn = Text()
        turn.append("last  ", style=MUTED)
        turn.append(f"↑{_k(s.last_in)}", style=ICE)
        turn.append("  ")
        shown_out = s.live_out if s.live_out else s.last_out
        turn.append(f"↓{_k(shown_out)}", style=AMBER)
        if s.live_out:
            turn.append(" live", style=f"dim {AMBER}")
        lines.append(turn)

        sess = Text()
        sess.append("sess  ", style=MUTED)
        sess.append(f"{_k(s.total_out + s.live_out)} out", style=AMBER)
        sess.append("   ", style=MUTED)
        sess.append(f"${s.session_cost:.4f}", style=AMBER)
        lines.append(sess)

        if s.pending:
            q = Text()
            q.append("queue ", style=MUTED)
            q.append(f"~{_k(s.pending)} tok", style=f"dim {AMBER}")
            lines.append(q)

        self.query_one("#tokens-body", Static).update(Group(*lines))


# --------------------------------------------------------------------------- #
#  Agents
# --------------------------------------------------------------------------- #
@dataclass
class AgentRow:
    key: str
    label: str
    detail: str
    started: float = field(default_factory=time.monotonic)
    running: bool = True
    ok: bool = True


class AgentsPanel(Vertical):
    """Live status lights for in-flight work: the main turn plus subagents."""

    MAIN_KEY = "__main__"

    def __init__(self, **kwargs) -> None:
        self._rows: dict[str, AgentRow] = {}
        super().__init__(**kwargs)

    def _title(self, running: int) -> str:
        state = f"{running} running" if running else "idle"
        return f"[{AMBER}]▍[/] AGENTS [dim]{state}[/dim]"

    def compose(self) -> ComposeResult:
        yield Static(self._title(0), id="agents-title")
        table = DataTable(id="agents-table", cursor_type="none", zebra_stripes=False)
        table.add_column("", key="status", width=1)
        table.add_column("agent", key="agent", width=13)
        table.add_column("detail", key="detail")
        table.add_column("t", key="time", width=5)
        yield table

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)

    # -- lifecycle -------------------------------------------------------- #
    def start_main(self, model: str) -> None:
        self.clear_finished()
        self._upsert(
            AgentRow(self.MAIN_KEY, model.replace("claude-", "") or "main", "streaming…")
        )
        self._refresh_rows()

    def stop_main(self, ok: bool = True) -> None:
        row = self._rows.get(self.MAIN_KEY)
        if row:
            row.running = False
            row.ok = ok
            row.detail = "done" if ok else "stopped"
        self._refresh_rows()

    def add_agent(self, key: str, subagent_type: str, description: str) -> None:
        label = (subagent_type or "agent")[:13]
        self._upsert(AgentRow(key, label, description[:60]))
        self._refresh_rows()

    def finish_agent(self, key: str, ok: bool = True) -> None:
        row = self._rows.get(key)
        if row:
            row.running = False
            row.ok = ok
        self._refresh_rows()

    def clear_finished(self) -> None:
        self._rows = {k: r for k, r in self._rows.items() if r.running}
        self._refresh_rows()

    def clear_all(self) -> None:
        self._rows.clear()
        self._refresh_rows()

    # -- internals -------------------------------------------------------- #
    def _upsert(self, row: AgentRow) -> None:
        self._rows[row.key] = row

    def _tick(self) -> None:
        if any(r.running for r in self._rows.values()):
            self._refresh_rows()

    def _status_cell(self, row: AgentRow) -> Text:
        if row.running:
            return Text("●", style=f"bold {NOMINAL}")
        return Text("✓", style=MUTED) if row.ok else Text("✗", style=DANGER)

    def _refresh_rows(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.clear()
        running = sum(1 for r in self._rows.values() if r.running)
        self.query_one("#agents-title", Static).update(self._title(running))
        for row in self._rows.values():
            elapsed = time.monotonic() - row.started
            tstr = f"{elapsed:3.0f}s" if elapsed < 600 else f"{elapsed / 60:2.0f}m"
            label = Text(row.label, style=AMBER if row.running else MUTED)
            detail = Text(row.detail, style=LABEL if row.running else MUTED)
            table.add_row(
                self._status_cell(row), label, detail,
                Text(tstr, style=MUTED), key=row.key,
            )
