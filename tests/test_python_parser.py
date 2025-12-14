"""Tests for Python file parsing."""

from pathlib import Path

from tunacode.indexing.python_parser import parse_python_file

# Test fixtures - complex file content
COMPLEX_FILE_CONTENT = '''"""Module docstring."""
import os
from pathlib import Path

class MyClass:
    """Class docstring."""

    def method(self):
        pass

def standalone_function():
    """Function docstring."""
    return 42

class AnotherClass(Base):
    pass
'''


class TestParsePythonFile:
    """Test Python source file parsing."""

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        """Should handle empty files."""
        file_path = tmp_path / "empty.py"
        file_path.write_text("")

        imports, classes, functions = parse_python_file(file_path)

        assert imports == set()
        assert classes == []
        assert functions == []

    def test_parse_simple_import(self, tmp_path: Path) -> None:
        """Should extract simple import statements."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import os\nimport sys")

        imports, classes, functions = parse_python_file(file_path)

        assert "os" in imports
        assert "sys" in imports
        assert classes == []
        assert functions == []

    def test_parse_from_import(self, tmp_path: Path) -> None:
        """Should extract from...import statements."""
        file_path = tmp_path / "test.py"
        content = "from pathlib import Path\nfrom os.path import join"
        file_path.write_text(content)

        imports, classes, functions = parse_python_file(file_path)

        assert "pathlib" in imports
        assert "os" in imports

    def test_parse_class_definition(self, tmp_path: Path) -> None:
        """Should extract class definitions."""
        file_path = tmp_path / "test.py"
        content = "class MyClass:\n    pass\n\nclass AnotherClass(Base):\n    pass"
        file_path.write_text(content)

        imports, classes, functions = parse_python_file(file_path)

        assert "MyClass" in classes
        assert "AnotherClass" in classes
        assert len(classes) == 2

    def test_parse_function_definition(self, tmp_path: Path) -> None:
        """Should extract function definitions."""
        file_path = tmp_path / "test.py"
        content = "def my_func():\n    pass\n\ndef another_func(arg1, arg2):\n    return None"
        file_path.write_text(content)

        imports, classes, functions = parse_python_file(file_path)

        assert "my_func" in functions
        assert "another_func" in functions
        assert len(functions) == 2

    def test_parse_complex_file(self, tmp_path: Path) -> None:
        """Should parse a complex file with imports, classes, and functions."""
        file_path = tmp_path / "test.py"
        file_path.write_text(COMPLEX_FILE_CONTENT)

        imports, classes, functions = parse_python_file(file_path)

        assert "os" in imports
        assert "pathlib" in imports
        assert "MyClass" in classes
        assert "AnotherClass" in classes
        assert "method" in functions
        assert "standalone_function" in functions

    def test_ignore_inline_class_keyword(self, tmp_path: Path) -> None:
        """Should not extract class keyword from comments or strings."""
        file_path = tmp_path / "test.py"
        content = '# class Comment\nx = "class in string"'
        file_path.write_text(content)

        imports, classes, functions = parse_python_file(file_path)

        assert classes == []

    def test_ignore_inline_def_keyword(self, tmp_path: Path) -> None:
        """Should not extract def keyword from comments or strings."""
        file_path = tmp_path / "test.py"
        content = '# def comment\nx = "def in string"'
        file_path.write_text(content)

        imports, classes, functions = parse_python_file(file_path)

        assert functions == []

    def test_handle_malformed_file(self, tmp_path: Path) -> None:
        """Should handle malformed Python files gracefully."""
        file_path = tmp_path / "bad.py"
        file_path.write_text("import\nclass\ndef")

        imports, classes, functions = parse_python_file(file_path)

        assert isinstance(imports, set)
        assert isinstance(classes, list)
        assert isinstance(functions, list)

    def test_handle_nonexistent_file(self, tmp_path: Path) -> None:
        """Should handle nonexistent files gracefully."""
        file_path = tmp_path / "nonexistent.py"

        imports, classes, functions = parse_python_file(file_path)

        assert imports == set()
        assert classes == []
        assert functions == []

    def test_handle_binary_file(self, tmp_path: Path) -> None:
        """Should handle binary files gracefully."""
        file_path = tmp_path / "binary.py"
        file_path.write_bytes(b"\x00\x01\x02\x03")

        imports, classes, functions = parse_python_file(file_path)

        assert isinstance(imports, set)
        assert isinstance(classes, list)
        assert isinstance(functions, list)

    def test_nested_imports(self, tmp_path: Path) -> None:
        """Should extract top-level module from nested imports."""
        file_path = tmp_path / "test.py"
        file_path.write_text("from foo.bar.baz import something")

        imports, classes, functions = parse_python_file(file_path)

        assert "foo" in imports
        assert "bar" not in imports
        assert "baz" not in imports

    def test_comma_separated_imports(self, tmp_path: Path) -> None:
        """Should extract all modules from comma-separated import statements."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import os, sys, json")

        imports, classes, functions = parse_python_file(file_path)

        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports

    def test_comma_separated_imports_with_alias(self, tmp_path: Path) -> None:
        """Should extract module names from aliased comma-separated imports."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import os, sys as system, json as j")

        imports, classes, functions = parse_python_file(file_path)

        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports
        assert "system" not in imports
        assert "j" not in imports
