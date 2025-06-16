#!/usr/bin/env python3
"""Test script to verify the orchestrator fix for primary request tracking."""

import asyncio
import os
from pathlib import Path
from src.tunacode.core.state import StateManager
from src.tunacode.core.agents.adaptive_orchestrator import AdaptiveOrchestrator

async def test_orchestrator_fix():
    """Test that the orchestrator correctly prioritizes primary request outputs."""
    # Initialize state manager
    state = StateManager()
    state.session.current_model = "anthropic:claude-3-haiku-20240307"  # Use a fast model for testing
    
    # Initialize orchestrator
    orchestrator = AdaptiveOrchestrator(state)
    
    # Test request that should focus on a specific file
    request = "Tell me about CHANGELOG.md"
    
    print(f"Testing with request: {request}")
    print("-" * 80)
    
    try:
        # Run the orchestrator
        results = await orchestrator.run(request)
        
        if results:
            print("\nOrchestrator Results:")
            for i, result in enumerate(results):
                if hasattr(result, 'result') and hasattr(result.result, 'output'):
                    output = result.result.output
                    # Truncate for display
                    if len(output) > 500:
                        output = output[:500] + "... (truncated)"
                    print(f"\nResult {i + 1}:")
                    print(output)
                    print("-" * 40)
        else:
            print("No results returned")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_orchestrator_fix())