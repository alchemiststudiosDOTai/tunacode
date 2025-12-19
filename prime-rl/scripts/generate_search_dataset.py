#!/usr/bin/env python3
"""Generate synthetic code search training dataset.

This script creates search tasks for training a model on the GLOB -> GREP -> READ
search funnel pattern. Tasks are generated from templates with variations.

Usage:
    python scripts/generate_search_dataset.py --output data/tunacode_search_sft.jsonl --count 100
"""

import argparse
import json
import random
import sys
import uuid
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "envs"))

from tunacode_search.schema import SearchTask, TaskType, ToolName

# Task templates organized by type
TASK_TEMPLATES: dict[TaskType, list[dict]] = {
    TaskType.FILE_SEARCH: [
        {
            "query": "Find all Python files in the project",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["*.py", "**/*.py"],
        },
        {
            "query": "Find all test files",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["test_*.py", "**/test_*.py", "**/*_test.py"],
        },
        {
            "query": "Find all configuration files",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["*.toml", "*.yaml", "*.yml", "*.json", "*.ini"],
        },
        {
            "query": "Find all TypeScript files in the src directory",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["src/**/*.ts", "src/**/*.tsx"],
        },
        {
            "query": "Find all markdown documentation files",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["*.md", "**/*.md", "docs/**/*.md"],
        },
        {
            "query": "Find all JavaScript files",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["**/*.js", "**/*.jsx"],
        },
        {
            "query": "Find all CSS and SCSS files",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["**/*.css", "**/*.scss"],
        },
        {
            "query": "Find all requirements files",
            "expected_tools": [ToolName.GLOB],
            "patterns": ["requirements*.txt", "pyproject.toml"],
        },
    ],
    TaskType.CONTENT_SEARCH: [
        {
            "query": "Search for all TODO comments in the codebase",
            "expected_tools": [ToolName.GREP],
            "content": ["TODO", "FIXME", "HACK"],
        },
        {
            "query": "Find all imports of the requests library",
            "expected_tools": [ToolName.GREP],
            "content": ["import requests", "from requests"],
        },
        {
            "query": "Search for error handling code",
            "expected_tools": [ToolName.GREP],
            "content": ["except", "try:", "raise"],
        },
        {
            "query": "Find all logging statements",
            "expected_tools": [ToolName.GREP],
            "content": ["logger.", "logging.", "console.log"],
        },
        {
            "query": "Search for API endpoint definitions",
            "expected_tools": [ToolName.GREP],
            "content": ["@app.route", "@router.", "def get_", "def post_"],
        },
        {
            "query": "Find all database queries",
            "expected_tools": [ToolName.GREP],
            "content": ["SELECT", "INSERT", "UPDATE", "DELETE", ".execute("],
        },
        {
            "query": "Search for environment variable usage",
            "expected_tools": [ToolName.GREP],
            "content": ["os.environ", "getenv", "process.env"],
        },
        {
            "query": "Find all async function definitions",
            "expected_tools": [ToolName.GREP],
            "content": ["async def", "async function"],
        },
    ],
    TaskType.DEFINITION_SEARCH: [
        {
            "query": "Find the definition of the User class",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["class User"],
            "expected_files": ["models.py", "user.py"],
        },
        {
            "query": "Find where the main function is defined",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["def main", "function main"],
            "expected_files": ["main.py", "__main__.py", "app.py"],
        },
        {
            "query": "Find the database connection configuration",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["DATABASE", "db_url", "connection_string"],
            "expected_files": ["config.py", "settings.py", "database.py"],
        },
        {
            "query": "Find the authentication middleware",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["auth", "authenticate", "middleware"],
            "expected_files": ["auth.py", "middleware.py"],
        },
        {
            "query": "Find the API router definitions",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["router", "APIRouter", "Blueprint"],
            "expected_files": ["routes.py", "router.py", "api.py"],
        },
        {
            "query": "Find the test fixtures",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["@pytest.fixture", "@fixture"],
            "expected_files": ["conftest.py", "fixtures.py"],
        },
        {
            "query": "Find the error handling utilities",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["class Error", "Exception", "handle_error"],
            "expected_files": ["errors.py", "exceptions.py", "utils.py"],
        },
        {
            "query": "Find the data validation schemas",
            "expected_tools": [ToolName.GLOB, ToolName.GREP, ToolName.READ_FILE],
            "content": ["Schema", "Validator", "pydantic"],
            "expected_files": ["schemas.py", "validators.py", "models.py"],
        },
    ],
    TaskType.USAGE_SEARCH: [
        {
            "query": "Find all places where the cache is used",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["cache.", "cache[", "@cached"],
        },
        {
            "query": "Find all usages of the send_email function",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["send_email(", "send_email "],
        },
        {
            "query": "Find where the config module is imported",
            "expected_tools": [ToolName.GREP],
            "content": ["from config import", "import config"],
        },
        {
            "query": "Find all usages of the database session",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["session.", "db.session", "Session("],
        },
        {
            "query": "Find where the logger is initialized",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["getLogger", "logging.basicConfig", "Logger("],
        },
        {
            "query": "Find all HTTP client usages",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["requests.", "httpx.", "aiohttp."],
        },
        {
            "query": "Find all places where dates are parsed",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["datetime.strptime", "dateutil.parser", "parse_date"],
        },
        {
            "query": "Find where JSON serialization happens",
            "expected_tools": [ToolName.GREP, ToolName.READ_FILE],
            "content": ["json.dumps", "json.loads", "JSON.stringify"],
        },
    ],
}

