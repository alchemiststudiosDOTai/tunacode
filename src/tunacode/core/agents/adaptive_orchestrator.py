"""
Adaptive orchestrator for architect mode.

Implements the hybrid approach with deterministic analysis, constrained planning,
parallel execution, and feedback loops.
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...types import AgentRun, ModelName, ResponseState
from ..analysis import ConstrainedPlanner, FeedbackDecision, FeedbackLoop
from ..analysis.hybrid_request_analyzer import HybridRequestAnalyzer
from ..state import StateManager
from . import main as agent_main
from .context_provider import ContextProvider
from .directory_indexer import DirectoryIndexer
from .parallel_executor import ParallelExecutor
from .readonly import ReadOnlyAgent


@dataclass
class ExecutionResult:
    """Result of executing a task."""

    task: Dict[str, Any]
    result: Any
    duration: float
    error: Optional[Exception] = None


class AdaptiveOrchestrator:
    """Orchestrates task execution with adaptive planning and parallel execution."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.analyzer = HybridRequestAnalyzer(model=state_manager.session.current_model)
        self.planner = ConstrainedPlanner(state_manager)
        self.feedback_loop = FeedbackLoop(state_manager)
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Timeouts
        self.task_timeout = 30  # 30s per task
        self.total_timeout = 120  # 2min total

        # Initialize context provider and directory indexer
        project_root = Path.cwd()  # Or get from state_manager if available
        self.context_provider = ContextProvider(project_root)
        self.directory_indexer = DirectoryIndexer(self.context_provider)
        self.parallel_executor = ParallelExecutor(self.context_provider)

    async def run(self, request: str, model: ModelName | None = None) -> List[AgentRun]:
        """Execute a request with adaptive planning and feedback loops.

        Implements the Frame → Think → Act → Loop pattern:
        1. Frame: Establish context (who, where, what)
        2. Think: Analyze request and plan tasks
        3. Act: Execute tasks
        4. Loop: Analyze results and adapt
        """
        from rich.console import Console

        console = Console()

        model = model or self.state.session.current_model
        overall_start_time = time.time()
        start_time = overall_start_time

        console.print("\n[cyan]Adaptive Orchestrator: Framing context...[/cyan]")

        try:
            # Step 1: FRAME - Establish context with optimized scanning
            frame_start_time = time.time()

            # Build initial index with shallow scanning
            await self.directory_indexer.build_index(max_depth=2)

            # Prefetch modified files for faster access
            modified_files = await self.context_provider.get_modified_files()
            if modified_files:
                console.print(f"[dim]Found {len(modified_files)} modified files[/dim]")

            project_context = self.analyzer.project_context.detect_context()
            frame_duration = time.time() - frame_start_time
            console.print(f"[bold yellow]FRAME duration: {frame_duration:.4f}s[/bold yellow]")

            sources = (
                ", ".join(project_context.source_dirs[:2])
                if project_context.source_dirs
                else "unknown"
            )
            framework = f"({project_context.framework})" if project_context.framework else ""
            console.print(
                f"[dim]Project: {project_context.project_type.value} {framework} | Sources: {sources}[/dim]"
            )

            # Step 2: THINK - Get tasks from LLM planner
            think_start_time = time.time()
            tasks = await self._get_initial_tasks(request, model)
            think_duration = time.time() - think_start_time
            console.print(f"[bold yellow]THINK duration: {think_duration:.4f}s[/bold yellow]")

            if not tasks:
                console.print("[yellow]No tasks generated. Falling back to regular mode.[/yellow]")
                return []

            console.print(f"\n[cyan]Executing plan with {len(tasks)} initial tasks...[/cyan]")

            # Step 3 & 4: ACT & LOOP - Execute with feedback loop
            act_loop_start_time = time.time()
            result = await self._execute_with_feedback(request, tasks, model, start_time)
            act_loop_duration = time.time() - act_loop_start_time
            console.print(
                f"[bold yellow]ACT & LOOP duration: {act_loop_duration:.4f}s[/bold yellow]"
            )
            overall_duration = time.time() - overall_start_time
            console.print(
                f"[bold green]Overall Orchestrator duration: {overall_duration:.4f}s[/bold green]"
            )

            # Log performance stats
            stats = self.get_performance_stats()
            console.print(
                f"[dim]Cache hits: {stats['cache']['cache_hits']}, misses: {stats['cache']['cache_misses']}[/dim]"
            )
            console.print(
                f"[dim]Files read: {stats['cache']['files_read']}, dirs scanned: {stats['cache']['dirs_scanned']}[/dim]"
            )

            return result

        except asyncio.TimeoutError:
            console.print("[red]Orchestrator timeout. Falling back to regular mode.[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Orchestrator error: {str(e)}. Falling back to regular mode.[/red]")
            return []

    async def _get_initial_tasks(
        self, request: str, model: ModelName
    ) -> Optional[List[Dict[str, Any]]]:
        """Get tasks from LLM planner."""
        from rich.console import Console

        console = Console()

        # Just use LLM planning for everything
        console.print("[dim]Using LLM planner[/dim]")
        try:
            # Build context from session state
            context_parts = []

            # Add recent conversation history to help resolve references like "that file"
            if self.state.session.messages:
                # Get last 3 message pairs (user + assistant)
                recent_messages = []
                for msg in self.state.session.messages[-6:]:  # Get last 6 messages (3 exchanges)
                    if msg.role == "user":
                        recent_messages.append(f"User: {msg.content[:100]}...")
                    elif msg.role == "assistant" and hasattr(msg, "content") and msg.content:
                        # Extract key information from assistant responses
                        content_str = str(msg.content)
                        # Look for file paths mentioned in responses
                        import re
                        file_paths = re.findall(r'src/[\w/]+\.py|[\w/]+\.py|[\w/]+\.md', content_str)
                        if file_paths:
                            recent_messages.append(f"Assistant found files: {', '.join(set(file_paths[:3]))}")
                        elif len(content_str) > 100:
                            recent_messages.append(f"Assistant: {content_str[:100]}...")
                
                if recent_messages:
                    context_parts.append("Recent conversation:")
                    context_parts.extend(recent_messages)

            # Add files in context
            if self.state.session.files_in_context:
                files_list = list(self.state.session.files_in_context)
                context_parts.append(f"Files currently in context: {', '.join(files_list)}")

            # Add recent tool calls if any
            if self.state.session.tool_calls:
                recent_tools = [tc["tool"] for tc in self.state.session.tool_calls[-3:]]
                context_parts.append(f"Recent operations: {', '.join(recent_tools)}")

            context = "\n".join(context_parts) if context_parts else None
            
            # Debug logging to see the context being passed
            if context:
                console.print(f"[yellow][DEBUG][/yellow] Context being passed to planner:")
                console.print(f"[yellow][DEBUG][/yellow] {context[:500]}...")

            plan_start_time = time.time()
            task_objects = await self.planner.plan(request, model, context=context)
            plan_duration = time.time() - plan_start_time
            console.print(
                f"[bold yellow]  --> Planner.plan duration: {plan_duration:.4f}s[/bold yellow]"
            )
            # Convert Task objects to dicts
            return [
                {
                    "id": t.id,
                    "description": t.description,
                    "mutate": t.mutate,
                    "tool": t.tool,
                    "args": t.args,
                }
                for t in task_objects
            ]
        except Exception as e:
            console.print(f"[yellow]Planning failed: {str(e)}[/yellow]")
            return None

    async def _execute_with_feedback(
        self, request: str, initial_tasks: List[Dict[str, Any]], model: ModelName, start_time: float
    ) -> List[AgentRun]:
        """Execute tasks with feedback loop - the ACT and LOOP phases."""
        from rich.console import Console

        console = Console()

        # all_results = []  # Not used after refactoring
        completed_tasks = []
        remaining_tasks = initial_tasks
        iteration = 0
        iteration_start_time = time.time()

        # Track aggregated output from all tasks with metadata
        aggregated_outputs = []
        has_any_output = False
        
        # Track primary request info
        primary_request_info = {
            "original_request": request,
            "primary_task_ids": [t["id"] for t in initial_tasks],  # Track which tasks are primary
            "primary_outputs": [],  # Store outputs from primary tasks separately
        }

        # Track findings for adaptive task generation
        findings = {
            "interesting_files": [],
            "directories_found": [],
            "patterns_detected": [],
            "explored_directories": set(),  # Track directories we've already explored
        }

        response_state = ResponseState()

        while remaining_tasks and iteration < self.feedback_loop.max_iterations:
            # Check total timeout
            if time.time() - start_time > self.total_timeout:
                console.print("[yellow]Total execution timeout reached[/yellow]")
                break

            console.print(
                f"\n[dim]Iteration {iteration + 1}: Executing {len(remaining_tasks)} tasks[/dim]"
            )

            # Execute current batch
            batch_start_time = time.time()
            batch_results = await self._execute_task_batch(remaining_tasks, model)
            batch_duration = time.time() - batch_start_time
            console.print(
                f"[bold magenta]  --> Batch execution duration: {batch_duration:.4f}s[/bold magenta]"
            )

            # Convert ExecutionResults to AgentRuns and collect
            for exec_result in batch_results:
                if exec_result.error:
                    console.print(f"[red]Task failed: {exec_result.task['description']}[/red]")
                    console.print(f"[red]Error: {str(exec_result.error)}[/red]")

                # Collect outputs instead of adding results directly
                if (
                    exec_result.result
                    and hasattr(exec_result.result, "result")
                    and exec_result.result.result
                ):
                    if (
                        hasattr(exec_result.result.result, "output")
                        and exec_result.result.result.output
                    ):
                        output = exec_result.result.result.output
                        aggregated_outputs.append(output)
                        has_any_output = True
                        response_state.has_user_response = True
                        
                        # Track primary task outputs separately
                        task_id = exec_result.task.get("id")
                        if task_id in primary_request_info["primary_task_ids"]:
                            primary_request_info["primary_outputs"].append({
                                "task": exec_result.task,
                                "output": output
                            })
                        # Also track if this is the first iteration (all first iteration tasks are primary)
                        elif iteration == 0:
                            primary_request_info["primary_outputs"].append({
                                "task": exec_result.task,
                                "output": output
                            })

                completed_tasks.append(exec_result.task)

                # Extract findings from successful tasks
                if exec_result.result and not exec_result.error:
                    self._extract_findings(exec_result, findings)

                    # Track files created/modified/read for context
                    tool = exec_result.task.get("tool")
                    if tool in ["write_file", "update_file", "read_file"]:
                        file_path = exec_result.task.get("args", {}).get("file_path")
                        if file_path:
                            # Ensure files_in_context is a set (fix for deserialization issues)
                            if not hasattr(self.state.session.files_in_context, 'add'):
                                # Convert to set if it's not already
                                self.state.session.files_in_context = set(
                                    self.state.session.files_in_context or []
                                )
                            self.state.session.files_in_context.add(file_path)

            # THINK phase of the loop - analyze and adapt
            # Get project context for smarter decisions
            project_context = self.analyzer.project_context.detect_context()

            # Generate adaptive follow-up tasks based on findings
            if iteration < self.feedback_loop.max_iterations - 1:  # Not last iteration
                followup_start_time = time.time()
                # Add original request to findings for context-aware follow-ups
                findings["original_request"] = request
                findings["primary_task_descriptions"] = [t["description"] for t in initial_tasks[:3]]
                followup_tasks = self.analyzer.task_generator.generate_followup_tasks(
                    findings, project_context
                )
                followup_duration = time.time() - followup_start_time
                console.print(
                    f"[bold magenta]  --> Follow-up task generation duration: {followup_duration:.4f}s[/bold magenta]"
                )

                if followup_tasks:
                    # Task generator already returns dicts, just limit them
                    new_tasks = followup_tasks[:3]  # Limit follow-ups per iteration

                    if new_tasks:
                        console.print(
                            f"[dim]Generated {len(new_tasks)} adaptive follow-up tasks[/dim]"
                        )
                        remaining_tasks = new_tasks
                    else:
                        # Use original feedback mechanism
                        feedback_start_time = time.time()
                        feedback = await self.feedback_loop.analyze_results(
                            request, completed_tasks, batch_results, iteration + 1, model
                        )
                        feedback_duration = time.time() - feedback_start_time
                        console.print(
                            f"[bold magenta]  --> Feedback analysis duration: {feedback_duration:.4f}s[/bold magenta]"
                        )

                        console.print(
                            f"[dim]Feedback: {feedback.decision.value} - {feedback.summary}[/dim]"
                        )

                        if feedback.decision == FeedbackDecision.COMPLETE:
                            break
                        elif feedback.decision == FeedbackDecision.ERROR:
                            console.print(
                                f"[red]Stopping due to error: {feedback.error_message}[/red]"
                            )
                            break
                        elif feedback.new_tasks:
                            remaining_tasks = feedback.new_tasks
                        else:
                            break
                else:
                    break
            else:
                remaining_tasks = []  # No more iterations

            iteration += 1
            iteration_duration = time.time() - iteration_start_time
            console.print(
                f"[bold cyan]Iteration {iteration} duration: {iteration_duration:.4f}s[/bold cyan]"
            )
            iteration_start_time = time.time()

        console.print(
            f"\n[green]Adaptive execution completed after {iteration + 1} iterations[/green]"
        )

        # If we have any output, consolidate and return it
        if has_any_output:
            summary_start_time = time.time()
            # Pass primary request info for better summarization
            final_summary = await self.feedback_loop.summarize_results(
                request, completed_tasks, aggregated_outputs, model, primary_request_info
            )
            summary_duration = time.time() - summary_start_time
            console.print(
                f"[bold yellow]  --> Final summary generation duration: {summary_duration:.4f}s[/bold yellow]"
            )

            class ConsolidatedResult:
                def __init__(self, output: str):
                    self.output = output

            class ConsolidatedRun:
                def __init__(self, output: str):
                    self.result = ConsolidatedResult(output)
                    self.response_state = response_state

            return [ConsolidatedRun(final_summary)]
        elif completed_tasks:
            # No output from tasks, create a summary
            summary_parts = [f"Completed {len(completed_tasks)} tasks:"]
            for task in completed_tasks[:5]:  # Show first 5
                summary_parts.append(f"• {task['description']}")
            if len(completed_tasks) > 5:
                summary_parts.append(f"• ... and {len(completed_tasks) - 5} more")

            class SummaryResult:
                def __init__(self, output: str):
                    self.output = output

            class SummaryRun:
                def __init__(self, output: str):
                    self.result = SummaryResult(output)
                    self.response_state = response_state

            return [SummaryRun("\n".join(summary_parts))]

        return []

    async def _execute_task_batch(
        self, tasks: List[Dict[str, Any]], model: ModelName
    ) -> List[ExecutionResult]:
        """Execute a batch of tasks with parallelization."""
        from rich.console import Console

        console = Console()

        # Optimize tasks before execution
        optimized_tasks = []
        for task in tasks:
            optimized = await self._optimize_task_for_context(task)
            if optimized:  # Skip None (ignored) tasks
                optimized_tasks.append(optimized)

        if not optimized_tasks:
            return []

        # Separate read and write tasks
        read_tasks = [t for t in optimized_tasks if not t.get("mutate", False)]
        write_tasks = [t for t in optimized_tasks if t.get("mutate", False)]

        results = []

        # Execute read tasks using the parallel executor for maximum efficiency
        if read_tasks:
            if len(read_tasks) > 1:
                console.print(f"[dim]Executing {len(read_tasks)} read tasks in parallel...[/dim]")

            # Use parallel executor for batch operations
            console.print(f"[yellow][DEBUG][/yellow] Executing {len(read_tasks)} read tasks in parallel")
            console.print(f"[yellow][DEBUG][/yellow] Read tasks: {[t['description'] for t in read_tasks]}")
            parallel_results = await self.parallel_executor.execute_batch(read_tasks)
            console.print(f"[yellow][DEBUG][/yellow] Got {len(parallel_results)} parallel results")

            # Convert ParallelTaskResult to ExecutionResult
            for i, (task, parallel_result) in enumerate(zip(read_tasks, parallel_results)):
                console.print(f"[yellow][DEBUG][/yellow] Processing read task #{i+1}: {task['description']}")
                
                if parallel_result.success:
                    console.print(f"[yellow][DEBUG][/yellow] Read task succeeded")
                    # Log the actual result structure
                    console.print(f"[yellow][DEBUG][/yellow] Parallel result: {str(parallel_result.result)[:200]}...")
                    
                    # Create a mock AgentRun-like object
                    class MockResult:
                        def __init__(self, output):
                            self.output = output

                    class MockAgentRun:
                        def __init__(self, result):
                            self.result = result

                    output_content = parallel_result.result.get("output", "")
                    console.print(f"[yellow][DEBUG][/yellow] Extracted output length: {len(output_content)}")
                    
                    agent_run = MockAgentRun(MockResult(output_content))
                    results.append(
                        ExecutionResult(
                            task=task,
                            result=agent_run,
                            duration=parallel_result.duration,
                            error=None,
                        )
                    )
                else:
                    console.print(f"[red][DEBUG][/red] Read task failed: {parallel_result.error}")
                    results.append(
                        ExecutionResult(
                            task=task,
                            result=None,
                            duration=parallel_result.duration,
                            error=Exception(parallel_result.error),
                        )
                    )

        # Execute write tasks sequentially
        for task in write_tasks:
            console.print(f"[dim]Executing write task: {task['description']}[/dim]")
            try:
                result = await self._execute_single_task(task, model)
                console.print(f"[yellow][DEBUG][/yellow] Write task result: {'success' if result.error is None else 'error'}")
                results.append(result)
            except Exception as e:
                console.print(f"[red][DEBUG][/red] Write task error: {str(e)}")
                results.append(ExecutionResult(task=task, result=None, duration=0, error=e))

        # Remove this line since we don't have a start_time for the batch
        console.print(f"[bold green]  --> _execute_task_batch completed[/bold green]")
        return results

    async def _execute_single_task(self, task: Dict[str, Any], model: ModelName) -> ExecutionResult:
        """Run a single task and capture its result."""
        start_time = time.time()
        error = None
        agent_run = None
        try:
            agent_run = await self._run_task(task, model)
        except Exception as e:
            error = e
        finally:
            duration = time.time() - start_time
            # The timer for the individual task is printed in _run_task,
            # but we capture duration here for the ExecutionResult.
            return ExecutionResult(task=task, result=agent_run, duration=duration, error=error)

    async def _run_task(self, task: Dict[str, Any], model: ModelName) -> AgentRun:
        """Runs a single task using the appropriate agent."""
        from rich.console import Console

        console = Console()

        task_description = self._format_tool_request(task)
        console.print(f"[cyan]› {task_description}[/cyan]")
        start_time = time.time()

        # Use ReadOnlyAgent for read-only tasks
        if not task.get("mutate"):
            agent = ReadOnlyAgent(model, self.state)
            agent_run = await agent.process_request(task_description)
        else:
            # For mutating tasks, use the main agent
            # Format the request as a tool call
            tool_args_str = json.dumps(task["args"], indent=2)
            tool_request = f'Please use the {task["tool"]} tool with these arguments:\n{tool_args_str}'
            
            agent_run = await agent_main.process_request(
                model=model,
                message=tool_request,
                state_manager=self.state,
            )

        duration = time.time() - start_time
        console.print(
            f"[bold blue]    --> Task '{task_description}' duration: {duration:.4f}s[/bold blue]"
        )
        return agent_run

    async def _optimize_task_for_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize a task based on context and ignore patterns."""
        tool = task.get("tool")
        args = task.get("args", {})

        # Optimize list_dir tasks to use cached snapshots
        if tool == "list_dir":
            directory = args.get("directory", ".")
            dir_path = Path(directory).resolve()

            # Check if this directory should be ignored
            if self.context_provider.ignore_patterns.should_ignore(dir_path):
                # Skip this task entirely
                return None

            # Use shallow snapshot instead of full directory listing
            snapshot = await self.context_provider.get_shallow_snapshot(dir_path)

            # Update task to use cached information
            task["cached_snapshot"] = snapshot

        # Optimize grep tasks to skip ignored paths
        elif tool == "grep":
            directory = args.get("directory", ".")
            dir_path = Path(directory).resolve()

            # Get relevant files from index
            query = args.get("pattern", "")
            relevant_files = await self.directory_indexer.get_relevant_files(query)

            # Limit search scope
            if relevant_files:
                task["search_scope"] = [str(f.path) for f in relevant_files[:20]]

        # Optimize read_file tasks
        elif tool == "read_file":
            file_path = args.get("file_path", "")
            if file_path:
                path = Path(file_path).resolve()

                # Check if file should be ignored
                if self.context_provider.ignore_patterns.should_ignore(path):
                    return None

        return task

    def _format_tool_request(self, task: Dict[str, Any]) -> str:
        """Format a tool request for display."""
        tool = task.get("tool")
        args = task.get("args", {})

        # Format based on tool type
        if tool == "read_file":
            return f"Read the file {args.get('file_path', '')}"
        elif tool == "grep":
            pattern = args.get("pattern", "")
            directory = args.get("directory", ".")
            include_files = args.get("include_files", "")
            use_regex = args.get("use_regex", False)

            # Build a more detailed request
            request_parts = [f"Search for '{pattern}' in {directory}"]
            if include_files:
                request_parts.append(f"in files matching {include_files}")
            if use_regex:
                request_parts.append("using regex")

            return " ".join(request_parts)
        elif tool == "list_dir":
            directory = args.get("directory", ".")
            return f"List the contents of directory {directory}"
        elif tool == "write_file":
            file_path = args.get("file_path", "")
            content = args.get("content", "")
            if content:
                # Include the actual content in the request
                return f"Create file {file_path} with the following content:\n{content}"
            else:
                return f"Create file {file_path} with appropriate content"
        elif tool == "update_file":
            file_path = args.get("file_path", "")
            target = args.get("target", "")
            patch = args.get("patch", "")
            if target and patch:
                return f"Update {file_path} by replacing '{target}' with '{patch}'"
            else:
                return f"Update {file_path} as described: {task['description']}"
        elif tool == "run_command":
            return f"Run command: {args.get('command', '')}"
        elif tool == "bash":
            command = args.get("command", "")
            # Handle special cases for better commands
            if "ls -R" in command:
                # Replace recursive ls with list_dir tool
                return "Use list_dir tool to list directory contents"
            elif command.strip() in ["ls", "ls -la", "ls -l"]:
                # Simple ls commands should use list_dir
                return "Use list_dir tool to list current directory"
            return f"Execute bash command: {command}"
        elif tool == "analyze":
            # For analyze tasks, pass through the original request
            original_request = args.get("request", task["description"])
            return original_request
        else:
            return task["description"]

    def _extract_findings(self, exec_result: ExecutionResult, findings: Dict[str, any]) -> None:
        """Extract interesting findings from task execution results."""
        task = exec_result.task
        tool = task.get("tool")

        # Extract output text if available
        output_text = ""
        if exec_result.result and hasattr(exec_result.result, "result"):
            result = exec_result.result.result
            if hasattr(result, "output"):
                output_text = str(result.output)

        if not output_text:
            return

        # Extract findings based on tool type
        if tool == "list_dir":
            # Mark this directory as explored
            directory = task.get("args", {}).get("directory", ".")
            findings["explored_directories"].add(directory)
            # Look for interesting files and directories
            lines = output_text.split("\n")
            for line in lines:
                line = line.strip()
                if "[DIR]" in line:
                    # Extract directory name
                    dir_name = line.split("[DIR]")[0].strip()
                    if dir_name and not dir_name.startswith("."):
                        findings["directories_found"].append(dir_name)
                elif "[FILE]" in line:
                    # Extract file name
                    file_name = line.split("[FILE]")[0].strip()
                    # Look for interesting files
                    if any(
                        pattern in file_name.lower()
                        for pattern in [
                            "config",
                            "settings",
                            "main",
                            "index",
                            "app",
                            "server",
                            "api",
                        ]
                    ):
                        findings["interesting_files"].append(file_name)

        elif tool == "grep":
            # Track that we found matches for this pattern
            pattern = task.get("args", {}).get("pattern", "")
            if "matches" in output_text.lower() or "found" in output_text.lower():
                findings["patterns_detected"].append(pattern)

        elif tool == "read_file":
            # Look for imports, dependencies, or other interesting patterns
            # file_path = task.get("args", {}).get("file_path", "")  # Not used yet

            # For package.json, pyproject.toml, etc., we could extract dependencies
            # but keeping it simple for now
            if "import" in output_text or "require" in output_text:
                # This file has imports, might be worth exploring imports
                findings["interesting_files"].extend(
                    [
                        f
                        for f in output_text.split()
                        if f.endswith((".py", ".js", ".ts", ".jsx", ".tsx"))
                    ]
                )

        # Limit findings to avoid explosion
        for key in findings:
            if key == "explored_directories":
                # Keep explored_directories as a set
                continue
            findings[key] = list(set(findings[key]))[:10]

    def get_performance_stats(self) -> Dict[str, any]:
        """Get performance statistics."""
        cache_stats = self.context_provider.get_cache_stats()
        index_stats = self.directory_indexer.get_statistics()

        return {
            "cache": cache_stats,
            "index": index_stats,
            "context_provider": {
                "project_root": str(self.context_provider.project_root),
                "ignored_patterns": len(self.context_provider.ignore_patterns.patterns),
            },
        }
