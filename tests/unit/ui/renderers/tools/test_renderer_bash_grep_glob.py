"""Tests for Bash, Grep, and Glob renderer zone methods.

Source: src/tunacode/ui/renderers/tools/{bash,grep,glob}.py
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from tunacode.ui.renderers.tools.base import RendererConfig
from tunacode.ui.renderers.tools.bash import BashData, BashRenderer
from tunacode.ui.renderers.tools.glob import GlobData, GlobRenderer
from tunacode.ui.renderers.tools.grep import GrepData, GrepRenderer

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_WIDTH = 80
DEFAULT_DURATION = 123.4


def _cfg(tool_name: str) -> RendererConfig:
    return RendererConfig(tool_name=tool_name)


# ---------------------------------------------------------------------------
# BashRenderer zone methods
# ---------------------------------------------------------------------------


class TestBashRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = BashRenderer(_cfg("bash"))
        self.data_ok = BashData(
            command="ls -la",
            exit_code=0,
            working_dir="/home/user",
            stdout="file1.txt\nfile2.txt",
            stderr="",
            is_truncated=False,
            timeout=30,
        )
        self.data_err = BashData(
            command="false",
            exit_code=1,
            working_dir="/tmp",
            stdout="",
            stderr="command failed",
            is_truncated=True,
            timeout=60,
        )

    # -- build_header --

    def test_header_success(self) -> None:
        header = self.renderer.build_header(
            self.data_ok,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert "ls -la" in header.plain
        assert "ok" in header.plain

    def test_header_failure(self) -> None:
        header = self.renderer.build_header(
            self.data_err,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert "exit 1" in header.plain

    def test_header_long_command_truncated(self) -> None:
        long_cmd = BashData(
            command="a" * 200,
            exit_code=0,
            working_dir=".",
            stdout="",
            stderr="",
            is_truncated=False,
            timeout=30,
        )
        header = self.renderer.build_header(long_cmd, None, 50)
        assert isinstance(header, Text)
        assert "..." in header.plain

    # -- build_params --

    def test_params_contains_cwd_and_timeout(self) -> None:
        params = self.renderer.build_params(self.data_ok, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        plain = params.plain
        assert "cwd:" in plain
        assert "/home/user" in plain
        assert "timeout:" in plain
        assert "30s" in plain

    # -- build_viewport --

    def test_viewport_with_stdout(self) -> None:
        result = self.renderer.build_viewport(self.data_ok, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_viewport_with_stderr(self) -> None:
        result = self.renderer.build_viewport(self.data_err, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_viewport_no_output(self) -> None:
        empty = BashData(
            command="true",
            exit_code=0,
            working_dir=".",
            stdout="",
            stderr="",
            is_truncated=False,
            timeout=30,
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_viewport_with_both_streams(self) -> None:
        both = BashData(
            command="make",
            exit_code=2,
            working_dir="/project",
            stdout="Building...\nDone",
            stderr="warning: unused variable",
            is_truncated=False,
            timeout=120,
        )
        result = self.renderer.build_viewport(both, DEFAULT_MAX_WIDTH)
        assert result is not None

    # -- build_status --

    def test_status_with_duration(self) -> None:
        status = self.renderer.build_status(
            self.data_ok,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "123ms" in status.plain

    def test_status_truncated(self) -> None:
        status = self.renderer.build_status(
            self.data_err,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert "(truncated)" in status.plain

    def test_status_no_duration(self) -> None:
        status = self.renderer.build_status(
            self.data_ok,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "ms" not in status.plain

    def test_status_empty_output(self) -> None:
        empty = BashData(
            command="true",
            exit_code=0,
            working_dir=".",
            stdout="",
            stderr="",
            is_truncated=False,
            timeout=30,
        )
        status = self.renderer.build_status(empty, None, DEFAULT_MAX_WIDTH)
        assert isinstance(status, Text)

    # -- border / status text --

    def test_border_color_success(self) -> None:
        color = self.renderer.get_border_color(self.data_ok)
        assert color == self.renderer.config.success_color

    def test_border_color_failure(self) -> None:
        color = self.renderer.get_border_color(self.data_err)
        assert color == self.renderer.config.warning_color

    def test_status_text_success(self) -> None:
        assert self.renderer.get_status_text(self.data_ok) == "done"

    def test_status_text_failure(self) -> None:
        assert self.renderer.get_status_text(self.data_err) == "exit 1"

    # -- full render --

    def test_render_success(self) -> None:
        raw = (
            "Command: ls\n"
            "Exit Code: 0\n"
            "Working Directory: /home\n\n"
            "STDOUT:\nfile.txt\n\n"
            "STDERR:\n(no errors)"
        )
        panel = self.renderer.render(None, raw, DEFAULT_DURATION, DEFAULT_MAX_WIDTH)
        assert isinstance(panel, Panel)

    def test_render_failure_exit_code(self) -> None:
        raw = (
            "Command: bad_cmd\n"
            "Exit Code: 127\n"
            "Working Directory: /tmp\n\n"
            "STDOUT:\n(no output)\n\n"
            "STDERR:\ncommand not found"
        )
        panel = self.renderer.render(None, raw, 50.0, DEFAULT_MAX_WIDTH)
        assert isinstance(panel, Panel)

    def test_render_returns_none_for_empty(self) -> None:
        assert self.renderer.render(None, "", None, DEFAULT_MAX_WIDTH) is None

    def test_render_returns_none_for_garbage(self) -> None:
        assert self.renderer.render(None, "garbage", None, DEFAULT_MAX_WIDTH) is None


# ---------------------------------------------------------------------------
# GrepRenderer zone methods
# ---------------------------------------------------------------------------


class TestGrepRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = GrepRenderer(_cfg("grep"))
        self.data = GrepData(
            pattern="TODO",
            total_matches=3,
            strategy="smart",
            candidates=42,
            matches=[
                {
                    "file": "src/main.py",
                    "line": 10,
                    "before": "# ",
                    "match": "TODO",
                    "after": ": fix",
                },
                {
                    "file": "src/main.py",
                    "line": 25,
                    "before": "# ",
                    "match": "TODO",
                    "after": ": refactor",
                },
                {
                    "file": "src/utils.py",
                    "line": 5,
                    "before": "# ",
                    "match": "TODO",
                    "after": "",
                },
            ],
            is_truncated=False,
            case_sensitive=True,
            use_regex=False,
            context_lines=2,
        )

    def test_header_pattern_and_count(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert '"TODO"' in header.plain
        assert "3 matches" in header.plain

    def test_header_singular_match(self) -> None:
        single = GrepData(
            pattern="FIXME",
            total_matches=1,
            strategy="smart",
            candidates=10,
            matches=[
                {
                    "file": "a.py",
                    "line": 1,
                    "before": "",
                    "match": "FIXME",
                    "after": "",
                }
            ],
            is_truncated=False,
            case_sensitive=False,
            use_regex=False,
            context_lines=0,
        )
        header = self.renderer.build_header(single, None, DEFAULT_MAX_WIDTH)
        assert "1 match" in header.plain
        assert "1 matches" not in header.plain

    def test_params_contains_flags(self) -> None:
        params = self.renderer.build_params(self.data, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        plain = params.plain
        assert "strategy:" in plain
        assert "smart" in plain
        assert "case: yes" in plain
        assert "regex: no" in plain
        assert "context:" in plain

    def test_params_case_insensitive_regex_on(self) -> None:
        data = GrepData(
            pattern="x",
            total_matches=0,
            strategy="regex",
            candidates=0,
            matches=[],
            is_truncated=False,
            case_sensitive=False,
            use_regex=True,
            context_lines=5,
        )
        params = self.renderer.build_params(data, DEFAULT_MAX_WIDTH)
        plain = params.plain
        assert "case: no" in plain
        assert "regex: yes" in plain

    def test_viewport_with_matches(self) -> None:
        result = self.renderer.build_viewport(self.data, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_viewport_no_matches(self) -> None:
        empty = GrepData(
            pattern="nonexistent",
            total_matches=0,
            strategy="smart",
            candidates=0,
            matches=[],
            is_truncated=False,
            case_sensitive=False,
            use_regex=False,
            context_lines=2,
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)
        assert "no matches" in result.plain

    def test_status_with_candidates_and_duration(self) -> None:
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "42 files searched" in status.plain
        assert "123ms" in status.plain

    def test_status_truncated(self) -> None:
        data = GrepData(
            pattern="x",
            total_matches=100,
            strategy="smart",
            candidates=50,
            matches=[
                {
                    "file": "a.py",
                    "line": 1,
                    "before": "",
                    "match": "x",
                    "after": "",
                }
            ],
            is_truncated=True,
            case_sensitive=False,
            use_regex=False,
            context_lines=2,
        )
        status = self.renderer.build_status(data, None, DEFAULT_MAX_WIDTH)
        assert "[1/100 shown]" in status.plain

    def test_status_no_items(self) -> None:
        data = GrepData(
            pattern="x",
            total_matches=1,
            strategy="smart",
            candidates=0,
            matches=[
                {
                    "file": "a.py",
                    "line": 1,
                    "before": "",
                    "match": "x",
                    "after": "",
                }
            ],
            is_truncated=False,
            case_sensitive=False,
            use_regex=False,
            context_lines=2,
        )
        status = self.renderer.build_status(data, None, DEFAULT_MAX_WIDTH)
        assert isinstance(status, Text)

    # -- full render --

    def test_render_valid_result(self) -> None:
        raw = (
            "Found 1 match for pattern: TODO\n"
            "Strategy: smart | Candidates: 5 files\n"
            "\U0001f4c1 src/main.py:10\n"
            "\u25b6  10\u2502# \u27e8TODO\u27e9: fix this"
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
# GlobRenderer zone methods
# ---------------------------------------------------------------------------


class TestGlobRendererZones:
    """Exercise build_header / build_params / build_viewport / build_status."""

    def setup_method(self) -> None:
        self.renderer = GlobRenderer(_cfg("glob"))
        self.data = GlobData(
            pattern="**/*.py",
            file_count=5,
            files=[
                "src/main.py",
                "src/utils.py",
                "tests/test_main.py",
                "setup.py",
                "docs/conf.py",
            ],
            source="index",
            is_truncated=False,
            recursive=True,
            include_hidden=False,
            sort_by="modified",
        )

    def test_header_pattern_and_count(self) -> None:
        header = self.renderer.build_header(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(header, Text)
        assert '"**/*.py"' in header.plain
        assert "5 files" in header.plain

    def test_header_single_file(self) -> None:
        single = GlobData(
            pattern="*.txt",
            file_count=1,
            files=["readme.txt"],
            source="filesystem",
            is_truncated=False,
            recursive=False,
            include_hidden=False,
            sort_by="name",
        )
        header = self.renderer.build_header(
            single,
            None,
            DEFAULT_MAX_WIDTH,
        )
        assert "1 file" in header.plain
        assert "1 files" not in header.plain

    def test_params_contains_flags(self) -> None:
        params = self.renderer.build_params(self.data, DEFAULT_MAX_WIDTH)
        assert isinstance(params, Text)
        plain = params.plain
        assert "recursive: on" in plain
        assert "hidden: off" in plain
        assert "sort:" in plain
        assert "modified" in plain

    def test_params_hidden_on(self) -> None:
        data = GlobData(
            pattern="*",
            file_count=0,
            files=[],
            source="filesystem",
            is_truncated=False,
            recursive=False,
            include_hidden=True,
            sort_by="name",
        )
        params = self.renderer.build_params(data, DEFAULT_MAX_WIDTH)
        plain = params.plain
        assert "recursive: off" in plain
        assert "hidden: on" in plain

    def test_viewport_with_files(self) -> None:
        result = self.renderer.build_viewport(self.data, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_viewport_no_files(self) -> None:
        empty = GlobData(
            pattern="*.xyz",
            file_count=0,
            files=[],
            source="filesystem",
            is_truncated=False,
            recursive=True,
            include_hidden=False,
            sort_by="name",
        )
        result = self.renderer.build_viewport(empty, DEFAULT_MAX_WIDTH)
        assert isinstance(result, Text)
        assert "no files" in result.plain

    def test_viewport_varied_file_types(self) -> None:
        data = GlobData(
            pattern="*",
            file_count=3,
            files=["src/main.py", "README.md", "data.json"],
            source="filesystem",
            is_truncated=False,
            recursive=True,
            include_hidden=False,
            sort_by="name",
        )
        result = self.renderer.build_viewport(data, DEFAULT_MAX_WIDTH)
        assert result is not None

    def test_status_indexed(self) -> None:
        status = self.renderer.build_status(
            self.data,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(status, Text)
        assert "indexed" in status.plain
        assert "123ms" in status.plain

    def test_status_scanned(self) -> None:
        data = GlobData(
            pattern="*",
            file_count=2,
            files=["a.txt", "b.txt"],
            source="filesystem",
            is_truncated=False,
            recursive=True,
            include_hidden=False,
            sort_by="name",
        )
        status = self.renderer.build_status(data, None, DEFAULT_MAX_WIDTH)
        assert "scanned" in status.plain

    def test_status_truncated(self) -> None:
        data = GlobData(
            pattern="*",
            file_count=100,
            files=["a.txt"],
            source="index",
            is_truncated=True,
            recursive=True,
            include_hidden=False,
            sort_by="name",
        )
        status = self.renderer.build_status(data, None, DEFAULT_MAX_WIDTH)
        assert "shown" in status.plain

    # -- full render --

    def test_render_valid_result(self) -> None:
        raw = "[source:index]\nFound 2 files matching pattern: *.py\n\nsrc/main.py\nsrc/utils.py"
        panel = self.renderer.render(
            None,
            raw,
            DEFAULT_DURATION,
            DEFAULT_MAX_WIDTH,
        )
        assert isinstance(panel, Panel)

    def test_render_returns_none_for_empty(self) -> None:
        assert self.renderer.render(None, "", None, DEFAULT_MAX_WIDTH) is None
