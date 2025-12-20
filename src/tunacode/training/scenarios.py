"""Tool usage scenario library for generating synthetic training data.

This module contains predefined scenarios that represent common tool-calling
patterns in tunacode. Each scenario includes:
- A user query pattern
- Expected tool calls with arguments
- Typical tool responses
- Model responses
"""

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A tool call with its name and arguments."""

    name: str
    arguments: dict[str, Any]


@dataclass
class Scenario:
    """A single tool-calling scenario.

    Attributes:
        name: Short identifier for the scenario
        description: What this scenario demonstrates
        user_queries: List of possible user query variations
        tool_calls: Sequence of tool calls to make
        tool_responses: Corresponding responses for each tool call
        model_response_template: Template for the model's final response
    """

    name: str
    description: str
    user_queries: list[str]
    tool_calls: list[ToolCall]
    tool_responses: list[str]
    model_response_template: str
    tags: list[str] = field(default_factory=list)

    def get_random_query(self) -> str:
        """Get a random user query variation."""
        return random.choice(self.user_queries)


# ============ READ FILE SCENARIOS ============

READ_FILE_BASIC = Scenario(
    name="read_file_basic",
    description="Basic file reading with full content",
    user_queries=[
        "Read the README.md file",
        "Show me the contents of README.md",
        "What's in README.md?",
        "Can you read README.md for me?",
        "Open README.md",
    ],
    tool_calls=[
        ToolCall(name="read_file", arguments={"filepath": "README.md"}),
    ],
    tool_responses=[
        "<file>\n00001| # Project Name\n00002| \n00003| A description of the project.\n00004| \n00005| ## Installation\n00006| \n00007| ```bash\n00008| pip install project\n00009| ```\n\n(End of file - total 9 lines)\n</file>",
    ],
    model_response_template="The README.md contains a project description with an Installation section. It shows how to install the project using pip.",
    tags=["read_file", "basic"],
)

READ_FILE_WITH_OFFSET = Scenario(
    name="read_file_with_offset",
    description="Reading a specific portion of a file",
    user_queries=[
        "Read lines 50-100 of src/main.py",
        "Show me the middle of main.py starting at line 50",
        "What's in main.py from line 50?",
    ],
    tool_calls=[
        ToolCall(name="read_file", arguments={"filepath": "src/main.py", "offset": 49, "limit": 50}),
    ],
    tool_responses=[
        "<file>\n00050| def process_data(data):\n00051|     \"\"\"Process the input data.\"\"\"\n00052|     result = []\n00053|     for item in data:\n00054|         result.append(transform(item))\n00055|     return result\n\n(File has more lines. Use 'offset' to read beyond line 55)\n</file>",
    ],
    model_response_template="Lines 50-55 of main.py show a `process_data` function that transforms each item in the input data.",
    tags=["read_file", "offset"],
)

# ============ GREP SCENARIOS ============

GREP_PATTERN = Scenario(
    name="grep_pattern",
    description="Search for a pattern across files",
    user_queries=[
        "Find all TODO comments in the codebase",
        "Search for TODO in all Python files",
        "Where are the TODOs in this project?",
        "Grep for TODO comments",
    ],
    tool_calls=[
        ToolCall(name="grep", arguments={"pattern": "TODO", "include_files": "*.py"}),
    ],
    tool_responses=[
        "Found 3 matches in 2 files\nStrategy: smart | Candidates: 15 files\n\nsrc/main.py:23: # TODO: Add error handling\nsrc/main.py:45: # TODO: Optimize this loop\nsrc/utils.py:12: # TODO: Refactor this function",
    ],
    model_response_template="I found 3 TODO comments across 2 files:\n- `src/main.py:23` - Add error handling\n- `src/main.py:45` - Optimize this loop\n- `src/utils.py:12` - Refactor this function",
    tags=["grep", "search"],
)

GREP_FUNCTION_DEF = Scenario(
    name="grep_function_definition",
    description="Find function definitions",
    user_queries=[
        "Where is the process_data function defined?",
        "Find the definition of process_data",
        "Search for def process_data",
    ],
    tool_calls=[
        ToolCall(name="grep", arguments={"pattern": "def process_data", "use_regex": False}),
    ],
    tool_responses=[
        "Found 1 match in 1 file\nStrategy: smart | Candidates: 20 files\n\nsrc/processor.py:45: def process_data(data: list[dict]) -> list[dict]:",
    ],
    model_response_template="The `process_data` function is defined in `src/processor.py` at line 45. It takes a list of dicts and returns a list of dicts.",
    tags=["grep", "definition"],
)

# ============ GLOB SCENARIOS ============

GLOB_PYTHON_FILES = Scenario(
    name="glob_python_files",
    description="Find all Python files",
    user_queries=[
        "List all Python files",
        "Find all .py files",
        "What Python files are in this project?",
        "Show me the Python files",
    ],
    tool_calls=[
        ToolCall(name="glob", arguments={"pattern": "**/*.py"}),
    ],
    tool_responses=[
        "[source:index]\nFound 12 files matching pattern: **/*.py\n\nsrc/main.py\nsrc/utils.py\nsrc/config.py\nsrc/models/user.py\nsrc/models/item.py\ntests/test_main.py\ntests/test_utils.py",
    ],
    model_response_template="I found 12 Python files in the project. The main source files are in `src/` and tests are in `tests/`.",
    tags=["glob", "list"],
)

GLOB_SPECIFIC_PATTERN = Scenario(
    name="glob_test_files",
    description="Find test files",
    user_queries=[
        "Find all test files",
        "Show me the test files",
        "List files starting with test_",
    ],
    tool_calls=[
        ToolCall(name="glob", arguments={"pattern": "**/test_*.py"}),
    ],
    tool_responses=[
        "[source:filesystem]\nFound 5 files matching pattern: **/test_*.py\n\ntests/test_main.py\ntests/test_utils.py\ntests/test_config.py\ntests/unit/test_models.py\ntests/integration/test_api.py",
    ],
    model_response_template="I found 5 test files. Unit tests are in `tests/` and there are subdirectories for `unit/` and `integration/` tests.",
    tags=["glob", "tests"],
)

# ============ LIST_DIR SCENARIOS ============

LIST_DIR_BASIC = Scenario(
    name="list_dir_basic",
    description="List directory contents",
    user_queries=[
        "List the project directory",
        "What files are in this directory?",
        "Show me the directory structure",
        "ls",
    ],
    tool_calls=[
        ToolCall(name="list_dir", arguments={"directory": "."}),
    ],
    tool_responses=[
        "15 files  4 dirs\nproject/\n├── src/\n│   ├── main.py\n│   ├── utils.py\n│   └── config.py\n├── tests/\n│   ├── test_main.py\n│   └── test_utils.py\n├── README.md\n├── pyproject.toml\n└── requirements.txt",
    ],
    model_response_template="The project has a standard Python structure with:\n- `src/` containing the main source code\n- `tests/` containing test files\n- Configuration files (pyproject.toml, requirements.txt)\n- README.md documentation",
    tags=["list_dir", "structure"],
)

LIST_DIR_SUBDIRECTORY = Scenario(
    name="list_dir_subdirectory",
    description="List a specific subdirectory",
    user_queries=[
        "List the src directory",
        "What's in src/?",
        "Show files in src/",
    ],
    tool_calls=[
        ToolCall(name="list_dir", arguments={"directory": "src"}),
    ],
    tool_responses=[
        "8 files  2 dirs\nsrc/\n├── models/\n│   ├── user.py\n│   └── item.py\n├── utils/\n│   └── helpers.py\n├── main.py\n├── config.py\n└── __init__.py",
    ],
    model_response_template="The `src/` directory contains:\n- `models/` with user.py and item.py\n- `utils/` with helpers.py\n- Core files: main.py, config.py, and __init__.py",
    tags=["list_dir", "specific"],
)

# ============ BASH SCENARIOS ============

BASH_GIT_STATUS = Scenario(
    name="bash_git_status",
    description="Check git status",
    user_queries=[
        "Check git status",
        "What's the git status?",
        "Show me uncommitted changes",
        "Run git status",
    ],
    tool_calls=[
        ToolCall(name="bash", arguments={"command": "git status"}),
    ],
    tool_responses=[
        "Command: git status\nExit Code: 0\nWorking Directory: /project\n\nSTDOUT:\nOn branch main\nYour branch is up to date with 'origin/main'.\n\nChanges not staged for commit:\n  modified:   src/main.py\n  modified:   src/utils.py\n\nSTDERR:\n(no errors)",
    ],
    model_response_template="You're on the `main` branch, up to date with origin. There are uncommitted changes in:\n- src/main.py\n- src/utils.py",
    tags=["bash", "git"],
)

BASH_RUN_TESTS = Scenario(
    name="bash_run_tests",
    description="Run pytest",
    user_queries=[
        "Run the tests",
        "Execute pytest",
        "Run pytest",
        "Test the code",
    ],
    tool_calls=[
        ToolCall(name="bash", arguments={"command": "pytest", "timeout": 60}),
    ],
    tool_responses=[
        "Command: pytest\nExit Code: 0\nWorking Directory: /project\n\nSTDOUT:\n============================= test session starts ==============================\ncollected 15 items\n\ntests/test_main.py ....                                                  [ 26%]\ntests/test_utils.py ......                                               [ 66%]\ntests/test_config.py .....                                               [100%]\n\n============================== 15 passed in 0.42s ==============================\n\nSTDERR:\n(no errors)",
    ],
    model_response_template="All 15 tests passed successfully in 0.42 seconds.",
    tags=["bash", "tests"],
)

BASH_INSTALL_DEPS = Scenario(
    name="bash_install_deps",
    description="Install dependencies",
    user_queries=[
        "Install the dependencies",
        "Run pip install",
        "Install requirements",
    ],
    tool_calls=[
        ToolCall(name="bash", arguments={"command": "pip install -r requirements.txt"}),
    ],
    tool_responses=[
        "Command: pip install -r requirements.txt\nExit Code: 0\nWorking Directory: /project\n\nSTDOUT:\nRequirement already satisfied: pydantic>=2.0 in .venv/lib/python3.11/site-packages\nRequirement already satisfied: httpx>=0.25 in .venv/lib/python3.11/site-packages\n\nSTDERR:\n(no errors)",
    ],
    model_response_template="Dependencies are already installed. All requirements from requirements.txt are satisfied.",
    tags=["bash", "dependencies"],
)

# ============ WRITE FILE SCENARIOS ============

WRITE_FILE_NEW = Scenario(
    name="write_file_new",
    description="Create a new file",
    user_queries=[
        "Create a new file called config.json",
        "Write a config.json file",
        "Make a new config.json",
    ],
    tool_calls=[
        ToolCall(
            name="write_file",
            arguments={
                "filepath": "config.json",
                "content": '{\n  "debug": true,\n  "port": 8080\n}',
            },
        ),
    ],
    tool_responses=[
        "Successfully wrote to new file: config.json",
    ],
    model_response_template="Created `config.json` with debug mode enabled and port set to 8080.",
    tags=["write_file", "create"],
)

# ============ UPDATE FILE SCENARIOS ============

UPDATE_FILE_FIX = Scenario(
    name="update_file_fix",
    description="Fix a bug in a file",
    user_queries=[
        "Fix the typo in main.py",
        "Update main.py to fix the bug",
        "Change 'pritn' to 'print' in main.py",
    ],
    tool_calls=[
        ToolCall(
            name="update_file",
            arguments={
                "filepath": "src/main.py",
                "target": "pritn(result)",
                "patch": "print(result)",
            },
        ),
    ],
    tool_responses=[
        "File 'src/main.py' updated successfully.\n\n--- a/src/main.py\n+++ b/src/main.py\n@@ -10,7 +10,7 @@\n def process():\n     result = compute()\n-    pritn(result)\n+    print(result)\n     return result",
    ],
    model_response_template="Fixed the typo in `src/main.py`: changed `pritn(result)` to `print(result)`.",
    tags=["update_file", "fix"],
)

UPDATE_FILE_REFACTOR = Scenario(
    name="update_file_refactor",
    description="Refactor a function",
    user_queries=[
        "Add type hints to the process function",
        "Refactor process function to include type annotations",
    ],
    tool_calls=[
        ToolCall(
            name="update_file",
            arguments={
                "filepath": "src/main.py",
                "target": "def process(data):",
                "patch": "def process(data: list[dict]) -> dict:",
            },
        ),
    ],
    tool_responses=[
        "File 'src/main.py' updated successfully.\n\n--- a/src/main.py\n+++ b/src/main.py\n@@ -5,7 +5,7 @@\n-def process(data):\n+def process(data: list[dict]) -> dict:\n     \"\"\"Process the input data.\"\"\"",
    ],
    model_response_template="Added type hints to the `process` function: it now takes `list[dict]` and returns `dict`.",
    tags=["update_file", "refactor"],
)

# ============ WEB FETCH SCENARIOS ============

WEB_FETCH_DOCS = Scenario(
    name="web_fetch_docs",
    description="Fetch documentation from a URL",
    user_queries=[
        "Fetch the Python requests documentation",
        "Get the docs from https://docs.python.org/3/library/json.html",
        "Read the documentation at this URL",
    ],
    tool_calls=[
        ToolCall(
            name="web_fetch",
            arguments={"url": "https://docs.python.org/3/library/json.html"},
        ),
    ],
    tool_responses=[
        "# json - JSON encoder and decoder\n\nJSON (JavaScript Object Notation) is a lightweight data interchange format...\n\n## Basic Usage\n\n```python\nimport json\ndata = json.loads('{\"key\": \"value\"}')\n```",
    ],
    model_response_template="The Python json module documentation covers JSON encoding and decoding. The basic usage shows `json.loads()` for parsing JSON strings.",
    tags=["web_fetch", "documentation"],
)

# ============ MULTI-STEP SCENARIOS ============

MULTI_STEP_EXPLORE = Scenario(
    name="multi_step_explore_codebase",
    description="Explore codebase structure before reading specific files",
    user_queries=[
        "Help me understand this codebase",
        "Explore the project structure",
        "What does this project do?",
    ],
    tool_calls=[
        ToolCall(name="list_dir", arguments={"directory": "."}),
        ToolCall(name="read_file", arguments={"filepath": "README.md"}),
    ],
    tool_responses=[
        "10 files  3 dirs\nproject/\n├── src/\n│   └── main.py\n├── tests/\n├── README.md\n└── pyproject.toml",
        "<file>\n00001| # My Project\n00002| \n00003| A tool for processing data.\n\n(End of file - total 3 lines)\n</file>",
    ],
    model_response_template="This project is a data processing tool. It has:\n- Source code in `src/`\n- Tests in `tests/`\n- Standard Python packaging with pyproject.toml",
    tags=["multi_step", "explore"],
)

MULTI_STEP_FIND_AND_READ = Scenario(
    name="multi_step_find_and_read",
    description="Find a file then read it",
    user_queries=[
        "Find the configuration file and show me its contents",
        "Where is the config and what does it contain?",
    ],
    tool_calls=[
        ToolCall(name="glob", arguments={"pattern": "**/config*"}),
        ToolCall(name="read_file", arguments={"filepath": "src/config.py"}),
    ],
    tool_responses=[
        "[source:index]\nFound 2 files matching pattern: **/config*\n\nsrc/config.py\nconfig.yaml",
        "<file>\n00001| \"\"\"Configuration module.\"\"\"\n00002| \n00003| DEBUG = True\n00004| PORT = 8080\n\n(End of file - total 4 lines)\n</file>",
    ],
    model_response_template="Found 2 config files. The main `src/config.py` sets DEBUG=True and PORT=8080.",
    tags=["multi_step", "find_read"],
)

# ============ ERROR RECOVERY SCENARIOS ============

ERROR_FILE_NOT_FOUND = Scenario(
    name="error_file_not_found",
    description="Handle file not found error with recovery",
    user_queries=[
        "Read the config.yml file",
        "Show me config.yml",
    ],
    tool_calls=[
        ToolCall(name="read_file", arguments={"filepath": "config.yml"}),
        ToolCall(name="glob", arguments={"pattern": "**/config*"}),
        ToolCall(name="read_file", arguments={"filepath": "config.yaml"}),
    ],
    tool_responses=[
        "File not found: config.yml. Check the path.",
        "[source:filesystem]\nFound 1 file matching pattern: **/config*\n\nconfig.yaml",
        "<file>\n00001| debug: true\n00002| port: 8080\n\n(End of file - total 2 lines)\n</file>",
    ],
    model_response_template="The file was `config.yaml` (not .yml). It contains debug=true and port=8080.",
    tags=["error_recovery", "file_not_found"],
)

ERROR_TYPO_RECOVERY = Scenario(
    name="error_typo_recovery",
    description="Recover from typo in tool arguments",
    user_queries=[
        "Search for imports in mian.py",
        "Find imports in mian.py",
    ],
    tool_calls=[
        ToolCall(name="grep", arguments={"pattern": "import", "include_files": "mian.py"}),
        ToolCall(name="glob", arguments={"pattern": "**/main*.py"}),
        ToolCall(name="grep", arguments={"pattern": "import", "include_files": "main.py"}),
    ],
    tool_responses=[
        "No files found matching pattern: mian.py",
        "[source:filesystem]\nFound 1 file matching pattern: **/main*.py\n\nsrc/main.py",
        "Found 3 matches in 1 file\n\nsrc/main.py:1: import sys\nsrc/main.py:2: import os\nsrc/main.py:3: from pathlib import Path",
    ],
    model_response_template="Found the imports in `src/main.py` (note: the file is 'main.py' not 'mian.py'):\n- import sys\n- import os\n- from pathlib import Path",
    tags=["error_recovery", "typo"],
)


# ============ SCENARIO REGISTRY ============

ALL_SCENARIOS: list[Scenario] = [
    # Read file
    READ_FILE_BASIC,
    READ_FILE_WITH_OFFSET,
    # Grep
    GREP_PATTERN,
    GREP_FUNCTION_DEF,
    # Glob
    GLOB_PYTHON_FILES,
    GLOB_SPECIFIC_PATTERN,
    # List dir
    LIST_DIR_BASIC,
    LIST_DIR_SUBDIRECTORY,
    # Bash
    BASH_GIT_STATUS,
    BASH_RUN_TESTS,
    BASH_INSTALL_DEPS,
    # Write file
    WRITE_FILE_NEW,
    # Update file
    UPDATE_FILE_FIX,
    UPDATE_FILE_REFACTOR,
    # Web fetch
    WEB_FETCH_DOCS,
    # Multi-step
    MULTI_STEP_EXPLORE,
    MULTI_STEP_FIND_AND_READ,
    # Error recovery
    ERROR_FILE_NOT_FOUND,
    ERROR_TYPO_RECOVERY,
]


def get_scenarios_by_tool(tool_name: str) -> list[Scenario]:
    """Get all scenarios that use a specific tool."""
    return [s for s in ALL_SCENARIOS if any(tc.name == tool_name for tc in s.tool_calls)]


def get_scenarios_by_tag(tag: str) -> list[Scenario]:
    """Get all scenarios with a specific tag."""
    return [s for s in ALL_SCENARIOS if tag in s.tags]


def get_random_scenarios(count: int = 10) -> list[Scenario]:
    """Get a random sample of scenarios."""
    return random.sample(ALL_SCENARIOS, min(count, len(ALL_SCENARIOS)))
