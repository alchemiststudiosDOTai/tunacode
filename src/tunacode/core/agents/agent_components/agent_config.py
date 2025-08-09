"""Agent configuration and creation utilities."""

from pathlib import Path

from pydantic_ai import Agent

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.services.mcp import get_mcp_servers
from tunacode.tools.bash import bash
from tunacode.tools.present_plan import create_present_plan_tool
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
    import logging
    logger = logging.getLogger(__name__)
    
    if model not in state_manager.session.agents:
        logger.debug(f"Creating new agent for model {model}, plan_mode={state_manager.is_plan_mode()}")
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
            plan_mode_override = """
🔍 PLAN MODE - YOU MUST USE THE present_plan TOOL 🔍

CRITICAL: You are in Plan Mode. Special rules apply that OVERRIDE normal behavior.

❌ DO NOT USE TUNACODE_TASK_COMPLETE IN PLAN MODE ❌
Instead of using TUNACODE_TASK_COMPLETE, you MUST call the present_plan tool.

Available tools in Plan Mode:
- read_file, grep, list_dir, glob: For research only
- present_plan: THE ONLY WAY TO COMPLETE A PLANNING TASK (MANDATORY)

❌ FORBIDDEN ACTIONS:
- DO NOT use TUNACODE_TASK_COMPLETE
- DO NOT write plans in text format
- DO NOT use markdown formatting for plans  
- DO NOT say "Here's the plan" or similar
- DO NOT present plans as prose or summaries
- DO NOT use any write tools (they are blocked)

✅ REQUIRED ACTION:
When ready to present a plan, you MUST call:
present_plan(
    title="Create markdown file highlighting TunaCode functions",
    overview="Document the key functionalities and features of TunaCode",
    steps=["Research existing documentation", "Outline structure", "Write content sections", ...],
    files_to_create=["TUNACODE_FEATURES.md"],
    # optional: risks, tests, success_criteria, etc.
)

IMPORTANT: 
- Text responses will be IGNORED
- TUNACODE_TASK_COMPLETE will be IGNORED
- Only present_plan() tool call will be recognized

If the user asks you to "plan" something:
1. Research using read-only tools if needed
2. Call present_plan() with structured data
3. DO NOT write any text or use TUNACODE_TASK_COMPLETE

"""
            # Prepend to beginning of system prompt for maximum visibility
            system_prompt = plan_mode_override + system_prompt

        # Initialize tools that need state manager
        todo_tool = TodoTool(state_manager=state_manager)
        present_plan = create_present_plan_tool(state_manager)
        logger.debug(f"Tools initialized, present_plan available: {present_plan is not None}")

        # Add todo context if available
        try:
            current_todos = todo_tool.get_current_todos_sync()
            if current_todos != "No todos found":
                system_prompt += f'\n\n# Current Todo List\n\nYou have existing todos that need attention:\n\n{current_todos}\n\nRemember to check progress on these todos and update them as you work. Use todo("list") to see current status anytime.'
        except Exception as e:
            logger.warning(f"Warning: Failed to load todos: {e}")

        # Create agent with all tools
        tools_list = [
            Tool(bash, max_retries=max_retries),
            Tool(present_plan, max_retries=max_retries),
            Tool(glob, max_retries=max_retries),
            Tool(grep, max_retries=max_retries),
            Tool(list_dir, max_retries=max_retries),
            Tool(read_file, max_retries=max_retries),
            Tool(run_command, max_retries=max_retries),
            Tool(todo_tool._execute, max_retries=max_retries),
            Tool(update_file, max_retries=max_retries),
            Tool(write_file, max_retries=max_retries),
        ]
        
        # Log which tools are being registered
        logger.debug(f"Registering {len(tools_list)} tools for agent in plan_mode={state_manager.is_plan_mode()}")
        if "PLAN MODE - YOU MUST USE THE present_plan TOOL" in system_prompt:
            logger.debug("Plan mode instructions ARE in system prompt")
        else:
            logger.debug("Plan mode instructions NOT in system prompt")
        
        state_manager.session.agents[model] = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools_list,
            mcp_servers=get_mcp_servers(state_manager),
        )
    return state_manager.session.agents[model]
