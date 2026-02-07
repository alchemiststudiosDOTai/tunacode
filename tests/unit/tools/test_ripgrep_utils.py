"""Tests for tunacode.tools.utils.ripgrep."""

from unittest.mock import MagicMock, patch

import pytest

from tunacode.tools.cache_accessors.ripgrep_cache import clear_ripgrep_cache
from tunacode.tools.utils.ripgrep import (
    RIPGREP_MATCH_FOUND_EXIT_CODE,
    RIPGREP_NO_MATCH_EXIT_CODE,
    RIPGREP_SUCCESS_EXIT_CODES,
    RipgrepExecutor,
    RipgrepMetrics,
    _check_ripgrep_version,
    get_platform_identifier,
    get_ripgrep_binary_path,
)

_RG = "tunacode.tools.utils.ripgrep"


class TestGetPlatformIdentifier:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        clear_ripgrep_cache()
        yield
        clear_ripgrep_cache()

    def test_darwin_arm64(self):
        with (
            patch(f"{_RG}.platform.system", return_value="Darwin"),
            patch(f"{_RG}.platform.machine", return_value="arm64"),
        ):
            key, system = get_platform_identifier()
            assert key == "arm64-darwin"
            assert system == "darwin"

    def test_darwin_x86(self):
        with (
            patch(f"{_RG}.platform.system", return_value="Darwin"),
            patch(f"{_RG}.platform.machine", return_value="x86_64"),
        ):
            key, _ = get_platform_identifier()
            assert key == "x64-darwin"

    def test_linux_x86(self):
        with (
            patch(f"{_RG}.platform.system", return_value="Linux"),
            patch(f"{_RG}.platform.machine", return_value="x86_64"),
        ):
            key, system = get_platform_identifier()
            assert key == "x64-linux"
            assert system == "linux"

    def test_linux_arm64(self):
        with (
            patch(f"{_RG}.platform.system", return_value="Linux"),
            patch(f"{_RG}.platform.machine", return_value="aarch64"),
        ):
            key, _ = get_platform_identifier()
            assert key == "arm64-linux"

    def test_windows_x86(self):
        with (
            patch(f"{_RG}.platform.system", return_value="Windows"),
            patch(f"{_RG}.platform.machine", return_value="x86_64"),
        ):
            key, _ = get_platform_identifier()
            assert key == "x64-win32"

    def test_unsupported_platform_raises(self):
        with (
            patch(f"{_RG}.platform.system", return_value="Haiku"),
            patch(f"{_RG}.platform.machine", return_value="riscv"),
            pytest.raises(ValueError, match="Unsupported platform"),
        ):
            get_platform_identifier()


class TestCheckRipgrepVersion:
    def test_sufficient_version(self, tmp_path):
        rg = tmp_path / "rg"
        mock_result = MagicMock(returncode=0, stdout="ripgrep 14.1.1\n")
        with patch(f"{_RG}.subprocess.run", return_value=mock_result):
            assert _check_ripgrep_version(rg, "13.0.0") is True

    def test_insufficient_version(self, tmp_path):
        rg = tmp_path / "rg"
        mock_result = MagicMock(returncode=0, stdout="ripgrep 12.0.0\n")
        with patch(f"{_RG}.subprocess.run", return_value=mock_result):
            assert _check_ripgrep_version(rg, "13.0.0") is False

    def test_equal_version(self, tmp_path):
        rg = tmp_path / "rg"
        mock_result = MagicMock(returncode=0, stdout="ripgrep 13.0.0\n")
        with patch(f"{_RG}.subprocess.run", return_value=mock_result):
            assert _check_ripgrep_version(rg, "13.0.0") is True

    def test_returns_false_on_exception(self, tmp_path):
        rg = tmp_path / "rg"
        with patch(f"{_RG}.subprocess.run", side_effect=OSError("boom")):
            assert _check_ripgrep_version(rg) is False

    def test_returns_false_on_nonzero_exit(self, tmp_path):
        rg = tmp_path / "rg"
        mock_result = MagicMock(returncode=1)
        with patch(f"{_RG}.subprocess.run", return_value=mock_result):
            assert _check_ripgrep_version(rg) is False


class TestGetRipgrepBinaryPath:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        clear_ripgrep_cache()
        yield
        clear_ripgrep_cache()

    def test_env_override(self, tmp_path):
        rg = tmp_path / "rg"
        rg.write_text("fake binary")
        with patch.dict("os.environ", {"TUNACODE_RIPGREP_PATH": str(rg)}):
            assert get_ripgrep_binary_path() == rg

    def test_env_override_nonexistent_file(self, tmp_path):
        with (
            patch.dict("os.environ", {"TUNACODE_RIPGREP_PATH": str(tmp_path / "nope")}),
            patch(f"{_RG}.shutil.which", return_value=None),
            patch(f"{_RG}.get_platform_identifier", side_effect=ValueError),
        ):
            assert get_ripgrep_binary_path() is None

    def test_system_rg_used_when_version_ok(self, tmp_path, monkeypatch):
        rg_path = tmp_path / "rg"
        rg_path.write_text("fake")
        monkeypatch.delenv("TUNACODE_RIPGREP_PATH", raising=False)
        with (
            patch(f"{_RG}.shutil.which", return_value=str(rg_path)),
            patch(f"{_RG}._check_ripgrep_version", return_value=True),
        ):
            assert get_ripgrep_binary_path() == rg_path

    def test_returns_none_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("TUNACODE_RIPGREP_PATH", raising=False)
        with (
            patch(f"{_RG}.shutil.which", return_value=None),
            patch(f"{_RG}.get_platform_identifier", side_effect=ValueError),
        ):
            assert get_ripgrep_binary_path() is None


