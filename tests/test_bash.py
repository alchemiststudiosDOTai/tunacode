"""Tests for the shell tool."""

from pathlib import Path

import pytest
from inline_snapshot import snapshot
from kosong.tooling import ToolError, ToolOk

from kimi_cli.tools.bash import Bash, Params
from kimi_cli.tools.utils import DEFAULT_MAX_CHARS


@pytest.mark.asyncio
async def test_simple_command(bash_tool: Bash):
    """Test executing a simple command."""
    result = await bash_tool(Params(command="echo 'Hello World'"))
    assert result == snapshot(
        ToolOk(output="Hello World\n", message="Command executed successfully.")
    )


@pytest.mark.asyncio
async def test_command_with_error(bash_tool: Bash):
    """Test executing a command that returns an error."""
    result = await bash_tool(Params(command="ls /nonexistent/directory"))
    assert isinstance(result, ToolError)
    assert "No such file or directory" in result.output
    assert "Command failed with exit code:" in result.message
    assert "Failed with exit code:" in result.brief


@pytest.mark.asyncio
async def test_command_chaining(bash_tool: Bash):
    """Test command chaining with &&."""
    result = await bash_tool(Params(command="echo 'First' && echo 'Second'"))
    assert result == snapshot(
        ToolOk(
            output="""\
First
Second
""",
            message="Command executed successfully.",
        )
    )


@pytest.mark.asyncio
async def test_command_sequential(bash_tool: Bash):
    """Test sequential command execution with ;."""
    result = await bash_tool(Params(command="echo 'One'; echo 'Two'"))
    assert result == snapshot(
        ToolOk(
            output="""\
One
Two
""",
            message="Command executed successfully.",
        )
    )


@pytest.mark.asyncio
async def test_command_conditional(bash_tool: Bash):
    """Test conditional command execution with ||."""
    result = await bash_tool(Params(command="false || echo 'Success'"))
    assert result == snapshot(ToolOk(output="Success\n", message="Command executed successfully."))


@pytest.mark.asyncio
async def test_command_pipe(bash_tool: Bash):
    """Test command piping."""
    result = await bash_tool(Params(command="echo 'Hello World' | wc -w"))
    assert isinstance(result, ToolOk)
    assert isinstance(result.output, str)
    assert result.output.strip() == snapshot("2")


@pytest.mark.asyncio
async def test_multiple_pipes(bash_tool: Bash):
    """Test multiple pipes in one command."""
    result = await bash_tool(Params(command="echo -e '1\\n2\\n3' | grep '2' | wc -l"))
    assert isinstance(result, ToolOk)
    assert isinstance(result.output, str)
    assert result.output.strip() == snapshot("1")


@pytest.mark.asyncio
async def test_command_with_timeout(bash_tool: Bash):
    """Test command execution with timeout."""
    result = await bash_tool(Params(command="sleep 0.1", timeout=1))
    assert result == snapshot(ToolOk(output="", message="Command executed successfully."))


@pytest.mark.asyncio
async def test_command_timeout_expires(bash_tool: Bash):
    """Test command that times out."""
    result = await bash_tool(Params(command="sleep 2", timeout=1))
    assert result == snapshot(
        ToolError(message="Command killed by timeout (1s)", brief="Killed by timeout (1s)")
    )


@pytest.mark.asyncio
async def test_environment_variables(bash_tool: Bash):
    """Test setting and using environment variables."""
    result = await bash_tool(Params(command="export TEST_VAR='test_value' && echo $TEST_VAR"))
    assert result == snapshot(
        ToolOk(output="test_value\n", message="Command executed successfully.")
    )


@pytest.mark.asyncio
async def test_file_operations(bash_tool: Bash, temp_work_dir: Path):
    """Test basic file operations."""
    # Create a test file
    result = await bash_tool(Params(command=f"echo 'Test content' > {temp_work_dir}/test_file.txt"))
    assert result == snapshot(ToolOk(output="", message="Command executed successfully."))

    # Read the file
    result = await bash_tool(Params(command=f"cat {temp_work_dir}/test_file.txt"))
    assert result == snapshot(
        ToolOk(output="Test content\n", message="Command executed successfully.")
    )


@pytest.mark.asyncio
async def test_text_processing(bash_tool: Bash):
    """Test text processing commands."""
    result = await bash_tool(Params(command="echo 'apple banana cherry' | sed 's/banana/orange/'"))
    assert result == snapshot(
        ToolOk(output="apple orange cherry\n", message="Command executed successfully.")
    )


@pytest.mark.asyncio
async def test_command_substitution(bash_tool: Bash):
    """Test command substitution with a portable command."""
    result = await bash_tool(Params(command='echo "Result: $(echo hello)"'))
    assert result == snapshot(
        ToolOk(output="Result: hello\n", message="Command executed successfully.")
    )


@pytest.mark.asyncio
async def test_arithmetic_substitution(bash_tool: Bash):
    """Test arithmetic substitution - more portable than date command."""
    result = await bash_tool(Params(command='echo "Answer: $((2 + 2))"'))
    assert result == snapshot(
        ToolOk(output="Answer: 4\n", message="Command executed successfully.")
    )


