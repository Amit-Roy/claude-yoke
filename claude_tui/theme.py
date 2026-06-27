"""The "Cockpit" visual identity — a glass-cockpit palette for an agent console.

The app is an instrument panel for driving an AI coding agent: a token *fuel
gauge*, agent *status lights*, tool-call *telemetry*. Colour carries meaning
rather than decoration — warm amber is the agent's chrome, a cool slate hull
sits behind it, and ice/green/red are reserved for live readouts and status.

These hex values are the single source of truth; ``styles.tcss`` mirrors the
ones it needs as literals (kept in sync by hand) and the Rich-rendered widgets
import the constants directly.
"""

from __future__ import annotations

from textual.theme import Theme

# -- palette ---------------------------------------------------------------- #
HULL = "#0F1419"      # background — cool slate, deliberately not black
SURFACE = "#12171E"   # base surface
PANEL = "#171D24"     # raised panels (the instrument cluster)
PANEL_HI = "#1E2630"  # hover / active / highlighted row
RULE = "#2A323C"      # dividers and quiet borders

AMBER = "#FFB454"     # the agent: brand, chrome, active state
AMBER_DIM = "#C8893A"  # recessed amber for secondary chrome
ICE = "#56C7D4"       # lit numeric readouts (context, tokens)
NOMINAL = "#6FCF97"   # status OK / running / tool telemetry
CAUTION = "#E5704B"   # high load, cost emphasis
DANGER = "#E5534B"    # errors / failures

LABEL = "#E6E1D6"     # warm off-white — instrument-label text
MUTED = "#6E7681"     # secondary / recessed text


COCKPIT = Theme(
    name="cockpit",
    primary=AMBER,
    secondary=ICE,
    accent=AMBER,
    success=NOMINAL,
    warning=CAUTION,
    error=DANGER,
    foreground=LABEL,
    background=HULL,
    surface=SURFACE,
    panel=PANEL,
    dark=True,
    variables={
        "amber": AMBER,
        "amber-dim": AMBER_DIM,
        "ice": ICE,
        "nominal": NOMINAL,
        "caution": CAUTION,
        "danger": DANGER,
        "label": LABEL,
        "muted": MUTED,
        "rule": RULE,
        "panel-hi": PANEL_HI,
        # chrome tuning
        "block-cursor-background": AMBER,
        "block-cursor-foreground": HULL,
        "block-cursor-text-style": "none",
        "input-cursor-background": AMBER,
        "input-selection-background": f"{ICE} 35%",
        "border": RULE,
        "scrollbar": PANEL_HI,
        "scrollbar-hover": AMBER_DIM,
        "scrollbar-active": AMBER,
    },
)
