"""A thin draggable grip that resizes an adjacent pane with the mouse.

Textual ships no splitter widget, so this is a 1-cell bar that captures the
mouse on press and, while dragging, rewrites the *target* pane's width (or
height) reactively. The pane on the other side is expected to be ``1fr`` so it
simply absorbs the remaining space.
"""

from __future__ import annotations

from textual import events
from textual.widget import Widget


class Splitter(Widget):
    """Drag to resize ``target_id``.

    axis ``"x"`` makes a vertical bar that resizes width (drag left/right);
    axis ``"y"`` makes a horizontal bar that resizes height (drag up/down).
    ``min_size`` floors the target; ``sibling_min`` reserves space for the
    1fr pane on the far side so it can't be crushed to nothing.
    """

    can_focus = False

    def __init__(
        self,
        target_id: str,
        *,
        axis: str = "x",
        min_size: int = 24,
        sibling_min: int = 30,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._target_id = target_id
        self._axis = axis
        self._min = min_size
        self._sibling_min = sibling_min
        self._dragging = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.add_class("-dragging")
        self.capture_mouse()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.remove_class("-dragging")
            self.release_mouse()
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        try:
            target = self.app.query_one(f"#{self._target_id}")
        except Exception:
            return
        container = self.parent
        if self._axis == "x":
            desired = event.screen_x - target.region.x
            limit = container.region.right - self._sibling_min - target.region.x
            target.styles.width = max(self._min, min(desired, limit))
        else:
            desired = event.screen_y - target.region.y
            limit = container.region.bottom - self._sibling_min - target.region.y
            target.styles.height = max(self._min, min(desired, limit))
        event.stop()
