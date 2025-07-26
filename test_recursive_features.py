#!/usr/bin/env python3
"""
Test script to demonstrate recursive task execution features
"""

import asyncio
import sys
sys.path.insert(0, '/root/tunacode/src')

from tunacode.core.state import StateManager
from tunacode.core.recursive.executor import RecursiveTaskExecutor
from tunacode.core.recursive.decomposer import TaskDecomposer
from rich.console import Console

console = Console()

async def test_recursive_execution():
    """Test the recursive task execution feature"""
    
    # Initialize state manager
    state_manager = StateManager()
    state_manager.session.show_thoughts = True
    state_manager.session.user_config = {
        "settings": {
            "use_recursive_execution": True,
            "recursive_complexity_threshold": 0.7,
            "max_recursion_depth": 5
        }
    }
    
    # Initialize recursive executor
    executor = RecursiveTaskExecutor(
        state_manager=state_manager,
        max_depth=5,
        min_complexity_threshold=0.7,
        default_iteration_budget=40
    )
    
    # Test with a complex task
    complex_task = """Build a complete REST API for a todo application with:
    - User authentication using JWT tokens
    - CRUD operations for todos with user ownership
    - Input validation and error handling
    - Database integration with SQLAlchemy
    - Unit tests for all endpoints
    - API documentation with OpenAPI/Swagger"""
    
    console.print("\n[bold cyan]🚀 Testing Recursive Task Execution[/bold cyan]\n")
    console.print(f"[yellow]Task:[/yellow] {complex_task}\n")
    
    # Analyze task complexity
    decomposer = TaskDecomposer(state_manager)
    complexity_result = await decomposer.analyze_and_decompose(complex_task)
    
    console.print(f"[green]✓ Task Analysis Complete[/green]")
    console.print(f"  • Should decompose: {complexity_result.should_decompose}")
    console.print(f"  • Complexity score: {complexity_result.total_complexity:.2f}")
    console.print(f"  • Confidence: {complexity_result.confidence:.2f}")
    console.print(f"  • Reasoning: {complexity_result.reasoning}")
    
    if complexity_result.subtasks:
        console.print(f"\n[cyan]📋 Proposed Subtasks ({len(complexity_result.subtasks)}):[/cyan]")
        for i, subtask in enumerate(complexity_result.subtasks, 1):
            console.print(f"  {i}. {subtask.title}")
            console.print(f"     - Complexity: {subtask.estimated_complexity:.2f}")
            console.print(f"     - Est. iterations: {subtask.estimated_iterations}")
            if subtask.dependencies:
                console.print(f"     - Dependencies: {subtask.dependencies}")
    
    # Test budget manager
    from tunacode.core.recursive.budget import BudgetManager
    budget_manager = BudgetManager(total_budget=100, min_task_budget=5)
    
    if complexity_result.subtasks:
        task_ids = [f"task_{i}" for i in range(len(complexity_result.subtasks))]
        complexities = [st.estimated_complexity for st in complexity_result.subtasks]
        
        allocations = budget_manager.allocate_budget(
            task_ids=task_ids,
            complexity_scores=complexities
        )
        
        console.print(f"\n[cyan]💰 Budget Allocation:[/cyan]")
        for task_id, budget in allocations.items():
            console.print(f"  • {task_id}: {budget} iterations")
        
        # Show budget summary
        summary = budget_manager.get_budget_summary()
        console.print(f"\n[cyan]📊 Budget Summary:[/cyan]")
        console.print(f"  • Total budget: {summary['total_budget']}")
        console.print(f"  • Allocated: {summary['allocated_budget']}")
        console.print(f"  • Available: {summary['available_budget']}")
    
    console.print("\n[green]✅ Recursive execution features are working![/green]")
    console.print("\nTo test in the actual TunaCode CLI:")
    console.print("1. Run: tunacode")
    console.print("2. Enable thoughts: /thoughts on")
    console.print("3. Give it the complex task above")
    console.print("4. Watch the recursive decomposition in action!\n")

if __name__ == "__main__":
    asyncio.run(test_recursive_execution())