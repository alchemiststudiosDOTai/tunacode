"""Tests for index storage and lookup operations."""

from pathlib import Path

from tunacode.indexing.index_storage import IndexStorage, _normalize_file_type


class TestNormalizeFileType:
    """Test file type normalization helper."""

    def test_none_returns_none(self) -> None:
        """Should return None for None input."""
        assert _normalize_file_type(None) is None

    def test_with_leading_dot(self) -> None:
        """Should return unchanged if already has dot."""
        assert _normalize_file_type(".py") == ".py"

    def test_without_leading_dot(self) -> None:
        """Should add leading dot if missing."""
        assert _normalize_file_type("py") == ".py"


class TestIndexStorage:
    """Test IndexStorage class."""

    def test_initialization(self) -> None:
        """Should initialize empty storage."""
        storage = IndexStorage()
        stats = storage.get_stats()
        assert stats["total_files"] == 0
        assert stats["unique_basenames"] == 0
        assert stats["python_files_indexed"] == 0
        assert stats["classes_indexed"] == 0
        assert stats["functions_indexed"] == 0

    def test_add_simple_file(self) -> None:
        """Should add a simple file to storage."""
        storage = IndexStorage()
        path = Path("src/test.py")
        storage.add_file(path)

        stats = storage.get_stats()
        assert stats["total_files"] == 1
        assert stats["unique_basenames"] == 1

        results = storage.lookup("test.py")
        assert path in results

    def test_add_file_with_symbols(self) -> None:
        """Should add file with Python symbols."""
        storage = IndexStorage()
        path = Path("src/module.py")
        imports = {"os", "sys"}
        classes = ["MyClass", "AnotherClass"]
        functions = ["my_func", "another_func"]

        storage.add_file(path, imports, classes, functions)

        stats = storage.get_stats()
        assert stats["total_files"] == 1
        assert stats["python_files_indexed"] == 1
        assert stats["classes_indexed"] == 2
        assert stats["functions_indexed"] == 2

    def test_add_file_replace_semantics(self) -> None:
        """Should replace existing file data without duplicates."""
        storage = IndexStorage()
        path = Path("src/module.py")

        storage.add_file(path, {"os"}, ["OldClass"], ["old_func"])
        storage.add_file(path, {"sys"}, ["NewClass"], ["new_func"])

        stats = storage.get_stats()
        assert stats["total_files"] == 1
        assert stats["classes_indexed"] == 1
        assert stats["functions_indexed"] == 1

        assert storage.lookup("NewClass") == [path]
        assert storage.lookup("OldClass") == []

    def test_add_file_with_empty_imports(self) -> None:
        """Should track Python file with no imports."""
        storage = IndexStorage()
        path = Path("src/empty.py")

        storage.add_file(path, imports=set())

        stats = storage.get_stats()
        assert stats["python_files_indexed"] == 1

    def test_add_file_clears_stale_imports(self) -> None:
        """Should clear old imports when re-adding file with empty imports."""
        storage = IndexStorage()
        path = Path("src/module.py")

        storage.add_file(path, imports={"os", "sys"})
        assert storage.find_imports("os") == [path]

        storage.add_file(path, imports=set())
        assert storage.find_imports("os") == []

    def test_remove_file(self) -> None:
        """Should remove file from all indices."""
        storage = IndexStorage()
        path = Path("src/test.py")
        storage.add_file(path, {"os"}, ["MyClass"], ["my_func"])

        storage.remove_file(path)

        stats = storage.get_stats()
        assert stats["total_files"] == 0
        assert stats["python_files_indexed"] == 0
        assert stats["classes_indexed"] == 0
        assert stats["functions_indexed"] == 0

    def test_clear(self) -> None:
        """Should clear all index data."""
        storage = IndexStorage()
        storage.add_file(Path("test1.py"))
        storage.add_file(Path("test2.py"))

        storage.clear()

        stats = storage.get_stats()
        assert stats["total_files"] == 0

    def test_lookup_by_basename(self) -> None:
        """Should find files by exact basename match."""
        storage = IndexStorage()
        path1 = Path("src/test.py")
        path2 = Path("tests/test.py")
        storage.add_file(path1)
        storage.add_file(path2)

        results = storage.lookup("test.py")
        assert path1 in results
        assert path2 in results

    def test_lookup_by_partial_name(self) -> None:
        """Should find files by partial name match."""
        storage = IndexStorage()
        path = Path("src/my_module.py")
        storage.add_file(path)

        results = storage.lookup("module")
        assert path in results

    def test_lookup_by_path(self) -> None:
        """Should find files by path component."""
        storage = IndexStorage()
        path = Path("src/core/utils.py")
        storage.add_file(path)

        results = storage.lookup("core")
        assert path in results

    def test_lookup_by_class_name(self) -> None:
        """Should find files by class name."""
        storage = IndexStorage()
        path = Path("src/models.py")
        storage.add_file(path, classes=["MyClass"])

        results = storage.lookup("MyClass")
        assert path in results

    def test_lookup_by_function_name(self) -> None:
        """Should find files by function name."""
        storage = IndexStorage()
        path = Path("src/utils.py")
        storage.add_file(path, functions=["my_func"])

        results = storage.lookup("my_func")
        assert path in results

    def test_lookup_with_file_type_filter(self) -> None:
        """Should filter results by file type."""
        storage = IndexStorage()
        py_path = Path("src/test.py")
        js_path = Path("src/test.js")
        storage.add_file(py_path)
        storage.add_file(js_path)

        results = storage.lookup("test", file_type=".py")
        assert py_path in results
        assert js_path not in results

    def test_lookup_with_file_type_no_dot(self) -> None:
        """Should accept file type without leading dot."""
        storage = IndexStorage()
        path = Path("src/test.py")
        storage.add_file(path)

        results = storage.lookup("test", file_type="py")
        assert path in results

    def test_lookup_sorts_by_relevance(self) -> None:
        """Should sort results with exact matches first."""
        storage = IndexStorage()
        exact = Path("test.py")
        partial1 = Path("src/test_utils.py")
        partial2 = Path("deep/path/to/test.py")

        storage.add_file(partial1)
        storage.add_file(partial2)
        storage.add_file(exact)

        results = storage.lookup("test.py")
        assert results[0] == exact

    def test_lookup_empty_query_returns_empty(self) -> None:
        """Should return empty list for empty query."""
        storage = IndexStorage()
        storage.add_file(Path("test.py"))
        storage.add_file(Path("module.py"))

        results = storage.lookup("")
        assert results == []

    def test_get_all_files(self) -> None:
        """Should return all indexed files."""
        storage = IndexStorage()
        path1 = Path("src/file1.py")
        path2 = Path("src/file2.py")
        storage.add_file(path1)
        storage.add_file(path2)

        all_files = storage.get_all_files()
        assert len(all_files) == 2
        assert path1 in all_files
        assert path2 in all_files

    def test_get_all_files_with_filter(self) -> None:
        """Should filter files by extension."""
        storage = IndexStorage()
        py_file = Path("test.py")
        js_file = Path("test.js")
        storage.add_file(py_file)
        storage.add_file(js_file)

        py_files = storage.get_all_files(file_type=".py")
        assert len(py_files) == 1
        assert py_file in py_files

    def test_find_imports(self) -> None:
        """Should find files that import a module."""
        storage = IndexStorage()
        path1 = Path("src/module1.py")
        path2 = Path("src/module2.py")
        path3 = Path("src/module3.py")

        storage.add_file(path1, imports={"os", "sys"})
        storage.add_file(path2, imports={"os"})
        storage.add_file(path3, imports={"pathlib"})

        results = storage.find_imports("os")
        assert len(results) == 2
        assert path1 in results
        assert path2 in results
        assert path3 not in results

    def test_multiple_files_same_basename(self) -> None:
        """Should handle multiple files with same basename."""
        storage = IndexStorage()
        path1 = Path("src/__init__.py")
        path2 = Path("tests/__init__.py")
        path3 = Path("docs/__init__.py")

        storage.add_file(path1)
        storage.add_file(path2)
        storage.add_file(path3)

        results = storage.lookup("__init__.py")
        assert len(results) == 3

    def test_remove_nonexistent_file(self) -> None:
        """Should handle removal of nonexistent files gracefully."""
        storage = IndexStorage()
        storage.remove_file(Path("nonexistent.py"))
        assert storage.get_stats()["total_files"] == 0

    def test_case_insensitive_lookup(self) -> None:
        """Should perform case-insensitive lookups."""
        storage = IndexStorage()
        path = Path("src/MyModule.py")
        storage.add_file(path)

        results = storage.lookup("mymodule")
        assert path in results

    def test_empty_lookup(self) -> None:
        """Should handle empty lookups gracefully."""
        storage = IndexStorage()
        results = storage.lookup("nonexistent")
        assert results == []

    def test_stats_accuracy(self) -> None:
        """Should maintain accurate statistics."""
        storage = IndexStorage()

        storage.add_file(
            Path("src/module.py"),
            imports={"os", "sys"},
            classes=["Class1", "Class2"],
            functions=["func1", "func2", "func3"],
        )

        storage.add_file(Path("README.md"))

        stats = storage.get_stats()
        assert stats["total_files"] == 2
        assert stats["python_files_indexed"] == 1
        assert stats["classes_indexed"] == 2
        assert stats["functions_indexed"] == 3
        assert stats["unique_basenames"] == 2
