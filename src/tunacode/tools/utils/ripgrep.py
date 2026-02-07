"""Ripgrep binary management and execution utilities."""

import asyncio
import locale
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tunacode.tools.cache_accessors import ripgrep_cache

PROCESS_OUTPUT_ENCODING = locale.getpreferredencoding(False)
RIPGREP_MATCH_FOUND_EXIT_CODE = 0
RIPGREP_NO_MATCH_EXIT_CODE = 1
RIPGREP_SEARCH_TIMEOUT_SECONDS = 10
RIPGREP_VERSION_TIMEOUT_SECONDS = 1
RIPGREP_LIST_FILES_TIMEOUT_SECONDS = 5
RIPGREP_SUCCESS_EXIT_CODES = {
    RIPGREP_MATCH_FOUND_EXIT_CODE,
    RIPGREP_NO_MATCH_EXIT_CODE,
}


def get_platform_identifier() -> tuple[str, str]:
    """Get the current platform identifier.

    Returns:
        Tuple of (platform_key, system_name)
    """

    cached = ripgrep_cache.get_platform_identifier()
    if cached is not None:
        return cached

    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ["x86_64", "amd64"]:
            ripgrep_cache.set_platform_identifier("x64-linux", system)
            return "x64-linux", system
        elif machine in ["aarch64", "arm64"]:
            ripgrep_cache.set_platform_identifier("arm64-linux", system)
            return "arm64-linux", system
    elif system == "darwin":  # noqa: SIM102
        if machine in ["x86_64", "amd64"]:
            ripgrep_cache.set_platform_identifier("x64-darwin", system)
            return "x64-darwin", system
        elif machine in ["arm64", "aarch64"]:
            ripgrep_cache.set_platform_identifier("arm64-darwin", system)
            return "arm64-darwin", system
    elif system == "windows":  # noqa: SIM102
        if machine in ["x86_64", "amd64"]:
            ripgrep_cache.set_platform_identifier("x64-win32", system)
            return "x64-win32", system

    raise ValueError(f"Unsupported platform: {system} {machine}")


