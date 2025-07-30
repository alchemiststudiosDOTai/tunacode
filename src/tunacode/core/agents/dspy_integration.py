"""DSPy Integration for TunaCode - Enhanced Tool Selection and Task Planning.

This module integrates DSPy's optimized prompts and tool selection logic
into TunaCode's agent system for 3x performance improvements.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager

logger = get_logger(__name__)


class DSPyIntegration:
    """Integrates DSPy optimization into TunaCode's agent system."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self._dspy_agent = None
        self._tool_selection_prompt = None
        self._task_planning_prompt = None
        self._load_prompts()

    def _load_prompts(self):
        """Load DSPy-optimized prompts from files."""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"

        try:
            # Load tool selection prompt
            tool_selection_path = prompts_dir / "dspy_tool_selection.md"
            if tool_selection_path.exists():
                self._tool_selection_prompt = tool_selection_path.read_text(encoding="utf-8")
                logger.debug("Loaded DSPy tool selection prompt")

            # Load task planning prompt
            task_planning_path = prompts_dir / "dspy_task_planning.md"
            if task_planning_path.exists():
                self._task_planning_prompt = task_planning_path.read_text(encoding="utf-8")
                logger.debug("Loaded DSPy task planning prompt")
        except Exception as e:
            logger.error(f"Failed to load DSPy prompts: {e}")

    def get_dspy_agent(self, api_key: Optional[str] = None):
        """Get or create the DSPy agent instance."""
        if self._dspy_agent is None:
            try:
                # Import DSPy components
                from tunacode.core.agents.dspy_tunacode import create_optimized_agent

                # Use API key from environment or config
                if not api_key:
                    api_key = os.getenv(
                        "OPENROUTER_API_KEY"
                    ) or self.state_manager.session.user_config.get("env", {}).get(
                        "OPENROUTER_API_KEY"
                    )

                if api_key:
                    self._dspy_agent = create_optimized_agent(api_key)
                    logger.info("DSPy agent initialized successfully")
                else:
                    logger.warning("No OpenRouter API key found for DSPy optimization")
            except Exception as e:
                logger.error(f"Failed to initialize DSPy agent: {e}")

        return self._dspy_agent

    def enhance_system_prompt(self, base_prompt: str) -> str:
        """Enhance the system prompt with DSPy optimizations."""
        if not self._tool_selection_prompt:
            return base_prompt

        # Extract the learned patterns from DSPy prompts
        enhanced_sections = []

        # Add DSPy tool selection insights
        enhanced_sections.append("\n\n# DSPy-Optimized Tool Selection Patterns\n")
        enhanced_sections.append("**Based on learned optimization patterns:**\n")
        enhanced_sections.append("- Always batch 3-4 read-only tools for parallel execution")
        enhanced_sections.append("- Group grep, list_dir, glob, read_file operations together")
        enhanced_sections.append("- Execute write/modify operations sequentially")
        enhanced_sections.append("- Use Chain of Thought reasoning for tool selection\n")

        # Add specific examples from DSPy prompt
        if "Example" in self._tool_selection_prompt:
            enhanced_sections.append("\n## Optimal Tool Batching Examples:\n")
            # Extract examples section
            examples_match = re.search(
                r"### Example.*?(?=###|\Z)", self._tool_selection_prompt, re.DOTALL
            )
            if examples_match:
                enhanced_sections.append(examples_match.group(0))

        return base_prompt + "".join(enhanced_sections)

    def should_use_task_planner(self, user_request: str) -> bool:
        """Determine if the request is complex enough for task planning."""
        complex_indicators = [
            "implement",
            "create",
            "build",
            "refactor",
            "add feature",
            "fix all",
            "update multiple",
            "migrate",
            "integrate",
            "debug",
            "optimize performance",
            "authentication",
            "setup",
        ]

        request_lower = user_request.lower()

        # Check for multiple files
        file_pattern = r"\b\w+\.\w+\b"
        files_mentioned = len(re.findall(file_pattern, user_request)) > 2

        # Check for complex keywords
        has_complex_keyword = any(indicator in request_lower for indicator in complex_indicators)

        # Check for multiple operations
        operation_words = ["and", "then", "also", "after", "before", "plus"]
        has_multiple_ops = sum(1 for word in operation_words if word in request_lower) >= 2

        return files_mentioned or has_complex_keyword or has_multiple_ops

    def optimize_tool_selection(
        self, user_request: str, tools_to_execute: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Optimize tool selection using DSPy patterns.

        Returns tool calls organized in optimal batches for parallel execution.
        """
        if not tools_to_execute:
            return []

        # Try to use DSPy agent if available
        dspy_agent = self.get_dspy_agent()
        if dspy_agent:
            try:
                result = dspy_agent(user_request, self.state_manager.session.cwd or ".")
                if hasattr(result, "tool_batches") and result.tool_batches:
                    return result.tool_batches
            except Exception as e:
                logger.debug(f"DSPy optimization failed, using fallback: {e}")

        # Fallback: Apply DSPy-learned patterns manually
        return self._apply_dspy_patterns(tools_to_execute)

    def _apply_dspy_patterns(self, tools: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Apply DSPy-learned batching patterns manually."""
        from tunacode.constants import READ_ONLY_TOOLS

        batches = []
        current_batch = []

        for tool in tools:
            tool_name = tool.get("tool", "")

            if tool_name in READ_ONLY_TOOLS:
                current_batch.append(tool)
                # Optimal batch size is 3-4 tools
                if len(current_batch) >= 4:
                    batches.append(current_batch)
                    current_batch = []
            else:
                # Flush current batch if any
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                # Add write/execute tool as single batch
                batches.append([tool])

        # Add remaining tools
        if current_batch:
            batches.append(current_batch)

        return batches

    def get_task_breakdown(self, complex_request: str) -> Optional[Dict[str, Any]]:
        """Get task breakdown for complex requests using DSPy."""
        dspy_agent = self.get_dspy_agent()
        if not dspy_agent:
            return None

        try:
            result = dspy_agent(complex_request, self.state_manager.session.cwd or ".")
            if result.get("is_complex") and result.get("subtasks"):
                return {
                    "subtasks": result["subtasks"],
                    "total_tool_calls": result.get("total_tool_calls", 0),
                    "requires_todo": result.get("requires_todo", False),
                    "parallelization_opportunities": result.get("parallelization_opportunities", 0),
                }
        except Exception as e:
            logger.error(f"Failed to get task breakdown: {e}")

        return None

    def format_chain_of_thought(self, request: str, tools: List[str]) -> str:
        """Format a Chain of Thought reasoning for tool selection."""
        reasoning = f"Let's think step by step about '{request}':\n"

        if "search" in request.lower() or "find" in request.lower():
            reasoning += "1. This requires searching for information\n"
            reasoning += "2. I'll use grep for content search and glob for file patterns\n"
            reasoning += "3. These read-only tools can be executed in parallel\n"
        elif "read" in request.lower() or "show" in request.lower():
            reasoning += "1. This requires reading file contents\n"
            reasoning += "2. I'll batch multiple read_file operations together\n"
            reasoning += "3. All reads can happen in parallel for speed\n"
        elif "fix" in request.lower() or "update" in request.lower():
            reasoning += "1. First, I need to understand the current state\n"
            reasoning += "2. I'll search and read relevant files in parallel\n"
            reasoning += "3. Then make modifications sequentially for safety\n"

        return reasoning
