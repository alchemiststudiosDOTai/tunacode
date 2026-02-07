"""Tests for parse_result() methods across all tool renderers.

Each tool renderer's parse_result takes (args, result) and returns a
typed dataclass or None when parsing fails.

Source: src/tunacode/ui/renderers/tools/*.py
"""

from __future__ import annotations

from tunacode.ui.renderers.tools.base import RendererConfig
from tunacode.ui.renderers.tools.bash import BashData, BashRenderer
from tunacode.ui.renderers.tools.glob import GlobData, GlobRenderer
from tunacode.ui.renderers.tools.grep import GrepData, GrepRenderer
from tunacode.ui.renderers.tools.list_dir import ListDirData, ListDirRenderer
from tunacode.ui.renderers.tools.read_file import ReadFileData, ReadFileRenderer
from tunacode.ui.renderers.tools.web_fetch import WebFetchData, WebFetchRenderer
from tunacode.ui.renderers.tools.write_file import WriteFileData, WriteFileRenderer

# ---------------------------------------------------------------------------
# BashRenderer.parse_result
# ---------------------------------------------------------------------------


class TestBashParseResult:
    """Parse structured bash output into BashData."""

    def setup_method(self) -> None:
        self.renderer = BashRenderer(RendererConfig(tool_name="bash"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_valid_result(self) -> None:
        result = (
            "Command: ls\n"
            "Exit Code: 0\n"
            "Working Directory: /home\n"
            "\n"
            "STDOUT:\n"
            "file.txt\n"
            "\n"
            "STDERR:\n"
            "(no errors)"
        )
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, BashData)
        assert data.command == "ls"
        assert data.exit_code == 0
        assert data.working_dir == "/home"
        assert data.stdout == "file.txt"
        assert data.stderr == ""

    def test_missing_command_returns_none(self) -> None:
        result = "Exit Code: 0\nWorking Directory: /home\n\nSTDOUT:\n\nSTDERR:\n"
        assert self.renderer.parse_result(None, result) is None

    def test_missing_exit_code_returns_none(self) -> None:
        result = "Command: ls\nWorking Directory: /home\n\nSTDOUT:\n\nSTDERR:\n"
        assert self.renderer.parse_result(None, result) is None

    def test_nonzero_exit_code(self) -> None:
        result = (
            "Command: false\n"
            "Exit Code: 1\n"
            "Working Directory: /tmp\n"
            "\n"
            "STDOUT:\n"
            "(no output)\n"
            "\n"
            "STDERR:\n"
            "error occurred"
        )
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, BashData)
        assert data.exit_code == 1
        assert data.stdout == ""
        assert data.stderr == "error occurred"

    def test_truncated_marker(self) -> None:
        result = (
            "Command: cat big.log\n"
            "Exit Code: 0\n"
            "Working Directory: /home\n"
            "[truncated]\n"
            "\n"
            "STDOUT:\n"
            "lots of output\n"
            "\n"
            "STDERR:\n"
            "(no errors)"
        )
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, BashData)
        assert data.is_truncated is True

    def test_timeout_from_args(self) -> None:
        result = (
            "Command: sleep 5\n"
            "Exit Code: 0\n"
            "Working Directory: /home\n"
            "\n"
            "STDOUT:\n"
            "(no output)\n"
            "\n"
            "STDERR:\n"
            "(no errors)"
        )
        data = self.renderer.parse_result({"timeout": 60}, result)
        assert isinstance(data, BashData)
        assert data.timeout == 60

    def test_default_timeout(self) -> None:
        result = (
            "Command: echo hi\n"
            "Exit Code: 0\n"
            "Working Directory: /home\n"
            "\n"
            "STDOUT:\n"
            "hi\n"
            "\n"
            "STDERR:\n"
            "(no errors)"
        )
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, BashData)
        assert data.timeout == 30


# ---------------------------------------------------------------------------
# GrepRenderer.parse_result
# ---------------------------------------------------------------------------


class TestGrepParseResult:
    """Parse structured grep output into GrepData."""

    def setup_method(self) -> None:
        self.renderer = GrepRenderer(RendererConfig(tool_name="grep"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_result_without_found_returns_none(self) -> None:
        result = "No matches at all"
        assert self.renderer.parse_result(None, result) is None

    def test_valid_result_with_strategy(self) -> None:
        # Build a result with the expected header format.
        # Match lines require special unicode characters from the renderer.
        result = (
            "Found 1 match for pattern: test\n"
            "Strategy: python | Candidates: 5 files\n"
            "\U0001f4c1 src/main.py:10\n"
            "\u25b6  10\u2502def \u27e8test\u27e9_func():\n"
        )
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, GrepData)
        assert data.pattern == "test"
        assert data.total_matches == 1
        assert data.strategy == "python"
        assert data.candidates == 5
        assert len(data.matches) == 1
        assert data.matches[0]["file"] == "src/main.py"
        assert data.matches[0]["match"] == "test"

    def test_zero_matches_returns_none(self) -> None:
        """Zero matches with no match data returns None."""
        result = "Found 0 matches for pattern: nope\nStrategy: smart | Candidates: 10 files\n"
        assert self.renderer.parse_result(None, result) is None

    def test_args_propagated(self) -> None:
        result = (
            "Found 2 matches for pattern: foo\n"
            "Strategy: regex | Candidates: 3 files\n"
            "\U0001f4c1 a.py:1\n"
            "\u25b6   1\u2502x = \u27e8foo\u27e9()\n"
            "\U0001f4c1 b.py:5\n"
            "\u25b6   5\u2502y = \u27e8foo\u27e9.bar\n"
        )
        args = {
            "case_sensitive": True,
            "use_regex": True,
            "context_lines": 4,
        }
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, GrepData)
        assert data.case_sensitive is True
        assert data.use_regex is True
        assert data.context_lines == 4

    def test_single_line_header_only_returns_none(self) -> None:
        result = "Found 1 match for pattern: foo"
        assert self.renderer.parse_result(None, result) is None


