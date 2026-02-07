"""Tests for syntax_utils pure functions."""

from __future__ import annotations

from tunacode.ui.renderers.tools.syntax_utils import (
    _detect_by_markers,
    _detect_json,
    _detect_shebang,
    detect_code_lexer,
    get_color,
    get_lexer,
)

# ---------------------------------------------------------------------------
# get_lexer
# ---------------------------------------------------------------------------


class TestGetLexer:
    """Map file extension to pygments lexer name."""

    def test_python_extension(self) -> None:
        assert get_lexer("main.py") == "python"

    def test_javascript_extension(self) -> None:
        assert get_lexer("app.js") == "javascript"

    def test_rust_extension(self) -> None:
        assert get_lexer("lib.rs") == "rust"

    def test_unknown_extension_returns_text(self) -> None:
        assert get_lexer("data.unknown") == "text"

    def test_dockerfile_exact_name(self) -> None:
        assert get_lexer("Dockerfile") == "docker"

    def test_makefile_exact_name(self) -> None:
        assert get_lexer("Makefile") == "make"

    def test_json_extension(self) -> None:
        assert get_lexer("config.json") == "json"

    def test_absolute_path_python(self) -> None:
        assert get_lexer("/home/user/project/main.py") == "python"

    def test_relative_path_javascript(self) -> None:
        assert get_lexer("./src/index.js") == "javascript"

    def test_nested_dockerfile(self) -> None:
        assert get_lexer("docker/Dockerfile") == "docker"

    def test_yaml_extension(self) -> None:
        assert get_lexer("config.yaml") == "yaml"

    def test_yml_extension(self) -> None:
        assert get_lexer("config.yml") == "yaml"

    def test_typescript_extension(self) -> None:
        assert get_lexer("app.ts") == "typescript"

    def test_no_extension_returns_text(self) -> None:
        assert get_lexer("README") == "text"

    def test_case_insensitive_extension(self) -> None:
        """Extension lookup is lowered, so .PY should resolve to python."""
        assert get_lexer("main.PY") == "python"


# ---------------------------------------------------------------------------
# get_color
# ---------------------------------------------------------------------------


class TestGetColor:
    """Map lexer name to color string."""

    def test_python_returns_bright_blue(self) -> None:
        assert get_color("python") == "bright_blue"

    def test_javascript_returns_yellow(self) -> None:
        assert get_color("javascript") == "yellow"

    def test_json_returns_green(self) -> None:
        assert get_color("json") == "green"

    def test_markdown_returns_cyan(self) -> None:
        assert get_color("markdown") == "cyan"

    def test_bash_returns_magenta(self) -> None:
        assert get_color("bash") == "magenta"

    def test_unknown_returns_empty(self) -> None:
        assert get_color("unknown") == ""

    def test_typescript_returns_yellow(self) -> None:
        assert get_color("typescript") == "yellow"

    def test_yaml_returns_green(self) -> None:
        assert get_color("yaml") == "green"

    def test_rst_returns_cyan(self) -> None:
        assert get_color("rst") == "cyan"

    def test_zsh_returns_magenta(self) -> None:
        assert get_color("zsh") == "magenta"

    def test_arbitrary_lexer_returns_empty(self) -> None:
        assert get_color("cobol") == ""


# ---------------------------------------------------------------------------
# _detect_shebang
# ---------------------------------------------------------------------------


class TestDetectShebang:
    """Detect language from shebang line."""

    def test_python3_env_shebang(self) -> None:
        assert _detect_shebang("#!/usr/bin/env python3") == "python"

    def test_bash_shebang(self) -> None:
        assert _detect_shebang("#!/bin/bash") == "bash"

    def test_node_env_shebang(self) -> None:
        assert _detect_shebang("#!/usr/bin/env node") == "javascript"

    def test_no_shebang_returns_none(self) -> None:
        assert _detect_shebang("no shebang") is None

    def test_empty_string_returns_none(self) -> None:
        assert _detect_shebang("") is None

    def test_sh_shebang_returns_bash(self) -> None:
        assert _detect_shebang("#!/bin/sh") == "bash"

    def test_ruby_shebang(self) -> None:
        assert _detect_shebang("#!/usr/bin/env ruby") == "ruby"

    def test_perl_shebang(self) -> None:
        assert _detect_shebang("#!/usr/bin/perl") == "perl"