def get_ripgrep_binary_path() -> Path | None:
    """Resolve the path to the ripgrep binary.

    Resolution order:
    1. Environment variable override (TUNACODE_RIPGREP_PATH)
    2. System ripgrep (if newer or equal version)
    3. Bundled ripgrep binary
    4. None (fallback to Python-based search)

    Returns:
        Path to ripgrep binary or None if not available
    """

    cache_hit, cached = ripgrep_cache.try_get_binary_path()
    if cache_hit:
        return cached

    # Check for environment variable override
    env_path = os.environ.get("TUNACODE_RIPGREP_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists() and path.is_file():
            ripgrep_cache.set_binary_path(path)
            return path

    # Check for system ripgrep
    system_rg = shutil.which("rg")
    if system_rg:
        system_rg_path = Path(system_rg)
        if _check_ripgrep_version(system_rg_path):
            ripgrep_cache.set_binary_path(system_rg_path)
            return system_rg_path

    # Check for bundled ripgrep
    try:
        platform_key, _ = get_platform_identifier()
        binary_name = "rg.exe" if platform_key == "x64-win32" else "rg"

        # Look for vendor directory relative to this file
        vendor_dir = (
            Path(__file__).parent.parent.parent.parent / "vendor" / "ripgrep" / platform_key
        )
        bundled_path = vendor_dir / binary_name

        if bundled_path.exists():
            ripgrep_cache.set_binary_path(bundled_path)
            return bundled_path
    except (OSError, ValueError):
        # Unsupported platform or filesystem issue; fall back to Python search.
        pass

    ripgrep_cache.set_binary_path(None)
    return None


def _check_ripgrep_version(rg_path: Path, min_version: str = "13.0.0") -> bool:
    """Check if ripgrep version meets minimum requirement."""

    try:
        result = subprocess.run(
            [str(rg_path), "--version"],
            capture_output=True,
            text=True,
            timeout=RIPGREP_VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False

    if result.returncode != 0:
        return False

    version_line = result.stdout.splitlines()[0] if result.stdout else ""
    parts = version_line.split()
    if not parts:
        return False

    version = parts[-1]
    try:
        current = tuple(int(part) for part in version.split("."))
        required = tuple(int(part) for part in min_version.split("."))
    except ValueError:
        return False

    return current >= required


class RipgrepExecutor:
    """Wrapper for executing ripgrep commands with error handling."""

    def __init__(self, binary_path: Path | None = None) -> None:
        """Initialize the executor.

        Args:
            binary_path: Optional path to ripgrep binary
        """
        self.binary_path = binary_path or get_ripgrep_binary_path()
        self._use_python_fallback = self.binary_path is None

    def _build_command(
        self,
        pattern: str,
        path: str,
        *,
        case_insensitive: bool = False,
        multiline: bool = False,
        context_before: int = 0,
        context_after: int = 0,
        max_matches: int | None = None,
        file_pattern: str | None = None,
    ) -> list[str]:
        """Build ripgrep command with flags."""
        cmd = [str(self.binary_path)]
        if case_insensitive:
            cmd.append("-i")
        if multiline:
            cmd.extend(["-U", "--multiline-dotall"])
        if context_before > 0:
            cmd.extend(["-B", str(context_before)])
        if context_after > 0:
            cmd.extend(["-A", str(context_after)])
        if max_matches:
            cmd.extend(["-m", str(max_matches)])
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        cmd.extend([pattern, path])
        return cmd

    async def search(
        self,
        pattern: str,
        path: str = ".",
        *,
        timeout: int = RIPGREP_SEARCH_TIMEOUT_SECONDS,
        max_matches: int | None = None,
        file_pattern: str | None = None,
        case_insensitive: bool = False,
        multiline: bool = False,
        context_before: int = 0,
        context_after: int = 0,
        **kwargs: Any,
    ) -> list[str]:
        """Execute a ripgrep search.

        Args:
            pattern: Search pattern (regex)
            path: Directory or file to search
            timeout: Maximum execution time in seconds
            max_matches: Maximum number of matches to return
            file_pattern: Glob pattern for files to include
            case_insensitive: Case-insensitive search
            multiline: Enable multiline mode
            context_before: Lines of context before match
            context_after: Lines of context after match
            **kwargs: Additional ripgrep arguments

        Returns:
            List of matching lines or file paths
        """
        if self._use_python_fallback:
            return self._python_fallback_search(
                pattern, path, file_pattern=file_pattern, case_insensitive=case_insensitive
            )

        try:
            cmd = self._build_command(
                pattern,
                path,
                case_insensitive=case_insensitive,
                multiline=multiline,
                context_before=context_before,
                context_after=context_after,
                max_matches=max_matches,
                file_pattern=file_pattern,
            )

            returncode, stdout_text = await self._run_ripgrep_command(cmd, timeout)

            if returncode in RIPGREP_SUCCESS_EXIT_CODES:
                return [line.strip() for line in stdout_text.splitlines() if line.strip()]
            return []

        except TimeoutError:
            return []
        except (OSError, asyncio.SubprocessError, UnicodeDecodeError):
            return self._python_fallback_search(pattern, path, file_pattern=file_pattern)

    async def _run_ripgrep_command(self, cmd: list[str], timeout: int) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise

        stdout_text = stdout_bytes.decode(PROCESS_OUTPUT_ENCODING)
        return_code = (
            process.returncode if process.returncode is not None else RIPGREP_NO_MATCH_EXIT_CODE
        )
        return return_code, stdout_text

    def list_files(self, pattern: str, directory: str = ".") -> list[str]:
        """List files matching a glob pattern using ripgrep.

        Args:
            pattern: Glob pattern for files
            directory: Directory to search

        Returns:
            List of file paths
        """
        if self._use_python_fallback:
            return self._python_fallback_list_files(pattern, directory)

        try:
            result = subprocess.run(
                [str(self.binary_path), "--files", "-g", pattern, directory],
                capture_output=True,
                text=True,
                timeout=RIPGREP_LIST_FILES_TIMEOUT_SECONDS,
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            return self._python_fallback_list_files(pattern, directory)

    def _python_fallback_search(
        self,
        pattern: str,
        path: str,
        file_pattern: str | None = None,
        case_insensitive: bool = False,
    ) -> list[str]:
        """Python-based fallback search implementation."""
        import re
        from pathlib import Path

        results = []
        path_obj = Path(path)

        # Compile regex pattern
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)

        # Search files
        if path_obj.is_file():
            files = [path_obj]
        else:
            glob_pattern = file_pattern or "**/*"
            files = list(path_obj.glob(glob_pattern))

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{line_num}:{line.strip()}")
            except OSError:  # nosec B112 - continue on file read errors is appropriate
                continue

        return results

    def _python_fallback_list_files(self, pattern: str, directory: str) -> list[str]:
        """Python-based fallback for listing files."""
        from pathlib import Path

        try:
            base_path = Path(directory)
            return [str(p) for p in base_path.glob(pattern) if p.is_file()]
        except OSError:
            return []


class RipgrepMetrics:
    """Collect performance metrics for ripgrep operations."""

    def __init__(self) -> None:
        self.search_count = 0
        self.total_search_time = 0.0
        self.fallback_count = 0

    def record_search(self, duration: float, used_fallback: bool = False) -> None:
        """Record a search operation."""
        self.search_count += 1
        self.total_search_time += duration
        if used_fallback:
            self.fallback_count += 1

    @property
    def average_search_time(self) -> float:
        """Get average search time."""
        if self.search_count == 0:
            return 0.0
        return self.total_search_time / self.search_count

    @property
    def fallback_rate(self) -> float:
        """Get fallback usage rate."""
        if self.search_count == 0:
            return 0.0
        return self.fallback_count / self.search_count


metrics = RipgrepMetrics()
