"""Adaptive task generator for context-aware task creation."""

from typing import Dict, List, Optional

from .project_context import ProjectContext, ProjectInfo, ProjectType


class AdaptiveTaskGenerator:
    """Generate context-aware tasks based on project structure and findings."""

    def __init__(self, project_context: ProjectContext):
        self.project_context = project_context
        self._task_id_counter = 1

    def generate_codebase_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate initial exploration tasks based on project type.

        Args:
            context: Project context information

        Returns:
            List of task dictionaries optimized for the project type
        """
        tasks = []

        # Always start with a directory listing (fast with list_dir)
        tasks.append(
            self._create_task(
                "List project structure",
                mutate=False,
                tool="list_dir",
                args={"directory": ".", "max_entries": 50, "show_hidden": False},
            )
        )

        # Read README if it exists
        tasks.append(
            self._create_task(
                "Read project documentation",
                mutate=False,
                tool="read_file",
                args={"file_path": "README.md"},
            )
        )

        # Add project-specific tasks
        if context.project_type == ProjectType.PYTHON:
            tasks.extend(self._generate_python_tasks(context))
        elif context.project_type == ProjectType.NODEJS:
            tasks.extend(self._generate_nodejs_tasks(context))
        elif context.project_type == ProjectType.RUST:
            tasks.extend(self._generate_rust_tasks(context))
        elif context.project_type == ProjectType.GO:
            tasks.extend(self._generate_go_tasks(context))
        elif context.project_type == ProjectType.JAVA:
            tasks.extend(self._generate_java_tasks(context))
        else:
            tasks.extend(self._generate_generic_tasks(context))

        return tasks

    def generate_followup_tasks(
        self, findings: Dict[str, any], context: ProjectInfo
    ) -> List[Dict[str, any]]:
        """Generate follow-up tasks based on what was discovered.

        Args:
            findings: Results from previous task execution
            context: Project context

        Returns:
            List of follow-up tasks
        """
        tasks = []
        
        # Check if this is a focused request (e.g., showing a specific file)
        original_request = findings.get("original_request", "").lower()
        primary_descriptions = findings.get("primary_task_descriptions", [])
        
        # Detect if user is asking about a specific file or focused topic
        is_focused_request = any([
            "@" in original_request,  # File reference
            "show" in original_request and ("file" in original_request or ".py" in original_request),
            "read" in original_request,
            "contents of" in original_request,
            any("read" in desc.lower() or "file" in desc.lower() for desc in primary_descriptions)
        ])
        
        # For focused requests, limit follow-up tasks to directly related items
        if is_focused_request:
            # Only generate minimal, directly related follow-up tasks
            interesting_files = findings.get("interesting_files", [])
            # Limit to files that seem directly related to the primary request
            for file_name in interesting_files[:1]:  # Max 1 related file
                if file_name not in str(findings):
                    tasks.append(
                        self._create_task(
                            f"Read related file {file_name}",
                            mutate=False,
                            tool="read_file",
                            args={"file_path": file_name},
                        )
                    )
            return tasks  # Return early for focused requests

        # Get already explored directories
        explored_dirs = findings.get("explored_directories", set())

        # Analyze findings and generate targeted follow-ups
        # This is where the "think" part of the loop happens

        # Example: If we found a Django project, explore models and views
        if context.project_type == ProjectType.PYTHON and "django" in str(findings).lower():
            tasks.append(
                self._create_task(
                    "Explore Django models",
                    mutate=False,
                    tool="grep",
                    args={"pattern": "class.*Model", "include_files": "*.py", "directory": "."},
                )
            )

        # Example: If we found test directories, check test structure
        # But only if we haven't already explored this directory
        explored_dirs = findings.get("explored_directories", set())
        if context.has_tests and not self._already_explored_tests(findings):
            test_dir = context.test_dirs[0] if context.test_dirs else "tests"
            # Check if we've already explored this directory
            if test_dir not in explored_dirs:
                tasks.append(
                    self._create_task(
                        f"Examine test structure in {test_dir}",
                        mutate=False,
                        tool="list_dir",
                        args={"directory": test_dir, "max_entries": 30},
                    )
                )

        # Only explore new directories found
        new_dirs = findings.get("directories_found", [])
        for dir_name in new_dirs[:2]:  # Limit to 2 new directories
            if dir_name not in explored_dirs and not dir_name.startswith("."):
                # Skip test directories if we're not specifically looking for tests
                if any(test_name in dir_name.lower() for test_name in ["test", "spec", "__test"]):
                    continue

                tasks.append(
                    self._create_task(
                        f"Explore {dir_name} directory",
                        mutate=False,
                        tool="list_dir",
                        args={"directory": dir_name, "max_entries": 30},
                    )
                )

        # Explore interesting files found
        interesting_files = findings.get("interesting_files", [])
        for file_name in interesting_files[:3]:  # Limit to 3 files
            # Only read files we haven't seen before
            if file_name not in str(findings):
                tasks.append(
                    self._create_task(
                        f"Read {file_name}",
                        mutate=False,
                        tool="read_file",
                        args={"file_path": file_name},
                    )
                )

        return tasks

    def _create_task(
        self,
        description: str,
        mutate: bool = False,
        tool: Optional[str] = None,
        args: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """Create a task dictionary."""
        task = {
            "id": self._task_id_counter,
            "description": description,
            "mutate": mutate,
        }

        if tool:
            task["tool"] = tool
        if args:
            task["args"] = args

        self._task_id_counter += 1
        return task

    def _generate_python_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate Python-specific tasks."""
        tasks = []

        # Read main configuration files
        for config_file in context.config_files[:1]:  # Just the first one
            if config_file.endswith((".toml", ".py", ".cfg", ".txt")):
                tasks.append(
                    self._create_task(
                        f"Read Python project configuration from {config_file}",
                        mutate=False,
                        tool="read_file",
                        args={"file_path": config_file},
                    )
                )
                break

        # Explore main source directory
        if context.source_dirs:
            main_dir = context.source_dirs[0]
            tasks.append(
                self._create_task(
                    f"Explore source code structure in {main_dir}",
                    mutate=False,
                    tool="list_dir",
                    args={"directory": main_dir, "max_entries": 40},
                )
            )

        # Check for entry points
        if context.entry_points:
            # Read the first entry point
            tasks.append(
                self._create_task(
                    f"Read main entry point: {context.entry_points[0]}",
                    mutate=False,
                    tool="read_file",
                    args={"file_path": context.entry_points[0]},
                )
            )
        else:
            # Look for common patterns
            tasks.append(
                self._create_task(
                    "Find Python entry points",
                    mutate=False,
                    tool="grep",
                    args={"pattern": "if __name__ == .__main__.", "include": "*.py", "path": "."},
                )
            )

        return tasks

    def _generate_nodejs_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate Node.js-specific tasks."""
        tasks = []

        # Read package.json
        for config_file in context.config_files:
            if config_file.endswith("package.json"):
                tasks.append(
                    self._create_task(
                        "Read package.json for project information",
                        mutate=False,
                        tool="read_file",
                        args={"file_path": config_file},
                    )
                )
                break

        # Check for TypeScript
        tasks.append(
            self._create_task(
                "Check for TypeScript configuration",
                mutate=False,
                tool="read_file",
                args={"file_path": "tsconfig.json"},
            )
        )

        # Explore source structure
        if context.source_dirs:
            main_dir = context.source_dirs[0]
            tasks.append(
                self._create_task(
                    f"Explore source structure in {main_dir}",
                    mutate=False,
                    tool="list_dir",
                    args={"directory": main_dir, "max_entries": 40},
                )
            )

        # Check entry points
        if context.entry_points:
            tasks.append(
                self._create_task(
                    f"Read main entry: {context.entry_points[0]}",
                    mutate=False,
                    tool="read_file",
                    args={"file_path": context.entry_points[0]},
                )
            )

        return tasks

    def _generate_rust_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate Rust-specific tasks."""
        tasks = []

        # Read Cargo.toml
        for config_file in context.config_files:
            if config_file.endswith("Cargo.toml"):
                tasks.append(
                    self._create_task(
                        "Read Cargo.toml for project configuration",
                        mutate=False,
                        tool="read_file",
                        args={"file_path": config_file},
                    )
                )
                break

        # Explore src directory
        tasks.append(
            self._create_task(
                "Explore Rust source structure",
                mutate=False,
                tool="list_dir",
                args={"directory": "src", "max_entries": 30},
            )
        )

        # Read main.rs or lib.rs
        for entry in ["src/main.rs", "src/lib.rs"]:
            if entry in context.entry_points:
                tasks.append(
                    self._create_task(
                        f"Read {entry}", mutate=False, tool="read_file", args={"file_path": entry}
                    )
                )
                break

        return tasks

    def _generate_go_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate Go-specific tasks."""
        tasks = []

        # Read go.mod
        for config_file in context.config_files:
            if config_file.endswith("go.mod"):
                tasks.append(
                    self._create_task(
                        "Read go.mod for module information",
                        mutate=False,
                        tool="read_file",
                        args={"file_path": config_file},
                    )
                )
                break

        # Explore Go project structure
        for dir_name in ["cmd", "pkg", "internal"]:
            if dir_name in context.source_dirs:
                tasks.append(
                    self._create_task(
                        f"Explore {dir_name} directory",
                        mutate=False,
                        tool="list_dir",
                        args={"directory": dir_name, "max_entries": 30},
                    )
                )
                break

        # Find main.go
        if context.entry_points:
            tasks.append(
                self._create_task(
                    f"Read main entry: {context.entry_points[0]}",
                    mutate=False,
                    tool="read_file",
                    args={"file_path": context.entry_points[0]},
                )
            )

        return tasks

    def _generate_java_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate Java-specific tasks."""
        tasks = []

        # Read build configuration
        for config_file in context.config_files:
            if config_file.endswith(("pom.xml", "build.gradle", "build.gradle.kts")):
                build_type = "Maven" if config_file.endswith("pom.xml") else "Gradle"
                tasks.append(
                    self._create_task(
                        f"Read {build_type} configuration",
                        mutate=False,
                        tool="read_file",
                        args={"file_path": config_file},
                    )
                )
                break

        # Explore source structure
        if "src/main/java" in context.source_dirs:
            tasks.append(
                self._create_task(
                    "Explore Java source structure",
                    mutate=False,
                    tool="list_dir",
                    args={"directory": "src/main/java", "max_entries": 40},
                )
            )

        # Look for main class
        tasks.append(
            self._create_task(
                "Find main application class",
                mutate=False,
                tool="grep",
                args={"pattern": "public static void main", "include": "*.java", "path": "."},
            )
        )

        return tasks

    def _generate_generic_tasks(self, context: ProjectInfo) -> List[Dict[str, any]]:
        """Generate tasks for unknown project types."""
        tasks = []

        # Explore main directories
        for main_dir in context.source_dirs[:2]:  # Limit to first 2
            if main_dir != ".":
                tasks.append(
                    self._create_task(
                        f"Explore {main_dir} directory",
                        mutate=False,
                        tool="list_dir",
                        args={"directory": main_dir, "max_entries": 30},
                    )
                )

        # Read any config files found
        for config_file in context.config_files[:2]:  # Limit to first 2
            tasks.append(
                self._create_task(
                    f"Read configuration: {config_file}",
                    mutate=False,
                    tool="read_file",
                    args={"file_path": config_file},
                )
            )

        # Try to find entry points by common patterns
        tasks.append(
            self._create_task(
                "Search for main entry points",
                mutate=False,
                tool="grep",
                args={"pattern": "\\bmain\\b", "include": "*", "path": "."},
            )
        )

        return tasks

    def _already_explored_tests(self, findings: Dict[str, any]) -> bool:
        """Check if we already explored test directories."""
        findings_str = str(findings).lower()
        return any(
            indicator in findings_str for indicator in ["test/", "tests/", "spec/", "__tests__"]
        )

    def create_analysis_task(self, request: str) -> Dict[str, any]:
        """Create a general analysis task."""
        return self._create_task(
            "Analyze codebase based on findings",
            mutate=False,
            tool="analyze",
            args={"request": request},
        )
