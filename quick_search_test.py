#!/usr/bin/env python3
"""Quick search test to show NLP search capabilities."""

import asyncio
from tunacode.tools.grep import ParallelGrep

async def test_searches():
    grep = ParallelGrep()
    
    # Test 1: Casual search for REPL
    print("TEST 1: Searching for 'repl' (case insensitive)")
    print("-" * 50)
    result = await grep._execute(
        pattern="repl",
        directory="src",
        include_files="*.py",
        case_sensitive=False,
        max_results=5
    )
    print(result[:500] + "...\n")
    
    # Test 2: Search with typo tolerance  
    print("TEST 2: Searching for files with 'architec' (typo)")
    print("-" * 50)
    result = await grep._execute(
        pattern="architec", 
        directory=".",
        include_files="*.py",
        max_results=5
    )
    print(result[:500] + "...\n")
    
    # Test 3: Multiple extensions
    print("TEST 3: Search across Python and Markdown files")
    print("-" * 50)
    result = await grep._execute(
        pattern="parallel",
        directory=".",
        include_files="*.py,*.md",
        max_results=5
    )
    print(result[:500] + "...\n")
    
    # Test 4: Complex pattern
    print("TEST 4: Find async functions")
    print("-" * 50)
    result = await grep._execute(
        pattern="async def",
        directory="src",
        include_files="*.py",
        max_results=5
    )
    print(result[:500] + "...\n")

asyncio.run(test_searches())