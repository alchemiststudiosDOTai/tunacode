"""
Characterization tests for commands.py

These tests aim to capture and document the current behavior of the commands module, providing a safety net for future refactoring.
"""

# Provide a minimal stub for defusedxml if not installed, to avoid import errors
import sys
import types
from unittest import mock

import pytest

if "defusedxml" not in sys.modules:
    _defusedxml = types.ModuleType("defusedxml")
    _etree = types.ModuleType("ElementTree")

    def _stub_parse(_path: str):  # minimal interface used by ReactTool
        class _Tree:
            def getroot(self):
                class _Root:
                    def find(self, _name: str):
                        return None

                    def findall(self, _name: str):
                        return []

                return _Root()

        return _Tree()

    _etree.parse = _stub_parse  # type: ignore[attr-defined]
    _defusedxml.ElementTree = _etree  # type: ignore[attr-defined]
    sys.modules["defusedxml"] = _defusedxml
    sys.modules["defusedxml.ElementTree"] = _etree

from tunacode.cli import commands


# Example: Test CommandFactory creation and dependency injection
class TestCommandFactory:
    def test_create_command_default(self):
        factory = commands.CommandFactory()
        # Should create a YoloCommand instance with no error
        cmd = factory.create_command(commands.YoloCommand)
        assert isinstance(cmd, commands.YoloCommand)

    def test_update_dependencies(self):
        factory = commands.CommandFactory()
        factory.update_dependencies(process_request_callback=lambda x: x)
        assert callable(factory.dependencies.process_request_callback)

    def test_create_command_with_dependencies(self):
        factory = commands.CommandFactory()
        factory.update_dependencies(process_request_callback=lambda x: x)
        cmd = factory.create_command(commands.CompactCommand)
        assert isinstance(cmd, commands.CompactCommand)


# Example: Test CommandRegistry registration and lookup
class TestCommandRegistry:
    def test_register_and_lookup(self):
        registry = commands.CommandRegistry()
        cmd = commands.YoloCommand()
        registry.register(cmd)
        # Current behavior: is_command converts input to lowercase,
        # but primary name is registered as-is, so "yolo" should match
        assert registry.is_command("yolo")
        # But aliases are registered in lowercase
        for alias in cmd.aliases:
            assert registry.is_command(alias.lower())

    def test_find_matching_commands(self):
        registry = commands.CommandRegistry()
        cmd = commands.YoloCommand()
        registry.register(cmd)
        matches = registry.find_matching_commands("yo")
        assert "yolo" in matches

    def test_auto_discover_commands(self):
        registry = commands.CommandRegistry()
        registry.discover_commands()
        # Should discover all command classes
        assert registry.is_command("help")
        assert registry.is_command("model")
        assert registry.is_command("clear")
        assert registry.is_command("yolo")
        assert registry.is_command("branch")
        assert registry.is_command("update")
        assert registry.is_command("thoughts")


