"""Unit tests for RecursiveTaskExecutor - focused on essential features."""

from unittest.mock import AsyncMock, Mock

import pytest

from tunacode.core.recursive.executor import (
    RecursiveTaskExecutor,
    TaskComplexityResult,
    TaskNode,
)
from tunacode.core.state import SessionState, StateManager


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager with necessary attributes."""
    state_manager = Mock(spec=StateManager)
    state_manager.session = Mock(spec=SessionState)
    state_manager.session.agents = {"main": AsyncMock()}
    state_manager.session.show_thoughts = False
    state_manager.session.user_config = {
        "settings": {
            "use_recursive_execution": True,
            "recursive_complexity_threshold": 0.7,
            "max_recursion_depth": 5,
        }
    }
    return state_manager


@pytest.fixture
def executor(mock_state_manager):
    """Create a RecursiveTaskExecutor instance."""
    return RecursiveTaskExecutor(
        state_manager=mock_state_manager,
        max_depth=3,
        min_complexity_threshold=0.7,
        default_iteration_budget=20,
    )


class TestRecursiveTaskExecutor:
    """Test core RecursiveTaskExecutor functionality."""

    @pytest.mark.asyncio
    async def test_simple_task_executes_directly(self, executor, mock_state_manager):
        """Test that simple tasks are executed directly without decomposition."""

        # Mock complexity analysis to return low complexity
        async def mock_analyze(request):
            return TaskComplexityResult(
                is_complex=False,
                complexity_score=0.3,
                reasoning="Simple task",
                suggested_subtasks=[],
            )

        executor._analyze_task_complexity = mock_analyze

        # Mock agent execution
        mock_agent = mock_state_manager.session.agents["main"]
        mock_agent.run.return_value = "Task completed successfully"

        # Execute a simple task
        success, result, error = await executor.execute_task("Simple task: add 2 + 2")

        assert success is True
        assert result == "Task completed successfully"
        assert error is None
        assert len(executor._task_hierarchy) == 1
        assert (
            executor._task_hierarchy[list(executor._task_hierarchy.keys())[0]].status == "completed"
        )

    @pytest.mark.asyncio
    async def test_complex_task_triggers_decomposition(self, executor, mock_state_manager):
        """Test that complex tasks trigger decomposition into subtasks."""

        # Override analyze method to return high complexity
        async def mock_analyze(request):
            return TaskComplexityResult(
                is_complex=True,
                complexity_score=0.85,
                reasoning="Task requires multiple operations",
                suggested_subtasks=["Step 1: Setup", "Step 2: Process", "Step 3: Validate"],
            )

        executor._analyze_task_complexity = mock_analyze

        # Mock subtask execution
        original_execute = executor.execute_task
        call_count = 0

        async def mock_execute(request, parent_task_id=None, depth=0, inherited_context=None):
            nonlocal call_count
            call_count += 1
            if depth > 0:  # Subtask execution
                return True, f"Subtask result {call_count}", None
            else:  # Main task
                return await original_execute(request, parent_task_id, depth, inherited_context)

        executor.execute_task = mock_execute

        # Execute complex task
        success, result, error = await executor.execute_task("Build complete REST API with auth")

        assert success is True
        assert error is None
        # Should have executed main task + 3 subtasks
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_max_recursion_depth_enforced(self, executor):
        """Test that max recursion depth is enforced."""
        # Execute at max depth
        success, result, error = await executor.execute_task("Deep task", depth=executor.max_depth)

        assert success is False
        assert error == f"Maximum recursion depth ({executor.max_depth}) exceeded"

    @pytest.mark.asyncio
    async def test_budget_allocation_distributes_correctly(self, executor):
        """Test iteration budget allocation across subtasks."""
        # Test equal distribution
        budgets = executor._allocate_iteration_budgets(100, 4)
        assert budgets == [25, 25, 25, 25]

        # Test with remainder
        budgets = executor._allocate_iteration_budgets(100, 3)
        assert budgets == [34, 33, 33]
        assert sum(budgets) == 100

        # Test empty subtasks
        budgets = executor._allocate_iteration_budgets(100, 0)
        assert budgets == []

    @pytest.mark.asyncio
    async def test_complexity_analysis_fallback(self, executor, mock_state_manager):
        """Test complexity analysis falls back to heuristics when agent unavailable."""
        # Remove agent
        mock_state_manager.session.agents = {}

        # Test heuristic analysis
        result = await executor._analyze_task_complexity(
            "This is a complex task with multiple parts and requirements and then some more"
        )

        assert isinstance(result, TaskComplexityResult)
        assert result.complexity_score > 0
        assert result.reasoning == "Heuristic analysis based on request length and structure"

    @pytest.mark.asyncio
    async def test_direct_execution_handles_no_agent(self, executor, mock_state_manager):
        """Test direct execution handles missing agent gracefully."""
        # Remove agent
        mock_state_manager.session.agents = {}

        # Create task node
        task_node = TaskNode(title="Test task", description="Test description")
        executor._task_hierarchy[task_node.id] = task_node

        success, result, error = await executor._execute_directly(task_node)

        assert success is False
        assert error == "Main agent not available"
        assert task_node.status == "failed"

    @pytest.mark.asyncio
    async def test_subtask_failure_propagates(self, executor, mock_state_manager):
        """Test that subtask failures are properly handled."""

        # Mock complex task analysis
        async def mock_analyze(request):
            return TaskComplexityResult(
                is_complex=True,
                complexity_score=0.9,
                reasoning="Complex task",
                suggested_subtasks=["Subtask 1", "Subtask 2"],
            )

        executor._analyze_task_complexity = mock_analyze

        # Mock subtask execution to fail on second subtask
        original_execute = executor.execute_task
        subtask_count = 0

        async def mock_execute(request, parent_task_id=None, depth=0, inherited_context=None):
            nonlocal subtask_count
            if depth > 0:  # Subtask execution
                subtask_count += 1
                if subtask_count == 2:
                    return False, None, "Subtask 2 failed"
                return True, f"Subtask {subtask_count} result", None
            else:  # Main task
                return await original_execute(request, parent_task_id, depth, inherited_context)

        executor.execute_task = mock_execute

        # Execute task
        success, result, error = await executor.execute_task("Complex task")

        assert success is False
        assert "Subtask 2 failed" in error

    def test_task_hierarchy_tracking(self, executor):
        """Test task hierarchy and execution stack management."""
        # Initially empty
        assert len(executor.get_task_hierarchy()) == 0
        assert len(executor.get_execution_stack()) == 0

        # After clear
        executor._task_hierarchy["test"] = TaskNode(id="test")
        executor._execution_stack.append("test")
        executor.clear_hierarchy()

        assert len(executor.get_task_hierarchy()) == 0
        assert len(executor.get_execution_stack()) == 0
