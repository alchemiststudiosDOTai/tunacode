"""Tests for ListDir and ReadFile renderer zone methods.

Source: src/tunacode/ui/renderers/tools/{list_dir,read_file}.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from tunacode.ui.renderers.tools.base import RendererConfig
from tunacode.ui.renderers.tools.list_dir import ListDirData, ListDirRenderer
from tunacode.ui.renderers.tools.read_file import ReadFileData, ReadFileRenderer

DEFAULT_MAX_WIDTH = 80
DEFAULT_DURATION = 123.4


def _cfg(tool_name: str) -> RendererConfig:
    return RendererConfig(tool_name=tool_name)


# ---------------------------------------------------------------------------
# ListDirRenderer zone methods
# ---------------------------------------------------------------------------


class TestListDirRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = ListDirRenderer(_cfg("list_dir"))
        tree = (
            "src\n"
            "\u251c\u2500\u2500 main.py\n"
            "\u251c\u2500\u2500 utils.py\n"
            "\u2514\u2500\u2500 tests/"
        )
        self.data = ListDirData(
            directory="src",
            tree_content=tree,
            file_count=10,
            dir_count=3,
            is_truncated=False,
            max_files=100,
            show_hidden=False,
            ignore_count=5,
        )

    def test_header_dir_and_counts(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        plain = header.plain
        assert "src" in plain
        assert "10 files" in plain
        assert "3 dirs" in plain

    def test_params_contains_flags(self) -> None:
        params = self.renderer.build_params(self.data, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        plain = params.plain
        assert "hidden:" in plain
        assert "off" in plain
        assert "max:" in plain
        assert "100" in plain
        assert "ignore:" in plain
        assert "5" in plain

    def test_params_show_hidden_on(self) -> None:
        data = ListDirData(
            directory="/tmp",
            tree_content="/tmp\n\u2514\u2500\u2500 .hidden",
            file_count=1,
            dir_count=0,
            is_truncated=False,
            max_files=50,
            show_hidden=True,
            ignore_count=0,
        )
        params = self.renderer.build_params(data, DEFAULT_MAX_WIDTH)
        assert "on" in params.plain

    def test_viewport_with_tree_content(self) -> None:
        result = self.renderer.build_viewport(self.data, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_viewport_empty_directory(self) -> None:
        empty = ListDirData(
            directory="empty_dir",
            tree_content="empty_dir",
            file_count=0,
            dir_count=0,
            is_truncated=False,
            max_files=100,
            show_hidden=False,
            ignore_count=0,
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)
        assert "empty directory" in result.plain

    def test_style_tree_line_directory(self) -> None:
        styled = self.renderer._style_tree_line(
            "\u251c\u2500\u2500 tests/",
        )
        assert isinstance(styled, Text)

    def test_style_tree_line_file(self) -> None:
        styled = self.renderer._style_tree_line(
            "\u2514\u2500\u2500 main.py",
        )
        assert isinstance(styled, Text)

    def test_status_with_duration(self) -> None:
        viewport = self.renderer.build_viewport(self.data, DEFAULT_MAX_WIDTH)
        assert viewport is not None  # viewport must succeed before status
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "123ms" in status.plain
        # Viewport sets shown/total lines that status reads
        if hasattr(self.data, "shown_lines") and self.data.shown_lines is not None:
            assert self.data.shown_lines > 0

    def test_status_truncated(self) -> None:
        lines = "\n".join(f"\u251c\u2500\u2500 file{i}.py" for i in range(20))
        data = ListDirData(
            directory="/big",
            tree_content="/big\n" + lines,
            file_count=500,
            dir_count=10,
            is_truncated=True,
            max_files=100,
            show_hidden=False,
            ignore_count=50,
        )
        viewport = self.renderer.build_viewport(data, DEFAULT_MAX_WIDTH)
        assert viewport is not None  # viewport must run before status
        status = self.renderer.build_status(data, None, DEFAULT_MAX_WIDTH)
        assert "(truncated)" in status.plain

    def test_status_no_data(self) -> None:
        data = ListDirData(
            directory="x",
            tree_content="x\n\u2514\u2500\u2500 a.txt",
            file_count=1,
            dir_count=0,
            is_truncated=False,
            max_files=100,
            show_hidden=False,
            ignore_count=0,
            shown_lines=1,
            total_lines=1,
        )
        status = self.renderer.build_status(data, None, DEFAULT_MAX_WIDTH)
        assert isinstance(status, Text)

    # -- full render --

    def test_render_valid_result(self) -> None:
        raw = (
            "10 files  3 dirs  5 ignored\n"
            "src\n"
            "\u251c\u2500\u2500 main.py\n"
            "\u2514\u2500\u2500 utils.py"
        )
        panel = self.renderer.render(
            None,
            raw,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)

    def test_render_returns_none_for_empty(self) -> None:
        assert self.renderer.render(None, "", None, DEFAULT_MAX_WIDTH) is None


# ---------------------------------------------------------------------------
# ReadFileRenderer zone methods
# ---------------------------------------------------------------------------


class TestReadFileRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = ReadFileRenderer(_cfg("read_file"))
        self.data = ReadFileData(
            filepath="/project/src/main.py",
            filename="main.py",
            root_path=Path("/project"),
            content_lines=[
                (1, "import os"),
                (2, "import sys"),
                (3, ""),
                (4, 'print("hello")'),
            ],
            total_lines=50,
            offset=0,
            has_more=True,
            end_message="(File has more lines beyond line 4)",
        )

    def test_header_filename_and_range(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert "main.py" in header.plain
        assert "lines 1-4" in header.plain

    def test_header_no_content_lines(self) -> None:
        data = ReadFileData(
            filepath="empty.py",
            filename="empty.py",
            root_path=Path("/"),
            content_lines=[],
            total_lines=0,
            offset=0,
            has_more=False,
            end_message="",
        )
        header = self.renderer.build_header(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert "empty.py" in header.plain

    def test_params_contains_filepath(self) -> None:
        params = self.renderer.build_params(self.data, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        assert "src/main.py" in params.plain

    def test_viewport_with_content(self) -> None:
        result = self.renderer.build_viewport(
            self.data,
            DEFAULT_MAX_WIDTH,
        )
        assert result is not None

    def test_viewport_empty_file(self) -> None:
        empty = ReadFileData(
            filepath="empty.py",
            filename="empty.py",
            root_path=Path("/"),
            content_lines=[],
            total_lines=0,
            offset=0,
            has_more=False,
            end_message="",
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)
        assert "empty file" in result.plain

    def test_viewport_python_gets_syntax(self) -> None:
        result = self.renderer.build_viewport(
            self.data,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(result, Syntax)

    def test_viewport_text_file_plain(self) -> None:
        data = ReadFileData(
            filepath="notes.txt",
            filename="notes.txt",
            root_path=Path("/"),
            content_lines=[(1, "Some notes"), (2, "More notes")],
            total_lines=2,
            offset=0,
            has_more=False,
            end_message="",
        )
        result = self.renderer.build_viewport(data, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)

    def test_status_has_more(self) -> None:
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        plain = status.plain
        assert "total: 50 lines" in plain
        assert "(more available)" in plain
        assert "123ms" in plain

    def test_status_complete_file(self) -> None:
        data = ReadFileData(
            filepath="small.py",
            filename="small.py",
            root_path=Path("/"),
            content_lines=[(1, "pass")],
            total_lines=1,
            offset=0,
            has_more=False,
            end_message="(End of file - total 1 lines)",
        )
        status = self.renderer.build_status(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "total: 1 line" in status.plain
        assert "(more available)" not in status.plain

    def test_status_empty(self) -> None:
        data = ReadFileData(
            filepath="x.py",
            filename="x.py",
            root_path=Path("/"),
            content_lines=[],
            total_lines=0,
            offset=0,
            has_more=False,
            end_message="",
        )
        status = self.renderer.build_status(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)

    # -- full render --

    def test_render_valid_result(self) -> None:
        raw = "<file>\n00001| import os\n00002| import sys\n(End of file - total 2 lines)\n</file>"
        args: dict[str, Any] = {"filepath": "src/main.py"}
        panel = self.renderer.render(
            args,
            raw,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)

    def test_render_returns_none_for_empty(self) -> None:
        assert self.renderer.render(None, "", None, DEFAULT_MAX_WIDTH) is None
