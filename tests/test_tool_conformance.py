"""Pattern validation tests - ensure all tools follow architectural rules.

Auto-discovers all tools in tunacode/tools/ and validates:
- All are async callables
- All have docstrings (from XML or inline)
- File tools have filepath as first parameter
- All have valid return annotations
"""

import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import cast

import pytest

from tests.tool_conformance_utils import DEFAULT_TOOL_RULES, ToolViolation, validate_tool
from tunacode.tools.xml_helper import load_prompt_from_xml

FILEPATH_PARAM_NAME = DEFAULT_TOOL_RULES.filepath_param_name
FIRST_PARAM_INDEX = 0
MIN_DISCOVERED_TOOL_COUNT = 1
MIN_TOOL_PARAM_COUNT = DEFAULT_TOOL_RULES.min_param_count
PRIVATE_NAME_PREFIX = "_"
PYTHON_MODULE_PATTERN = "*.py"
TOOLS_MODULE_PATH = "tunacode.tools"
ToolCallable = Callable[..., object]
VIOLATION_SEPARATOR = "; "


class ExcludedModule(str, Enum):
    INIT = "__init__"
    DECORATORS = "decorators"
    XML_HELPER = "xml_helper"
    REACT = "react"


class ToolsPathPart(str, Enum):
    SRC = "src"
    TUNACODE = "tunacode"
    TOOLS = "tools"


EXCLUDED_MODULES = frozenset(module.value for module in ExcludedModule)


def _tools_root() -> Path:
    repo_root = Path(__file__).parent.parent
    return (
        repo_root
        / ToolsPathPart.SRC.value
        / ToolsPathPart.TUNACODE.value
        / ToolsPathPart.TOOLS.value
    )


def discover_tools() -> tuple[list[ToolCallable], list[ToolCallable], list[ToolCallable]]:
    """Auto-discover all tool functions from tunacode/tools/*.py."""
    tools_dir = _tools_root()
    all_tools: list[ToolCallable] = []
    file_tools: list[ToolCallable] = []
    base_tools: list[ToolCallable] = []

    for py_file in tools_dir.glob(PYTHON_MODULE_PATTERN):
        module_name = py_file.stem
        if module_name in EXCLUDED_MODULES:
            continue
        if module_name.startswith(PRIVATE_NAME_PREFIX):
            continue

        module = importlib.import_module(f"{TOOLS_MODULE_PATH}.{module_name}")

        for name, obj in inspect.getmembers(module):
            if name.startswith(PRIVATE_NAME_PREFIX):
                continue
            if not inspect.iscoroutinefunction(obj):
                continue
            if getattr(obj, "__module__", "") != f"{TOOLS_MODULE_PATH}.{module_name}":
                continue

            tool = cast(ToolCallable, obj)
            all_tools.append(tool)

            signature = inspect.signature(tool)
            params = list(signature.parameters.keys())
            if params and params[FIRST_PARAM_INDEX] == FILEPATH_PARAM_NAME:
                file_tools.append(tool)
            else:
                base_tools.append(tool)

    return all_tools, file_tools, base_tools


@dataclass(frozen=True)
class ToolCollection:
    all_tools: list[ToolCallable]
    file_tools: list[ToolCallable]
    base_tools: list[ToolCallable]


@pytest.fixture()
def tool_collection() -> ToolCollection:
    all_tools, file_tools, base_tools = discover_tools()
    return ToolCollection(
        all_tools=all_tools,
        file_tools=file_tools,
        base_tools=base_tools,
    )


def _format_violations(tool_name: str, violations: tuple[ToolViolation, ...]) -> str:
    violation_messages = [violation.message for violation in violations]
    joined_messages = VIOLATION_SEPARATOR.join(violation_messages)
    return f"{tool_name} violations: {joined_messages}"


class TestToolDiscovery:
    """Verify tool discovery works."""

    def test_discovered_at_least_one_tool(self, tool_collection: ToolCollection):
        """Sanity check: we should find tools."""
        all_tool_count = len(tool_collection.all_tools)
        assert all_tool_count >= MIN_DISCOVERED_TOOL_COUNT, "No tools discovered"

    def test_discovered_file_tools(self, tool_collection: ToolCollection):
        """Should find file tools (read_file, write_file, update_file)."""
        file_tool_count = len(tool_collection.file_tools)
        assert file_tool_count >= MIN_DISCOVERED_TOOL_COUNT, "No file tools discovered"

    def test_discovered_base_tools(self, tool_collection: ToolCollection):
        """Should find base tools (bash, glob, grep, list_dir)."""
        base_tool_count = len(tool_collection.base_tools)
        assert base_tool_count >= MIN_DISCOVERED_TOOL_COUNT, "No base tools discovered"