# Test individual command behaviors
@pytest.mark.asyncio
class TestCommandBehaviors:
    async def test_model_command_no_args(self, capsys):
        """Test ModelCommand with no arguments shows current model."""
        cmd = commands.ModelCommand()
        # CLAUDE_ANCHOR[model-command-registry-validation-skip]
        # Pydantic validation in ModelsRegistry may reject cached API entries (e.g., zero limits).
        # For characterization, we skip live registry loading to avoid brittle cache/network coupling.
        # This preserves the intent: command prints current model info when invoked with no args.
        cmd._registry_loaded = True
        context = mock.Mock()
        context.state_manager.session.current_model = "openai:gpt-4"

        # Mock the UI info function to capture output
        with mock.patch("tunacode.ui.console.info") as mock_info:
            await cmd.execute([], context)
            # Check that info was called with the current model
            mock_info.assert_called()

    async def test_model_command_switch_model(self, capsys):
        """Test ModelCommand switching to new model."""
        cmd = commands.ModelCommand()
        context = mock.Mock()
        context.state_manager.session.current_model = "openai:gpt-3.5"
        # Ensure user_config is a real dict to support persistence
        context.state_manager.session.user_config = {}

        # Mock the models registry to avoid network calls and provide predictable results
        mock_registry = mock.Mock()
        mock_registry.get_model.return_value = None  # Model not found in registry
        mock_registry.search_models.return_value = []  # No similar models
        cmd.registry = mock_registry
        cmd._registry_loaded = True

        # Mock UI functions and stub out config save to avoid real IO
        with (
            mock.patch("tunacode.ui.console.warning") as mock_warning,
            mock.patch("tunacode.utils.user_configuration.save_config", return_value=True),
        ):
            result = await cmd.execute(["anthropic:claude-3.5-sonnet"], context)

        # Model should be updated even if not found in registry (with warning)
        assert context.state_manager.session.current_model == "anthropic:claude-3.5-sonnet"
        assert result is None  # No restart needed
        mock_warning.assert_called_with("Model not found in registry - setting anyway")

    async def test_model_command_search_behavior(self, capsys):
        """Test ModelCommand treats non-colon input as search query."""
        cmd = commands.ModelCommand()
        context = mock.Mock()

        # Mock the models registry to simulate search behavior
        mock_registry = mock.Mock()
        mock_registry.search_models.return_value = []  # No models found
        cmd.registry = mock_registry
        cmd._registry_loaded = True

        # Mock UI functions
        with (
            mock.patch("tunacode.ui.console.error") as mock_error,
            mock.patch("tunacode.ui.console.muted") as mock_muted,
        ):
            result = await cmd.execute(["gpt-4"], context)  # No colon - treated as search

            # Check that it searches and shows "no models found" error
            mock_registry.search_models.assert_called_once_with("gpt-4")
            mock_error.assert_called_once_with("No models found matching 'gpt-4'")
            mock_muted.assert_called_once_with("Try /model --list to see all available models")
            assert result is None

    async def test_yolo_command(self):
        """Test YoloCommand toggles yolo mode."""
        cmd = commands.YoloCommand()
        context = mock.Mock()
        context.state_manager.session.yolo = False

        # Mock the UI functions
        with mock.patch("tunacode.ui.console.success"):
            with mock.patch("tunacode.ui.console.info"):
                await cmd.execute([], context)

        # Should toggle yolo mode
        assert context.state_manager.session.yolo

        # Toggle back
        with mock.patch("tunacode.ui.console.info"):
            await cmd.execute([], context)
        assert not context.state_manager.session.yolo

    async def test_clear_command(self):
        """Test ClearCommand clears message history."""
        cmd = commands.ClearCommand()
        context = mock.Mock()
        context.state_manager.session.messages = ["msg1", "msg2", "msg3"]

        # Mock the UI clear function
        with mock.patch("tunacode.ui.console.clear"):
            result = await cmd.execute([], context)

        # Should clear messages and command returns None
        assert context.state_manager.session.messages == []
        assert result is None

    async def test_branch_command_no_args(self, capsys):
        """Test BranchCommand with no arguments shows usage."""
        cmd = commands.BranchCommand()
        context = mock.Mock()

        # Mock the UI error function
        with mock.patch("tunacode.ui.console.error") as mock_error:
            await cmd.execute([], context)
            # Check that error was called with usage info
            mock_error.assert_called_once()
            assert "Usage:" in str(mock_error.call_args)
            assert "branch" in str(mock_error.call_args)

    async def test_thoughts_command_toggle(self):
        """Test ThoughtsCommand toggles show_thoughts."""
        cmd = commands.ThoughtsCommand()
        context = mock.Mock()
        context.state_manager.session.show_thoughts = False

        # Turn on
        await cmd.execute(["on"], context)
        assert context.state_manager.session.show_thoughts

        # Turn off
        await cmd.execute(["off"], context)
        assert not context.state_manager.session.show_thoughts

        # Toggle (no args)
        await cmd.execute([], context)
        assert context.state_manager.session.show_thoughts

    async def test_iterations_command_show_current(self, capsys):
        """Test IterationsCommand shows current iteration limit."""
        cmd = commands.IterationsCommand()
        context = mock.Mock()
        context.state_manager.session.user_config = {"settings": {"max_iterations": 20}}

        # Mock the UI info function
        with mock.patch("tunacode.ui.console.info") as mock_info:
            await cmd.execute([], context)
            # Check that info was called with the iteration limit
            mock_info.assert_called()
            assert "20" in str(mock_info.call_args)

    async def test_iterations_command_update(self):
        """Test IterationsCommand updates iteration limit."""
        cmd = commands.IterationsCommand()
        context = mock.Mock()
        context.state_manager.session.user_config = {"settings": {"max_iterations": 20}}

        result = await cmd.execute(["30"], context)

        # Should update the limit
        assert context.state_manager.session.user_config["settings"]["max_iterations"] == 30
        assert result is None

    async def test_help_command_shows_commands(self, capsys):
        """Test HelpCommand displays available commands."""
        registry = commands.CommandRegistry()
        registry.discover_commands()  # Changed from auto_discover to discover_commands

        cmd = commands.HelpCommand(registry)
        context = mock.Mock()

        await cmd.execute([], context)
        captured = capsys.readouterr()

        # Should display available commands table (uses rich box drawing)
        assert "Available Commands" in (captured.out + captured.err)
        # Verify some command names are present
        assert "/help" in (captured.out + captured.err)
        assert "/model" in (captured.out + captured.err)

    async def test_update_command_no_installation(self, capsys):
        """Test UpdateCommand when installation method not detected."""
        cmd = commands.UpdateCommand()
        context = mock.Mock()

        # Mock subprocess to simulate no installation found
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""

            # Mock the UI muted function to capture output
            with (
                mock.patch("tunacode.ui.console.muted") as mock_muted,
                mock.patch("tunacode.ui.console.error") as mock_error,
            ):
                await cmd.execute([], context)
                # One of the UI functions should have been called noting manual options
                output = "".join(
                    str(c) for c in (*mock_muted.call_args_list, *mock_error.call_args_list)
                )
                assert "pip" in output or "pipx" in output

    async def test_compact_command_callback(self):
        """Test CompactCommand with process callback."""
        callback = mock.AsyncMock()
        # Create a proper mock result structure
        mock_result = mock.Mock()
        mock_result.result = mock.Mock()
        mock_result.result.output = "Test summary of the conversation"
        callback.return_value = mock_result

        cmd = commands.CompactCommand(callback)
        context = mock.Mock()
        context.state_manager.session.messages = ["msg1", "msg2"]

        # Mock the UI functions
        with mock.patch("tunacode.ui.panels.panel"):
            with mock.patch("tunacode.ui.console.info"):
                with mock.patch("tunacode.ui.console.success"):
                    result = await cmd.execute([], context)

        # Should call the callback
        callback.assert_called_once()
        # Result is None, not "compact"
        assert result is None

    async def test_dump_command(self, capsys):
        """Test DumpCommand outputs state information."""
        cmd = commands.DumpCommand()
        context = mock.Mock()
        context.state_manager.session.messages = ["msg1", "msg2"]
        context.state_manager.session.current_model = "test-model"

        # Mock the UI dump_messages function
        with mock.patch("tunacode.ui.console.dump_messages") as mock_dump:
            await cmd.execute([], context)
            # Check that dump_messages was called with session.messages list
            mock_dump.assert_called_once_with(context.state_manager.session.messages)


