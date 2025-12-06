"""Ripgrep binary management and execution utilities."""

import functools
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_platform_identifier() -> Tuple[str, str]:
    """Get the current platform identifier.

    Returns:
        Tuple of (platform_key, system_name)
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ["x86_64", "amd64"]:
            return "x64-linux", system
        elif machine in ["aarch64", "arm64"]:
            return "arm64-linux", system
    elif system == "darwin":
        if machine in ["x86_64", "amd64"]:
            return "x64-darwin", system
        elif machine in ["arm64", "aarch64"]:
            return "arm64-darwin", system
    elif system == "windows":
        if machine in ["x86_64", "amd64"]:
            return "x64-win32", system

    raise ValueError(f"Unsupported platform: {system} {machine}")


@functools.lru_cache(maxsize=1)
def get_ripgrep_binary_path() -> Optional[Path]:
    """Resolve the path to the ripgrep binary.

    Resolution order:
    1. Environment variable override (TUNACODE_RIPGREP_PATH)
    2. System ripgrep (if newer or equal version)
    3. Bundled ripgrep binary
    4. None (fallback to Python-based search)

    Returns:
        Path to ripgrep binary or None if not available
    """
    # Check for environment variable override
    env_path = os.environ.get("TUNACODE_RIPGREP_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists() and path.is_file():
            logger.debug(f"Using ripgrep from environment variable: {path}")
            return path
        else:
            logger.warning(f"Invalid TUNACODE_RIPGREP_PATH: {env_path}")

    # Check for system ripgrep
    system_rg = shutil.which("rg")
    if system_rg:
        system_rg_path = Path(system_rg)
        if _check_ripgrep_version(system_rg_path):
            logger.debug(f"Using system ripgrep: {system_rg_path}")
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
            logger.debug(f"Using bundled ripgrep: {bundled_path}")
            return bundled_path
    except Exception as e:
        logger.debug(f"Could not find bundled ripgrep: {e}")

    logger.debug("No ripgrep binary found, will use Python fallback")
    return None


def _check_ripgrep_version(rg_path: Path, min_version: str = "13.0.0") -> bool:
    """Check if ripgrep version meets minimum requirement.

    Args:
        rg_path: Path to ripgrep binary
        min_version: Minimum required version

    Returns:
        True if version is sufficient, False otherwise
    """
    try:
        result = subprocess.run(
            [str(rg_path), "--version"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            # Parse version from output like "ripgrep 14.1.1"
            version_line = result.stdout.split("\n")[0]
            version = version_line.split()[-1]

            # Simple version comparison (works for x.y.z format)
            current = tuple(map(int, version.split(".")))
            required = tuple(map(int, min_version.split(".")))

            return current >= required
    except Exception as e:
        logger.debug(f"Could not check ripgrep version: {e}")

    return False


class RipgrepExecutor:
    """Wrapper for executing ripgrep commands with error handling."""

    def __init__(self, binary_path: Optional[Path] = None):
        """Initialize the executor.

        Args:
            binary_path: Optional path to ripgrep binary
        """
        self.binary_path = binary_path or get_ripgrep_binary_path()
        self._use_python_fallback = self.binary_path is None

        if self._use_python_fallback:
            logger.info("Ripgrep binary not available, using Python fallback")

    def search(
        self,
        pattern: str,
        path: str = ".",
        *,
        timeout: int = 10,
        max_matches: Optional[int] = None,
        file_pattern: Optional[str] = None,
        case_insensitive: bool = False,
        multiline: bool = False,
        context_before: int = 0,
        context_after: int = 0,
        **kwargs,
    ) -> List[str]:
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
            cmd = [str(self.binary_path)]

            # Add flags
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

            # Add pattern and path
            cmd.extend([pattern, path])

            logger.debug(f"Executing ripgrep: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode in [0, 1]:  # 0 = matches found, 1 = no matches
                return [line.strip() for line in result.stdout.splitlines() if line.strip()]
            else:
                logger.warning(f"Ripgrep error: {result.stderr}")
                return []

        except subprocess.TimeoutExpired:
            logger.warning(f"Ripgrep search timed out after {timeout} seconds")
            return []
        except Exception as e:
            logger.error(f"Ripgrep execution failed: {e}")
            return self._python_fallback_search(pattern, path, file_pattern=file_pattern)

    def list_files(self, pattern: str, directory: str = ".") -> List[str]:
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
                timeout=5,
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return self._python_fallback_list_files(pattern, directory)

    def _python_fallback_search(
        self,
        pattern: str,
        path: str,
        file_pattern: Optional[str] = None,
        case_insensitive: bool = False,
    ) -> List[str]:
        """Python-based fallback search implementation."""
        import re
        from pathlib import Path

        results = []
        path_obj = Path(path)

        # Compile regex pattern
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            logger.error(f"Invalid regex pattern: {pattern}")
            return []

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
            except Exception:  # nosec B112 - continue on file read errors is appropriate
                continue

        return results

    def _python_fallback_list_files(self, pattern: str, directory: str) -> List[str]:
        """Python-based fallback for listing files."""
        from pathlib import Path

        try:
            base_path = Path(directory)
            return [str(p) for p in base_path.glob(pattern) if p.is_file()]
        except Exception:
            return []


# Maintain backward compatibility
def ripgrep(pattern: str, directory: str = ".") -> List[str]:
    """Return a list of file paths matching a pattern using ripgrep.

    This function maintains backward compatibility with the original implementation.
    """
    executor = RipgrepExecutor()
    return executor.list_files(pattern, directory)


# Performance metrics collection
class RipgrepMetrics:
    """Collect performance metrics for ripgrep operations."""

    def __init__(self):
        self.search_count = 0
        self.total_search_time = 0.0
        self.fallback_count = 0

    def record_search(self, duration: float, used_fallback: bool = False):
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


# Global metrics instance
metrics = RipgrepMetrics()
