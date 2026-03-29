"""Tests for TUI and headless mode startup.

These tests verify that both execution modes initialize correctly:
1. Headless mode can process a simple prompt end-to-end
2. TUI components initialize without import errors
3. Mock tests for headless response handling
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tinyagent.agent_types import AssistantMessage, TextContent, ToolCallContent, UserMessage
from typer.testing import CliRunner

HEADLESS_TIMEOUT_SECONDS = 60
STARTUP_TIMEOUT_SECONDS = 15


def _build_invalid_config_env(tmp_path: Path) -> dict[str, str]:
    """Create an environment that points TunaCode at a malformed config file."""
    home_dir = tmp_path / "home"
    config_dir = home_dir / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "tunacode.json").write_text(
        json.dumps({"settings": {"lsp": {"timeout": "oops"}}}),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(config_dir)
    return env


class TestHeadlessModeStartup:
    """Tests for headless mode CLI startup."""

    def test_headless_responds_to_simple_prompt_mocked(self) -> None:
        """Verify headless mode CLI plumbing works with mocked agent."""
        from tunacode.ui.main import app

        runner = CliRunner()

        # Create a mock agent run with a result
        mock_agent_run = MagicMock()
        mock_agent_run.result = "gm! Good morning to you too!"

        # Patch at the source module since import happens inside the function
        with patch(
            "tunacode.core.agents.main.process_request",
            new_callable=AsyncMock,
            return_value=mock_agent_run,
        ):
            result = runner.invoke(
                app,
                ["run", "say gm", "--auto-approve", "--timeout", "30"],
            )

        assert result.exit_code == 0, f"stderr: {result.output}"
        assert "gm" in result.output.lower() or "good morning" in result.output.lower()

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("TUNACODE_TEST_API_KEY"),
        reason="Requires TUNACODE_TEST_API_KEY for real API integration tests",
    )
    def test_headless_responds_to_simple_prompt_real(self) -> None:
        """Verify headless mode can process a prompt with real API (integration test)."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "tunacode",
                "run",
                "say gm",
                "--auto-approve",
                "--timeout",
                "30",
            ],
            capture_output=True,
            text=True,
            timeout=HEADLESS_TIMEOUT_SECONDS,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Agent should respond with something containing "gm"
        assert "gm" in result.stdout.lower() or "good morning" in result.stdout.lower()

    def test_headless_version_flag(self) -> None:
        """Verify --version works without starting the agent."""
        result = subprocess.run(
            ["uv", "run", "tunacode", "--version"],
            capture_output=True,
            text=True,
            timeout=STARTUP_TIMEOUT_SECONDS,
        )
        assert result.returncode == 0
        assert "tunacode" in result.stdout.lower()

    def test_headless_help_flag(self) -> None:
        """Verify --help works without starting the agent."""
        result = subprocess.run(
            ["uv", "run", "tunacode", "--help"],
            capture_output=True,
            text=True,
            timeout=STARTUP_TIMEOUT_SECONDS,
        )
        assert result.returncode == 0
        assert "TunaCode" in result.stdout

    def test_headless_version_flag_with_invalid_config(self, tmp_path: Path) -> None:
        """Verify --version bypasses malformed config files."""
        result = subprocess.run(
            ["uv", "run", "tunacode", "--version"],
            capture_output=True,
            text=True,
            timeout=STARTUP_TIMEOUT_SECONDS,
            env=_build_invalid_config_env(tmp_path),
        )
        assert result.returncode == 0
        assert "tunacode" in result.stdout.lower()
        assert "Traceback" not in result.stderr

    def test_headless_help_flag_with_invalid_config(self, tmp_path: Path) -> None:
        """Verify --help bypasses malformed config files."""
        result = subprocess.run(
            ["uv", "run", "tunacode", "--help"],
            capture_output=True,
            text=True,
            timeout=STARTUP_TIMEOUT_SECONDS,
            env=_build_invalid_config_env(tmp_path),
        )
        assert result.returncode == 0
        assert "TunaCode" in result.stdout
        assert "Traceback" not in result.stderr

    def test_headless_run_reports_invalid_config_cleanly(self, tmp_path: Path) -> None:
        """Verify runtime commands fail cleanly after parsing malformed config."""
        result = subprocess.run(
            ["uv", "run", "tunacode", "run", "say gm", "--timeout", "30"],
            capture_output=True,
            text=True,
            timeout=STARTUP_TIMEOUT_SECONDS,
            env=_build_invalid_config_env(tmp_path),
        )
        assert result.returncode == 1
        assert "Invalid user config" in result.stderr
        assert "Traceback" not in result.stderr

    def test_headless_output_json_serializes_tinyagent_messages(self) -> None:
        """Verify --output-json serializes the in-memory tinyagent message models."""
        from tunacode.core.session import StateManager

        from tunacode.ui.main import app

        runner = CliRunner()
        isolated_state_manager = StateManager()

        async def _mock_process_request(*, state_manager: StateManager, **_: object) -> MagicMock:
            state_manager.session.conversation.messages = [
                UserMessage(content=[TextContent(text="say gm")]),
                AssistantMessage(content=[TextContent(text="gm!")]),
            ]
            state_manager.session.runtime.tool_registry.register(
                "call_1",
                "bash",
                {"cmd": "pwd"},
            )
            usage = state_manager.session.usage.session_total_usage
            usage.input = 11
            usage.output = 7
            usage.total_tokens = 18
            usage.cost.input = 0.11
            usage.cost.output = 0.07
            usage.cost.total = 0.18

            mock_agent_run = MagicMock()
            mock_agent_run.result = "ignored in JSON mode"
            return mock_agent_run

        with (
            patch("tunacode.ui.main.state_manager", isolated_state_manager),
            patch(
                "tunacode.core.agents.main.process_request",
                new_callable=AsyncMock,
                side_effect=_mock_process_request,
            ),
        ):
            result = runner.invoke(
                app,
                ["run", "say gm", "--auto-approve", "--output-json", "--timeout", "30"],
            )

        assert result.exit_code == 0, f"stderr: {result.output}"
        payload = json.loads(result.output)

        assert payload["success"] is True
        assert payload["messages"] == [
            {"role": "user", "content": [{"type": "text", "text": "say gm"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "gm!"}]},
        ]
        assert payload["tool_calls"] == [
            {
                "tool": "bash",
                "args": {"cmd": "pwd"},
                "timestamp": None,
                "tool_call_id": "call_1",
            }
        ]
        assert payload["usage"] == {
            "input": 11,
            "output": 7,
            "cache_read": 0,
            "cache_write": 0,
            "total_tokens": 18,
            "cost": {
                "input": 0.11,
                "output": 0.07,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "total": 0.18,
            },
        }


