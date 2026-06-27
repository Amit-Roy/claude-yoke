# Claude TUI

A multi-pane **terminal UI for Claude Code**. It drives the real `claude` CLI
as its engine (via streaming JSON), so you get Claude Code's actual tools, MCP
servers, permissions and session storage — wrapped in a keyboard- and
mouse-friendly dashboard.

![screenshot](docs/screenshot.png)

## Layout

```
┌────────────┬──────────────────┬───────────────────────────┐
│ Activity   │ Sidebar (switch) │  Main Chat  (right half)   │
│ Bar        │  SESSIONS        │   model / permission bar   │
│            │   list+metadata  │   transcript               │
│ Chat       │  (or .claude     │   (text · thinking ·       │
│ Sessions   │   file tree)     │    tool calls · results)   │
│ .claude    ├──────────────────┤                            │
│ Files      │  TOKENS (est.)   │                            │
│ (extensible)├─────────────────┤   ──────────────────────   │
│            │  AGENTS running  │   > message…      [Send]   │
└────────────┴──────────────────┴───────────────────────────┘
```

The UI is deliberately emoji-free: it uses only glyphs present in common
terminal fonts (box-drawing, arrows, `●✓✗`, block bars) so it renders cleanly
everywhere, including in the exported SVG/PNG above.

### Visual identity — "Cockpit"

The app is treated as an **instrument panel for driving an AI coding agent**, and
colour carries meaning rather than decoration (defined in `theme.py`):

* **amber `#FFB454`** — the agent: brand, active nav, and `claude`'s messages
* **ice `#56C7D4`** — context the agent has *consumed* (the token readouts, `you`)
* **nominal green `#6FCF97`** — status lights and tool telemetry
* **caution/danger** — gauge load zones and errors
* a cool slate **hull `#0F1419`** behind warm off-white labels

The **signature** is the token gauge: a zone-coloured fuel bar (green → amber →
red across its length, with sub-cell precision and `▏ ▕` end-caps). Section
labels are quiet muted eyebrows with a small amber index tab `▍`, so the *data*
is what lights up, not the chrome.

* **Activity bar (left pane).** A vertical stack of buttons, driven by an
  extensible registry (`widgets/activity_bar.py → VIEWS`). Ships with **Chat
  Sessions** and **.claude Files**; adding another destination is one entry plus
  a matching widget in the sidebar's `ContentSwitcher`.
* **Sidebar.** Switches between:
  * **Sessions** — every session for the current project
    (`~/.claude/projects/<encoded-cwd>`), each row showing **title, model,
    duration, size, message count, context tokens and last-updated**. Select one
    to replay its transcript and resume the conversation.
  * **.claude files** — a directory tree of `~/.claude`; click any file to open
    it in a modal editor (Ctrl+S saves, Esc closes).
* **Tokens panel.** Live context-window gauge, last-turn ↑/↓, cumulative session
  output, and cost — authoritative numbers come from the CLI's own `result`
  events, with a live char-based estimate while a turn streams.
* **Agents panel.** The in-flight turn plus any **`Task` subagents**, with live
  status (● running / ✓ done) and elapsed time.
* **Main chat (right half).** Model + permission-mode selectors, the transcript,
  and the composer.

## Requirements

* **Python 3.10+**
* The **`claude` CLI** on `PATH` (or point `CLAUDE_TUI_CLI` at it). Browsing
  sessions and editing files works without it; only *sending* needs it.
* [Textual](https://textual.textualize.io/) (installed automatically below).

## Run

```powershell
# Windows (PowerShell) — creates .venv and installs deps on first run
./run.ps1
```

```bash
# or manually, any platform
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # .venv/bin on macOS/Linux
.venv/Scripts/python -m claude_tui
```

## Keybindings

| Key | Action |
| --- | --- |
| `Enter` | Send the message |
| `Ctrl+N` | New session |
| `Ctrl+R` | Reload the sessions list |
| `Esc` | Stop the current turn |
| `Ctrl+Q` | Quit |
| `Ctrl+S` | Save (in the file editor) |

The **model** and **permission-mode** dropdowns map straight onto
`claude --model` / `claude --permission-mode`. The default permission mode is
`default` (tools needing approval are auto-denied in headless mode rather than
running unattended); switch to `acceptEdits` to let Claude edit files.

## How it works

Each turn runs:

```
claude -p "<prompt>" --output-format stream-json --verbose \
       [--resume <session-id>] [--model <model>] [--permission-mode <mode>]
```

`core/claude_client.py` spawns that subprocess with `asyncio`, reads stdout line
by line and yields each JSON event. `app.py` dispatches events to the panels:
`system/init` captures the session id (for `--resume`), `assistant` blocks render
text / thinking / tool calls and feed the token gauge, `Task` tool calls populate
the Agents panel, and `result` commits authoritative tokens and cost.

## Project structure

```
claude_tui/
  app.py              # App: layout, wiring, the streaming turn loop
  config.py           # paths, CLI discovery, model/permission lists, pricing
  theme.py            # the "Cockpit" palette + Textual theme
  render.py           # Rich renderables shared by live + replayed transcripts
  core/
    claude_client.py  # async streaming wrapper around the claude CLI
    sessions.py       # index/parse ~/.claude session transcripts
  widgets/
    activity_bar.py   # extensible left-pane button registry
    sessions_list.py  # sessions browser with metadata
    files_tree.py     # ~/.claude directory tree
    info_panels.py    # Tokens + Agents panels
    chat.py           # toolbar + transcript + composer
    editor.py         # modal file editor
  styles.tcss         # layout + theme
tests/
  smoke_test.py       # headless: compose, view switching, event handling
  stream_probe.py     # real subprocess streaming against a fake CLI
  layout_probe.py     # asserts pane geometry, writes screenshot.svg
  showcase.py         # drives a realistic state, writes the docs screenshot
```

## Tests

```powershell
.venv/Scripts/python tests/smoke_test.py
.venv/Scripts/python tests/stream_probe.py
.venv/Scripts/python tests/layout_probe.py
```

None of the tests call the real API.

## Extending the activity bar

```python
# widgets/activity_bar.py
VIEWS = [
    ViewDef("sessions", "Chat Sessions"),
    ViewDef("files",    ".claude Files"),
    ViewDef("settings", "Settings"),   # 1) add here
]
```

```python
# app.py compose(), inside the ContentSwitcher  — 2) mount a widget with the same id
yield SettingsView(id="settings")
```

That's it — the bar builds its buttons from `VIEWS` and the switcher routes to
the matching id.
