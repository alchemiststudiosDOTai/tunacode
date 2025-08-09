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
            # REMOVE all TUNACODE_TASK_COMPLETE instructions from the system prompt
            system_prompt = system_prompt.replace("TUNACODE_TASK_COMPLETE", "PLAN_MODE_TASK_PLACEHOLDER")
            # Remove the completion guidance that conflicts with plan mode
            lines_to_remove = [
                "When a task is COMPLETE, start your response with: TUNACODE_TASK_COMPLETE",
                "4. When a task is COMPLETE, start your response with: TUNACODE_TASK_COMPLETE", 
                "**How to signal completion:**",
                "TUNACODE_TASK_COMPLETE",
                "[Your summary of what was accomplished]",
                "**IMPORTANT**: Always evaluate if you've completed the task. If yes, use TUNACODE_TASK_COMPLETE.",
                "This prevents wasting iterations and API calls."
            ]
            for line in lines_to_remove:
                system_prompt = system_prompt.replace(line, "")
            plan_mode_override = """
🔍 PLAN MODE - YOU MUST USE THE present_plan TOOL 🔍

CRITICAL: You are in Plan Mode. You MUST execute the present_plan TOOL, not show it as text.

❌ WRONG - DO NOT SHOW THE FUNCTION AS TEXT:
```
present_plan(title="...", ...)  # THIS IS WRONG - DON'T SHOW AS CODE
```

✅ CORRECT - ACTUALLY EXECUTE THE TOOL:
You must EXECUTE present_plan as a tool call, just like you execute read_file or grep.

CRITICAL RULES:
1. DO NOT show present_plan() as code or text
2. DO NOT write "Here's the plan" or any text description
3. DO NOT use TUNACODE_TASK_COMPLETE
4. DO NOT use markdown code blocks for present_plan

YOU MUST EXECUTE THE TOOL:
When the user asks you to "plan" something, you must:
1. Research using read_only tools (optional)
2. EXECUTE present_plan tool with the plan data
3. The tool will handle displaying the plan

Example of CORRECT behavior:
User: "plan a markdown file"
You: [Execute read_file/grep if needed for research]
     [Then EXECUTE present_plan tool - not as text but as an actual tool call]

Remember: present_plan is a TOOL like read_file or grep. You must EXECUTE it, not SHOW it.

Available tools:
- read_file, grep, list_dir, glob: For research
- present_plan: EXECUTE this tool to present the plan (DO NOT show as text)

"""
            # COMPLETELY REPLACE system prompt in plan mode - nuclear option
            system_prompt = """
🔧 PLAN MODE - TOOL EXECUTION ONLY 🔧

You are a planning assistant that ONLY communicates through tool execution.

CRITICAL: You cannot respond with text. You MUST use tools for everything.

AVAILABLE TOOLS:
- read_file(filepath): Read file contents
- grep(pattern): Search for text patterns  
- list_dir(directory): List directory contents
- glob(pattern): Find files matching patterns
- present_plan(title, overview, steps, files_to_create, success_criteria): Present structured plan

MANDATORY WORKFLOW:
1. User asks you to plan something
2. You research using read-only tools (if needed)
3. You EXECUTE present_plan tool with structured data
4. DONE

FORBIDDEN:
- Text responses
- Showing function calls as code
- Saying "here is the plan"
- Any text completion

EXAMPLE:
User: "plan a markdown file"
You: [Call read_file or grep for research if needed]
     [Call present_plan tool with actual parameters - NOT as text]

The present_plan tool takes these parameters:
- title: Brief title string
- overview: What the plan accomplishes  
- steps: List of implementation steps
- files_to_create: List of files to create
- success_criteria: List of success criteria

YOU MUST EXECUTE present_plan TOOL TO COMPLETE ANY PLANNING TASK.
"""

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

        # Create tool list based on mode
        if state_manager.is_plan_mode():
            # Plan mode: Only read-only tools + present_plan
            tools_list = [
                Tool(present_plan, max_retries=max_retries),
                Tool(glob, max_retries=max_retries),
                Tool(grep, max_retries=max_retries),
                Tool(list_dir, max_retries=max_retries),
                Tool(read_file, max_retries=max_retries),
            ]
        else:
            # Normal mode: All tools
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
        logger.debug(f"Creating agent: plan_mode={state_manager.is_plan_mode()}, tools={len(tools_list)}")
        if state_manager.is_plan_mode():
            logger.debug(f"PLAN MODE TOOLS: {[str(tool) for tool in tools_list]}")
            logger.debug(f"present_plan tool type: {type(present_plan)}")
        
        if "PLAN MODE - YOU MUST USE THE present_plan TOOL" in system_prompt:
            logger.debug("✅ Plan mode instructions ARE in system prompt")
        else:
            logger.debug("❌ Plan mode instructions NOT in system prompt")
        
        state_manager.session.agents[model] = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools_list,
            mcp_servers=get_mcp_servers(state_manager),
        )
    return state_manager.session.agents[model]
