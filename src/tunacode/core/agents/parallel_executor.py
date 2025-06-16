"""
Parallel task executor for efficient batch operations.

This module provides parallel execution capabilities for read-only tasks,
integrating with the context provider for lazy file reading and the
parallel grep tool for content search.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...tools.grep import ParallelGrep
from .context_provider import ContextProvider


@dataclass
class ParallelTaskResult:
    """Result of a parallel task execution."""

    task_id: str
    task_type: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration: float = 0.0


class ParallelExecutor:
    """Executes read-only tasks in parallel for maximum efficiency."""

    def __init__(self, context_provider: ContextProvider, max_workers: int = 8):
        self.context_provider = context_provider
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._grep_tool = ParallelGrep()

    async def execute_batch(self, tasks: List[Dict[str, Any]]) -> List[ParallelTaskResult]:
        """Execute a batch of read-only tasks in parallel."""
        # Group tasks by type for optimized execution
        grouped_tasks = self._group_tasks_by_type(tasks)

        results = []

        # Execute each group with specialized handling
        for task_type, task_list in grouped_tasks.items():
            if task_type == "read_file":
                group_results = await self._execute_read_file_batch(task_list)
            elif task_type == "list_dir":
                group_results = await self._execute_list_dir_batch(task_list)
            elif task_type == "grep":
                group_results = await self._execute_grep_batch(task_list)
            else:
                # Generic parallel execution for other read-only tasks
                group_results = await self._execute_generic_batch(task_list)
            
            results.extend(group_results)

        return results

    def _group_tasks_by_type(self, tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group tasks by their tool type for optimized batch execution."""
        grouped = {}
        for task in tasks:
            tool = task.get("tool", "unknown")
            if tool not in grouped:
                grouped[tool] = []
            grouped[tool].append(task)
        return grouped

    async def _execute_read_file_batch(
        self, tasks: List[Dict[str, Any]]
    ) -> List[ParallelTaskResult]:
        """Execute multiple read_file tasks efficiently using batch reading."""
        import time
        
        # Extract file paths from tasks
        task_map = {}
        abs_to_orig = {}  # Map absolute paths back to original paths
        file_paths = []
        for task in tasks:
            file_path = task["args"]["file_path"]  # Keep as string for consistent key matching
            # Convert to absolute path to ensure proper ignore pattern matching
            abs_path = Path(file_path).resolve()
            file_paths.append(abs_path)
            # Store mappings
            task_map[file_path] = task
            abs_to_orig[str(abs_path)] = file_path

        # Batch read all files in parallel
        start_time = time.time()
        file_contents = await self.context_provider.batch_read_files(file_paths)
        duration = time.time() - start_time

        # Build results
        results = []
        for file_path, content in file_contents.items():
            str_path = str(file_path)
            
            # Get original path from absolute path
            orig_path = abs_to_orig.get(str_path)
            if orig_path is None:
                continue
                
            if orig_path not in task_map:
                continue
            task = task_map[orig_path]
            if content is not None:
                results.append(
                    ParallelTaskResult(
                        task_id=str(task.get("id", "unknown")),
                        task_type="read_file",
                        success=True,
                        result={"output": content},
                        duration=duration / len(tasks),  # Average duration
                    )
                )
            else:
                results.append(
                    ParallelTaskResult(
                        task_id=str(task.get("id", "unknown")),
                        task_type="read_file",
                        success=False,
                        result=None,
                        error=f"Could not read file: {file_path}",
                        duration=duration / len(tasks),
                    )
                )

        return results

    async def _execute_list_dir_batch(
        self, tasks: List[Dict[str, Any]]
    ) -> List[ParallelTaskResult]:
        """Execute multiple list_dir tasks using cached snapshots."""
        import time

        async def list_single_dir(task: Dict[str, Any]) -> ParallelTaskResult:
            start_time = time.time()
            try:
                directory = Path(task["args"].get("directory", "."))

                # Use cached snapshot if available
                if "cached_snapshot" in task:
                    snapshot = task["cached_snapshot"]
                else:
                    snapshot = await self.context_provider.get_shallow_snapshot(directory)

                # Format output
                output_lines = []
                output_lines.append(f"Contents of {directory}:")
                output_lines.append("=" * 40)

                # List subdirectories
                if snapshot.subdirs:
                    output_lines.append("\nDirectories:")
                    for subdir in snapshot.subdirs[:30]:  # Limit output
                        output_lines.append(f"  [DIR]  {subdir.name}")

                # List files
                if snapshot.files:
                    output_lines.append("\nFiles:")
                    for file in snapshot.files[:30]:  # Limit output
                        output_lines.append(f"  [FILE] {file.name}")

                if len(snapshot.subdirs) > 30 or len(snapshot.files) > 30:
                    output_lines.append(
                        f"\n... and {len(snapshot.subdirs) + len(snapshot.files) - 60} more items"
                    )

                duration = time.time() - start_time
                return ParallelTaskResult(
                    task_id=str(task.get("id", "unknown")),
                    task_type="list_dir",
                    success=True,
                    result={"output": "\n".join(output_lines)},
                    duration=duration,
                )
            except Exception as e:
                duration = time.time() - start_time
                return ParallelTaskResult(
                    task_id=str(task.get("id", "unknown")),
                    task_type="list_dir",
                    success=False,
                    result=None,
                    error=str(e),
                    duration=duration,
                )

        # Execute all list_dir tasks in parallel
        tasks_coroutines = [list_single_dir(task) for task in tasks]
        results = await asyncio.gather(*tasks_coroutines, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append(
                    ParallelTaskResult(
                        task_id="unknown",
                        task_type="list_dir",
                        success=False,
                        result=None,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results

    async def _execute_grep_batch(self, tasks: List[Dict[str, Any]]) -> List[ParallelTaskResult]:
        """Execute multiple grep tasks using the parallel grep tool."""
        import time

        async def grep_single(task: Dict[str, Any]) -> ParallelTaskResult:
            start_time = time.time()
            try:
                args = task["args"]

                # Use search scope if optimized
                if "search_scope" in task:
                    # Convert search scope to include pattern
                    include_files = ",".join(task["search_scope"])
                    args = {**args, "include_files": include_files}

                # Execute grep with parallel strategy
                result = await self._grep_tool._execute(
                    pattern=args.get("pattern", ""),
                    directory=args.get("directory", "."),
                    case_sensitive=args.get("case_sensitive", False),
                    use_regex=args.get("use_regex", False),
                    include_files=args.get("include_files"),
                    exclude_files=args.get("exclude_files"),
                    max_results=args.get("max_results", 50),
                    context_lines=args.get("context_lines", 2),
                    search_type="smart",  # Always use smart strategy for batched grep
                )

                duration = time.time() - start_time
                return ParallelTaskResult(
                    task_id=str(task.get("id", "unknown")),
                    task_type="grep",
                    success=True,
                    result={"output": result},
                    duration=duration,
                )
            except Exception as e:
                duration = time.time() - start_time
                return ParallelTaskResult(
                    task_id=str(task.get("id", "unknown")),
                    task_type="grep",
                    success=False,
                    result=None,
                    error=str(e),
                    duration=duration,
                )

        # Execute all grep tasks in parallel
        grep_coroutines = [grep_single(task) for task in tasks]
        results = await asyncio.gather(*grep_coroutines, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append(
                    ParallelTaskResult(
                        task_id="unknown",
                        task_type="grep",
                        success=False,
                        result=None,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results

    async def _execute_generic_batch(self, tasks: List[Dict[str, Any]]) -> List[ParallelTaskResult]:
        """Execute generic read-only tasks in parallel."""
        results = []
        
        for task in tasks:
            tool = task.get("tool")
            
            if tool == "bash":
                # For bash commands, we should suggest using our specialized tools instead
                command = task.get("args", {}).get("command", "")
                
                # Detect common search patterns and suggest better alternatives
                if "find" in command and ("-name" in command or "-iname" in command):
                    # Convert find command to grep usage
                    import time
                    import re
                    start_time = time.time()
                    
                    # Extract pattern from find command
                    pattern_match = re.search(r'-i?name\s+["\']?([^\s"\']+)["\']?', command)
                    if pattern_match:
                        pattern = pattern_match.group(1)
                        
                        # Extract directory if specified
                        parts = command.split()
                        directory = "."
                        if len(parts) > 1 and parts[1] != "-name" and parts[1] != "-iname":
                            directory = parts[1]
                        
                        try:
                            # Use grep with empty search pattern to just find files
                            from ...tools.grep import ParallelGrep
                            grep_tool = ParallelGrep()
                            result = await grep_tool._execute(
                                pattern="",  # Empty pattern to just match filenames
                                directory=directory,
                                include_files=pattern,
                                max_results=100,
                                case_sensitive="-iname" not in command,
                                search_type="python"  # Fast for filename matching
                            )
                            
                            # Convert result to look like find output
                            lines = result.strip().split('\n')
                            file_paths = []
                            for line in lines:
                                if line.startswith("📁"):
                                    # Extract file path from grep output format
                                    file_path = line.split("📁")[1].strip().split(":")[0]
                                    file_paths.append(file_path)
                            
                            if file_paths:
                                output = "\n".join(file_paths)
                            else:
                                output = f"No files found matching pattern: {pattern}"
                            
                            duration = time.time() - start_time
                            results.append(
                                ParallelTaskResult(
                                    task_id=str(task.get("id", "unknown")),
                                    task_type="bash",
                                    success=True,
                                    result={"output": output},
                                    duration=duration,
                                )
                            )
                        except Exception as e:
                            results.append(
                                ParallelTaskResult(
                                    task_id=str(task.get("id", "unknown")),
                                    task_type="bash",
                                    success=False,
                                    result=None,
                                    error=f"Failed to search files: {str(e)}",
                                    duration=0.0,
                                )
                            )
                    else:
                        # Couldn't parse find command
                        results.append(
                            ParallelTaskResult(
                                task_id=str(task.get("id", "unknown")),
                                task_type="bash",
                                success=False,
                                result=None,
                                error="Could not parse find command pattern",
                                duration=0.0,
                            )
                        )
                elif "ls" in command or "dir" in command:
                    # Convert ls command to list_dir usage
                    import time
                    start_time = time.time()
                    
                    # Extract directory from ls command (simple parsing)
                    parts = command.split()
                    directory = "."
                    for i, part in enumerate(parts):
                        if part in ["ls", "dir"] and i + 1 < len(parts):
                            potential_dir = parts[i + 1]
                            if not potential_dir.startswith("-"):
                                directory = potential_dir
                                break
                    
                    # Execute using list_dir internally
                    try:
                        from ...tools.list_dir import list_dir
                        result = await list_dir._execute(directory=directory, show_hidden="-a" in command)
                        duration = time.time() - start_time
                        
                        results.append(
                            ParallelTaskResult(
                                task_id=str(task.get("id", "unknown")),
                                task_type="bash",
                                success=True,
                                result={"output": result},
                                duration=duration,
                            )
                        )
                    except Exception as e:
                        results.append(
                            ParallelTaskResult(
                                task_id=str(task.get("id", "unknown")),
                                task_type="bash",
                                success=False,
                                result=None,
                                error=f"Failed to list directory: {str(e)}",
                                duration=0.0,
                            )
                        )
                else:
                    # Generic bash command - not supported in parallel mode
                    error_msg = (
                        "Bash commands are not supported in parallel read mode. "
                        "Use specialized tools: grep (for searching), list_dir (for listing), "
                        "or mark the task as mutate=true for sequential execution."
                    )
                    results.append(
                        ParallelTaskResult(
                            task_id=str(task.get("id", "unknown")),
                            task_type="bash",
                            success=False,
                            result=None,
                            error=error_msg,
                            duration=0.0,
                        )
                    )
            else:
                # Unknown tool type
                results.append(
                    ParallelTaskResult(
                        task_id=str(task.get("id", "unknown")),
                        task_type=tool or "unknown",
                        success=False,
                        result=None,
                        error=f"Tool '{tool}' is not supported in parallel executor",
                        duration=0.0,
                    )
                )
        
        return results

    async def find_files_needing_read(self, grep_results: List[ParallelTaskResult]) -> List[Path]:
        """Analyze grep results to determine which files need to be read."""
        files_to_read = set()

        for result in grep_results:
            if result.success and result.result:
                output = result.result.get("output", "")
                # Parse grep output to extract file paths
                lines = output.split("\n")
                for line in lines:
                    if "📁" in line:  # File header in grep output
                        # Extract file path from format: "📁 path/to/file.py:123"
                        parts = line.split("📁", 1)[1].strip().split(":", 1)
                        if parts:
                            file_path = Path(parts[0].strip())
                            files_to_read.add(file_path)

        return list(files_to_read)
