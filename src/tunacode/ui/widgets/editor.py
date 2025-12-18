"""Editor widget for TunaCode REPL."""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.expand_tabs import expand_tabs_inline
from textual.geometry import Offset, Region, Size
from textual.strip import Strip
from textual.widgets import Input

from .messages import EditorSubmitRequested
from .status_bar import StatusBar


@dataclass(frozen=True, slots=True)
class _WrappedEditorState:
    lines: list[Text]
    cursor_offset: tuple[int, int]
    wrap_width: int


class Editor(Input):
    """Single-line editor with Enter to submit."""

    value: str  # type re-declaration for mypy (inherited reactive from Input)

    BASH_MODE_PREFIX = "!"
    BASH_MODE_PREFIX_WITH_SPACE = "! "
    PASTE_BUFFER_LONG_LINE_THRESHOLD: int = 400
    PASTE_BUFFER_SEPARATOR: str = "\n\n"

    BINDINGS = [
        Binding("enter", "submit", "Submit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(placeholder="we await...")
        self._placeholder_cleared: bool = False
        self._was_pasted: bool = False
        self._pasted_content: str = ""
        self._paste_after_typed_text: bool = False
        self._wrap_cache: _WrappedEditorState | None = None
        self._wrap_cache_key: tuple[object, ...] | None = None

    @property
    def has_paste_buffer(self) -> bool:
        return bool(self._was_pasted and self._pasted_content)

    @property
    def paste_summary(self) -> str | None:
        if not self.has_paste_buffer:
            return None
        line_count = max(1, len(self._pasted_content.splitlines()))
        if line_count > 1:
            return f"pasted {line_count} lines"
        return f"pasted {len(self._pasted_content)} chars"

    @property
    def _status_bar(self) -> StatusBar | None:
        """Get status bar or None if not available."""
        from textual.css.query import NoMatches

        try:
            return self.app.query_one(StatusBar)
        except NoMatches:
            return None

    def on_key(self, event: events.Key) -> None:
        """Handle key events for confirmation and bash-mode auto-spacing."""
        if event.key in ("1", "2", "3"):
            app = self.app
            if (
                hasattr(app, "pending_confirmation")
                and app.pending_confirmation is not None
                and not app.pending_confirmation.future.done()
            ):
                event.prevent_default()
                return

        has_paste_buffer = bool(getattr(self, "has_paste_buffer", False))
        if has_paste_buffer and not self.value and event.key == "backspace":
            event.prevent_default()
            self._clear_paste_buffer()
            return

        if event.character == self.BASH_MODE_PREFIX:
            if self.value.startswith(self.BASH_MODE_PREFIX):
                event.prevent_default()
                value = self.value[len(self.BASH_MODE_PREFIX) :]
                if value.startswith(" "):
                    value = value[1:]
                self.value = value
                self.cursor_position = len(self.value)
                return

            if not self.value:
                event.prevent_default()
                self.value = self.BASH_MODE_PREFIX_WITH_SPACE
                self.cursor_position = len(self.value)
                return

        # Auto-insert space after ! prefix
        # When value is "!" and user types a non-space character,
        # insert space between ! and the character
        if self.value == "!" and event.character and event.character != " ":
            event.prevent_default()
            self.value = f"! {event.character}"
            self.cursor_position = len(self.value)

    def clear_input(self) -> None:
        self.value = ""
        self._clear_paste_buffer()
        self.scroll_to(x=0, y=0, animate=False, immediate=True)

    async def action_submit(self) -> None:
        submission = self._build_submission()
        if submission is None:
            return
        text, raw_text, was_pasted = submission

        self.post_message(
            EditorSubmitRequested(text=text, raw_text=raw_text, was_pasted=was_pasted)
        )
        self.value = ""
        self.placeholder = ""  # Reset placeholder after paste submit
        self._clear_paste_buffer()
        self.scroll_to(x=0, y=0, animate=False, immediate=True)

        # Reset StatusBar mode
        if status_bar := self._status_bar:
            status_bar.set_mode(None)

    def _on_paste(self, event: events.Paste) -> None:
        """Capture full paste content before Input truncates to first line."""
        line_count = max(1, len(event.text.splitlines()))
        is_multiline = line_count > 1
        is_long_single_line = len(event.text) >= self.PASTE_BUFFER_LONG_LINE_THRESHOLD

        if not is_multiline and not is_long_single_line:
            super()._on_paste(event)
            return

        self._was_pasted = True
        self._pasted_content = event.text
        self._paste_after_typed_text = bool(self.value.strip())

        if paste_summary := self.paste_summary:
            self.placeholder = paste_summary
            if status_bar := self._status_bar:
                status_bar.set_mode(paste_summary)

        event.stop()

    def watch_value(self, value: str) -> None:
        """React to value changes."""
        self._maybe_clear_placeholder(value)
        self._update_bash_mode(value)

    def _maybe_clear_placeholder(self, value: str) -> None:
        """Clear placeholder on first non-paste input."""
        if value and not self._placeholder_cleared and not self.has_paste_buffer:
            self.placeholder = ""
            self._placeholder_cleared = True

    def _update_bash_mode(self, value: str) -> None:
        """Toggle bash-mode class and status bar indicator."""
        self.remove_class("bash-mode")

        if self.has_paste_buffer:
            return

        if value.startswith(self.BASH_MODE_PREFIX):
            self.add_class("bash-mode")

        if status_bar := self._status_bar:
            mode = "bash mode" if value.startswith(self.BASH_MODE_PREFIX) else None
            status_bar.set_mode(mode)

    def _clear_paste_buffer(self) -> None:
        previous_summary = self.paste_summary
        self._was_pasted = False
        self._pasted_content = ""
        self._paste_after_typed_text = False

        if previous_summary and self.placeholder == previous_summary:
            self.placeholder = ""

        self._update_bash_mode(self.value)

    def _invalidate_wrap_cache(self) -> None:
        self._wrap_cache = None
        self._wrap_cache_key = None

    def _watch_value(self, value: str) -> None:
        super()._watch_value(value)
        self._invalidate_wrap_cache()

    def _watch__suggestion(self, value: str) -> None:  # noqa: ARG002
        del value
        self._invalidate_wrap_cache()

    def _watch_selection(self, selection: object) -> None:  # noqa: ARG002
        del selection

        self.app.clear_selection()
        self.app.cursor_position = self.cursor_screen_offset
        if self._initial_value:
            return

        cursor_x, cursor_y = self._wrapped_state().cursor_offset
        self.scroll_to_region(
            Region(cursor_x, cursor_y, width=1, height=1),
            force=True,
            animate=False,
            x_axis=False,
        )

    @property
    def cursor_screen_offset(self) -> Offset:
        """Cursor offset in screen-space (column, row)."""
        cursor_x, cursor_y = self._wrapped_state().cursor_offset
        content_x, content_y, _width, _height = self.content_region
        scroll_x, scroll_y = self.scroll_offset
        return Offset(content_x + cursor_x - scroll_x, content_y + cursor_y - scroll_y)

    def get_content_width(self, container: Size, viewport: Size) -> int:  # noqa: ARG002
        del container
        return max(1, viewport.width)

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:  # noqa: ARG002
        del container, viewport
        return len(self._wrapped_state(wrap_width=max(1, width)).lines)

    def render_line(self, y: int) -> Strip:
        state = self._wrapped_state()
        if y < 0 or y >= len(state.lines):
            return Strip.blank(self.size.width)

        console = self.app.console
        segments = list(
            console.render(state.lines[y], console.options.update_width(state.wrap_width))
        )
        strip = Strip(segments).extend_cell_length(state.wrap_width)
        return strip.apply_style(self.rich_style)

    def _wrapped_state(self, *, wrap_width: int | None = None) -> _WrappedEditorState:
        width = self._wrap_width(wrap_width)
        key: tuple[object, ...] = (
            width,
            self.value,
            self.placeholder,
            self._suggestion,
            self.selection.start,
            self.selection.end,
            self.has_focus,
            self._cursor_visible,
            self.cursor_position,
            self.cursor_at_end,
        )
        if self._wrap_cache_key == key and self._wrap_cache is not None:
            return self._wrap_cache

        state = self._compute_wrapped_state(width)
        self._wrap_cache_key = key
        self._wrap_cache = state
        self.virtual_size = Size(width, len(state.lines))
        return state

    def _wrap_width(self, override: int | None) -> int:
        if override is not None:
            return max(1, override)
        return max(1, self.scrollable_content_region.width)

    def _compute_wrapped_state(self, wrap_width: int) -> _WrappedEditorState:
        display_text, cursor_index = self._build_wrapped_display_text()
        wrapped_lines = list(display_text.wrap(self.app.console, width=wrap_width, overflow="fold"))
        cursor_x, cursor_y = self._cursor_offset_in_wrapped_lines(wrapped_lines, cursor_index)
        return _WrappedEditorState(
            lines=wrapped_lines,
            cursor_offset=(cursor_x, cursor_y),
            wrap_width=wrap_width,
        )

    def _build_wrapped_display_text(self) -> tuple[Text, int]:
        cursor_style = self.get_component_rich_style("input--cursor")

        if not self.value:
            placeholder = Text(self.placeholder, justify="left", end="", overflow="fold")
            placeholder.stylize(self.get_component_rich_style("input--placeholder"))
            if self.has_focus and self._cursor_visible:
                if len(placeholder) == 0:
                    placeholder = Text(" ", end="", overflow="fold")
                placeholder.stylize(cursor_style, 0, 1)
            return placeholder, 0

        value = self.value
        value_length = len(value)
        suggestion = self._suggestion
        show_suggestion = len(suggestion) > value_length and self.has_focus

        result = Text(value, end="", overflow="fold")
        if self.highlighter is not None:
            result = self.highlighter(result)

        if show_suggestion:
            result += Text(
                suggestion[value_length:],
                self.get_component_rich_style("input--suggestion"),
                end="",
            )

        if self.cursor_at_end and not show_suggestion:
            result.pad_right(1)

        if self.has_focus:
            if not self.selection.is_empty:
                start, end = sorted(self.selection)
                selection_style = self.get_component_rich_style("input--selection")
                result.stylize_before(selection_style, start, end)

            if self._cursor_visible:
                cursor = self.cursor_position
                result.stylize(cursor_style, cursor, cursor + 1)

        cursor_index = self.cursor_position
        return result, cursor_index

    def _cursor_offset_in_wrapped_lines(
        self,
        lines: list[Text],
        cursor_index: int,
    ) -> tuple[int, int]:
        remaining = max(0, cursor_index)
        for y, line in enumerate(lines):
            line_length = len(line.plain)
            if remaining <= line_length:
                prefix = line.plain[:remaining]
                return cell_len(expand_tabs_inline(prefix, 4)), y
            remaining -= line_length

        last_line = lines[-1]
        return cell_len(expand_tabs_inline(last_line.plain, 4)), len(lines) - 1

    def _build_submission(self) -> tuple[str, str, bool] | None:
        typed_text = self.value
        typed_has_content = bool(typed_text.strip())
        paste_text = self._pasted_content.rstrip("\n")
        paste_has_content = bool(paste_text.strip())

        if not typed_has_content and not paste_has_content:
            return None

        if not paste_has_content:
            text = typed_text.strip()
            return text, typed_text, False

        if not typed_has_content:
            return paste_text, paste_text, True

        typed_stripped = typed_text.strip()
        if self._paste_after_typed_text:
            combined = typed_stripped + self.PASTE_BUFFER_SEPARATOR + paste_text
        else:
            combined = paste_text + self.PASTE_BUFFER_SEPARATOR + typed_stripped

        return combined, combined, True
