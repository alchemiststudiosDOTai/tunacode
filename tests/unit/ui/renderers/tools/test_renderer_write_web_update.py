"""Tests for WriteFile, WebFetch, and UpdateFile renderer zone methods.

Source: src/tunacode/ui/renderers/tools/{write_file,web_fetch,update_file}.py
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from tunacode.ui.renderers.tools.base import RendererConfig
from tunacode.ui.renderers.tools.update_file import UpdateFileData, UpdateFileRenderer
from tunacode.ui.renderers.tools.web_fetch import WebFetchData, WebFetchRenderer
from tunacode.ui.renderers.tools.write_file import WriteFileData, WriteFileRenderer

DEFAULT_MAX_WIDTH = 80
DEFAULT_DURATION = 123.4


def _cfg(tool_name: str) -> RendererConfig:
    return RendererConfig(tool_name=tool_name)


# ---------------------------------------------------------------------------
# WriteFileRenderer zone methods
# ---------------------------------------------------------------------------


class TestWriteFileRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = WriteFileRenderer(_cfg("write_file"))
        self.data = WriteFileData(
            filepath="/project/src/new_file.py",
            filename="new_file.py",
            root_path=Path("/project"),
            content='print("hello world")\n',
            line_count=1,
            is_success=True,
        )

    def test_header_filename_and_new(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        plain = header.plain
        assert "new_file.py" in plain
        assert "NEW" in plain
        assert "1 line" in plain

    def test_params_contains_filepath(self) -> None:
        params = self.renderer.build_params(self.data, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        assert "src/new_file.py" in params.plain

    def test_viewport_with_content(self) -> None:
        result = self.renderer.build_viewport(
            self.data,
            DEFAULT_MAX_WIDTH,
        )
        assert result is not None

    def test_viewport_empty_content(self) -> None:
        empty = WriteFileData(
            filepath="empty.py",
            filename="empty.py",
            root_path=Path("/"),
            content="",
            line_count=0,
            is_success=True,
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)
        assert "empty file" in result.plain

    def test_viewport_python_gets_syntax(self) -> None:
        data = WriteFileData(
            filepath="script.py",
            filename="script.py",
            root_path=Path("/"),
            content="def foo():\n    return 42\n",
            line_count=2,
            is_success=True,
        )
        result = self.renderer.build_viewport(data, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Syntax)

    def test_status_with_duration(self) -> None:
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "123ms" in status.plain

    def test_status_truncated_file(self) -> None:
        big = WriteFileData(
            filepath="big.py",
            filename="big.py",
            root_path=Path("/"),
            content="\n".join(f"line {i}" for i in range(100)),
            line_count=100,
            is_success=True,
        )
        status = self.renderer.build_status(
            big,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert "lines" in status.plain

    def test_border_color_always_success(self) -> None:
        color = self.renderer.get_border_color(self.data)
        assert color == self.renderer.config.success_color

    # -- full render --

    def test_render_valid_result(self) -> None:
        args: dict[str, Any] = {
            "filepath": "/tmp/new.py",
            "content": "x = 1\n",
        }
        raw = "Successfully wrote to new file: /tmp/new.py"
        panel = self.renderer.render(
            args,
            raw,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)

    def test_render_returns_none_for_empty(self) -> None:
        assert self.renderer.render(None, "", None, DEFAULT_MAX_WIDTH) is None


# ---------------------------------------------------------------------------
# WebFetchRenderer zone methods
# ---------------------------------------------------------------------------


class TestWebFetchRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = WebFetchRenderer(_cfg("web_fetch"))
        self.data = WebFetchData(
            url="https://example.com/api/data",
            domain="example.com",
            content="Hello World\nLine 2\nLine 3",
            content_lines=3,
            is_truncated=False,
            timeout=60,
        )

    def test_header_domain_and_line_count(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert "example.com" in header.plain.split()
        assert "3 lines" in header.plain

    def test_header_no_domain(self) -> None:
        data = WebFetchData(
            url="",
            domain="",
            content="x",
            content_lines=1,
            is_truncated=False,
            timeout=30,
        )
        header = self.renderer.build_header(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert "web" in header.plain

    def test_params_url_and_timeout(self) -> None:
        params = self.renderer.build_params(self.data, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        plain = params.plain
        assert "url:" in plain
        assert any("example.com" in tok for tok in plain.split())
        assert "timeout:" in plain
        assert "60s" in plain

    def test_params_long_url_truncated(self) -> None:
        long_url = "https://x.com/" + "a" * 80
        data = WebFetchData(
            url=long_url,
            domain="x.com",
            content="x",
            content_lines=1,
            is_truncated=False,
            timeout=30,
        )
        params = self.renderer.build_params(data, DEFAULT_MAX_WIDTH)
        assert "..." in params.plain

    def test_viewport_with_content(self) -> None:
        result = self.renderer.build_viewport(
            self.data,
            DEFAULT_MAX_WIDTH,
        )
        assert result is not None

    def test_viewport_no_content(self) -> None:
        empty = WebFetchData(
            url="https://example.com",
            domain="example.com",
            content="",
            content_lines=0,
            is_truncated=False,
            timeout=30,
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)
        assert "no content" in result.plain

    def test_viewport_json_detection(self) -> None:
        data = WebFetchData(
            url="https://api.example.com/data.json",
            domain="api.example.com",
            content='{"key": "value"}',
            content_lines=1,
            is_truncated=False,
            timeout=30,
        )
        result = self.renderer.build_viewport(data, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Syntax)

    def test_viewport_plain_text(self) -> None:
        data = WebFetchData(
            url="https://example.com/page",
            domain="example.com",
            content="Just some text.\nMore text.",
            content_lines=2,
            is_truncated=False,
            timeout=30,
        )
        result = self.renderer.build_viewport(data, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)

    def test_status_with_duration(self) -> None:
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "123ms" in status.plain

    def test_status_truncated(self) -> None:
        data = WebFetchData(
            url="https://example.com",
            domain="example.com",
            content="[Content truncated due to size]\ndata",
            content_lines=2,
            is_truncated=True,
            timeout=30,
        )
        status = self.renderer.build_status(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert "(content truncated)" in status.plain

    def test_status_empty(self) -> None:
        data = WebFetchData(
            url="https://example.com",
            domain="example.com",
            content="short",
            content_lines=1,
            is_truncated=False,
            timeout=30,
        )
        status = self.renderer.build_status(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)

    # -- full render --

    def test_render_valid_result(self) -> None:
        args: dict[str, Any] = {
            "url": "https://example.com",
            "timeout": 60,
        }
        panel = self.renderer.render(
            args,
            "Hello World",
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)

    def test_render_returns_none_for_empty(self) -> None:
        assert (
            self.renderer.render(
                None,
                "",
                None,
                DEFAULT_MAX_WIDTH,
            )
            is None
        )


# ---------------------------------------------------------------------------
# UpdateFileRenderer zone methods
# ---------------------------------------------------------------------------


class TestUpdateFileRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = UpdateFileRenderer(_cfg("update_file"))
        self.data = UpdateFileData(
            filepath="src/main.py",
            filename="main.py",
            root_path=Path("/project"),
            message="File 'src/main.py' updated successfully.",
            diff_content=(
                "--- a/src/main.py\n"
                "+++ b/src/main.py\n"
                "@@ -1,3 +1,5 @@\n"
                " import os\n"
                "+import sys\n"
                "+import json\n"
                " \n"
                "-print('old')\n"
                "+print('new')\n"
            ),
            additions=3,
            deletions=1,
            hunks=1,
        )

    def test_header_filename_and_stats(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        plain = header.plain
        assert "main.py" in plain
        assert "+3" in plain
        assert "-1" in plain

    def test_params_contains_filepath(self) -> None:
        params = self.renderer.build_params(
            self.data,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(params, Text)
        assert "src/main.py" in params.plain

    def test_viewport_renders_diff(self) -> None:
        result = self.renderer.build_viewport(
            self.data,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(result, Syntax)

    def test_status_contains_hunks(self) -> None:
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "1 hunk" in status.plain
        assert "123ms" in status.plain

    def test_status_plural_hunks(self) -> None:
        data = UpdateFileData(
            filepath="x.py",
            filename="x.py",
            root_path=Path("/project"),
            message="ok",
            diff_content=("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n@@ -10 +10 @@\n-c\n+d\n"),
            additions=2,
            deletions=2,
            hunks=2,
        )
        status = self.renderer.build_status(
            data,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert "2 hunks" in status.plain

    # -- full render (overridden in UpdateFileRenderer) --

    def test_render_valid_result(self) -> None:
        raw = (
            "File 'src/main.py' updated successfully.\n\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "+import sys\n"
            " \n"
            " print('hello')\n"
        )
        panel = self.renderer.render(
            None,
            raw,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)

    def test_render_with_diagnostics(self) -> None:
        raw = (
            "File 'src/main.py' updated successfully.\n\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,2 +1,3 @@\n"
            " import os\n"
            "+import sys\n"
            " print('hello')\n"
            "\n"
            "<file_diagnostics>\n"
            "Error (line 10): type mismatch\n"
            "Warning (line 15): unused import\n"
            "</file_diagnostics>"
        )
        panel = self.renderer.render(
            None,
            raw,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)
        buf = StringIO()
        console = Console(file=buf, width=120, force_terminal=False)
        console.print(panel)
        rendered = buf.getvalue()
        assert "type mismatch" in rendered
        assert "unused import" in rendered

    def test_render_returns_none_for_empty(self) -> None:
        assert (
            self.renderer.render(
                None,
                "",
                None,
                DEFAULT_MAX_WIDTH,
            )
            is None
        )

    def test_render_returns_none_for_no_diff(self) -> None:
        result = self.renderer.render(
            None,
            "Some message without diff",
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert result is None