class TestTUIInitialization:
    """Tests for TUI component initialization without running the full app."""

    def test_state_manager_initializes(self) -> None:
        """Verify StateManager creates correctly."""
        from tunacode.core.session import StateManager

        state_manager = StateManager()
        assert state_manager is not None
        assert state_manager.session is not None

    def test_ui_main_imports_without_tools_layer(self) -> None:
        """Verify ui/main.py has no direct imports from tunacode.tools."""
        import tunacode.ui.main as main_module

        source = Path(main_module.__file__).read_text()
        assert "from tunacode.tools" not in source, "ui/main.py should not import from tools layer"

    def test_ui_repl_support_imports_without_tools_layer(self) -> None:
        """Verify ui/repl_support.py has no direct imports from tunacode.tools."""
        import tunacode.ui.repl_support as repl_module

        source = Path(repl_module.__file__).read_text()
        assert "from tunacode.tools" not in source, (
            "ui/repl_support.py should not import from tools layer"
        )

    def test_tui_module_imports_cleanly(self) -> None:
        """Verify TUI modules import without errors."""
        # These imports would fail if there were circular dependencies
        import tunacode.ui.main as main_module

        assert main_module.state_manager is None

        from tunacode.ui.repl_support import build_textual_tool_callback

        assert callable(build_textual_tool_callback)


class TestHeadlessModeMocked:
    """Mock tests for headless mode response handling."""

    def test_headless_output_resolution(self) -> None:
        """Test that headless output resolver extracts text correctly."""
        from tunacode.ui.headless import resolve_output

        # Mock an agent run result - resolve_output looks for .result attribute
        mock_run = MagicMock()
        mock_run.result = "Test response data"

        # Mock messages list (empty for simple case)
        messages: list = []

        result = resolve_output(mock_run, messages)
        assert result == "Test response data"

    def test_headless_output_with_none_result(self) -> None:
        """Test headless output when agent returns None."""
        from tunacode.ui.headless import resolve_output

        mock_run = MagicMock()
        mock_run.result = None

        messages: list = []
        result = resolve_output(mock_run, messages)
        # Should return None or handle gracefully
        assert result is None

    def test_headless_output_falls_back_to_latest_assistant_message(self) -> None:
        """Test headless output fallback reads assistant messages from history."""
        from tunacode.ui.headless import resolve_output

        mock_run = MagicMock()
        mock_run.result = None

        messages: list = [
            UserMessage(content=[TextContent(text="Hi")]),
            AssistantMessage(content=[TextContent(text="  Hello there  ")]),
        ]

        result = resolve_output(mock_run, messages)
        assert result == "Hello there"

    def test_headless_output_skips_tool_call_only_assistant_message(self) -> None:
        """Tool-call-only assistant messages should not become headless output."""
        from tunacode.ui.headless import resolve_output

        mock_run = MagicMock()
        mock_run.result = None

        messages: list = [
            AssistantMessage(content=[TextContent(text="First response")]),
            AssistantMessage(
                content=[
                    ToolCallContent(
                        id="call_1",
                        name="bash",
                        arguments={"cmd": "echo hi"},
                    )
                ]
            ),
        ]

        result = resolve_output(mock_run, messages)
        assert result == "First response"
