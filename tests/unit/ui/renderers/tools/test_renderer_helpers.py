"""Tests for base renderer methods, output type detection, file style, and config.

Source: src/tunacode/ui/renderers/tools/base.py and private helpers across renderers.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from tunacode.constants import UI_COLORS

from tunacode.core.ui_api.constants import MIN_VIEWPORT_LINES

from tunacode.ui.renderers.tools.base import RendererConfig
from tunacode.ui.renderers.tools.bash import BashRenderer
from tunacode.ui.renderers.tools.glob import GlobRenderer
from tunacode.ui.renderers.tools.list_dir import ListDirRenderer
from tunacode.ui.renderers.tools.web_fetch import WebFetchRenderer
from tunacode.ui.renderers.tools.write_file import WriteFileData, WriteFileRenderer

DEFAULT_MAX_WIDTH = 80


def _cfg(tool_name: str) -> RendererConfig:
    return RendererConfig(tool_name=tool_name)


# ---------------------------------------------------------------------------
# BaseToolRenderer common methods
# ---------------------------------------------------------------------------


class TestBaseToolRendererCommon:
    """Test base class methods shared across all renderers."""

    def setup_method(self) -> None:
        self.renderer = BashRenderer(_cfg("bash"))

    def test_build_separator(self) -> None:
        sep = self.renderer.build_separator()
        assert isinstance(sep, Text)
        assert len(sep.plain) > 0

    def test_pad_viewport_lines_below_minimum(self) -> None:
        padded = self.renderer.pad_viewport_lines(["one"])
        assert len(padded) >= MIN_VIEWPORT_LINES

    def test_pad_viewport_lines_at_minimum(self) -> None:
        padded = self.renderer.pad_viewport_lines(["a", "b", "c"])
        assert len(padded) == MIN_VIEWPORT_LINES

    def test_pad_viewport_lines_above_minimum(self) -> None:
        padded = self.renderer.pad_viewport_lines(["a", "b", "c", "d", "e"])
        assert len(padded) == 5

    def test_default_get_border_color(self) -> None:
        renderer = WriteFileRenderer(_cfg("write_file"))
        data = WriteFileData(
            filepath="x.py",
            filename="x.py",
            root_path=Path("/"),
            content="",
            line_count=0,
            is_success=True,
        )
        assert renderer.get_border_color(data) == renderer.config.success_color

    def test_default_get_status_text(self) -> None:
        renderer = WriteFileRenderer(_cfg("write_file"))
        data = WriteFileData(
            filepath="x.py",
            filename="x.py",
            root_path=Path("/"),
            content="",
            line_count=0,
            is_success=True,
        )
        assert renderer.get_status_text(data) == "done"


# ---------------------------------------------------------------------------
# Bash _detect_output_type coverage
# ---------------------------------------------------------------------------


class TestBashDetectOutputType:
    """Exercise the private _detect_output_type method."""

    def setup_method(self) -> None:
        self.renderer = BashRenderer(_cfg("bash"))

    def test_json_command(self) -> None:
        result = self.renderer._detect_output_type(
            "curl -s http://api.com",
            '{"key": "val"}',
        )
        assert result == "json"

    def test_git_diff_command(self) -> None:
        result = self.renderer._detect_output_type(
            "git diff HEAD",
            "--- a/file\n+++ b/file",
        )
        assert result == "diff"

    def test_git_log_command(self) -> None:
        result = self.renderer._detect_output_type(
            "git log",
            "commit abc123\nAuthor: test",
        )
        assert result is None

    def test_python_command(self) -> None:
        result = self.renderer._detect_output_type(
            "python script.py",
            "output text",
        )
        assert result is None

    def test_plain_command(self) -> None:
        result = self.renderer._detect_output_type("ls", "file1\nfile2")
        assert result is None

    def test_json_flag_non_json_output(self) -> None:
        result = self.renderer._detect_output_type("cmd --json", "not json")
        assert result != "json"


# ---------------------------------------------------------------------------
# WebFetch _detect_content_type coverage
# ---------------------------------------------------------------------------


class TestWebFetchDetectContentType:
    """Exercise the private _detect_content_type method."""

    def setup_method(self) -> None:
        self.renderer = WebFetchRenderer(_cfg("web_fetch"))

    def test_json_url(self) -> None:
        result = self.renderer._detect_content_type(
            "https://api.com/data.json",
            '{"k":"v"}',
        )
        assert result == "json"

    def test_xml_url(self) -> None:
        result = self.renderer._detect_content_type(
            "https://site.com/feed.xml",
            "<rss>data</rss>",
        )
        assert result == "xml"

    def test_yaml_url(self) -> None:
        result = self.renderer._detect_content_type(
            "https://site.com/config.yaml",
            "key: value",
        )
        assert result == "yaml"

    def test_yml_url(self) -> None:
        result = self.renderer._detect_content_type(
            "https://site.com/config.yml",
            "key: value",
        )
        assert result == "yaml"

    def test_raw_github_python(self) -> None:
        url = "https://raw.githubusercontent.com/u/r/main/s.py"
        result = self.renderer._detect_content_type(url, "import os")
        assert result == "python"

    def test_raw_github_js(self) -> None:
        url = "https://raw.githubusercontent.com/u/r/main/a.js"
        result = self.renderer._detect_content_type(url, "const x=1;")
        assert result == "javascript"

    def test_raw_github_ts(self) -> None:
        url = "https://raw.githubusercontent.com/u/r/main/a.ts"
        result = self.renderer._detect_content_type(url, "const x=1;")
        assert result == "typescript"

    def test_raw_github_rust(self) -> None:
        url = "https://raw.githubusercontent.com/u/r/main/lib.rs"
        result = self.renderer._detect_content_type(url, "fn main(){}")
        assert result == "rust"

    def test_raw_github_go(self) -> None:
        url = "https://raw.githubusercontent.com/u/r/main/main.go"
        result = self.renderer._detect_content_type(url, "package main")
        assert result == "go"

    def test_api_url_json(self) -> None:
        result = self.renderer._detect_content_type(
            "https://example.com/api/users",
            '[{"name":"alice"}]',
        )
        assert result == "json"

    def test_rss_url(self) -> None:
        result = self.renderer._detect_content_type(
            "https://blog.example.com/rss",
            "<feed>x</feed>",
        )
        assert result == "xml"

    def test_atom_url(self) -> None:
        result = self.renderer._detect_content_type(
            "https://blog.example.com/atom",
            "<feed>x</feed>",
        )
        assert result == "xml"

    def test_plain_content(self) -> None:
        result = self.renderer._detect_content_type(
            "https://example.com/page",
            "Just some text.",
        )
        assert result is None


# ---------------------------------------------------------------------------
# Glob _get_file_style coverage
# ---------------------------------------------------------------------------


class TestGlobGetFileStyle:
    """Exercise the private _get_file_style method."""

    def setup_method(self) -> None:
        self.renderer = GlobRenderer(_cfg("glob"))

    def test_python_file(self) -> None:
        assert self.renderer._get_file_style("src/main.py") == "bright_blue"

    def test_javascript_file(self) -> None:
        assert self.renderer._get_file_style("app.js") == "yellow"

    def test_json_file(self) -> None:
        assert self.renderer._get_file_style("config.json") == "green"

    def test_markdown_file(self) -> None:
        assert self.renderer._get_file_style("README.md") == "cyan"

    def test_unknown_file(self) -> None:
        assert self.renderer._get_file_style("data.xyz") == ""

    def test_bash_file(self) -> None:
        assert self.renderer._get_file_style("run.sh") == "magenta"


# ---------------------------------------------------------------------------
# ListDir _style_tree_line / _get_file_style coverage
# ---------------------------------------------------------------------------


class TestListDirStyleTreeLine:
    """Exercise the private _style_tree_line method."""

    def setup_method(self) -> None:
        self.renderer = ListDirRenderer(_cfg("list_dir"))

    def test_directory_line(self) -> None:
        styled = self.renderer._style_tree_line("\u251c\u2500\u2500 subdir/")
        assert isinstance(styled, Text)

    def test_file_with_extension(self) -> None:
        styled = self.renderer._style_tree_line("\u2514\u2500\u2500 script.py")
        assert isinstance(styled, Text)

    def test_file_no_extension_treated_as_dir(self) -> None:
        styled = self.renderer._style_tree_line("\u2514\u2500\u2500 Makefile")
        assert isinstance(styled, Text)

    def test_deeply_nested_prefix(self) -> None:
        line = "\u2502   \u2502   \u2514\u2500\u2500 deep.rs"
        styled = self.renderer._style_tree_line(line)
        assert isinstance(styled, Text)

    def test_plain_name_no_prefix(self) -> None:
        styled = self.renderer._style_tree_line("toplevel.py")
        assert isinstance(styled, Text)


class TestListDirGetFileStyle:
    """Exercise the private _get_file_style method."""

    def setup_method(self) -> None:
        self.renderer = ListDirRenderer(_cfg("list_dir"))

    def test_python_file_color(self) -> None:
        assert self.renderer._get_file_style("main.py") == "bright_blue"

    def test_unknown_file_empty(self) -> None:
        assert self.renderer._get_file_style("data.xyz") == ""


# ---------------------------------------------------------------------------
# RendererConfig defaults
# ---------------------------------------------------------------------------


class TestRendererConfig:
    """Verify RendererConfig default values."""

    def test_defaults(self) -> None:
        config = RendererConfig(tool_name="test")
        assert config.tool_name == "test"
        assert config.success_color == UI_COLORS["success"]
        assert config.warning_color == UI_COLORS["warning"]
        assert config.muted_color == UI_COLORS["muted"]

    def test_custom_colors(self) -> None:
        config = RendererConfig(
            tool_name="custom",
            success_color="green",
            warning_color="yellow",
            muted_color="gray",
        )
        assert config.success_color == "green"
        assert config.warning_color == "yellow"
        assert config.muted_color == "gray"
