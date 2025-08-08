"""Agent configuration and creation utilities."""

from pathlib import Path

from pydantic_ai import Agent

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.services.mcp import get_mcp_servers
from tunacode.tools.bash import bash
from tunacode.tools.exit_plan_mode import create_exit_plan_mode_tool
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.tools.run_command import run_command
from tunacode.tools.todo import TodoTool
from tunacode.tools.update_file import update_file
from tunacode.tools.write_file import write_file
from tunacode.types import ModelName, PydanticAgent

logger = get_logger(__name__)


def get_agent_tool():
    """Lazy import for Agent and Tool to avoid circular imports."""
    from pydantic_ai import Tool

    return Agent, Tool


def load_system_prompt(base_path: Path) -> str:
    """Load the system prompt from file."""
    prompt_path = base_path / "prompts" / "system.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback to system.txt if system.md not found
        prompt_path = base_path / "prompts" / "system.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            # Use a default system prompt if neither file exists
            return "You are a helpful AI assistant for software development tasks."


def load_tunacode_context() -> str:
    """Load TUNACODE.md context if it exists."""
    try:
        tunacode_path = Path.cwd() / "TUNACODE.md"
        if tunacode_path.exists():
            tunacode_content = tunacode_path.read_text(encoding="utf-8")
            if tunacode_content.strip():
                logger.info("📄 TUNACODE.md located: Loading context...")
                return "\n\n# Project Context from TUNACODE.md\n" + tunacode_content
            else:
                logger.info("📄 TUNACODE.md not found: Using default context")
        else:
            logger.info("📄 TUNACODE.md not found: Using default context")
    except Exception as e:
        logger.debug(f"Error loading TUNACODE.md: {e}")
    return ""


def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
    """Get existing agent or create new one for the specified model."""
    if model not in state_manager.session.agents:
        max_retries = state_manager.session.user_config.get("settings", {}).get("max_retries", 3)

        # Lazy import Agent and Tool
        Agent, Tool = get_agent_tool()

        # Load system prompt
        base_path = Path(__file__).parent.parent.parent.parent
        system_prompt = load_system_prompt(base_path)

        # Load TUNACODE.md context
        system_prompt += load_tunacode_context()

        # Add plan mode context if in plan mode
        if state_manager.is_plan_mode():
            system_prompt += """

🔍 PLAN MODE ACTIVE

You are currently in Plan Mode - a read-only research phase. Your objectives:

1. RESEARCH PHASE: Use only read-only tools to explore and understand the codebase
   - Available tools: read_file, grep, list_dir, glob
   - Write operations (write_file, update_file, bash, run_command) are BLOCKED

2. PLAN DEVELOPMENT: Based on your research, develop a comprehensive implementation plan

3. PLAN PRESENTATION: When ready, use the 'exit_plan_mode' tool to present your plan

Remember: No code changes can be made in Plan Mode. Focus on understanding the codebase structure, identifying the files that need changes, and creating a detailed implementation strategy.
"""

        # Initialize tools that need state manager
        todo_tool = TodoTool(state_manager=state_manager)
        exit_plan_mode = create_exit_plan_mode_tool(state_manager)

        # Add todo context if available
        try:
            current_todos = todo_tool.get_current_todos_sync()
            if current_todos != "No todos found":
                system_prompt += f'\n\n# Current Todo List\n\nYou have existing todos that need attention:\n\n{current_todos}\n\nRemember to check progress on these todos and update them as you work. Use todo("list") to see current status anytime.'
        except Exception as e:
            logger.warning(f"Warning: Failed to load todos: {e}")

        # Create agent with all tools
        state_manager.session.agents[model] = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=[
                Tool(bash, max_retries=max_retries),
                Tool(exit_plan_mode, max_retries=max_retries),
                Tool(glob, max_retries=max_retries),
                Tool(grep, max_retries=max_retries),
                Tool(list_dir, max_retries=max_retries),
                Tool(read_file, max_retries=max_retries),
                Tool(run_command, max_retries=max_retries),
                Tool(todo_tool._execute, max_retries=max_retries),
                Tool(update_file, max_retries=max_retries),
                Tool(write_file, max_retries=max_retries),
            ],
            mcp_servers=get_mcp_servers(state_manager),
        )
    return state_manager.session.agents[model]
