"""Template processing engine for markdown slash commands."""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

import yaml  # type: ignore[import-untyped]

from .types import ContextInjectionResult
from .validator import CommandValidator

if TYPE_CHECKING:
    from ....types import CommandContext

logger = logging.getLogger(__name__)


class MarkdownTemplateProcessor:
    """Processes markdown templates with variable substitution and command execution."""

    def __init__(self, max_context_size: int = 100_000, max_files: int = 50):
        self.validator = CommandValidator()
        self.max_context_size = max_context_size
        self.max_files = max_files

        # Regex patterns for template syntax
        self.argument_pattern = re.compile(r"\$ARGUMENTS\b")
        self.env_var_pattern = re.compile(r"\$([A-Z_][A-Z0-9_]*)\b")
        self.command_pattern = re.compile(r"!\`([^`]+)\`")
        self.file_pattern = re.compile(r"@([^\s\)\],]+)")
        self.glob_pattern = re.compile(r"@@([^\s\)\],]+)")

        # Context tracking
        self._included_files: Set[Path] = set()
        self._total_context_size = 0
        self._warnings: List[str] = []

    def parse_frontmatter(self, content: str) -> Tuple[Optional[Dict], str]:
        """Parse YAML frontmatter from markdown content."""
        if not content.strip().startswith("---"):
            return {}, content

        try:
            # Split on --- boundaries
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}, content

            frontmatter_text = parts[1].strip()
            markdown_content = parts[2].lstrip("\n")

            if not frontmatter_text:
                return {}, markdown_content

            frontmatter = yaml.safe_load(frontmatter_text)
            return frontmatter, markdown_content

        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML frontmatter: {e}")
            return {}, content

    def process_template_with_context(
        self, content: str, args: List[str], context: "CommandContext"
    ) -> ContextInjectionResult:
        """Process template with comprehensive context injection tracking."""

        # Reset tracking
        self._included_files.clear()
        self._total_context_size = len(content)
        self._warnings.clear()
        executed_commands = []

        processed = content

        # 1. Replace $ARGUMENTS
        args_string = " ".join(args) if args else ""
        processed = self.argument_pattern.sub(args_string, processed)

        # 2. Replace environment variables
        processed = self._process_env_vars(processed)

        # 3. Execute !`command` blocks (track executed commands)
        processed, cmd_list = self._process_command_blocks_with_tracking(processed, context)
        executed_commands.extend(cmd_list)

        # 4. Include @file contents (with size tracking)
        processed = self._process_file_inclusions_with_tracking(processed, context)

        # 5. Process @@glob patterns (with limits)
        processed = self._process_glob_inclusions_with_tracking(processed, context)

        return ContextInjectionResult(
            processed_content=processed,
            included_files=list(self._included_files),
            executed_commands=executed_commands,
            total_size=self._total_context_size,
            warnings=self._warnings.copy(),
        )

    def _process_env_vars(self, content: str) -> str:
        """Replace environment variables."""

        def replace_env_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, f"${var_name}")  # Leave unchanged if not found

        return self.env_var_pattern.sub(replace_env_var, content)

    def _process_command_blocks_with_tracking(
        self, content: str, context: "CommandContext"
    ) -> Tuple[str, List[str]]:
        """Execute commands with tracking."""
        executed_commands = []

        def replace_command(match):
            command = match.group(1).strip()
            executed_commands.append(command)

            # Security validation
            validation_result = self.validator.validate_shell_command(command)
            if not validation_result.allowed:
                error_violations = [
                    v for v in validation_result.violations if v.severity == "error"
                ]
                if error_violations:
                    return f"[BLOCKED: Unsafe command '{command}']"

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,  # 10 second timeout
                    cwd=getattr(context.state_manager.config, "current_directory", os.getcwd()),
                )

                if result.returncode == 0:
                    output = result.stdout.strip()
                    self._total_context_size += len(output)

                    # Check context size limit
                    if self._total_context_size > self.max_context_size:
                        self._warnings.append(
                            f"Command output truncated due to size limit: {command}"
                        )
                        return output[:1000] + "...[truncated]"

                    return output
                else:
                    error_msg = f"[ERROR: Command failed with code {result.returncode}]"
                    if result.stderr:
                        error_msg += f"\n{result.stderr.strip()}"
                    return error_msg

            except subprocess.TimeoutExpired:
                return "[ERROR: Command timed out]"
            except Exception as e:
                return f"[ERROR: {str(e)}]"

        processed_content = self.command_pattern.sub(replace_command, content)
        return processed_content, executed_commands

    def _process_file_inclusions_with_tracking(
        self, content: str, context: "CommandContext"
    ) -> str:
        """Include files with comprehensive tracking and limits."""

        def replace_file(match):
            file_path = match.group(1).strip()

            # Check file limit
            if len(self._included_files) >= self.max_files:
                self._warnings.append(f"File inclusion limit reached, skipping: {file_path}")
                return f"[LIMIT: Too many files included, skipping '{file_path}']"

            try:
                base_path = Path(
                    getattr(context.state_manager.config, "current_directory", os.getcwd())
                )
                full_path = (base_path / file_path).resolve()

                # Security validation
                validation_result = self.validator.validate_file_path(file_path, base_path)
                if not validation_result.allowed:
                    error_violations = [
                        v for v in validation_result.violations if v.severity == "error"
                    ]
                    if error_violations:
                        return f"[BLOCKED: Unsafe file path '{file_path}']"

                # Check for circular inclusion
                if full_path in self._included_files:
                    self._warnings.append(f"Circular file inclusion detected: {file_path}")
                    return f"[CIRCULAR: File already included '{file_path}']"

                if full_path.exists() and full_path.is_file():
                    file_content = full_path.read_text(encoding="utf-8")

                    # Check size limits
                    if self._total_context_size + len(file_content) > self.max_context_size:
                        self._warnings.append(
                            f"File content truncated due to size limit: {file_path}"
                        )
                        remaining_space = self.max_context_size - self._total_context_size
                        file_content = file_content[:remaining_space] + "...[truncated]"

                    self._included_files.add(full_path)
                    self._total_context_size += len(file_content)

                    # Add file header for context
                    return f"\n# File: {file_path}\n{file_content}\n# End of {file_path}\n"
                else:
                    return f"[ERROR: File not found '{file_path}']"

            except Exception as e:
                return f"[ERROR: Cannot read file '{file_path}': {str(e)}]"

        return self.file_pattern.sub(replace_file, content)

    def _process_glob_inclusions_with_tracking(
        self, content: str, context: "CommandContext"
    ) -> str:
        """Process glob patterns with comprehensive tracking."""

        def replace_glob(match):
            pattern = match.group(1).strip()

            # Security validation
            validation_result = self.validator.validate_glob_pattern(pattern)
            if not validation_result.allowed:
                error_violations = [
                    v for v in validation_result.violations if v.severity == "error"
                ]
                if error_violations:
                    return f"[BLOCKED: Unsafe glob pattern '{pattern}']"

            try:
                base_path = Path(
                    getattr(context.state_manager.config, "current_directory", os.getcwd())
                )
                matching_files = list(base_path.glob(pattern))

                # Limit number of files
                if len(matching_files) > self.max_files - len(self._included_files):
                    self._warnings.append(
                        f"Glob pattern matched too many files, truncating: {pattern}"
                    )
                    matching_files = matching_files[: self.max_files - len(self._included_files)]

                if not matching_files:
                    return f"[INFO: No files matched pattern '{pattern}']"

                # Aggregate file contents
                aggregated_content = []
                aggregated_content.append(f"\n# Files matching pattern: {pattern}")

                for file_path in sorted(matching_files):
                    if file_path in self._included_files:
                        continue  # Skip already included files

                    if not file_path.is_file():
                        continue  # Skip directories

                    try:
                        file_content = file_path.read_text(encoding="utf-8")

                        # Check size limits
                        if self._total_context_size + len(file_content) > self.max_context_size:
                            self._warnings.append(
                                f"Glob inclusion stopped due to size limit at: {file_path}"
                            )
                            break

                        relative_path = file_path.relative_to(base_path)
                        aggregated_content.append(f"\n## File: {relative_path}")
                        aggregated_content.append(file_content)

                        self._included_files.add(file_path)
                        self._total_context_size += len(file_content)

                    except Exception as e:
                        aggregated_content.append(f"\n## Error reading {file_path}: {str(e)}")

                aggregated_content.append(f"\n# End of pattern: {pattern}\n")
                return "\n".join(aggregated_content)

            except Exception as e:
                return f"[ERROR: Glob pattern failed '{pattern}': {str(e)}]"

        return self.glob_pattern.sub(replace_glob, content)