@pytest.mark.asyncio
async def test_very_long_output(bash_tool: Bash):
    """Test command that produces very long output."""
    result = await bash_tool(Params(command="seq 1 100 | head -50"))

    assert isinstance(result, ToolOk)
    assert isinstance(result.output, str)
    assert "1" in result.output
    assert "50" in result.output
    assert "51" not in result.output  # Should not contain 51


@pytest.mark.asyncio
async def test_output_truncation_on_success(bash_tool: Bash):
    """Test that very long output gets truncated on successful command."""
    # Generate output longer than MAX_OUTPUT_LENGTH
    oversize_length = DEFAULT_MAX_CHARS + 1000
    result = await bash_tool(Params(command=f"python3 -c \"print('X' * {oversize_length})\""))

    assert isinstance(result, ToolOk)
    assert isinstance(result.output, str)
    # Check if output was truncated (it should be)
    if len(result.output) > DEFAULT_MAX_CHARS:
        assert result.output.endswith("[...truncated]\n")
        assert "Output is truncated" in result.message
    assert "Command executed successfully" in result.message


@pytest.mark.asyncio
async def test_output_truncation_on_failure(bash_tool: Bash):
    """Test that very long output gets truncated even when command fails."""
    # Generate long output with a command that will fail
    result = await bash_tool(
        Params(command="python3 -c \"import sys; print('ERROR_' * 8000); sys.exit(1)\"")
    )

    assert isinstance(result, ToolError)
    assert isinstance(result.output, str)
    # Check if output was truncated
    if len(result.output) > DEFAULT_MAX_CHARS:
        assert result.output.endswith("[...truncated]\n")
        assert "Output is truncated" in result.message
    assert "Command failed with exit code:" in result.message


@pytest.mark.asyncio
async def test_timeout_parameter_validation_bounds(bash_tool: Bash):
    """Test timeout parameter validation (bounds checking)."""
    # Test timeout < 1 (should fail validation)
    with pytest.raises(ValueError, match="timeout"):
        Params(command="echo test", timeout=0)

    with pytest.raises(ValueError, match="timeout"):
        Params(command="echo test", timeout=-1)

    # Test timeout > MAX_TIMEOUT (should fail validation)
    from kimi_cli.tools.bash import MAX_TIMEOUT

    with pytest.raises(ValueError, match="timeout"):
        Params(command="echo test", timeout=MAX_TIMEOUT + 1)


# ========== Persistent Mode Tests ==========


@pytest.mark.asyncio
async def test_persistent_mode_simple_command(bash_tool_persistent: Bash):
    """Test simple command in persistent mode."""
    result = await bash_tool_persistent(Params(command="echo 'Persistent Mode'"))
    assert isinstance(result, ToolOk)
    assert "Persistent Mode" in result.output


@pytest.mark.asyncio
async def test_persistent_mode_working_directory_persists(bash_tool_persistent: Bash):
    """Test that working directory persists across commands in persistent mode."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to temp directory
        result1 = await bash_tool_persistent(Params(command=f"cd {tmpdir}"))
        assert isinstance(result1, ToolOk)

        # Verify we're still in that directory
        result2 = await bash_tool_persistent(Params(command="pwd"))
        assert isinstance(result2, ToolOk)
        assert tmpdir in result2.output


@pytest.mark.asyncio
async def test_persistent_mode_environment_variable_persists(bash_tool_persistent: Bash):
    """Test that environment variables persist across commands in persistent mode."""
    # Set an environment variable
    result1 = await bash_tool_persistent(Params(command="export TEST_VAR=persistent_value"))
    assert isinstance(result1, ToolOk)

    # Verify the variable persists
    result2 = await bash_tool_persistent(Params(command="echo $TEST_VAR"))
    assert isinstance(result2, ToolOk)
    assert "persistent_value" in result2.output


@pytest.mark.asyncio
async def test_persistent_mode_exit_code_handling(bash_tool_persistent: Bash):
    """Test that exit codes are properly reported in persistent mode."""
    result = await bash_tool_persistent(Params(command="false"))
    assert isinstance(result, ToolError)
    assert "exit code: 1" in result.message


@pytest.mark.asyncio
async def test_persistent_mode_timeout(bash_tool_persistent: Bash):
    """Test timeout handling in persistent mode."""
    result = await bash_tool_persistent(Params(command="sleep 10", timeout=1))
    assert isinstance(result, ToolError)
    assert "timeout" in result.message.lower()


@pytest.mark.asyncio
async def test_mode_fallback_on_error():
    """Test fallback to ephemeral mode when persistent shell fails."""
    from kimi_cli.config import PersistentShellConfig
    from kimi_cli.shell_manager import ShellManager
    from kimi_cli.soul.approval import Approval
    from tests.conftest import tool_call_context

    # Create a shell manager that will fail
    config = PersistentShellConfig(enabled=True, shell_executable="/nonexistent/shell")
    broken_manager = ShellManager(config)
    approval = Approval(yolo=True)

    with tool_call_context("Bash"):
        bash = Bash(approval, shell_manager=broken_manager)

        # First command should fail and fall back to ephemeral
        result = await bash(Params(command="echo 'fallback test'"))
        assert isinstance(result, ToolOk)
        assert "fallback test" in result.output

        # Verify shell_manager was disabled
        assert bash._shell_manager is None