# ---------------------------------------------------------------------------
# _detect_json
# ---------------------------------------------------------------------------


class TestDetectJson:
    """Detect JSON content."""

    def test_valid_json_object(self) -> None:
        assert _detect_json('{"key": "value"}') == "json"

    def test_invalid_json_returns_none(self) -> None:
        assert _detect_json("{not json at all}") is None

    def test_non_object_content_returns_none(self) -> None:
        assert _detect_json("just plain text") is None

    def test_array_content_returns_none(self) -> None:
        """Arrays do not match -- must start with { and end with }."""
        assert _detect_json("[1, 2, 3]") is None

    def test_nested_json_object(self) -> None:
        assert _detect_json('{"a": {"b": 1}}') == "json"

    def test_whitespace_padded_json(self) -> None:
        assert _detect_json('  {"key": "value"}  ') == "json"

    def test_empty_string_returns_none(self) -> None:
        assert _detect_json("") is None

    def test_empty_braces_is_valid_json(self) -> None:
        assert _detect_json("{}") == "json"


# ---------------------------------------------------------------------------
# _detect_by_markers
# ---------------------------------------------------------------------------


class TestDetectByMarkers:
    """Detect language by content markers."""

    def test_def_keyword_returns_python(self) -> None:
        assert _detect_by_markers("def hello():") == "python"

    def test_function_keyword_returns_javascript(self) -> None:
        assert _detect_by_markers("function hello() {}") == "javascript"

    def test_const_keyword_returns_javascript(self) -> None:
        assert _detect_by_markers("const x = 42;") == "javascript"

    def test_no_markers_returns_none(self) -> None:
        assert _detect_by_markers("just some text") is None

    def test_class_keyword_returns_python(self) -> None:
        assert _detect_by_markers("class Foo:") == "python"

    def test_import_keyword_returns_python(self) -> None:
        assert _detect_by_markers("import os") == "python"

    def test_export_keyword_returns_javascript(self) -> None:
        assert _detect_by_markers("export default App") == "javascript"

    def test_empty_string_returns_none(self) -> None:
        assert _detect_by_markers("") is None

    def test_python_takes_precedence_over_javascript(self) -> None:
        """Python markers are checked first in _CONTENT_MARKER_LEXERS."""
        content = "def foo():\n  const x = 1"
        assert _detect_by_markers(content) == "python"


# ---------------------------------------------------------------------------
# detect_code_lexer
# ---------------------------------------------------------------------------


class TestDetectCodeLexer:
    """Top-level detection: shebang -> JSON -> markers -> None."""

    def test_empty_content_returns_none(self) -> None:
        assert detect_code_lexer("") is None

    def test_shebang_detected(self) -> None:
        assert detect_code_lexer("#!/usr/bin/env python3\nprint('hi')") == "python"

    def test_json_detected(self) -> None:
        assert detect_code_lexer('{"key": "value"}') == "json"

    def test_marker_detected(self) -> None:
        assert detect_code_lexer("def main():\n    pass") == "python"

    def test_no_detection_returns_none(self) -> None:
        assert detect_code_lexer("random gibberish 12345") is None

    def test_shebang_takes_precedence_over_markers(self) -> None:
        content = "#!/bin/bash\ndef fake_python():"
        assert detect_code_lexer(content) == "bash"

    def test_json_takes_precedence_over_markers(self) -> None:
        content = '{"def ": "looks like python marker but is json"}'
        assert detect_code_lexer(content) == "json"
