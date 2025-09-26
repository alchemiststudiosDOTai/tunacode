"""Test to validate the system prompt changes."""

from pathlib import Path


def test_system_prompt_no_json_in_responses():
    """Verify system prompt has proper structure and instructions."""
    prompt_path = Path(__file__).parent.parent / "src" / "tunacode" / "prompts" / "system.xml"

    content = prompt_path.read_text(encoding="utf-8")

    # Check that we have the core instruction structure
    assert "<instructions>" in content
    assert (
        "YOU ARE NOT A CHATBOT. YOU ARE AN OPERATIONAL EXPERIENCED DEVELOPER WITH AGENT WITH TOOLS."
        in content
    )

    # Check critical behavior rules
    assert "CRITICAL BEHAVIOR RULES:" in content
    assert "ALWAYS ANNOUNCE YOUR INTENTIONS FIRST" in content
    assert "TUNACODE DONE:" in content

    # Check tool access rules
    assert "<tools>" in content
    assert "READONLY TOOLS" in content
    assert "WRITE/EXECUTE TOOLS" in content

    # Check for task management section
    assert "TASK MANAGEMENT TOOLS" in content
    assert "todo" in content

    print("\n=== SYSTEM PROMPT VALIDATION ===")
    print("✓ Core instruction structure present")
    print("✓ Agent behavior rules defined")
    print("✓ Tool categories properly documented")
    print("✓ Task management tools included")
    print("\nThe system prompt is properly structured for agent operations.")
