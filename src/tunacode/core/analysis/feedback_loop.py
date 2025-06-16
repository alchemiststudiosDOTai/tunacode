"""
Feedback loop handler for adaptive task execution.

Analyzes execution results and determines if additional tasks are needed,
enabling the think-act-think cycle.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ...exceptions import TooBroadPatternError
from ...types import ModelName
from ..state import StateManager


class FeedbackDecision(Enum):
    """Possible decisions after analyzing results."""

    COMPLETE = "complete"
    CONTINUE = "continue"
    RETRY = "retry"
    ERROR = "error"


@dataclass
class FeedbackResult:
    """Result of feedback analysis."""

    decision: FeedbackDecision
    new_tasks: Optional[List[dict]] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    reason: Optional[str] = None  # Added for better diagnostics


def _load_feedback_prompt() -> str:
    """Load the feedback prompt from file."""
    from pathlib import Path

    # Get the prompt file path
    current_dir = Path(__file__).parent.parent.parent
    prompt_path = current_dir / "prompts" / "architect_feedback.md"

    if prompt_path.exists():
        with open(prompt_path, "r") as f:
            return f.read()
    else:
        # Fallback prompt if file not found
        return """Analyze task results and decide: COMPLETE, CONTINUE, RETRY, or ERROR.
Return JSON: {"decision": "...", "summary": "...", "new_tasks": [...]}"""


FEEDBACK_PROMPT = _load_feedback_prompt()


class FeedbackLoop:
    """Handles the feedback loop for adaptive execution."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.max_iterations = 5
        self.attempted_strategies = set()
        self.retry_budget = {}  # Track retries per pattern to prevent infinite loops

    async def analyze_results(
        self,
        original_request: str,
        completed_tasks: List[Dict[str, Any]],
        results: List[Any],
        iteration: int,
        model: ModelName,
    ) -> FeedbackResult:
        """Analyze execution results and determine next steps."""
        from rich.console import Console

        console = Console()

        console.print(f"\n[dim][Feedback Loop] Analyzing results from iteration {iteration}[/dim]")

        # Quick checks for obvious completion/failure
        quick_result = self._quick_analysis(completed_tasks, results, iteration)
        if quick_result:
            return quick_result

        # Use LLM for complex analysis
        try:
            return await self._llm_analysis(original_request, completed_tasks, results, model)
        except Exception as e:
            console.print(f"[red][Feedback Loop] Analysis failed: {str(e)}[/red]")
            return FeedbackResult(
                decision=FeedbackDecision.ERROR, error_message=f"Feedback analysis failed: {str(e)}"
            )

    def _quick_analysis(
        self, completed_tasks: List[Dict[str, Any]], results: List[Any], iteration: int
    ) -> Optional[FeedbackResult]:
        """Quick deterministic analysis for common cases."""
        # Check iteration limit
        if iteration >= self.max_iterations:
            return FeedbackResult(
                decision=FeedbackDecision.COMPLETE,
                summary=f"Reached maximum iterations ({self.max_iterations}). Stopping execution.",
                reason="Max iterations reached",
            )

        # Check if all tasks succeeded
        all_succeeded = all(
            not isinstance(r, Exception) and (not hasattr(r, "error") or not r.error)
            for r in results
        )

        # If all read-only tasks succeeded, usually complete
        all_read_only = all(not task.get("mutate", False) for task in completed_tasks)
        if all_succeeded and all_read_only:
            return FeedbackResult(
                decision=FeedbackDecision.COMPLETE,
                summary="All read operations completed successfully.",
                reason="All tasks succeeded",
            )

        # Check for common errors
        for i, (task, result) in enumerate(zip(completed_tasks, results)):
            if isinstance(result, Exception):
                error_str = str(result).lower()

                # Handle TooBroadPatternError specifically
                if isinstance(result, TooBroadPatternError):
                    pattern = result.pattern
                    retry_key = f"pattern:{pattern}"

                    # Check retry budget (max 2 retries per pattern)
                    retries = self.retry_budget.get(retry_key, 0)
                    if retries >= 2:
                        return FeedbackResult(
                            decision=FeedbackDecision.ERROR,
                            error_message=f"Pattern '{pattern}' failed after maximum retries.",
                            summary="Search pattern too broad even after narrowing attempts.",
                            reason="Exceeded retry budget for broad pattern",
                        )

                    # Increment retry count
                    self.retry_budget[retry_key] = retries + 1

                    # Create a retry task with narrowed pattern
                    narrowed_pattern = self._narrow_pattern(pattern, task)
                    new_task = task.copy()
                    new_task["pattern"] = narrowed_pattern
                    new_task["description"] = (
                        f"Retry search with narrowed pattern: {narrowed_pattern}"
                    )

                    return FeedbackResult(
                        decision=FeedbackDecision.RETRY,
                        new_tasks=[new_task],
                        summary=f"Pattern '{pattern}' timed out. Retrying with narrowed pattern.",
                        reason=f"TooBroadPatternError: timeout after {result.timeout_seconds}s",
                    )

                elif "file not found" in error_str:
                    return FeedbackResult(
                        decision=FeedbackDecision.ERROR,
                        error_message="File not found. Cannot proceed.",
                        summary="Execution failed due to missing file.",
                        reason="FileNotFoundError",
                    )
                elif "permission denied" in error_str:
                    return FeedbackResult(
                        decision=FeedbackDecision.ERROR,
                        error_message="Permission denied. Cannot proceed.",
                        summary="Execution failed due to permissions.",
                        reason="PermissionError",
                    )

        return None

    async def _llm_analysis(
        self,
        original_request: str,
        completed_tasks: List[Dict[str, Any]],
        results: List[Any],
        model: ModelName,
    ) -> FeedbackResult:
        """Use LLM to analyze complex cases."""
        import json

        from rich.console import Console

        from ..agents.main import get_agent_tool

        console = Console()
        Agent, _ = get_agent_tool()

        # Build context for analysis
        context = self._build_context(original_request, completed_tasks, results)

        try:
            # Create analyzer agent
            analyzer = Agent(model=model, system_prompt=FEEDBACK_PROMPT, result_type=str, retries=2)

            # Get analysis
            result = await analyzer.run(context)
            response_text = result.data.strip()

            # Parse response
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            analysis = json.loads(response_text)

            # Convert to FeedbackResult
            decision_map = {
                "complete": FeedbackDecision.COMPLETE,
                "continue": FeedbackDecision.CONTINUE,
                "retry": FeedbackDecision.RETRY,
                "error": FeedbackDecision.ERROR,
            }

            decision = decision_map.get(
                analysis.get("decision", "").lower(), FeedbackDecision.ERROR
            )

            return FeedbackResult(
                decision=decision,
                new_tasks=analysis.get("new_tasks"),
                summary=analysis.get("summary", "Analysis complete."),
                reason=analysis.get("reason", "LLM analysis"),
            )

        except Exception as e:
            console.print(f"[yellow][Feedback Loop] LLM analysis failed: {str(e)}[/yellow]")
            # Fallback to simple completion
            return FeedbackResult(
                decision=FeedbackDecision.COMPLETE,
                summary="Assuming completion due to analysis failure.",
                reason="Analysis failure - defaulting to complete",
            )

    def _build_context(
        self, original_request: str, completed_tasks: List[Dict[str, Any]], results: List[Any]
    ) -> str:
        """Build context string for LLM analysis."""
        context_parts = [
            f"Original Request: {original_request}",
            f"\nCompleted Tasks ({len(completed_tasks)}):",
        ]

        # Add task summaries
        for i, (task, result) in enumerate(zip(completed_tasks, results)):
            task_desc = task.get("description", "Unknown task")

            # Determine result status
            if isinstance(result, TooBroadPatternError):
                status = f"TIMEOUT: Pattern '{result.pattern}' too broad (timeout: {result.timeout_seconds}s)"
            elif isinstance(result, Exception):
                status = f"FAILED: {str(result)}"
            elif hasattr(result, "error") and result.error:
                status = f"ERROR: {result.error}"
            elif hasattr(result, "result") and hasattr(result.result, "output"):
                # Truncate long outputs
                output = str(result.result.output)
                if len(output) > 200:
                    output = output[:200] + "..."
                status = f"SUCCESS: {output}"
            else:
                status = "COMPLETED"

            context_parts.append(f"{i + 1}. {task_desc} - {status}")

        # Add attempted strategies to prevent loops
        if self.attempted_strategies:
            context_parts.append(f"\nPreviously attempted: {', '.join(self.attempted_strategies)}")

        # Add retry budget information
        if self.retry_budget:
            retry_info = []
            for key, count in self.retry_budget.items():
                retry_info.append(f"{key}: {count} retries")
            context_parts.append(f"\nRetry attempts: {', '.join(retry_info)}")

        return "\n".join(context_parts)

    def record_strategy(self, strategy: str):
        """Record a strategy that was attempted."""
        self.attempted_strategies.add(strategy)

    def _narrow_pattern(self, broad_pattern: str, task: Dict[str, Any]) -> str:
        """
        Attempt to narrow a broad search pattern based on context.

        Args:
            broad_pattern: The pattern that was too broad
            task: The original task containing context

        Returns:
            A narrowed pattern that should be more specific
        """
        # Get additional context from the task
        path = task.get("path", "")
        file_type = task.get("file_type", "")

        # Simple heuristics to narrow patterns
        if len(broad_pattern) <= 2:
            # Very short patterns - add word boundaries or common prefixes
            if broad_pattern.isalpha():
                return f"\\b{broad_pattern}\\b"  # Word boundaries
            else:
                return f"^{broad_pattern}"  # Start of line

        # If searching in specific file types, we can be more aggressive
        if file_type:
            if file_type in [".py", ".js", ".ts", ".java", ".cpp", ".c"]:
                # For code files, look for function/variable usage
                if broad_pattern.isidentifier():
                    return f"(def |function |var |let |const |class ){broad_pattern}"

        # For paths, limit to specific directories
        if path and path != ".":
            # Already searching in a specific path, try to make pattern more specific
            if "." in broad_pattern:
                # Might be a file extension or method call
                parts = broad_pattern.split(".")
                if len(parts) == 2 and parts[1]:
                    return f"\\.{parts[1]}\\b"  # More specific file extension

        # Default: Add word boundaries if alphanumeric
        if broad_pattern.isalnum():
            return f"\\b{broad_pattern}\\b"

        # Last resort: limit to start of line or after whitespace
        return f"(^|\\s){broad_pattern}"

    async def summarize_results(
        self,
        original_request: str,
        completed_tasks: List[Dict[str, Any]],
        outputs: List[str],
        model: ModelName,
        primary_request_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Summarize the results of all completed tasks."""
        from ..agents.main import get_agent_tool

        Agent, _ = get_agent_tool()

        # Build context for summarization
        context_parts = [
            f"Original Request: {original_request}",
            f"\nCompleted {len(completed_tasks)} tasks.",
        ]
        
        # If we have primary request info, emphasize primary outputs
        if primary_request_info and primary_request_info.get("primary_outputs"):
            context_parts.append("\nPrimary Task Results (MOST IMPORTANT - directly answer the original request):")
            for i, primary_output in enumerate(primary_request_info["primary_outputs"]):
                task_desc = primary_output["task"]["description"]
                output = primary_output["output"]
                if len(output) > 2000:
                    output = output[:2000] + "... (truncated)"
                context_parts.append(f"\n{task_desc}:\n{output}")
            
            # Add follow-up outputs separately if any
            if len(outputs) > len(primary_request_info["primary_outputs"]):
                context_parts.append("\n\nAdditional Context from Follow-up Tasks:")
                # Add only non-primary outputs
                for i, output in enumerate(outputs):
                    if output and output not in [p["output"] for p in primary_request_info["primary_outputs"]]:
                        if len(output) > 500:
                            output = output[:500] + "... (truncated)"
                        context_parts.append(f"\nFollow-up Output:\n{output}")
        else:
            # Fall back to original behavior if no primary info
            context_parts.append("\nTask Outputs:")
            for i, output in enumerate(outputs):
                if output:
                    if len(output) > 1000:
                        output = output[:1000] + "... (truncated)"
                    context_parts.append(f"\nOutput {i + 1}:\n{output}")

        context = "\n".join(context_parts)

        # Create summarizer agent with improved prompt
        system_prompt = """You are summarizing the results of task execution.

CRITICAL: Your PRIMARY goal is to answer the original request. Focus on the primary task results that directly address what the user asked for.

Instructions:
1. First and foremost, answer the original request using the primary task results
2. If the user asked to see a specific file, show its contents from the primary output
3. Only mention follow-up/additional findings if they add important context
4. Do NOT let follow-up task outputs overshadow the main answer
5. Be concise but complete in answering the original request"""
        
        summarizer = Agent(
            model=model,
            system_prompt=system_prompt,
            result_type=str,
            retries=1,
        )

        try:
            result = await summarizer.run(context)
            return result.data.strip()
        except Exception:
            # Fallback summary
            return f"Completed {len(completed_tasks)} tasks successfully."
