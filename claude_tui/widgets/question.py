"""Modal for the agent's ``AskUserQuestion`` tool.

The CLI sends AskUserQuestion as a ``can_use_tool`` request whose input carries
one or more questions, each with labelled options. We render them as selectable
buttons; ``Submit`` returns an ``{question: "label[, label]"}`` map that the app
feeds back as the tool's answer (via ``updatedInput.answers``). ``Skip``/``Esc``
returns ``None`` so the agent is simply told the question went unanswered.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..theme import AMBER, ICE, MUTED, NOMINAL


class QuestionScreen(ModalScreen):
    """Collect answers to one or more AskUserQuestion questions."""

    BINDINGS = [Binding("escape", "skip", "Skip")]

    def __init__(self, questions: list[dict]) -> None:
        self._questions = [q for q in questions if isinstance(q, dict)]
        # question index -> list of selected option indices
        self._selected: dict[int, list[int]] = {}
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="ask-box"):
            yield Static(
                f"[{AMBER}]▍[/] [bold {AMBER}]Claude is asking[/]", id="ask-title"
            )
            with VerticalScroll(id="ask-body"):
                for qi, q in enumerate(self._questions):
                    header = str(q.get("header", "")).strip()
                    multi = bool(q.get("multiSelect"))
                    tag = f"[{ICE}]{header}[/]  " if header else ""
                    hint = "  [dim](choose any)[/]" if multi else ""
                    yield Static(
                        f"{tag}{q.get('question', '')}{hint}", classes="ask-q"
                    )
                    with Horizontal(classes="ask-options"):
                        for oi, opt in enumerate(q.get("options", [])):
                            label = str(opt.get("label", f"Option {oi + 1}"))
                            btn = Button(label, id=f"opt-{qi}-{oi}", classes="ask-opt")
                            desc = str(opt.get("description", "")).strip()
                            if desc:
                                btn.tooltip = desc
                            yield btn
                    descs = [
                        f"[{NOMINAL}]{o.get('label', '')}[/] — {o.get('description', '')}"
                        for o in q.get("options", [])
                        if o.get("description")
                    ]
                    if descs:
                        yield Static("\n".join(descs), classes="ask-descs")
            with Horizontal(id="ask-buttons"):
                yield Button("Submit", id="ask-submit", variant="success")
                yield Button("Skip  (Esc)", id="ask-skip", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "ask-submit":
            self.action_submit()
        elif bid == "ask-skip":
            self.action_skip()
        elif bid.startswith("opt-"):
            _, qs, os_ = bid.split("-")
            self._toggle(int(qs), int(os_))

    def _toggle(self, qi: int, oi: int) -> None:
        multi = bool(self._questions[qi].get("multiSelect"))
        current = self._selected.get(qi, [])
        if multi:
            if oi in current:
                current.remove(oi)
            else:
                current = current + [oi]
        else:
            current = [] if current == [oi] else [oi]
        self._selected[qi] = current
        # Repaint this question's option buttons to reflect selection.
        for oj, _ in enumerate(self._questions[qi].get("options", [])):
            try:
                btn = self.query_one(f"#opt-{qi}-{oj}", Button)
            except Exception:
                continue
            btn.variant = "primary" if oj in current else "default"

    def _answers(self) -> dict:
        out: dict[str, str] = {}
        for qi, q in enumerate(self._questions):
            sel = self._selected.get(qi)
            if not sel:
                continue
            options = q.get("options", [])
            labels = [str(options[oi].get("label", "")) for oi in sel if oi < len(options)]
            key = str(q.get("question", q.get("header", f"question {qi + 1}")))
            out[key] = ", ".join(p for p in labels if p)
        return out

    def action_submit(self) -> None:
        self.dismiss(self._answers() or None)

    def action_skip(self) -> None:
        self.dismiss(None)
