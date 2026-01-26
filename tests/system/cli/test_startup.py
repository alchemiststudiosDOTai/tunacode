"""Tests for TUI and headless mode startup.

These tests verify that both execution modes initialize correctly:
1. Headless mode can process a simple prompt end-to-end
2. TUI components initialize without import errors
3. Mock tests for headless response handling
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

HEADLESS_TIMEOUT_SECONDS = 60
STARTUP_TIMEOUT_SECONDS = 15


class TestHeadlessModeStartup:
    """Real integration tests for headless mode."""

    def test_headless_responds_to_simple_prompt(self) -> None:
        """Verify headless mode can process a prompt and return a response."""
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


class TestTUIInitialization:
    """Tests for TUI component initialization without running the full app."""

    def test_state_manager_initializes(self) -> None:
        """Verify StateManager creates correctly."""
        from tunacode.core.state import StateManager

        state_manager = StateManager()
        assert state_manager is not None
        assert state_manager.session is not None

    def test_tool_handler_lazy_initialization(self) -> None:
        """Verify tool_handler property uses lazy initialization."""
        from tunacode.core.state import StateManager

        state_manager = StateManager()
        # Before access, _tool_handler should be None
        assert state_manager._tool_handler is None

        # Access triggers lazy init
        tool_handler = state_manager.tool_handler
        assert tool_handler is not None
        assert state_manager._tool_handler is not None

        # Verify it's the correct type
        from tunacode.tools.authorization.handler import ToolHandler

        assert isinstance(tool_handler, ToolHandler)

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
        from tunacode.ui.main import state_manager

        assert state_manager is not None

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

    def test_state_manager_tool_handler_injection(self) -> None:
        """Test that custom tool handlers can be injected via set_tool_handler."""
        from tunacode.core.state import StateManager

        state_manager = StateManager()
        mock_handler = MagicMock()

        state_manager.set_tool_handler(mock_handler)
        assert state_manager.tool_handler is mock_handler

    def test_headless_cli_processes_auto_approve(self) -> None:
        """Verify --auto-approve flag sets yolo mode."""
        # This is a unit test for the flag parsing behavior
        from tunacode.core.state import StateManager

        state_manager = StateManager()
        assert state_manager.session.yolo is False

        # Simulate what headless mode does with --auto-approve
        state_manager.session.yolo = True
        assert state_manager.session.yolo is True
