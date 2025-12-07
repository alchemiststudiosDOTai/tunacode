#!/usr/bin/env python3
"""
Playwright Cache Management Utility

Cross-platform utility for managing Playwright browser binaries cache.
Supports removing and restoring cache for testing purposes.

Usage:
    python playwright_cache.py remove   # Remove/backup cache
    python playwright_cache.py restore  # Restore cache from backup
"""

import argparse
import shutil
import sys
from pathlib import Path


def get_playwright_cache_paths() -> tuple[Path | None, Path | None]:
    """
    Get platform-specific Playwright cache paths.

    Returns:
        Tuple of (cache_path, backup_path) or (None, None) if not found
    """
    # macOS cache path
    mac_cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    if mac_cache.exists():
        return mac_cache, Path(str(mac_cache) + "_backup")

    # Linux/Unix cache path
    linux_cache = Path.home() / ".cache" / "ms-playwright"
    if linux_cache.exists():
        return linux_cache, Path(str(linux_cache) + "_backup")

    # Windows cache path (for future compatibility)
    if sys.platform == "win32":
        windows_cache = Path.home() / "AppData" / "Local" / "ms-playwright"
        if windows_cache.exists():
            return windows_cache, Path(str(windows_cache) + "_backup")

    return None, None


def remove_playwright_cache() -> int:
    """
    Remove/backup Playwright cache.

    Returns:
        0 on success, 1 on error
    """
    print("Removing Playwright binaries for testing...")

    cache_path, backup_path = get_playwright_cache_paths()

    if cache_path is None:
        print(
            "No Playwright binaries found. Please run 'playwright install' first "
            "if you want to test the reinstall flow."
        )
        return 0

    try:
        if backup_path and backup_path.exists():
            print(f"Removing existing backup at {backup_path}")
            shutil.rmtree(backup_path, ignore_errors=True)

        print(f"Moving Playwright binaries from {cache_path} to {backup_path}")
        shutil.move(str(cache_path), str(backup_path))
        print(f"Playwright binaries moved to {backup_path}")
        return 0

    except Exception as e:
        print(f"Error removing Playwright cache: {e}", file=sys.stderr)
        return 1


def restore_playwright_cache() -> int:
    """
    Restore Playwright cache from backup.

    Returns:
        0 on success, 1 on error
    """
    print("Restoring Playwright binaries...")

    cache_path, backup_path = get_playwright_cache_paths()

    # Check for backup even if current cache doesn't exist
    if cache_path is None:
        # Try to detect backup paths manually
        potential_backups = [
            Path.home() / "Library" / "Caches" / "ms-playwright_backup",
            Path.home() / ".cache" / "ms-playwright_backup",
        ]

        for backup in potential_backups:
            if backup.exists():
                cache_path = Path(str(backup).replace("_backup", ""))
                backup_path = backup
                break

    if backup_path is None or not backup_path.exists():
        print("No backed up Playwright binaries found. Nothing to restore.")
        return 0

    try:
        if cache_path and cache_path.exists():
            print(f"Removing current cache at {cache_path}")
            shutil.rmtree(cache_path, ignore_errors=True)

        print(f"Restoring Playwright binaries from {backup_path} to {cache_path}")
        shutil.move(str(backup_path), str(cache_path))
        print(f"Playwright binaries restored from {backup_path}")
        return 0

    except Exception as e:
        print(f"Error restoring Playwright cache: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Manage Playwright browser cache for testing")
    parser.add_argument(
        "action", choices=["remove", "restore"], help="Action to perform on Playwright cache"
    )

    args = parser.parse_args()

    if args.action == "remove":
        return remove_playwright_cache()
    elif args.action == "restore":
        return restore_playwright_cache()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
