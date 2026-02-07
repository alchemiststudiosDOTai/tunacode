"""Chat container widget with insertion tracking for tool panels.

This widget provides a scrollable chat history with the ability to insert
widgets at tracked positions.  Child messages use CopyOnSelectStatic so
that highlighting text with the mouse copies it to the system clipboard
automatically (no keystrokes required).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice

from rich.console import RenderableType
from rich.segment import Segment
from rich.style import Style as RichStyle
from textual._context import active_app
from textual.containers import VerticalScroll
from textual.css.styles import RulesMap
from textual.geometry import Region, Size
from textual.selection import Selection
from textual.strip import Strip
from textual.style import Style
from textual.timer import Timer
from textual.visual import RichVisual, Visual, visualize
from textual.widget import Widget
from textual.widgets import Static

from tunacode.ui.clipboard import copy_to_clipboard


class SelectableRichVisual(RichVisual):
    """RichVisual subclass that injects offset metadata into rendered segments.

    Textual's text selection requires {"offset": (x, y)} in each segment's
    style.meta to map mouse coordinates to text positions.  The base
    RichVisual never adds this metadata, so selection silently fails.

    This subclass post-processes each rendered strip, injecting the offset
    metadata and applying selection highlighting when active.
    """

    def render_strips(
        self,
        _rules: RulesMap,
        width: int,
        height: int | None,
        style: Style,
        selection: Selection | None = None,
        selection_style: Style | None = None,
        _post_style: Style | None = None,
    ) -> list[Strip]:
        console = active_app.get().console
        options = console.options.update(
            highlight=False,
            width=width,
            height=height,
        )
        rich_style = style.rich_style
        renderable = self._widget.post_render(self._renderable, rich_style)
        segments = console.render(renderable, options.update_width(width))
        raw_lines = Segment.split_and_crop_lines(
            segments, width, include_new_lines=False, pad=False
        )

        get_span = selection.get_span if selection is not None else None
        sel_rich_style = selection_style.rich_style if selection_style is not None else None

        def with_offset(style: RichStyle | None, x: int, y: int) -> RichStyle:
            base = style or RichStyle.null()
            # Textual selection relies on this metadata to map mouse coordinates.
            return base + RichStyle(meta={"offset": (x, y)})

        strips: list[Strip] = []
        for y, line in enumerate(islice(raw_lines, None, height)):
            span = get_span(y) if get_span is not None else None
            x = 0
            new_segments: list[Segment] = []

            for segment in line:
                if segment.control:
                    # Control codes take no space; keep x unchanged.
                    new_segments.append(segment)
                    continue

                seg_cells = segment.cell_length
                base_style = segment.style

                if span is None or sel_rich_style is None:
                    new_segments.append(
                        Segment(segment.text, with_offset(base_style, x, y), segment.control)
                    )
                    x += seg_cells
                    continue

                start_sel, end_sel_inclusive = span
                end_sel_exclusive = (
                    x + seg_cells if end_sel_inclusive == -1 else end_sel_inclusive + 1
                )

                overlap_start = max(x, start_sel)
                overlap_end = min(x + seg_cells, end_sel_exclusive)

                if overlap_start >= overlap_end:
                    new_segments.append(
                        Segment(segment.text, with_offset(base_style, x, y), segment.control)
                    )
                    x += seg_cells
                    continue

                pre_cut = overlap_start - x
                post_cut = overlap_end - x

                left, remainder = segment.split_cells(pre_cut)
                middle, right = remainder.split_cells(post_cut - pre_cut)

                if left.text:
                    new_segments.append(
                        Segment(left.text, with_offset(base_style, x, y), left.control)
                    )

                if middle.text:
                    new_segments.append(
                        Segment(
                            middle.text,
                            with_offset(base_style, x + pre_cut, y) + sel_rich_style,
                            middle.control,
                        )
                    )

                if right.text:
                    new_segments.append(
                        Segment(
                            right.text,
                            with_offset(base_style, x + post_cut, y),
                            right.control,
                        )
                    )

                x += seg_cells

            strips.append(Strip(new_segments))

        return strips


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

    Overrides ``_render`` to swap RichVisual for SelectableRichVisual (which
    injects offset metadata so Textual's selection can map mouse coordinates
    to text positions).  Also overrides ``get_selection`` so text can be
    extracted from Rich renderables, not just Text/Content objects.
    """

    def __init__(self, content: RenderableType = "") -> None:
        super().__init__(content)
        self._copy_timer: Timer | None = None

    def _render(self) -> Visual:
        """Promote RichVisual to SelectableRichVisual for offset metadata."""
        cache_key = "_render.visual"
        cached = self._layout_cache.get(cache_key, None)
        if cached is not None:
            assert isinstance(cached, Visual)
            return cached
        visual = visualize(self, self.render(), markup=self._render_markup)
        if isinstance(visual, RichVisual) and not isinstance(visual, SelectableRichVisual):
            visual = SelectableRichVisual(self, visual._renderable)
        self._layout_cache[cache_key] = visual
        return visual

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Extract selected text from any visual, including Rich renderables."""
        visual = self._render()
        if isinstance(visual, SelectableRichVisual):
            width = self.size.width
            strips = Visual.to_strips(
                self,
                visual,
                width,
                None,
                self.visual_style,
                pad=False,
            )
            text = "\n".join(strip.text for strip in strips)
            return selection.extract(text), "\n"
        return super().get_selection(selection)

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

        # Rich renderables frequently include trailing spaces to align columns.
        # Those look like "blank space" junk when pasted elsewhere.
        cleaned = "\n".join(line.rstrip() for line in text.splitlines()).strip("\n")
        if not cleaned:
            return

        copy_to_clipboard(cleaned, app=self.app)
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
