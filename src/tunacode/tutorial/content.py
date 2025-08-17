"""Tutorial content definitions for the TunaCode tutorial system."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TutorialContent:
    """Tutorial content for a single step."""

    title: str
    description: str
    instructions: List[str]
    examples: List[str]
    tips: Optional[List[str]] = None
    next_action: Optional[str] = None


# Tutorial content library
TUTORIAL_STEPS: Dict[str, TutorialContent] = {
    "welcome": TutorialContent(
        title="Welcome to TunaCode!",
        description="Your AI-powered coding assistant is ready to help.",
        instructions=[
            "TunaCode helps you write, debug, and improve code using AI",
            "You can ask questions in natural language",
            "The AI can read and modify files in your project",
            "Let's learn the basics together!"
        ],
        examples=[
            "\"Help me write a Python function\"",
            "\"Explain what this code does\"",
            "\"Find bugs in my JavaScript\"",
            "\"Create a README for my project\""
        ],
        tips=[
            "Be specific in your requests",
            "Mention the programming language",
            "Ask for explanations when learning"
        ],
        next_action="Try asking TunaCode a simple question"
    ),

    "basic_interaction": TutorialContent(
        title="Basic AI Interaction",
        description="Learn how to communicate effectively with TunaCode.",
        instructions=[
            "Type your questions or requests in natural language",
            "TunaCode understands context from your conversation",
            "You can interrupt responses with Ctrl+C if needed",
            "Press Up arrow to edit your previous message"
        ],
        examples=[
            "\"Create a simple hello world program\"",
            "\"What's wrong with this error message?\"",
            "\"Refactor this function to be more efficient\"",
            "\"Add comments to explain this code\""
        ],
        tips=[
            "Use specific terms like 'function', 'class', 'variable'",
            "Mention file names if working with specific files",
            "Ask follow-up questions for clarification"
        ],
        next_action="Ask TunaCode to help with something in your project"
    ),

    "file_operations": TutorialContent(
        title="Working with Files",
        description="TunaCode can read, write, and analyze your project files.",
        instructions=[
            "Reference files by name in your requests",
            "TunaCode automatically tracks mentioned files",
            "You can ask to create, modify, or analyze files",
            "File changes are made directly to your project"
        ],
        examples=[
            "\"Read the package.json file\"",
            "\"Create a new Python module called utils.py\"",
            "\"Find all TODO comments in the src directory\"",
            "\"Update the main.py file with error handling\""
        ],
        tips=[
            "Use relative paths from your project root",
            "Be clear about what changes you want",
            "Review changes before accepting them"
        ],
        next_action="Try asking TunaCode to read or create a file"
    ),

    "commands": TutorialContent(
        title="Essential Commands",
        description="Learn the most useful TunaCode slash commands.",
        instructions=[
            "Commands start with / and provide special functionality",
            "Most commands can be tab-completed",
            "Use /help to see all available commands",
            "Commands work alongside natural language requests"
        ],
        examples=[
            "/help - Show all commands",
            "/clear - Clear conversation history",
            "/model - Switch AI models",
            "/branch - Create git branch for changes",
            "/quickstart - This tutorial!"
        ],
        tips=[
            "Try tab completion after typing /",
            "Use /compact to summarize long conversations",
            "Use /thoughts to see AI reasoning"
        ],
        next_action="Try the /help command"
    ),

    "best_practices": TutorialContent(
        title="Best Practices",
        description="Tips for getting the most out of TunaCode.",
        instructions=[
            "Start with clear, specific requests",
            "Break complex tasks into smaller steps",
            "Use /branch before making significant changes",
            "Ask for explanations to learn as you go"
        ],
        examples=[
            "\"Explain how this authentication system works\"",
            "\"Create a unit test for the login function\"",
            "\"Review this code for security issues\"",
            "\"Help me optimize this database query\""
        ],
        tips=[
            "TunaCode learns your coding style over time",
            "Use version control to track AI-suggested changes",
            "Ask for multiple approaches to compare options",
            "Don't hesitate to ask clarifying questions"
        ],
        next_action="Start working on your project with TunaCode!"
    ),

    "completion": TutorialContent(
        title="Tutorial Complete!",
        description="You're ready to use TunaCode effectively.",
        instructions=[
            "You've learned the basics of TunaCode",
            "Practice with your own projects to get comfortable",
            "Explore advanced features as you need them",
            "Remember: TunaCode is here to help, not replace your thinking"
        ],
        examples=[
            "Complex refactoring tasks",
            "Code review and optimization",
            "Learning new frameworks",
            "Debugging difficult issues"
        ],
        tips=[
            "Use /quickstart anytime to review basics",
            "Check the documentation for advanced features",
            "Join the community for tips and best practices"
        ],
        next_action="Happy coding with TunaCode! 🚀"
    )
}
