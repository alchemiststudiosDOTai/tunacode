"""Ripgrep binary management and execution utilities."""

import os
import platform
import shutil
import subprocess
from pathlib import Path

from tunacode.tools.cache_accessors import ripgrep_cache

RIPGREP_VERSION_TIMEOUT_SECONDS = 1


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
