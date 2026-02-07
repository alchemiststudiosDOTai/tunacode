"""Chat container widget with insertion tracking for tool panels.

This widget provides a scrollable chat history with the ability to insert
widgets at tracked positions.  Child messages use CopyOnSelectStatic so
that highlighting text with the mouse copies it to the system clipboard
automatically (no keystrokes required).
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from textual.containers import VerticalScroll
from textual.geometry import Region, Size
from textual.selection import Selection
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static

from tunacode.ui.clipboard import copy_to_clipboard


@dataclass(frozen=True)
class PanelMeta:
    """Metadata for styling a CopyOnSelectStatic widget as a CSS panel.

    Renderers return (content, PanelMeta) tuples; ChatContainer.write()
    applies the metadata as CSS classes and border_title/border_subtitle.
    """

    css_class: str = ""
    border_title: str = ""
    border_subtitle: str = ""


# Delay after the last selection change before we copy (milliseconds).
# Prevents copying on every intermediate drag event; fires once the
# mouse stops / is released.
_COPY_DEBOUNCE_MS = 0.15


class CopyOnSelectStatic(Static):
    """Static widget that copies highlighted text to the clipboard on mouse release.

    Overrides ``selection_updated`` with a short debounce so that
    only the *final* selection (after the drag ends) triggers the copy.
    """

    def __init__(self, content: RenderableType = "") -> None:
        super().__init__(content)
        self._copy_timer: Timer | None = None

    def selection_updated(self, selection: Selection | None) -> None:
        """Called by Textual when the mouse selection changes on this widget."""
        super().selection_updated(selection)
        if self._copy_timer is not None:
            self._copy_timer.stop()
            self._copy_timer = None
        if selection is None:
            return
        self._copy_timer = self.set_timer(_COPY_DEBOUNCE_MS, self._copy_current_selection)

    def _copy_current_selection(self) -> None:
        """Extract the current selection text and copy it to the clipboard."""
        self._copy_timer = None
        selection = self.text_selection
        if selection is None:
            return
        result = self.get_selection(selection)
        if result is None:
            return
        text, _ending = result
        if not text:
            return
        copy_to_clipboard(text, app=self.app)
        self.app.notify("Copied", timeout=1)


class ChatContainer(VerticalScroll):
    """Scrollable chat container with insertion point tracking.

    This container manages a chat history where widgets can be inserted
    at tracked positions.

    Attributes:
        _insertion_anchor: Widget before which to insert late-arriving content.
        _auto_scroll: Whether to auto-scroll on content changes.
    """

    DEFAULT_CSS = """
    ChatContainer {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        auto_scroll: bool = True,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._insertion_anchor: Widget | None = None
        self._auto_scroll = auto_scroll

    def clear_insertion_anchor(self) -> None:
        """Clear any stored insertion anchor."""
        self._insertion_anchor = None

    def set_insertion_anchor(self, anchor: Widget) -> None:
        """Set the widget used as an insertion anchor."""
        self._insertion_anchor = anchor

    def write(
        self,
        renderable: RenderableType,
        *,
        expand: bool = False,
        panel_meta: PanelMeta | None = None,
    ) -> Widget:
        """Append a renderable to the chat container.

        This is the primary API for adding content, compatible with RichLog.write().

        Args:
            renderable: Rich renderable to display.
            expand: If True, widget expands to fill available width.
            panel_meta: Optional panel metadata for CSS-styled borders.

        Returns:
            The created Static widget.
        """
        widget = CopyOnSelectStatic(renderable)
        widget.add_class("chat-message")
        if expand:
            widget.add_class("expand")

        if panel_meta is not None:
            if panel_meta.css_class:
                for cls in panel_meta.css_class.split():
                    widget.add_class(cls)
            if panel_meta.border_title:
                widget.border_title = panel_meta.border_title
            if panel_meta.border_subtitle:
                widget.border_subtitle = panel_meta.border_subtitle

        self.mount(widget)

        if self._auto_scroll:
            self.scroll_end(animate=False)

        return widget

    def clear(self) -> None:
        """Clear all content from the container."""
        self._insertion_anchor = None
        for child in list(self.children):
            child.remove()

    @property
    def content_region(self) -> Region:
        """Return the content region for width calculations."""
        return self.scrollable_content_region

    @property
    def size(self) -> Size:
        """Return the widget size."""
        return super().size