class TestToolsAreAsyncCallables:
    """Verify all tools are async functions."""

    def test_all_tools_are_coroutine_functions(self, tool_collection: ToolCollection):
        """Every tool must be an async function."""
        for tool in tool_collection.all_tools:
            assert inspect.iscoroutinefunction(tool), f"{tool.__name__} is not an async function"


class TestToolsHaveDocstrings:
    """Verify all tools have documentation."""

    def test_all_tools_have_docstring(self, tool_collection: ToolCollection):
        """Every tool must have a docstring from its XML prompt."""
        for tool in tool_collection.all_tools:
            docstring = tool.__doc__
            assert docstring, f"{tool.__name__} has no docstring"
            xml_prompt = load_prompt_from_xml(tool.__name__)
            assert xml_prompt is not None, f"{tool.__name__} is missing an XML prompt"
            matches_xml_prompt = docstring == xml_prompt
            assert matches_xml_prompt, f"{tool.__name__} docstring does not match XML prompt"
            min_docstring_length = DEFAULT_TOOL_RULES.min_docstring_length
            assert len(docstring) > min_docstring_length, (
                f"{tool.__name__} docstring too short: {docstring!r}"
            )


class TestToolsAreDecorated:
    """Verify all tools are decorated with base_tool or file_tool."""

    def test_all_tools_are_wrapped(self, tool_collection: ToolCollection):
        """Every tool must be wrapped by the tool decorators."""
        for tool in tool_collection.all_tools:
            unwrapped = inspect.unwrap(tool)
            assert unwrapped is not tool, f"{tool.__name__} is not wrapped by a tool decorator"


class TestFileToolSignatures:
    """Verify file tool signatures follow the pattern."""

    def test_file_tools_have_filepath_first_param(self, tool_collection: ToolCollection):
        """File tools must have 'filepath' as first parameter."""
        for tool in tool_collection.file_tools:
            sig = inspect.signature(tool)
            params = list(sig.parameters.keys())
            assert len(params) >= MIN_TOOL_PARAM_COUNT, f"{tool.__name__} has no parameters"
            first_param = params[FIRST_PARAM_INDEX]
            filepath_param_name = DEFAULT_TOOL_RULES.filepath_param_name
            assert first_param == filepath_param_name, (
                f"{tool.__name__} first param is '{first_param}', expected '{filepath_param_name}'"
            )

    def test_file_tools_filepath_is_string(self, tool_collection: ToolCollection):
        """File tools' filepath parameter should be typed as str."""
        for tool in tool_collection.file_tools:
            sig = inspect.signature(tool)
            filepath_param = sig.parameters.get("filepath")
            assert filepath_param is not None
            annotation = filepath_param.annotation
            if annotation is not inspect.Parameter.empty:
                assert annotation is str, (
                    f"{tool.__name__} filepath annotation is {annotation}, expected str"
                )


class TestBaseToolSignatures:
    """Verify base tool signatures are valid."""

    def test_base_tools_have_parameters(self, tool_collection: ToolCollection):
        """Base tools should have at least one parameter."""
        for tool in tool_collection.base_tools:
            sig = inspect.signature(tool)
            params = list(sig.parameters.keys())
            assert len(params) >= MIN_TOOL_PARAM_COUNT, f"{tool.__name__} has no parameters"


class TestToolReturnAnnotations:
    """Verify tool return types are valid."""

    def test_tools_return_string_types(self, tool_collection: ToolCollection):
        """Tools should return str or have appropriate return annotation."""
        for tool in tool_collection.all_tools:
            sig = inspect.signature(tool)
            return_annotation = sig.return_annotation
            has_return_annotation = return_annotation is not inspect.Parameter.empty
            assert has_return_annotation, f"{tool.__name__} missing return annotation"
            return_type_name = DEFAULT_TOOL_RULES.return_type_name
            valid = return_annotation is str or return_type_name in str(return_annotation)
            assert valid, f"{tool.__name__} return annotation is {return_annotation}"


class TestToolRules:
    """Verify tool rules as a single validation pass."""

    def test_all_tools_follow_rules(self, tool_collection: ToolCollection):
        for tool in tool_collection.all_tools:
            violations = validate_tool(tool, rules=DEFAULT_TOOL_RULES)
            assert not violations, _format_violations(tool.__name__, violations)
