"""Tests for tunacode.configuration.paths."""

import hashlib
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from tunacode.configuration.paths import (
    check_for_updates,
    delete_session_file,
    get_cwd,
    get_project_id,
    get_session_dir,
    get_session_storage_dir,
    get_tunacode_home,
)
from tunacode.constants import SESSIONS_SUBDIR, TUNACODE_HOME_DIR


class TestGetTunaCodeHome:
    def test_returns_path_under_home(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_tunacode_home()
            assert result == tmp_path / TUNACODE_HOME_DIR
            assert result.exists()

    def test_creates_directory(self, tmp_path):
        home_dir = tmp_path / TUNACODE_HOME_DIR
        assert not home_dir.exists()

        with patch.object(Path, "home", return_value=tmp_path):
            result = get_tunacode_home()
            assert result == home_dir
            assert home_dir.exists()


class TestGetSessionDir:
    def test_creates_session_directory(self, tmp_path):
        state_manager = MagicMock()
        state_manager.session.session_id = "test-session-123"

        with patch.object(Path, "home", return_value=tmp_path):
            result = get_session_dir(state_manager)
            expected = tmp_path / TUNACODE_HOME_DIR / SESSIONS_SUBDIR / "test-session-123"
            assert result == expected
            assert result.exists()


class TestGetCwd:
    def test_returns_current_directory(self):
        assert get_cwd() == os.getcwd()


class TestGetProjectId:
    def test_returns_16_char_hex(self):
        result = get_project_id()
        assert len(result) == 16
        int(result, 16)  # validates hex

    def test_falls_back_to_cwd_hash_on_git_failure(self):
        with patch("tunacode.configuration.paths.subprocess.run", side_effect=Exception("no git")):
            result = get_project_id()
            expected = hashlib.sha256(os.getcwd().encode()).hexdigest()[:16]
            assert result == expected


class TestGetSessionStorageDir:
    def test_default_path(self, tmp_path):
        with (
            patch.dict(os.environ, {}, clear=False),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            os.environ.pop("XDG_DATA_HOME", None)
            result = get_session_storage_dir()
            expected = tmp_path / ".local" / "share" / "tunacode" / "sessions"
            assert result == expected

    def test_xdg_override(self, tmp_path):
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            result = get_session_storage_dir()
            expected = tmp_path / "tunacode" / "sessions"
            assert result == expected
            assert result.exists()


class TestDeleteSessionFile:
    def test_deletes_existing_file(self, tmp_path):
        with patch("tunacode.configuration.paths.get_session_storage_dir", return_value=tmp_path):
            session_file = tmp_path / "proj123_sess456.json"
            session_file.write_text("{}")
            assert session_file.exists()

            result = delete_session_file("proj123", "sess456")
            assert result is True
            assert not session_file.exists()

    def test_returns_true_when_file_missing(self, tmp_path):
        with patch("tunacode.configuration.paths.get_session_storage_dir", return_value=tmp_path):
            result = delete_session_file("proj123", "sess456")
            assert result is True

    def test_returns_false_on_error(self):
        with patch(
            "tunacode.configuration.paths.get_session_storage_dir",
            side_effect=Exception("boom"),
        ):
            result = delete_session_file("proj123", "sess456")
            assert result is False


class TestCheckForUpdates:
    def test_returns_false_on_subprocess_failure(self):
        with patch(
            "tunacode.configuration.paths.subprocess.run",
            side_effect=Exception("pip not found"),
        ):
            has_update, _version = check_for_updates()
            assert has_update is False

    def test_returns_false_when_no_newer_version(self):
        mock_result = MagicMock()
        mock_result.stdout = "Available versions: 0.0.1"

        with patch("tunacode.configuration.paths.subprocess.run", return_value=mock_result):
            has_update, _ = check_for_updates()
            assert has_update is False
