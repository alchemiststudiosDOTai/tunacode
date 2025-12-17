"""Tests for LSP diagnostics rendering."""

from tunacode.ui.renderers.tools.diagnostics import (
    DiagnosticItem,
    DiagnosticsData,
    extract_diagnostics_from_result,
    parse_diagnostics_block,
    truncate_diagnostic_message,
)


class TestMessageTruncation:
    def test_truncate_multiline_pyright_error(self):
        """Verbose Pyright output should be truncated to first line."""
        verbose = """Type "int" is not compatible with type "str"
  "int" is incompatible with "str"
    Type cannot be assigned"""
        result = truncate_diagnostic_message(verbose)
        assert "\n" not in result
        assert result == 'Type "int" is not compatible with type "str"'

    def test_truncate_long_single_line(self):
        """Long single-line messages should be truncated with ellipsis."""
        long_msg = "x" * 200
        result = truncate_diagnostic_message(long_msg, max_length=100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_short_message_unchanged(self):
        """Short messages should pass through unchanged."""
        short = "Type mismatch"
        result = truncate_diagnostic_message(short)
        assert result == short

    def test_empty_message(self):
        """Empty message should return empty string."""
        result = truncate_diagnostic_message("")
        assert result == ""


class TestDiagnosticsParser:
    def test_parse_empty_string(self):
        """Empty string should return None."""
        result = parse_diagnostics_block("")
        assert result is None

    def test_parse_no_tags(self):
        """String without tags should return None."""
        result = parse_diagnostics_block("Some random text")
        assert result is None

    def test_parse_empty_block(self):
        """Empty tags should return None."""
        result = parse_diagnostics_block("<file_diagnostics></file_diagnostics>")
        assert result is None

    def test_parse_single_error(self):
        """Single error should be parsed correctly."""
        block = """<file_diagnostics>
Error (line 10): Type mismatch
</file_diagnostics>"""
        result = parse_diagnostics_block(block)
        assert result is not None
        assert len(result.items) == 1
        assert result.error_count == 1
        assert result.warning_count == 0
        assert result.items[0].severity == "error"
        assert result.items[0].line == 10
        assert result.items[0].message == "Type mismatch"

    def test_parse_multiple_diagnostics(self):
        """Multiple diagnostics should all be parsed."""
        block = """<file_diagnostics>
Error (line 10): Type mismatch
Warning (line 15): Unused variable
Info (line 20): Consider using f-string
</file_diagnostics>"""
        result = parse_diagnostics_block(block)
        assert result is not None
        assert len(result.items) == 3
        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.info_count == 1

    def test_parse_with_summary_line(self):
        """Summary line should be skipped."""
        block = """<file_diagnostics>
Summary: 2 errors, 1 warnings
Error (line 10): First error
Error (line 20): Second error
Warning (line 30): A warning
</file_diagnostics>"""
        result = parse_diagnostics_block(block)
        assert result is not None
        assert len(result.items) == 3
        assert result.error_count == 2
        assert result.warning_count == 1

    def test_parse_case_insensitive_severity(self):
        """Severity parsing should be case-insensitive."""
        block = """<file_diagnostics>
ERROR (line 10): Uppercase error
warning (line 15): Lowercase warning
</file_diagnostics>"""
        result = parse_diagnostics_block(block)
        assert result is not None
        assert len(result.items) == 2
        assert result.items[0].severity == "error"
        assert result.items[1].severity == "warning"


class TestExtractDiagnostics:
    def test_extract_no_diagnostics(self):
        """Result without diagnostics should return original and None."""
        result = "File updated successfully.\n--- a/file.py\n+++ b/file.py"
        clean, block = extract_diagnostics_from_result(result)
        assert clean == result
        assert block is None

    def test_extract_with_diagnostics(self):
        """Diagnostics block should be extracted and removed."""
        result = """File updated successfully.

--- a/file.py
+++ b/file.py
@@ -1,1 +1,1 @@
-old
+new

<file_diagnostics>
Error (line 10): Type mismatch
</file_diagnostics>"""

        clean, block = extract_diagnostics_from_result(result)
        assert "<file_diagnostics>" not in clean
        assert block is not None
        assert "Error (line 10)" in block

    def test_extract_preserves_diff(self):
        """Diff content should be preserved after extraction."""
        result = """File updated.

--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-foo
+bar

<file_diagnostics>
Error (line 1): Issue
</file_diagnostics>"""

        clean, _ = extract_diagnostics_from_result(result)
        assert "--- a/test.py" in clean
        assert "+++ b/test.py" in clean
        assert "-foo" in clean
        assert "+bar" in clean


class TestDiagnosticsData:
    def test_dataclass_creation(self):
        """DiagnosticsData should be correctly created."""
        items = [
            DiagnosticItem(severity="error", line=10, message="Error msg"),
            DiagnosticItem(severity="warning", line=20, message="Warning msg"),
        ]
        data = DiagnosticsData(
            items=items,
            error_count=1,
            warning_count=1,
            info_count=0,
        )
        assert len(data.items) == 2
        assert data.error_count == 1
        assert data.warning_count == 1
