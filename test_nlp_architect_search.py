#!/usr/bin/env python3
"""
Test NLP search in architect mode - like real users would search.
Tests various natural language queries to ensure the agent can understand and navigate.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tunacode.core.agents.adaptive_orchestrator import AdaptiveOrchestrator
from tunacode.core.state import StateManager
from tunacode.types import ModelName


async def test_nlp_searches():
    """Test natural language searches that real users would type."""
    
    # Initialize
    state = StateManager()
    state.session.current_model = ModelName("openrouter:gpt-4.1")
    orchestrator = AdaptiveOrchestrator(state)
    
    # Real user searches - typos and all
    test_queries = [
        # Vague searches
        "where is the repl stuff",
        "show me the file that handles user input",
        "i need to find where commands are processed",
        
        # Typos and casual language
        "find the fiel that does architect mode",
        "wher is the code for searchin files",
        "show me anythign related to grep or search",
        
        # Complex semantic searches
        "I'm looking for the code that converts bash commands to specialized tools",
        "find where parallel execution happens for read tasks",
        "which files handle the feedback loop in architect mode",
        
        # Navigation queries
        "what files are in the cli directory",
        "show me all the agent files",
        "list everything in core/analysis",
        
        # Pattern searches
        "find all async functions",
        "search for classes that inherit from BaseCommand",
        "where are decorators used",
        
        # Context-aware searches
        "find files that import parallel executor",
        "which files use the grep tool",
        "show me where StateManager is used"
    ]
    
    print("TESTING NLP ARCHITECT MODE SEARCHES")
    print("=" * 70)
    print("Testing how architect mode handles real user queries...\n")
    
    for i, query in enumerate(test_queries[:5]):  # Test first 5 to save time
        print(f"\nTEST {i+1}: '{query}'")
        print("-" * 70)
        
        try:
            results = await orchestrator.run(query)
            
            if results and len(results) > 0:
                for result in results:
                    if hasattr(result, 'result') and hasattr(result.result, 'output'):
                        output = result.result.output
                        # Show first 500 chars of output
                        if len(output) > 500:
                            print(f"Found results:\n{output[:500]}...\n[truncated]")
                        else:
                            print(f"Found results:\n{output}")
            else:
                print("No results found")
                
        except Exception as e:
            print(f"Error: {e}")
        
        # Small delay between queries
        await asyncio.sleep(0.5)


async def test_search_edge_cases():
    """Test edge cases and difficult searches."""
    
    state = StateManager()
    state.session.current_model = ModelName("openrouter:gpt-4.1")
    orchestrator = AdaptiveOrchestrator(state)
    
    print("\n\nTESTING EDGE CASES")
    print("=" * 70)
    
    edge_cases = [
        # Ambiguous references
        "that file we were just looking at",
        "the main one",
        "you know, the thing that does the thing",
        
        # Multiple concepts
        "find files that have both async and grep but not test",
        "show python files in src but not in tools",
        
        # Regex-like patterns in natural language
        "files starting with test_",
        "anything ending in .md",
        "files with numbers in the name"
    ]
    
    for i, query in enumerate(edge_cases[:3]):
        print(f"\nEDGE CASE {i+1}: '{query}'")
        print("-" * 70)
        
        try:
            results = await orchestrator.run(query)
            if results:
                print("✓ Handled successfully")
            else:
                print("✗ No results")
        except Exception as e:
            print(f"✗ Error: {e}")


async def test_conversation_context():
    """Test that architect mode remembers context between searches."""
    
    state = StateManager()
    state.session.current_model = ModelName("openrouter:gpt-4.1")
    orchestrator = AdaptiveOrchestrator(state)
    
    print("\n\nTESTING CONVERSATION CONTEXT")
    print("=" * 70)
    
    # Simulate a conversation
    queries = [
        "find the repl file",
        "now show me what's in that file",  # References previous result
        "are there any similar files?"       # References context
    ]
    
    for i, query in enumerate(queries):
        print(f"\nQUERY {i+1}: '{query}'")
        print("-" * 70)
        
        try:
            results = await orchestrator.run(query)
            if results and len(results) > 0:
                print("✓ Found results")
                # Add to context for next query
                if i == 0 and hasattr(results[0], 'result'):
                    # Simulate finding repl.py
                    state.session.files_in_context.add("src/tunacode/cli/repl.py")
            else:
                print("✗ No results")
        except Exception as e:
            print(f"✗ Error: {e}")


async def test_performance():
    """Test search performance with timing."""
    
    from tunacode.tools.grep import ParallelGrep
    import time
    
    print("\n\nTESTING SEARCH PERFORMANCE")
    print("=" * 70)
    
    grep = ParallelGrep()
    
    searches = [
        ("Simple literal", "REPL", "*.py", False),
        ("Case insensitive", "repl", "*.py", False),
        ("Regex pattern", r"class\s+\w+Agent", "*.py", True),
        ("Multiple extensions", "tunacode", "*.py,*.md,*.txt", False),
        ("Large scope", "def", "*", False)
    ]
    
    for desc, pattern, includes, use_regex in searches:
        print(f"\n{desc}: pattern='{pattern}', includes='{includes}'")
        
        start = time.time()
        try:
            result = await grep._execute(
                pattern=pattern,
                directory=".",
                include_files=includes,
                use_regex=use_regex,
                max_results=10
            )
            duration = time.time() - start
            
            matches = result.count("📁")
            print(f"✓ Found {matches} files in {duration:.3f} seconds")
            
            # Show which strategy was used
            if "Strategy:" in result:
                strategy_line = [l for l in result.split('\n') if "Strategy:" in l][0]
                print(f"  {strategy_line}")
                
        except Exception as e:
            print(f"✗ Error: {e}")


async def main():
    """Run all NLP search tests."""
    
    print("\n🔍 TUNACODE NLP SEARCH TESTING 🔍\n")
    
    # Test direct grep tool first
    await test_performance()
    
    # Test NLP searches with orchestrator
    try:
        await test_nlp_searches()
        await test_search_edge_cases()
        await test_conversation_context()
    except Exception as e:
        print(f"\nNote: Some tests require API key: {e}")
    
    print("\n\n✅ TESTING COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())