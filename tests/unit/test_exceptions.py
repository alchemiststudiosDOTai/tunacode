"""Tests for tunacode.exceptions."""

import pytest

from tunacode.exceptions import (
    JSON_TRUNCATION_LIMIT,
    AgentError,
    AggregateToolError,
    ConfigurationError,
    FileOperationError,
    GitOperationError,
    GlobalRequestTimeoutError,
    ModelConfigurationError,
    SetupValidationError,
    StateError,
    TooBroadPatternError,
    ToolBatchingJSONError,
    ToolExecutionError,
    ToolRetryError,
    TunaCodeError,
    UserAbortError,
    ValidationError,
    _build_error_message,
    _format_section,
)


class TestFormatSection:
    def test_empty_lines_returns_empty(self):
        assert _format_section("Label", []) == ""

    def test_single_line(self):
        result = _format_section("Fix", ["do this"])
        assert result == "Fix:\ndo this"

    def test_multiple_lines(self):
        result = _format_section("Steps", ["step1", "step2"])
        assert "step1\nstep2" in result


class TestBuildErrorMessage:
    def test_base_only(self):
        assert _build_error_message("base") == "base"

    def test_with_suggested_fix(self):
        result = _build_error_message("base", suggested_fix="fix it")
        assert "Suggested fix:" in result
        assert "fix it" in result

    def test_with_help_url(self):
        result = _build_error_message("base", help_url="https://example.com")
        assert "More help:" in result
        assert "https://example.com" in result.split()

    def test_with_valid_examples(self):
        result = _build_error_message("base", valid_examples=["ex1", "ex2"])
        assert "Valid examples:" in result
        assert "ex1" in result

    def test_with_recovery_commands(self):
        result = _build_error_message("base", recovery_commands=["cmd1"])
        assert "Recovery commands:" in result

    def test_with_troubleshooting_steps(self):
        result = _build_error_message("base", troubleshooting_steps=["step1", "step2"])
        assert "Troubleshooting steps:" in result
        assert "1." in result
        assert "2." in result

    def test_all_sections(self):
        result = _build_error_message(
            "base",
            suggested_fix="fix",
            help_url="url",
            valid_examples=["ex"],
            recovery_commands=["cmd"],
            troubleshooting_steps=["step"],
        )
        assert "base" in result
        assert "Suggested fix:" in result
        assert "More help:" in result
        assert "Valid examples:" in result
        assert "Recovery commands:" in result
        assert "Troubleshooting steps:" in result


class TestTunaCodeError:
    def test_is_exception(self):
        assert issubclass(TunaCodeError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(TunaCodeError):
            raise TunaCodeError("test")


class TestConfigurationError:
    def test_basic(self):
        err = ConfigurationError("bad config")
        assert "bad config" in str(err)

    def test_with_fix_and_url(self):
        err = ConfigurationError("bad", suggested_fix="fix", help_url="url")
        assert err.suggested_fix == "fix"
        assert err.help_url == "url"
        assert "Suggested fix:" in str(err)


class TestValidationError:
    def test_includes_prefix(self):
        err = ValidationError("bad input")
        assert "Validation failed:" in str(err)

    def test_with_examples(self):
        err = ValidationError("bad", valid_examples=["a", "b"])
        assert err.valid_examples == ["a", "b"]


class TestToolExecutionError:
    def test_includes_tool_name(self):
        err = ToolExecutionError("grep", "search failed")
        assert "grep" in str(err)
        assert "search failed" in str(err)

    def test_with_original_error(self):
        orig = ValueError("original")
        err = ToolExecutionError("bash", "failed", original_error=orig)
        assert err.original_error is orig

    def test_with_recovery_commands(self):
        err = ToolExecutionError("bash", "failed", recovery_commands=["try again"])
        assert err.recovery_commands == ["try again"]


class TestAgentError:
    def test_includes_prefix(self):
        err = AgentError("something broke")
        assert "Agent error:" in str(err)

    def test_with_troubleshooting(self):
        err = AgentError("broke", troubleshooting_steps=["step1"])
        assert err.troubleshooting_steps == ["step1"]


class TestGitOperationError:
    def test_format(self):
        err = GitOperationError("push", "remote rejected")
        assert "Git push failed" in str(err)
        assert err.operation == "push"


class TestFileOperationError:
    def test_format(self):
        err = FileOperationError("read", "/path/file.txt", "permission denied")
        assert "File read failed" in str(err)
        assert "/path/file.txt" in str(err)
        assert err.path == "/path/file.txt"


class TestModelConfigurationError:
    def test_basic(self):
        err = ModelConfigurationError("gpt-5", "not found")
        assert "gpt-5" in str(err)
        assert err.model == "gpt-5"

    def test_with_valid_models(self):
        err = ModelConfigurationError("gpt-5", "not found", valid_models=["gpt-4", "gpt-3.5"])
        assert err.valid_models == ["gpt-4", "gpt-3.5"]


class TestSetupValidationError:
    def test_basic(self):
        err = SetupValidationError("API", "missing key")
        assert "API validation failed" in str(err)

    def test_with_quick_fixes(self):
        err = SetupValidationError("API", "issue", quick_fixes=["set API key"])
        assert err.quick_fixes == ["set API key"]


class TestTooBroadPatternError:
    def test_format(self):
        err = TooBroadPatternError(".*", 3.0)
        assert err.pattern == ".*"
        assert err.timeout_seconds == 3.0
        assert "too broad" in str(err)


class TestGlobalRequestTimeoutError:
    def test_format(self):
        err = GlobalRequestTimeoutError(120.0)
        assert err.timeout_seconds == 120.0
        assert "120.0s" in str(err)


class TestToolBatchingJSONError:
    def test_short_content(self):
        err = ToolBatchingJSONError('{"a": 1}', 3)
        assert err.retry_count == 3
        assert '{"a": 1}' in str(err)

    def test_truncates_long_content(self):
        long_json = "x" * (JSON_TRUNCATION_LIMIT + 1)
        err = ToolBatchingJSONError(long_json, 2)
        assert "..." in str(err)


class TestToolRetryError:
    def test_basic(self):
        err = ToolRetryError("retry hint")
        assert str(err) == "retry hint"

    def test_with_original(self):
        orig = ValueError("orig")
        err = ToolRetryError("hint", original_error=orig)
        assert err.original_error is orig


class TestAggregateToolError:
    def test_lists_failed_tools(self):
        failures = [("bash", ValueError("e1")), ("grep", RuntimeError("e2"))]
        err = AggregateToolError(failures)
        assert "bash" in str(err)
        assert "grep" in str(err)
        assert len(err.failures) == 2


class TestUserAbortError:
    def test_is_tunacode_error(self):
        assert issubclass(UserAbortError, TunaCodeError)


class TestStateError:
    def test_is_tunacode_error(self):
        assert issubclass(StateError, TunaCodeError)
