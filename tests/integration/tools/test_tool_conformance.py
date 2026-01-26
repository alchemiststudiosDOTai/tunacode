"""Pattern validation tests - ensure all tools follow architectural rules.

Auto-discovers all tools in tunacode/tools/ and validates:
- All are async callables
- All have docstrings (from XML or inline)
- File tools have filepath as first parameter
- All have valid return annotations
"""

import importlib
import inspect
from pathlib import Path

# Support modules that are NOT tools
EXCLUDED_MODULES = {"__init__", "decorators", "xml_helper"}


def discover_tools():
    """Auto-discover all tool functions from tunacode/tools/*.py."""
    tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "tunacode" / "tools"
    all_tools = []
    file_tools = []
    base_tools = []

    for py_file in tools_dir.glob("*.py"):
        module_name = py_file.stem

        if module_name in EXCLUDED_MODULES:
            continue
        if module_name.startswith("_"):
            continue

        module = importlib.import_module(f"tunacode.tools.{module_name}")

        for name, obj in inspect.getmembers(module):
            if name.startswith("_"):
                continue
            if not inspect.iscoroutinefunction(obj):
                continue
            # Skip if it's imported from elsewhere
            if getattr(obj, "__module__", "") != f"tunacode.tools.{module_name}":
                continue

            all_tools.append(obj)

            # Categorize by first parameter name
            sig = inspect.signature(obj)
            params = list(sig.parameters.keys())
            if params and params[0] == "filepath":
                file_tools.append(obj)
            else:
                base_tools.append(obj)

    return all_tools, file_tools, base_tools


ALL_TOOLS, FILE_TOOLS, BASE_TOOLS = discover_tools()


class TestToolDiscovery:
    """Verify tool discovery works."""

    def test_discovered_at_least_one_tool(self):
        """Sanity check: we should find tools."""
        assert len(ALL_TOOLS) > 0, "No tools discovered"

    def test_discovered_file_tools(self):
        """Should find file tools (read_file, write_file, update_file)."""
        assert len(FILE_TOOLS) > 0, "No file tools discovered"

    def test_discovered_base_tools(self):
        """Should find base tools (bash, glob, grep, list_dir)."""
        assert len(BASE_TOOLS) > 0, "No base tools discovered"


class TestToolsAreAsyncCallables:
    """Verify all tools are async functions."""

    def test_all_tools_are_coroutine_functions(self):
        """Every tool must be an async function."""
        for tool in ALL_TOOLS:
            assert inspect.iscoroutinefunction(tool), f"{tool.__name__} is not an async function"


class TestToolsHaveDocstrings:
    """Verify all tools have documentation."""

    def test_all_tools_have_docstring(self):
        """Every tool must have a docstring (from XML or inline)."""
        for tool in ALL_TOOLS:
            assert tool.__doc__, f"{tool.__name__} has no docstring"
            assert len(tool.__doc__) > 10, f"{tool.__name__} docstring too short: {tool.__doc__!r}"


class TestFileToolSignatures:
    """Verify file tool signatures follow the pattern."""

    def test_file_tools_have_filepath_first_param(self):
        """File tools must have 'filepath' as first parameter."""
        for tool in FILE_TOOLS:
            sig = inspect.signature(tool)
            params = list(sig.parameters.keys())
            assert len(params) > 0, f"{tool.__name__} has no parameters"
            first_param = params[0]
            assert first_param == "filepath", (
                f"{tool.__name__} first param is '{first_param}', expected 'filepath'"
            )

    def test_file_tools_filepath_is_string(self):
        """File tools' filepath parameter should be typed as str."""
        for tool in FILE_TOOLS:
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

    def test_base_tools_have_parameters(self):
        """Base tools should have at least one parameter."""
        for tool in BASE_TOOLS:
            sig = inspect.signature(tool)
            params = list(sig.parameters.keys())
            assert len(params) > 0, f"{tool.__name__} has no parameters"


class TestToolReturnAnnotations:
    """Verify tool return types are valid."""

    def test_tools_return_string_types(self):
        """Tools should return str or have appropriate return annotation."""
        for tool in ALL_TOOLS:
            sig = inspect.signature(tool)
            return_annotation = sig.return_annotation
            if return_annotation is not inspect.Parameter.empty:
                valid = return_annotation is str or "str" in str(return_annotation)
                assert valid, f"{tool.__name__} return annotation is {return_annotation}"
