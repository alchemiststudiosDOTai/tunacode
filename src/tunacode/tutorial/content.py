"""
Module: tunacode.tutorial.content

Tutorial content definitions and step configurations.
"""

from typing import Dict, List

# Tutorial step content library
TUTORIAL_CONTENT: Dict[str, Dict[str, str]] = {
    "welcome": {
        "title": "🎯 Welcome to TunaCode!",
        "content": """TunaCode is your AI-powered development assistant.

In this quick tutorial, you'll learn how to:
• Chat with AI about your code
• Use commands to control TunaCode
• Work with files and projects
• Get help when you need it

This tutorial takes about 2-3 minutes. Ready to start?""",
        "action": "Press Enter to continue...",
    },
    "basic_chat": {
        "title": "💬 Basic AI Chat",
        "content": """The core of TunaCode is natural conversation with AI.

You can ask questions like:
• "How do I implement a binary search in Python?"
• "Review this function and suggest improvements"
• "Help me debug this error message"
• "Explain what this code does"

Just type your question naturally - no special syntax needed!""",
        "action": "Try asking: 'What can you help me with?'",
    },
    "file_operations": {
        "title": "📁 Working with Files",
        "content": """TunaCode can read, create, and modify files in your project.

Useful commands:
• Reference files with @filename.py
• Use /read to explicitly read files
• Ask to create or modify files
• Get help with /help

TunaCode understands your project structure and can work across multiple files.""",
        "action": "Try: 'Read the current directory structure'",
    },
    "commands": {
        "title": "⚙️ TunaCode Commands",
        "content": """Commands start with / and give you control over TunaCode:

Essential commands:
• /help - Show all available commands
• /model - Switch AI models
• /clear - Clear conversation history
• /exit - Exit TunaCode

System commands:
• !command - Run shell commands
• /streaming - Toggle streaming responses""",
        "action": "Try typing: /help",
    },
    "best_practices": {
        "title": "✨ Best Practices",
        "content": """To get the most out of TunaCode:

🎯 Be specific: "Fix the bug in login.py line 42" vs "fix my code"
📁 Use file references: "@app.py" to include files in context
🔄 Break down large tasks: Ask for step-by-step guidance
💬 Ask follow-up questions: TunaCode remembers your conversation
🚀 Experiment: Try different prompts to see what works best

Remember: TunaCode is here to help you code faster and better!""",
        "action": "Press Enter to complete the tutorial...",
    },
    "completion": {
        "title": "🎉 Tutorial Complete!",
        "content": """Congratulations! You're ready to use TunaCode.

Quick recap:
✅ Chat naturally with AI about code
✅ Use @ to reference files
✅ Try /help for commands
✅ Ask specific questions for better results

🚀 Ready to start coding? Just ask TunaCode anything!

Need help later? Use /quickstart to review this tutorial anytime.""",
        "action": "Press Enter to start using TunaCode...",
    },
}


def get_tutorial_steps() -> List[str]:
    """Get the ordered list of tutorial step IDs."""
    return ["welcome", "basic_chat", "file_operations", "commands", "best_practices", "completion"]
