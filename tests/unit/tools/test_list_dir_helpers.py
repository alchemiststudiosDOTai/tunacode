"""Tests for list_dir helper functions in tunacode.tools.list_dir."""

from unittest.mock import MagicMock

from tunacode.tools.list_dir import (
    TREE_LAST,
    _collect_files,
    _render_tree,
)


class TestRenderTree:
    def test_single_file(self):
        tree, file_count, dir_count = _render_tree("project", ["main.py"])
        assert file_count == 1
        assert dir_count == 0
        assert "main.py" in tree
        assert "project/" in tree

    def test_multiple_files(self):
        tree, file_count, dir_count = _render_tree("project", ["a.py", "b.py"])
        assert file_count == 2
        assert "a.py" in tree
        assert "b.py" in tree

    def test_nested_files(self):
        files = ["src/main.py", "src/utils.py", "README.md"]
        tree, file_count, dir_count = _render_tree("project", files)
        assert file_count == 3
        assert dir_count >= 1
        assert "src/" in tree
        assert "main.py" in tree
        assert "README.md" in tree

    def test_deeply_nested(self):
        files = ["a/b/c/d.py"]
        tree, file_count, dir_count = _render_tree("root", files)
        assert file_count == 1
        assert dir_count >= 1
        assert "d.py" in tree

    def test_uses_tree_connectors(self):
        files = ["a.py", "b.py"]
        tree, _, _ = _render_tree("root", files)
        assert TREE_LAST in tree

    def test_empty_files(self):
        tree, file_count, dir_count = _render_tree("root", [])
        assert file_count == 0
        assert "root/" in tree


def _make_ignore_manager():
    mgr = MagicMock()
    mgr.should_ignore_dir.return_value = False
    mgr.should_ignore.return_value = False
    return mgr


class TestCollectFiles:
    def test_collects_files(self, tmp_path):
        (tmp_path / "file1.py").write_text("")
        (tmp_path / "file2.txt").write_text("")
        mgr = _make_ignore_manager()

        files = _collect_files(
            tmp_path,
            max_files=100,
            show_hidden=False,
            ignore_manager=mgr,
        )
        assert len(files) == 2
        assert "file1.py" in files
        assert "file2.txt" in files

    def test_respects_max_files(self, tmp_path):
        for i in range(20):
            (tmp_path / f"file{i}.py").write_text("")
        mgr = _make_ignore_manager()

        files = _collect_files(
            tmp_path,
            max_files=5,
            show_hidden=False,
            ignore_manager=mgr,
        )
        assert len(files) == 5

    def test_skips_hidden_by_default(self, tmp_path):
        (tmp_path / "visible.py").write_text("")
        (tmp_path / ".hidden.py").write_text("")
        mgr = _make_ignore_manager()

        files = _collect_files(
            tmp_path,
            max_files=100,
            show_hidden=False,
            ignore_manager=mgr,
        )
        assert "visible.py" in files
        assert ".hidden.py" not in files

    def test_shows_hidden_when_requested(self, tmp_path):
        (tmp_path / ".hidden.py").write_text("")
        mgr = _make_ignore_manager()

        files = _collect_files(
            tmp_path,
            max_files=100,
            show_hidden=True,
            ignore_manager=mgr,
        )
        assert ".hidden.py" in files

    def test_skips_ignored_files(self, tmp_path):
        (tmp_path / "keep.py").write_text("")
        (tmp_path / "skip.pyc").write_text("")
        mgr = MagicMock()
        mgr.should_ignore_dir.return_value = False
        mgr.should_ignore.side_effect = lambda p: p.suffix == ".pyc"

        files = _collect_files(
            tmp_path,
            max_files=100,
            show_hidden=False,
            ignore_manager=mgr,
        )
        assert "keep.py" in files
        assert "skip.pyc" not in files

    def test_skips_ignored_dirs(self, tmp_path):
        sub = tmp_path / "node_modules"
        sub.mkdir()
        (sub / "index.js").write_text("")
        (tmp_path / "app.py").write_text("")
        mgr = MagicMock()
        mgr.should_ignore_dir.side_effect = lambda p: p.name == "node_modules"
        mgr.should_ignore.return_value = False

        files = _collect_files(
            tmp_path,
            max_files=100,
            show_hidden=False,
            ignore_manager=mgr,
        )
        assert "app.py" in files
        assert all("node_modules" not in f for f in files)

    def test_uses_posix_paths(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("")
        mgr = _make_ignore_manager()

        files = _collect_files(
            tmp_path,
            max_files=100,
            show_hidden=False,
            ignore_manager=mgr,
        )
        assert "src/main.py" in files
