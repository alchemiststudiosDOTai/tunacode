"""
Test search functionality including parallel grep and architect mode search.

Tests cover:
- Basic grep search patterns
- Architect mode bash command conversion
- Multiple file extension support
- Parallel execution and performance
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.core.agents.adaptive_orchestrator import AdaptiveOrchestrator
from tunacode.core.agents.context_provider import ContextProvider
from tunacode.core.agents.parallel_executor import ParallelExecutor, ParallelTaskResult
from tunacode.core.state import SessionState, StateManager
from tunacode.tools.grep import ParallelGrep
from tunacode.types import ModelName


class TestParallelGrepSearch:
    """Test the parallel grep tool functionality."""

    @pytest.fixture
    def grep_tool(self):
        """Create a ParallelGrep instance."""
        return ParallelGrep()

    @pytest.fixture
    def test_files(self, tmp_path):
        """Create test files for searching."""
        # Create Python files
        (tmp_path / "repl.py").write_text("""
# REPL implementation
class REPL:
    def __init__(self):
        self.prompt = ">>> "
    
    def run(self):
        print("Starting REPL...")
""")
        
        (tmp_path / "architect.py").write_text("""
# Architect mode implementation
def architect_mode():
    print("Enabling architect mode")
    return True
""")
        
        (tmp_path / "utils.py").write_text("""
# Utility functions
def find_repl():
    return "repl.py"
    
def search_files(pattern):
    # Search for pattern in files
    pass
""")
        
        # Create JavaScript file
        (tmp_path / "app.js").write_text("""
