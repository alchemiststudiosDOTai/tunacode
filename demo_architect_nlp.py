#!/usr/bin/env python3
"""
Demo showing how architect mode converts NLP queries to actual searches.
This simulates what happens when users type natural language.
"""

import asyncio
from tunacode.core.agents.parallel_executor import ParallelExecutor
from tunacode.core.agents.context_provider import ContextProvider
from pathlib import Path

async def demo_nlp_conversion():
    """Show how NLP queries get converted to search tasks."""
    
    # Initialize components
    context_provider = ContextProvider(Path.cwd())
    executor = ParallelExecutor(context_provider)
    
    print("🤖 ARCHITECT MODE NLP SEARCH DEMO")
    print("=" * 60)
    
    # Example 1: User types casual query
    print("\n1️⃣ User types: 'wheres the repl stuff'")
    print("   Architect converts to:")
    tasks1 = [
        {
            "id": "1",
            "tool": "bash",
            "args": {"command": "find . -iname '*repl*'"},
            "description": "Find files with 'repl' in the name"
        },
        {
            "id": "2", 
            "tool": "grep",
            "args": {"pattern": "repl|REPL", "directory": ".", "include_files": "*.py", "use_regex": True},
            "description": "Search for REPL references in code"
        }
    ]
    print(f"   - Task 1: {tasks1[0]['description']}")
    print(f"   - Task 2: {tasks1[1]['description']}")
    
    results = await executor.execute_batch(tasks1)
    print(f"\n   ✓ Found {sum(1 for r in results if r.success)} successful results")
    
    # Example 2: User searches with typo
    print("\n2️⃣ User types: 'find the fiel that does architect mode'")
    print("   Architect understands 'fiel' → 'file' and converts to:")
    tasks2 = [
        {
            "id": "1",
            "tool": "grep",
            "args": {"pattern": "architect", "directory": ".", "include_files": "*.py"},
            "description": "Search for 'architect' in Python files"
        }
    ]
    print(f"   - Task: {tasks2[0]['description']}")
    
    # Example 3: Semantic search
    print("\n3️⃣ User types: 'I need the code that converts bash to other tools'")
    print("   Architect understands the concept and searches for:")
    tasks3 = [
        {
            "id": "1",
            "tool": "grep",
            "args": {"pattern": "bash.*command.*convert|find.*command.*grep", "directory": ".", "include_files": "*.py", "use_regex": True},
            "description": "Search for bash command conversion logic"
        },
        {
            "id": "2",
            "tool": "grep", 
            "args": {"pattern": "_execute_generic_batch", "directory": ".", "include_files": "*.py"},
            "description": "Find the generic batch execution method"
        }
    ]
    print(f"   - Task 1: {tasks3[0]['description']}")
    print(f"   - Task 2: {tasks3[1]['description']}")
    
    # Example 4: Context-aware search
    print("\n4️⃣ User already found repl.py, then types: 'show me similar files'")
    print("   Architect uses context and searches for:")
    tasks4 = [
        {
            "id": "1",
            "tool": "list_dir",
            "args": {"directory": "src/tunacode/cli"},
            "description": "List other files in the same directory as repl.py"
        },
        {
            "id": "2",
            "tool": "grep",
            "args": {"pattern": "class.*REPL|def.*repl", "directory": ".", "include_files": "*.py", "use_regex": True},
            "description": "Find other files with REPL-related classes or functions"
        }
    ]
    print(f"   - Task 1: {tasks4[0]['description']}")
    print(f"   - Task 2: {tasks4[1]['description']}")
    
    # Example 5: Navigation query
    print("\n5️⃣ User types: 'what's in the agents folder'")
    print("   Architect converts to:")
    tasks5 = [
        {
            "id": "1",
            "tool": "bash",
            "args": {"command": "ls -la src/tunacode/core/agents/"},
            "description": "List contents of agents directory"
        }
    ]
    print(f"   - Task: {tasks5[0]['description']}")
    
    results = await executor.execute_batch(tasks5)
    if results[0].success:
        output = results[0].result["output"]
        files = [line for line in output.split('\n') if line.strip() and not line.startswith('total')][:5]
        print(f"\n   Found files:")
        for f in files:
            print(f"   - {f}")

    print("\n" + "=" * 60)
    print("💡 KEY INSIGHTS:")
    print("- Architect mode understands typos and casual language")
    print("- It converts vague requests into specific search tasks")
    print("- It can use multiple search strategies in parallel")
    print("- It remembers context from previous searches")
    print("- Bash commands are automatically converted to specialized tools")

if __name__ == "__main__":
    asyncio.run(demo_nlp_conversion())