class TestRipgrepExecutor:
    def test_init_with_custom_path(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        assert executor.binary_path == rg
        assert executor._use_python_fallback is False

    def test_init_no_binary_uses_fallback(self):
        with patch(f"{_RG}.get_ripgrep_binary_path", return_value=None):
            executor = RipgrepExecutor(binary_path=None)
            assert executor._use_python_fallback is True

    def test_build_command_basic(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        cmd = executor._build_command("pattern", "/path")
        assert cmd == [str(rg), "pattern", "/path"]

    def test_build_command_case_insensitive(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        cmd = executor._build_command("pattern", "/path", case_insensitive=True)
        assert "-i" in cmd

    def test_build_command_multiline(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        cmd = executor._build_command("pattern", "/path", multiline=True)
        assert "-U" in cmd
        assert "--multiline-dotall" in cmd

    def test_build_command_context(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        cmd = executor._build_command(
            "pattern",
            "/path",
            context_before=3,
            context_after=5,
        )
        assert "-B" in cmd
        assert "3" in cmd
        assert "-A" in cmd
        assert "5" in cmd

    def test_build_command_max_matches(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        cmd = executor._build_command("pattern", "/path", max_matches=10)
        assert "-m" in cmd
        assert "10" in cmd

    def test_build_command_file_pattern(self, tmp_path):
        rg = tmp_path / "rg"
        executor = RipgrepExecutor(binary_path=rg)
        cmd = executor._build_command("pattern", "/path", file_pattern="*.py")
        assert "-g" in cmd
        assert "*.py" in cmd


class TestRipgrepExecutorSearch:
    @pytest.fixture(autouse=True)
    def _force_no_binary(self, monkeypatch):
        monkeypatch.setattr(f"{_RG}.get_ripgrep_binary_path", lambda: None)

    @pytest.mark.asyncio
    async def test_python_fallback_search(self, tmp_path):
        (tmp_path / "test.py").write_text("hello world\nfoo bar\n")
        executor = RipgrepExecutor(binary_path=None)
        results = await executor.search("hello", str(tmp_path))
        assert any("hello" in r for r in results)

    @pytest.mark.asyncio
    async def test_python_fallback_case_insensitive(self, tmp_path):
        (tmp_path / "test.py").write_text("Hello World\n")
        executor = RipgrepExecutor(binary_path=None)
        results = await executor.search(
            "hello",
            str(tmp_path),
            case_insensitive=True,
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_python_fallback_no_match(self, tmp_path):
        (tmp_path / "test.py").write_text("hello world\n")
        executor = RipgrepExecutor(binary_path=None)
        results = await executor.search("zzzzz", str(tmp_path))
        assert results == []

    @pytest.mark.asyncio
    async def test_python_fallback_invalid_regex_raises(self, tmp_path):
        import re

        (tmp_path / "test.py").write_text("hello\n")
        executor = RipgrepExecutor(binary_path=None)
        with pytest.raises(re.error):
            await executor.search("[invalid", str(tmp_path))


class TestRipgrepExecutorListFiles:
    def test_python_fallback_list_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        executor = RipgrepExecutor(binary_path=None)
        assert len(executor.list_files("*.py", str(tmp_path))) == 2


class TestRipgrepMetrics:
    def test_initial_state(self):
        m = RipgrepMetrics()
        assert m.search_count == 0
        assert m.total_search_time == 0.0
        assert m.fallback_count == 0

    def test_record_search(self):
        m = RipgrepMetrics()
        m.record_search(0.5)
        assert m.search_count == 1
        assert m.total_search_time == pytest.approx(0.5)
        assert m.fallback_count == 0

    def test_record_fallback(self):
        m = RipgrepMetrics()
        m.record_search(0.3, used_fallback=True)
        assert m.fallback_count == 1

    def test_average_search_time(self):
        m = RipgrepMetrics()
        m.record_search(1.0)
        m.record_search(3.0)
        assert m.average_search_time == pytest.approx(2.0)

    def test_average_search_time_zero(self):
        assert RipgrepMetrics().average_search_time == 0.0

    def test_fallback_rate(self):
        m = RipgrepMetrics()
        m.record_search(0.1, used_fallback=True)
        m.record_search(0.1, used_fallback=False)
        assert m.fallback_rate == pytest.approx(0.5)

    def test_fallback_rate_zero(self):
        assert RipgrepMetrics().fallback_rate == 0.0


class TestConstants:
    def test_success_exit_codes(self):
        assert RIPGREP_MATCH_FOUND_EXIT_CODE in RIPGREP_SUCCESS_EXIT_CODES
        assert RIPGREP_NO_MATCH_EXIT_CODE in RIPGREP_SUCCESS_EXIT_CODES
        assert 2 not in RIPGREP_SUCCESS_EXIT_CODES