# Query variations (prefix/suffix modifiers)
QUERY_PREFIXES = [
    "Can you ",
    "Please ",
    "I need to ",
    "Help me ",
    "",
    "Could you ",
]

QUERY_SUFFIXES = [
    "",
    " in this project",
    " in the codebase",
    " for me",
    " quickly",
]


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return f"task_{uuid.uuid4().hex[:8]}"


def vary_query(query: str) -> str:
    """Add natural variation to a query."""
    prefix = random.choice(QUERY_PREFIXES)
    suffix = random.choice(QUERY_SUFFIXES)

    # Adjust capitalization
    if prefix:
        query = query[0].lower() + query[1:]
    else:
        query = query[0].upper() + query[1:]

    # Sometimes add question mark
    if random.random() < 0.3 and not query.endswith("?"):
        query = query.rstrip(".") + "?"

    return prefix + query + suffix


def generate_task_from_template(
    task_type: TaskType,
    template: dict,
    codebase_root: str = ".",
) -> SearchTask:
    """Generate a task from a template with variations."""
    query = vary_query(template["query"])

    expected_content = template.get("content", [])
    if expected_content:
        # Pick a subset of expected content
        expected_content = random.sample(expected_content, min(len(expected_content), random.randint(1, 3)))

    expected_files = template.get("expected_files", [])
    if expected_files:
        expected_files = random.sample(expected_files, min(len(expected_files), random.randint(1, 2)))

    return SearchTask(
        task_id=generate_task_id(),
        task_type=task_type,
        query=query,
        codebase_root=codebase_root,
        expected_tool_sequence=template["expected_tools"],
        expected_files=expected_files,
        expected_content=expected_content,
        metadata={"template": template["query"][:50]},
    )


def generate_dataset(
    count: int = 100,
    codebase_root: str = ".",
    seed: int | None = None,
) -> list[SearchTask]:
    """Generate a dataset of search tasks.

    Args:
        count: Number of tasks to generate
        codebase_root: Root directory for search tasks
        seed: Random seed for reproducibility

    Returns:
        List of SearchTask objects
    """
    if seed is not None:
        random.seed(seed)

    tasks: list[SearchTask] = []

    # Flatten all templates with their types
    all_templates: list[tuple[TaskType, dict]] = []
    for task_type, templates in TASK_TEMPLATES.items():
        for template in templates:
            all_templates.append((task_type, template))

    # Generate tasks
    for _ in range(count):
        task_type, template = random.choice(all_templates)
        task = generate_task_from_template(task_type, template, codebase_root)
        tasks.append(task)

    return tasks


def save_dataset(tasks: list[SearchTask], output_path: Path) -> None:
    """Save tasks to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task.to_dict()) + "\n")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate code search training dataset")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/tunacode_search_sft.jsonl"),
        help="Output file path (default: data/tunacode_search_sft.jsonl)",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=100,
        help="Number of tasks to generate (default: 100)",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--codebase",
        "-c",
        type=str,
        default=".",
        help="Codebase root directory (default: .)",
    )

    args = parser.parse_args()

    print(f"Generating {args.count} search tasks...")
    tasks = generate_dataset(
        count=args.count,
        codebase_root=args.codebase,
        seed=args.seed,
    )

    print(f"Saving to {args.output}...")
    save_dataset(tasks, args.output)

    # Print stats
    type_counts: dict[str, int] = {}
    for task in tasks:
        type_name = task.task_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    print(f"\nGenerated {len(tasks)} tasks:")
    for type_name, count in sorted(type_counts.items()):
        print(f"  {type_name}: {count}")

    print(f"\nOutput saved to: {args.output}")


if __name__ == "__main__":
    main()
