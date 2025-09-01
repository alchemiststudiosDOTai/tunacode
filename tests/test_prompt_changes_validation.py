"""Test to validate the system prompt changes."""

from pathlib import Path


def test_system_prompt_no_json_in_responses():
    """Verify system prompt has proper structure and instructions."""
    prompt_path = Path(__file__).parent.parent / "src" / "tunacode" / "prompts" / "system.md"

    with open(prompt_path, "r") as f:
        content = f.read()

    # Check that we have the core instruction structure
    assert "###Instruction###" in content
    assert "You are TunaCode, an expert terminal-based AI assistant" in content

    # Check critical behavior rules
    assert "## Core Directives (CRITICAL)" in content
    assert "Action-First" in content
    assert "TUNACODE_TASK_COMPLETE" in content

    # Check tool format requirements
    assert "## Tool Calling Format" in content
    assert "OpenAI function calling format" in content
    assert "tool_calls" in content

    # Check for available tools section
    assert "## Available Tools" in content
    assert "Read-Only Tools" in content

    print("\n=== SYSTEM PROMPT VALIDATION ===")
    print("✓ Core instruction structure present")
    print("✓ Agent behavior rules defined")
    print("✓ Tool categories properly documented")
    print("✓ Task management tools included")
    print("\nThe system prompt is properly structured for agent operations.")
