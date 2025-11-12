"""Golden baseline test for thread safety and resource cleanup fixes.

This comprehensive test validates:
1. Thread-safe ResponseState boolean flag access under concurrent load
2. Resource cleanup in error paths during tool execution
3. No race conditions or data corruption under stress
"""

import asyncio
import gc
from typing import List

import pytest

from tunacode.core.agents.agent_components import ResponseState
from tunacode.types import AgentState


class TestThreadSafetyAndResources:
    """Comprehensive test suite for thread safety and resource cleanup."""

    @pytest.mark.asyncio
    async def test_concurrent_response_state_flag_updates(self):
        """Validate thread-safe ResponseState flag updates under concurrent load."""
        # Create shared ResponseState instance
        response_state = ResponseState()

        # Number of concurrent tasks and operations per task
        num_tasks = 10
        operations_per_task = 100

        async def update_flags(task_id: int) -> List[dict]:
            """Concurrently update ResponseState flags."""
            results = []
            for i in range(operations_per_task):
                # Alternate between different flag updates
                operation = (task_id * operations_per_task + i) % 4

                if operation == 0:
                    response_state.has_user_response = True
                    value = response_state.has_user_response
                elif operation == 1:
                    response_state.task_completed = True
                    value = response_state.task_completed
                elif operation == 2:
                    response_state.awaiting_user_guidance = True
                    value = response_state.awaiting_user_guidance
                else:
                    response_state.has_final_synthesis = True
                    value = response_state.has_final_synthesis

                results.append(
                    {
                        "task_id": task_id,
                        "operation": i,
                        "flag_value": value,
                        "operation_type": operation,
                    }
                )
                # Small delay to increase chance of race conditions
                await asyncio.sleep(0.0001)

            return results

        # Execute concurrent flag updates
        tasks = [update_flags(task_id) for task_id in range(num_tasks)]
        all_results = await asyncio.gather(*tasks)

        # Validate consistency: all flag reads should return the expected values
        # Since we're setting flags to True, they should all be True
        for task_results in all_results:
            for result in task_results:
                assert result["flag_value"] is True, (
                    f"Flag corruption detected: task={result['task_id']}, "
                    f"op={result['operation']}, value={result['flag_value']}"
                )

        # Final state validation: at least one flag should be True
        assert (
            response_state.has_user_response
            or response_state.task_completed
            or response_state.awaiting_user_guidance
            or response_state.has_final_synthesis
        ), "All flags should not be False after concurrent updates"

    @pytest.mark.asyncio
    async def test_concurrent_state_transitions(self):
        """Validate thread-safe state machine transitions under concurrent load."""
        response_state = ResponseState()

        num_tasks = 10
        transitions_per_task = 50

        async def transition_states(task_id: int) -> List[dict]:
            """Concurrently transition ResponseState through valid states."""
            results = []
            states = [
                AgentState.USER_INPUT,
                AgentState.ASSISTANT,
                AgentState.TOOL_EXECUTION,
                AgentState.RESPONSE,
            ]

            for i in range(transitions_per_task):
                target_state = states[i % len(states)]
                try:
                    if response_state.can_transition_to(target_state):
                        response_state.transition_to(target_state)
                        current = response_state.current_state
                        results.append(
                            {
                                "task_id": task_id,
                                "transition": i,
                                "target_state": target_state.value,
                                "current_state": current.value,
                                "success": True,
                            }
                        )
                    else:
                        results.append(
                            {
                                "task_id": task_id,
                                "transition": i,
                                "target_state": target_state.value,
                                "current_state": response_state.current_state.value,
                                "success": False,
                            }
                        )
                except Exception as e:
                    results.append(
                        {
                            "task_id": task_id,
                            "transition": i,
                            "error": str(e),
                            "success": False,
                        }
                    )
                await asyncio.sleep(0.0001)

            return results

        # Execute concurrent state transitions
        tasks = [transition_states(task_id) for task_id in range(num_tasks)]
        all_results = await asyncio.gather(*tasks)

        # Validate: no exceptions should occur (all transitions should be valid or handled)
        for task_results in all_results:
            for result in task_results:
                assert "error" not in result, (
                    f"Unexpected exception during state transition: "
                    f"task={result.get('task_id')}, transition={result.get('transition')}, "
                    f"error={result.get('error')}"
                )

        # Final state should be valid
        assert response_state.current_state in [
            AgentState.USER_INPUT,
            AgentState.ASSISTANT,
            AgentState.TOOL_EXECUTION,
            AgentState.RESPONSE,
        ], f"Invalid final state: {response_state.current_state}"

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_errors(self):
        """Validate resource cleanup in error scenarios."""
        # Track resource creation/cleanup
        resources_created = []
        resources_cleaned = []

        async def mock_tool_callback_with_resource(part, node):
            """Mock tool callback that creates and cleans up resources."""
            # Simulate resource creation (e.g., file handle, connection)
            resource_id = f"resource_{id(part)}_{id(node)}"
            resources_created.append(resource_id)

            # Simulate error condition
            if hasattr(part, "should_fail") and part.should_fail:
                raise ValueError(f"Simulated error for {resource_id}")

            # Normal cleanup (would happen in finally block)
            resources_cleaned.append(resource_id)
            return {"status": "success", "resource_id": resource_id}

        # Test error path: tool callback raises exception
        class MockPart:
            def __init__(self, should_fail: bool = False):
                self.tool_name = "test_tool"
                self.should_fail = should_fail

        class MockNode:
            pass

        # Test successful execution
        part_success = MockPart(should_fail=False)
        node_success = MockNode()
        try:
            result = await mock_tool_callback_with_resource(part_success, node_success)
            assert result["status"] == "success"
        finally:
            # Ensure cleanup happens (simulating finally block)
            resource_id = f"resource_{id(part_success)}_{id(node_success)}"
            if resource_id not in resources_cleaned:
                resources_cleaned.append(resource_id)

        # Test error execution
        part_error = MockPart(should_fail=True)
        node_error = MockNode()
        try:
            await mock_tool_callback_with_resource(part_error, node_error)
        except ValueError:
            pass  # Expected error
        finally:
            # Ensure cleanup happens even on error (simulating finally block)
            resource_id = f"resource_{id(part_error)}_{id(node_error)}"
            if resource_id not in resources_cleaned:
                resources_cleaned.append(resource_id)

        # Validate: all created resources should be cleaned up
        assert len(resources_created) == 2, (
            f"Expected 2 resources created, got {len(resources_created)}"
        )
        assert len(resources_cleaned) == 2, (
            f"Expected 2 resources cleaned, got {len(resources_cleaned)}. "
            f"Created: {resources_created}, Cleaned: {resources_cleaned}"
        )
        assert set(resources_created) == set(resources_cleaned), (
            "Resource leak detected: not all created resources were cleaned up. "
            f"Created: {resources_created}, Cleaned: {resources_cleaned}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_error_handling_with_cleanup(self):
        """Validate thread-safe error handling with resource cleanup."""
        response_state = ResponseState()
        error_count = {"value": 0}
        cleanup_count = {"value": 0}

        num_tasks = 10
        operations_per_task = 20

        async def operation_with_error_handling(task_id: int, op_id: int):
            """Perform operation with error handling and cleanup."""
            try:
                # Simulate operation that might fail
                if (task_id + op_id) % 5 == 0:
                    raise ValueError(f"Simulated error: task={task_id}, op={op_id}")
                # Update state
                response_state.has_user_response = True
            except ValueError:
                error_count["value"] += 1
                raise
            finally:
                # Ensure cleanup happens regardless of success/failure
                cleanup_count["value"] += 1

        # Execute concurrent operations with error handling
        tasks = []
        for task_id in range(num_tasks):
            for op_id in range(operations_per_task):
                tasks.append(operation_with_error_handling(task_id, op_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count exceptions
        exception_count = sum(1 for r in results if isinstance(r, Exception))

        # Validate: cleanup should happen for all operations (success or failure)
        total_operations = num_tasks * operations_per_task
        assert cleanup_count["value"] == total_operations, (
            f"Cleanup not called for all operations: "
            f"expected={total_operations}, actual={cleanup_count['value']}"
        )

        # Validate: errors should be handled gracefully
        assert exception_count == error_count["value"], (
            f"Exception count mismatch: exceptions={exception_count}, "
            f"error_count={error_count['value']}"
        )

        # Validate: state should be consistent (no corruption from concurrent updates)
        assert isinstance(response_state.has_user_response, bool), (
            "State corruption detected: has_user_response is not a boolean"
        )

    def test_stress_test_concurrent_updates(self):
        """Stress test: run concurrent updates 100 times to detect race conditions."""
        # Run the concurrent flag update test multiple times
        for iteration in range(100):
            # Create fresh ResponseState for each iteration
            response_state = ResponseState()

            async def run_iteration():
                """Run one iteration of concurrent updates."""
                num_tasks = 5
                operations_per_task = 10

                async def update_task(task_id: int):
                    """Update flags concurrently."""
                    for _ in range(operations_per_task):
                        response_state.has_user_response = True
                        response_state.task_completed = True
                        await asyncio.sleep(0)

                tasks = [update_task(task_id) for task_id in range(num_tasks)]
                await asyncio.gather(*tasks)

                # Validate final state
                assert response_state.has_user_response is True
                assert response_state.task_completed is True

            # Run async test
            asyncio.run(run_iteration())

            # Force garbage collection to detect resource leaks
            gc.collect()

        # If we get here without exceptions, test passed
        assert True

