#!/usr/bin/env python3
"""
Test script to demonstrate TunaCode architect mode search functionality.
This shows how architect mode converts natural language queries into search tasks.
"""

import asyncio
from pathlib import Path

from tunacode.core.agents.adaptive_orchestrator import AdaptiveOrchestrator
from tunacode.core.state import StateManager
from tunacode.types import ModelName


async def test_architect_search():
    """Test architect mode with various search queries."""
    
    # Initialize state and orchestrator
    state = StateManager()
    state.session.current_model = ModelName("openrouter:gpt-4.1")
    orchestrator = AdaptiveOrchestrator(state)
    
    # Test 1: Natural language search for REPL files
    print("\n" + "="*60)
    print("TEST 1: Natural language search for REPL")
    print("Query: 'Find all files related to REPL functionality'")
    print("="*60)
    
    results = await orchestrator.run("Find all files related to REPL functionality")
    if results:
        for result in results:
            if hasattr(result, 'result') and hasattr(result.result, 'output'):
                print(f"\nResult:\n{result.result.output}")
    
    # Test 2: Search for architect mode
    print("\n" + "="*60)
    print("TEST 2: Search for architect mode implementation")
    print("Query: 'Where is the architect mode implemented?'")
    print("="*60)
    
    results = await orchestrator.run("Where is the architect mode implemented?")
    if results:
        for result in results:
            if hasattr(result, 'result') and hasattr(result.result, 'output'):
                print(f"\nResult:\n{result.result.output}")
    
    # Test 3: Complex semantic search
    print("\n" + "="*60)
    print("TEST 3: Complex semantic search")
    print("Query: 'Find all Python files that handle user input or commands'")
    print("="*60)
    
    results = await orchestrator.run("Find all Python files that handle user input or commands")
    if results:
        for result in results:
            if hasattr(result, 'result') and hasattr(result.result, 'output'):
                print(f"\nResult:\n{result.result.output}")
    
    # Test 4: Code pattern search
    print("\n" + "="*60)
    print("TEST 4: Code pattern search")
    print("Query: 'Search for all async functions that use grep'")
    print("="*60)
    
    results = await orchestrator.run("Search for all async functions that use grep")
    if results:
        for result in results:
            if hasattr(result, 'result') and hasattr(result.result, 'output'):
                print(f"\nResult:\n{result.result.output}")


async def test_parallel_executor_search():
    """Test the parallel executor's search capabilities directly."""
    from tunacode.core.agents.context_provider import ContextProvider
    from tunacode.core.agents.parallel_executor import ParallelExecutor
    
    print("\n" + "="*60)
    print("TEST 5: Direct parallel executor search")
    print("="*60)
    
    context_provider = ContextProvider(Path.cwd())
    executor = ParallelExecutor(context_provider)
    
    # Test bash find command conversion
    tasks = [
        {
            "id": "1",
            "tool": "bash",
            "args": {"command": "find . -name '*repl*' -type f"},
            "description": "Find REPL files"
        },
        {
            "id": "2",
            "tool": "grep",
            "args": {
                "pattern": "architect",
                "directory": ".",
                "include_files": "*.py"
            },
            "description": "Search for architect pattern"
        }
    ]
    
    results = await executor.execute_batch(tasks)
    
    for result in results:
        print(f"\nTask: {result.task_id} - {result.task_type}")
        print(f"Success: {result.success}")
        if result.success and result.result:
            output = result.result.get("output", "")
            print(f"Output preview: {output[:200]}...")
        else:
            print(f"Error: {result.error}")


async def test_grep_tool_directly():
    """Test the grep tool with various patterns."""
    from tunacode.tools.grep import ParallelGrep
    
    print("\n" + "="*60)
    print("TEST 6: Direct grep tool tests")
    print("="*60)
    
    grep = ParallelGrep()
    
    # Test 1: Multiple file extensions
    print("\n--- Testing multiple extensions (*.py,*.md) ---")
    result = await grep._execute(
        pattern="tunacode",
        directory=".",
        include_files="*.py,*.md",
        max_results=5
    )
    print(f"Found matches in: {result.count('📁')} files")
    
    # Test 2: Case-insensitive regex
    print("\n--- Testing case-insensitive regex ---")
    result = await grep._execute(
        pattern="repl|REPL",
        directory="src",
        include_files="*.py",
        use_regex=True,
        case_sensitive=False,
        max_results=5
    )
    print(f"Found matches in: {result.count('📁')} files")
    
    # Test 3: Smart strategy selection
    print("\n--- Testing smart strategy ---")
    result = await grep._execute(
        pattern="async def",
        directory="src",
        include_files="*.py",
        search_type="smart",
        max_results=10
    )
    lines = result.split('\n')
    if len(lines) > 0:
        print(lines[0])  # Print strategy info


async def main():
    """Run all tests."""
    print("TUNACODE ARCHITECT MODE SEARCH TESTS")
    print("====================================")
    
    # Test grep tool directly first
    await test_grep_tool_directly()
    
    # Test parallel executor
    await test_parallel_executor_search()
    
    # Test full architect mode (requires API key)
    try:
        await test_architect_search()
    except Exception as e:
        print(f"\nSkipping architect mode tests: {e}")
        print("(This requires a valid API key configured)")


if __name__ == "__main__":
    asyncio.run(main())