// JavaScript REPL
function startREPL() {
    console.log("REPL started");
}
""")
        
        # Create subdirectory with more files
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "core.py").write_text("""
# Core functionality
REPL_VERSION = "1.0"
ARCHITECT_ENABLED = True
""")
        
        return tmp_path

    @pytest.mark.asyncio
    async def test_basic_grep_search(self, grep_tool, test_files):
        """Test basic literal string search."""
        # Search for "REPL" in Python files
        result = await grep_tool._execute(
            pattern="REPL",
            directory=str(test_files),
            include_files="*.py"
        )
        
        assert "repl.py" in result
        assert "REPL implementation" in result
        assert "class REPL" in result  # Remove the colon as it might be highlighted differently
        assert "core.py" in result
        assert "REPL_VERSION" in result
        
        # Should not include JS files
        assert "app.js" not in result

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, grep_tool, test_files):
        """Test case-insensitive search."""
        # Search for "repl" (lowercase) should find "REPL" (uppercase)
        result = await grep_tool._execute(
            pattern="repl",
            directory=str(test_files),
            include_files="*.py",
            case_sensitive=False
        )
        
        assert "repl.py" in result
        assert "REPL" in result  # Should find uppercase matches
        assert "find_repl" in result  # Should find lowercase matches

    @pytest.mark.asyncio
    async def test_regex_search(self, grep_tool, test_files):
        """Test regex pattern search."""
        # Search for functions/methods
        result = await grep_tool._execute(
            pattern=r"def\s+\w+\(",
            directory=str(test_files),
            include_files="*.py",
            use_regex=True
        )
        
        assert "def __init__" in result
        assert "def run" in result
        assert "def architect_mode" in result
        assert "def find_repl" in result
        assert "def search_files" in result

    @pytest.mark.asyncio
    async def test_multiple_extension_search(self, grep_tool, test_files):
        """Test searching across multiple file extensions."""
        # Test comma-separated extensions (should be converted to brace format)
        result = await grep_tool._execute(
            pattern="REPL",
            directory=str(test_files),
            include_files="*.py,*.js"
        )
        
        assert "repl.py" in result
        assert "app.js" in result
        assert "JavaScript REPL" in result
        assert "REPL implementation" in result

    @pytest.mark.asyncio
    async def test_search_strategies(self, grep_tool, test_files):
        """Test different search strategies."""
        strategies = ["python", "ripgrep", "smart"]
        
        for strategy in strategies:
            result = await grep_tool._execute(
                pattern="architect",
                directory=str(test_files),
                include_files="*.py",
                search_type=strategy
            )
            
            # All strategies should find the pattern
            assert "architect.py" in result
            assert "architect_mode" in result
            
            # Verify strategy is mentioned in output
            if strategy != "smart":  # Smart auto-selects
                assert f"Strategy: {strategy}" in result

    @pytest.mark.asyncio
    async def test_context_lines(self, grep_tool, test_files):
        """Test context lines in search results."""
        result = await grep_tool._execute(
            pattern="architect_mode",
            directory=str(test_files),
            include_files="*.py",
            context_lines=2
        )
        
        # Should include context around the match
        assert "Architect mode implementation" in result  # Comment above
        assert "print(" in result  # Line below
        assert "return True" in result  # Second line below

    @pytest.mark.asyncio
    async def test_max_results_limit(self, grep_tool, test_files):
        """Test max_results parameter."""
        # Create many matches
        for i in range(10):
            (test_files / f"test{i}.py").write_text(f"# File {i}\nREPL test\n")
        
        result = await grep_tool._execute(
            pattern="REPL",
            directory=str(test_files),
            include_files="*.py",
            max_results=5
        )
        
        # Count matches in result
        match_count = result.count("📁")  # File headers in output
        assert match_count <= 5


class TestArchitectModeSearch:
    """Test architect mode search functionality."""

    @pytest.fixture
    def state_manager(self):
        """Create a mock state manager."""
        state = StateManager()
        state.session.current_model = ModelName("openai:gpt-4")
        state.session.files_in_context = set()
        state.session.tool_calls = []
        state.session.messages = []
        return state

    @pytest.fixture
    def orchestrator(self, state_manager):
        """Create an AdaptiveOrchestrator instance."""
        return AdaptiveOrchestrator(state_manager)

    @pytest.fixture
    def context_provider(self, tmp_path):
        """Create a ContextProvider instance."""
        return ContextProvider(tmp_path)

    @pytest.fixture
    def parallel_executor(self, context_provider):
        """Create a ParallelExecutor instance."""
        return ParallelExecutor(context_provider)

    @pytest.mark.asyncio
    async def test_bash_find_command_conversion(self, parallel_executor):
        """Test conversion of bash find commands to grep."""
        # Test find command with -name
        task = {
            "id": "1",
            "tool": "bash",
            "args": {"command": "find . -name '*.py'"},
            "description": "Find Python files"
        }
        
        with patch.object(ParallelGrep, '_execute') as mock_execute:
            mock_execute.return_value = "repl.py\narchitect.py\n"
            
            results = await parallel_executor._execute_generic_batch([task])
            
            assert len(results) == 1
            result = results[0]
            assert result.success
            assert "repl.py" in result.result["output"]
            assert "architect.py" in result.result["output"]
            
            # Verify grep was called with correct parameters
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[1]
            assert call_args["pattern"] == ""  # Empty pattern for filename matching
            assert call_args["include_files"] == "*.py"

    @pytest.mark.asyncio
    async def test_bash_find_case_insensitive(self, parallel_executor):
        """Test conversion of case-insensitive find commands."""
        task = {
            "id": "1",
            "tool": "bash",
            "args": {"command": "find . -iname '*repl*'"},
            "description": "Find files with 'repl' in name"
        }
        
        with patch.object(ParallelGrep, '_execute') as mock_execute:
            mock_execute.return_value = "REPL.py\nrepl_utils.py\n"
            
            results = await parallel_executor._execute_generic_batch([task])
            
            assert len(results) == 1
            result = results[0]
            assert result.success
            
            # Verify case_sensitive was set to False
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[1]
            assert call_args["case_sensitive"] is False
            assert call_args["include_files"] == "*repl*"

    @pytest.mark.asyncio
    async def test_bash_ls_command_conversion(self, parallel_executor):
        """Test conversion of ls commands to list_dir."""
        task = {
            "id": "1",
            "tool": "bash",
            "args": {"command": "ls -la src/"},
            "description": "List directory contents"
        }
        
        with patch('tunacode.tools.list_dir.list_dir._execute') as mock_execute:
            mock_execute.return_value = "file1.py\nfile2.py\n"
            
            results = await parallel_executor._execute_generic_batch([task])
            
            assert len(results) == 1
            result = results[0]
            assert result.success
            assert "file1.py" in result.result["output"]
            
            # Verify list_dir was called with correct directory
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[1]
            assert call_args["directory"] == "src/"
            assert call_args["show_hidden"] is True  # -a flag

    @pytest.mark.asyncio
    async def test_unsupported_bash_command(self, parallel_executor):
        """Test that unsupported bash commands are rejected."""
        task = {
            "id": "1",
            "tool": "bash",
            "args": {"command": "rm -rf /"},
            "description": "Dangerous command"
        }
        
        results = await parallel_executor._execute_generic_batch([task])
        
        assert len(results) == 1
        result = results[0]
        assert not result.success
        assert "not supported in parallel read mode" in result.error

    @pytest.mark.asyncio
    async def test_parallel_read_file_batch(self, parallel_executor, tmp_path):
        """Test parallel batch reading of multiple files."""
        # Create test files
        files = []
        for i in range(5):
            file_path = tmp_path / f"file{i}.py"
            file_path.write_text(f"# Content of file {i}\nREPL test {i}")
            files.append(str(file_path))
        
        # Create read tasks
        tasks = [
            {
                "id": str(i),
                "tool": "read_file",
                "args": {"file_path": file_path},
                "description": f"Read {file_path}"
            }
            for i, file_path in enumerate(files)
        ]
        
        start_time = time.time()
        results = await parallel_executor._execute_read_file_batch(tasks)
        duration = time.time() - start_time
        
        # Verify all files were read
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.success
            assert f"Content of file {i}" in result.result["output"]
            assert f"REPL test {i}" in result.result["output"]
        
        # Verify parallel execution (should be faster than sequential)
        # In real parallel execution, this should take less time than reading sequentially
        assert duration < 1.0  # Reasonable threshold for parallel execution

    @pytest.mark.asyncio
    async def test_grep_batch_execution(self, parallel_executor):
        """Test parallel batch execution of grep tasks."""
        tasks = [
            {
                "id": "1",
                "tool": "grep",
                "args": {
                    "pattern": "REPL",
                    "directory": ".",
                    "include_files": "*.py"
                },
                "description": "Search for REPL"
            },
            {
                "id": "2",
                "tool": "grep",
                "args": {
                    "pattern": "architect",
                    "directory": ".",
                    "include_files": "*.py"
                },
                "description": "Search for architect"
            }
        ]
        
        with patch.object(ParallelGrep, '_execute') as mock_execute:
            # Mock different results for each search
            mock_execute.side_effect = [
                "Found REPL in repl.py",
                "Found architect in architect.py"
            ]
            
            results = await parallel_executor._execute_grep_batch(tasks)
            
            assert len(results) == 2
            assert results[0].success
            assert "REPL" in results[0].result["output"]
            assert results[1].success
            assert "architect" in results[1].result["output"]

    @pytest.mark.asyncio
    async def test_search_performance_scaling(self, grep_tool, tmp_path):
        """Test that search scales well with file count."""
        # Create many files
        file_counts = [10, 50, 100]
        timings = []
        
        for count in file_counts:
            # Create test files
            test_dir = tmp_path / f"test_{count}"
            test_dir.mkdir()
            
            for i in range(count):
                (test_dir / f"file{i}.py").write_text(f"# File {i}\nif i == {count//2}: print('REPL')")
            
            # Time the search
            start_time = time.time()
            result = await grep_tool._execute(
                pattern="REPL",
                directory=str(test_dir),
                include_files="*.py",
                search_type="python"  # Use Python strategy for consistent timing
            )
            duration = time.time() - start_time
            timings.append(duration)
            
            # Verify search found the pattern
            assert "REPL" in result
        
        # Verify performance scales reasonably (not exponentially)
        # The ratio of time increase should be less than file count increase
        if len(timings) >= 2:
            time_ratio = timings[-1] / timings[0]
            file_ratio = file_counts[-1] / file_counts[0]
            assert time_ratio < file_ratio * 2  # Allow some overhead


@pytest.mark.asyncio
async def test_architect_search_integration(state_manager):
    """Integration test for architect mode search functionality."""
    orchestrator = AdaptiveOrchestrator(state_manager)
    
    # Mock the planner to return search tasks
    with patch.object(orchestrator.planner, 'plan') as mock_plan:
        from tunacode.core.analysis.schemas import TaskSchema
        
        mock_plan.return_value = [
            TaskSchema(
                id=1,
                description="Search for REPL files",
                mutate=False,
                tool="bash",
                args={"command": "find . -name '*repl*'"}
            ),
            TaskSchema(
                id=2,
                description="Search for architect pattern",
                mutate=False,
                tool="grep",
                args={
                    "pattern": "architect",
                    "directory": ".",
                    "include_files": "*.py"
                }
            )
        ]
        
        # Mock the parallel executor
        with patch.object(orchestrator.parallel_executor, 'execute_batch') as mock_execute:
            mock_execute.return_value = [
                ParallelTaskResult(
                    task_id="1",
                    task_type="bash",
                    success=True,
                    result={"output": "repl.py\ncore/repl_handler.py"},
                    duration=0.1
                ),
                ParallelTaskResult(
                    task_id="2",
                    task_type="grep",
                    success=True,
                    result={"output": "Found 'architect' in architect.py:10"},
                    duration=0.2
                )
            ]
            
            # Run the orchestrator
            results = await orchestrator.run("Find files related to REPL and architect mode")
            
            # Verify results
            assert len(results) > 0
            assert any("repl.py" in str(r.result.output) for r in results if hasattr(r, 'result') and hasattr(r.result, 'output'))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])