# ---------------------------------------------------------------------------
# GlobRenderer.parse_result
# ---------------------------------------------------------------------------


class TestGlobParseResult:
    """Parse structured glob output into GlobData."""

    def setup_method(self) -> None:
        self.renderer = GlobRenderer(RendererConfig(tool_name="glob"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_valid_result(self) -> None:
        result = "Found 2 files matching pattern: *.py\n./src/a.py\n./src/b.py"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, GlobData)
        assert data.pattern == "*.py"
        assert data.file_count == 2
        assert len(data.files) == 2
        assert "./src/a.py" in data.files
        assert "./src/b.py" in data.files

    def test_with_source_marker(self) -> None:
        result = "[source:index]\nFound 1 file matching pattern: *.rs\n./lib.rs"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, GlobData)
        assert data.source == "index"
        assert data.file_count == 1

    def test_without_source_marker(self) -> None:
        result = "Found 1 file matching pattern: *.txt\n./readme.txt"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, GlobData)
        assert data.source == "filesystem"

    def test_truncated_result(self) -> None:
        result = "Found 100 files matching pattern: *.py\n./a.py\n./b.py\n(truncated at 2)"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, GlobData)
        assert data.is_truncated is True
        assert data.file_count == 100

    def test_no_header_match_returns_none(self) -> None:
        result = "No files found"
        assert self.renderer.parse_result(None, result) is None

    def test_args_propagated(self) -> None:
        result = "Found 1 file matching pattern: *.py\n./a.py"
        args = {
            "recursive": False,
            "include_hidden": True,
            "sort_by": "name",
        }
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, GlobData)
        assert data.recursive is False
        assert data.include_hidden is True
        assert data.sort_by == "name"

    def test_default_args(self) -> None:
        result = "Found 1 file matching pattern: *.py\n./a.py"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, GlobData)
        assert data.recursive is True
        assert data.include_hidden is False
        assert data.sort_by == "modified"


# ---------------------------------------------------------------------------
# ReadFileRenderer.parse_result
# ---------------------------------------------------------------------------


class TestReadFileParseResult:
    """Parse structured read_file output into ReadFileData."""

    def setup_method(self) -> None:
        self.renderer = ReadFileRenderer(RendererConfig(tool_name="read_file"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_result_without_file_tag_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "just some text") is None

    def test_valid_result_with_numbered_lines(self) -> None:
        result = (
            "<file>\n1| def hello():\n2|     print('hi')\n(End of file - total 2 lines)\n</file>"
        )
        args = {"filepath": "/tmp/test.py", "offset": 0}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, ReadFileData)
        assert data.filepath == "/tmp/test.py"
        assert data.filename == "test.py"
        assert len(data.content_lines) == 2
        assert data.content_lines[0] == (1, "def hello():")
        assert data.content_lines[1] == (2, "    print('hi')")
        assert data.total_lines == 2
        assert data.has_more is False

    def test_has_more_lines(self) -> None:
        result = (
            "<file>\n"
            "1| line one\n"
            "2| line two\n"
            "(File has more lines. Use 'offset' to read beyond line 2)\n"
            "</file>"
        )
        args = {"filepath": "/tmp/big.py"}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, ReadFileData)
        assert data.has_more is True
        assert data.total_lines == 2

    def test_empty_file_tag_returns_none(self) -> None:
        result = "<file>\n</file>"
        assert self.renderer.parse_result(None, result) is None

    def test_empty_file_with_end_message(self) -> None:
        result = "<file>\n(End of file - total 0 lines)\n</file>"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, ReadFileData)
        assert data.content_lines == []
        assert data.total_lines == 0

    def test_default_filepath_when_no_args(self) -> None:
        result = "<file>\n1| content\n(End of file - total 1 lines)\n</file>"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, ReadFileData)
        assert data.filepath == "unknown"


# ---------------------------------------------------------------------------
# WriteFileRenderer.parse_result
# ---------------------------------------------------------------------------