# Test CommandSpec properties
class TestCommandSpec:
    def test_simple_command_properties(self):
        """Test that SimpleCommand correctly uses CommandSpec."""
        cmd = commands.YoloCommand()

        assert cmd.name == "yolo"
        assert "/yolo" in cmd.aliases
        assert cmd.category == commands.CommandCategory.DEVELOPMENT
        assert "confirmation" in cmd.description.lower()


# Test edge cases and error handling
@pytest.mark.asyncio
class TestCommandEdgeCases:
    async def test_branch_command_creates_branch(self):
        """Test BranchCommand creates git branch."""
        cmd = commands.BranchCommand()
        context = mock.Mock()

        with mock.patch("subprocess.run") as mock_run:
            # Simulate successful git commands
            mock_run.return_value.returncode = 0

            # Mock the UI success function
            with mock.patch("tunacode.ui.console.success"):
                result = await cmd.execute(["feature-branch"], context)

            # Should have called git checkout -b
            calls = mock_run.call_args_list
            assert any("checkout" in str(call) and "-b" in str(call) for call in calls)
            # BranchCommand returns None, not "restart"
            assert result is None

    async def test_fix_command_spawns_process(self):
        """Test FixCommand runs black formatter."""
        cmd = commands.FixCommand()
        context = mock.Mock()

        context.state_manager = mock.Mock()
        context.state_manager.session = mock.Mock()
        context.state_manager.session.messages = []

        # In current implementation FixCommand no longer formats with black; it only
        # patches orphaned tool messages and logs status. Verify it completes without
        # invoking subprocesses.
        with (
            mock.patch("subprocess.Popen") as mock_popen,
            mock.patch("tunacode.ui.console.info") as mock_info,
            mock.patch("tunacode.ui.console.success") as mock_success,
        ):
            await cmd.execute([], context)

            # Ensure no subprocess was spawned
            mock_popen.assert_not_called()
            # One of the UI functions should have been called to inform the user
            assert mock_info.called or mock_success.called


# Note: These are characterization tests. If you change the underlying implementation and these tests fail, update the tests only if you intend to change the behavior!
