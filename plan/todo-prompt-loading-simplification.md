# Plan: Simplify Prompt Loading in todo.py

## Problem
The todo.py file contains defensive prompt loading checks that add unnecessary complexity. The prompts are always available via `load_prompt_from_xml()`, so we can simplify the code.

## Solution
1. Remove the conditional branch checks for prompt loading
2. Always load and apply prompts without checking if they exist
3. Keep error handling for the actual loading function

## Implementation Steps
- Remove the `if prompt:` conditional checks in `create_todowrite_tool()` and `create_todoread_tool()`
- Remove the conditional check in `create_todoclear_tool()`
- Ensure `load_prompt_from_xml()` handles its own error cases

## Task Breakdown
1. ✅ Create plan document
2. Modify `create_todowrite_tool()` to always apply prompt
3. Modify `create_todoread_tool()` to always apply prompt
4. Modify `create_todoclear_tool()` to always apply prompt
5. Verify changes with tests