class TestWriteFileParseResult:
    """Parse structured write_file output into WriteFileData."""

    def setup_method(self) -> None:
        self.renderer = WriteFileRenderer(RendererConfig(tool_name="write_file"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_valid_result_with_args(self) -> None:
        result = "Successfully wrote to new file: /tmp/test.py"
        args = {
            "filepath": "/tmp/test.py",
            "content": "print('hello')\nprint('world')",
        }
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WriteFileData)
        assert data.filepath == "/tmp/test.py"
        assert data.filename == "test.py"
        assert data.is_success is True
        assert data.line_count == 2

    def test_filepath_extracted_from_result(self) -> None:
        """When filepath not in args, extract from result message."""
        result = "Successfully wrote to new file: /tmp/output.txt"
        data = self.renderer.parse_result({}, result)
        assert isinstance(data, WriteFileData)
        assert data.filepath == "/tmp/output.txt"

    def test_no_filepath_anywhere_returns_none(self) -> None:
        result = "Something happened"
        data = self.renderer.parse_result({}, result)
        assert data is None

    def test_empty_content(self) -> None:
        result = "Successfully wrote to new file: /tmp/empty.py"
        args = {"filepath": "/tmp/empty.py", "content": ""}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WriteFileData)
        assert data.line_count == 0

    def test_success_flag(self) -> None:
        result = "Successfully wrote to new file: /tmp/test.py"
        args = {"filepath": "/tmp/test.py"}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WriteFileData)
        assert data.is_success is True

    def test_failure_result(self) -> None:
        result = "Failed to write file"
        args = {"filepath": "/tmp/test.py"}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WriteFileData)
        assert data.is_success is False


# ---------------------------------------------------------------------------
# WebFetchRenderer.parse_result
# ---------------------------------------------------------------------------


class TestWebFetchParseResult:
    """Parse web_fetch result into WebFetchData."""

    def setup_method(self) -> None:
        self.renderer = WebFetchRenderer(RendererConfig(tool_name="web_fetch"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_valid_result_with_content(self) -> None:
        result = "# Welcome\n\nThis is some web content.\nLine two."
        args = {"url": "https://example.com/page", "timeout": 30}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WebFetchData)
        assert data.url == "https://example.com/page"
        assert data.domain == "example.com"
        assert data.content_lines == 4
        assert data.timeout == 30

    def test_domain_parsed_from_url(self) -> None:
        result = "content"
        args = {"url": "https://docs.python.org/3/library/re.html"}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WebFetchData)
        assert data.domain == "docs.python.org"

    def test_truncated_content(self) -> None:
        result = "some content\n[Content truncated due to size]\nmore"
        args = {"url": "https://example.com"}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, WebFetchData)
        assert data.is_truncated is True

    def test_no_url_in_args(self) -> None:
        result = "web content here"
        data = self.renderer.parse_result({}, result)
        assert isinstance(data, WebFetchData)
        assert data.url == ""
        assert data.domain == ""

    def test_default_timeout(self) -> None:
        result = "some content"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, WebFetchData)
        assert data.timeout == 60


# ---------------------------------------------------------------------------
# ListDirRenderer.parse_result
# ---------------------------------------------------------------------------


class TestListDirParseResult:
    """Parse structured list_dir output into ListDirData."""

    def setup_method(self) -> None:
        self.renderer = ListDirRenderer(RendererConfig(tool_name="list_dir"))

    def test_empty_result_returns_none(self) -> None:
        assert self.renderer.parse_result(None, "") is None

    def test_valid_result(self) -> None:
        result = (
            "45 files  12 dirs  5 ignored\n"
            "src/\n"
            "\u251c\u2500\u2500 main.py\n"
            "\u251c\u2500\u2500 utils/\n"
            "\u2514\u2500\u2500 config.py"
        )
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, ListDirData)
        assert data.file_count == 45
        assert data.dir_count == 12
        assert data.ignore_count == 5
        assert data.directory == "src"
        assert data.is_truncated is False

    def test_truncated_result(self) -> None:
        result = "100 files  20 dirs  10 ignored (truncated)\nproject/\n\u251c\u2500\u2500 file.py"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, ListDirData)
        assert data.is_truncated is True

    def test_single_line_returns_none(self) -> None:
        result = "45 files  12 dirs  5 ignored"
        assert self.renderer.parse_result(None, result) is None

    def test_invalid_summary_returns_none(self) -> None:
        result = "not a valid summary\nsrc/\nfile.py"
        assert self.renderer.parse_result(None, result) is None

    def test_args_propagated(self) -> None:
        result = "10 files  3 dirs  0 ignored\nmydir/\n\u2514\u2500\u2500 a.py"
        args = {"max_files": 50, "show_hidden": True}
        data = self.renderer.parse_result(args, result)
        assert isinstance(data, ListDirData)
        assert data.max_files == 50
        assert data.show_hidden is True

    def test_default_args(self) -> None:
        result = "5 files  1 dirs  0 ignored\ndir/\n\u2514\u2500\u2500 f.py"
        data = self.renderer.parse_result(None, result)
        assert isinstance(data, ListDirData)
        assert data.max_files == 100
        assert data.show_hidden is False
