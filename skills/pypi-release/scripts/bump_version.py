#!/usr/bin/env python3
"""
Automatically bump version across all required files for tunacode-cli.

Updates version in:
1. pyproject.toml (project version at line ~8)
2. src/tunacode/constants.py (APP_VERSION at line ~12)
3. README.md (version header)

Increments the patch version (0.0.X.Y -> 0.0.X.Y+1)
"""

import re
import sys
from pathlib import Path


def get_current_version(pyproject_path: Path) -> str:
    """Extract current version from pyproject.toml."""
    content = pyproject_path.read_text()

    # Look for version in [project] section
    match = re.search(r'\[project\].*?version\s*=\s*"([^"]+)"', content, re.DOTALL)
    if not match:
        raise ValueError("Could not find version in pyproject.toml [project] section")

    return match.group(1)


def bump_patch_version(version: str) -> str:
    """Increment the patch version number."""
    parts = version.split(".")
    if len(parts) < 2:
        raise ValueError(f"Version format should be at least X.Y, got: {version}")

    # Increment the last part (patch)
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def update_pyproject(pyproject_path: Path, old_version: str, new_version: str) -> None:
    """Update both version locations in pyproject.toml."""
    content = pyproject_path.read_text()

    # Replace version = "old" with version = "new"
    updated = content.replace(f'version = "{old_version}"', f'version = "{new_version}"')

    if content == updated:
        raise ValueError("No version replacements made in pyproject.toml")

    # Verify we updated at least 1 occurrence
    count = updated.count(f'version = "{new_version}"')
    if count < 1:
        raise ValueError(f"Expected to update at least 1 version location, updated {count}")

    pyproject_path.write_text(updated)
    print(f"✓ Updated pyproject.toml: {old_version} -> {new_version}")


def update_constants(constants_path: Path, old_version: str, new_version: str) -> None:
    """Update APP_VERSION in constants.py."""
    content = constants_path.read_text()

    # Replace APP_VERSION = "old" with APP_VERSION = "new"
    updated = content.replace(f'APP_VERSION = "{old_version}"', f'APP_VERSION = "{new_version}"')

    if content == updated:
        raise ValueError("No version replacement made in constants.py")

    constants_path.write_text(updated)
    print(f"✓ Updated constants.py: {old_version} -> {new_version}")


def update_readme(readme_path: Path, old_version: str, new_version: str) -> bool:
    """Update version header in README.md. Returns True if updated, False if not found."""
    content = readme_path.read_text()

    # Replace ## vX.Y.Z - with ## vX.Y.Z (keep any suffix after the dash)
    pattern = rf"## v{re.escape(old_version)}\b"
    updated = re.sub(pattern, f"## v{new_version}", content)

    if content == updated:
        print("⚠ No version header found in README.md, skipping")
        return False

    readme_path.write_text(updated)
    print(f"✓ Updated README.md: {old_version} -> {new_version}")
    return True


def main() -> int:
    """Main version bump workflow."""
    # Find project root (assumes script runs from project root or skill dir)
    project_root = Path.cwd()

    # Check if we're in the skill directory, go up if needed
    if project_root.name == "pypi-release":
        project_root = project_root.parent.parent.parent / "tunacode"

    pyproject_path = project_root / "pyproject.toml"
    constants_path = project_root / "src" / "tunacode" / "constants.py"
    readme_path = project_root / "README.md"

    # Validate files exist
    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found at {pyproject_path}")
        return 1

    if not constants_path.exists():
        print(f"Error: constants.py not found at {constants_path}")
        return 1

    # README.md is optional (may not exist in all environments)
    readme_exists = readme_path.exists()

    try:
        # Get current version and calculate new version
        current_version = get_current_version(pyproject_path)
        new_version = bump_patch_version(current_version)

        print(f"Bumping version: {current_version} -> {new_version}")

        # Update all files
        update_pyproject(pyproject_path, current_version, new_version)
        update_constants(constants_path, current_version, new_version)
        readme_updated = False
        if readme_exists:
            readme_updated = update_readme(readme_path, current_version, new_version)

        print(f"\n✅ Version bump complete: {new_version}")
        print("   Files updated:")
        print(f"   - {pyproject_path}")
        print(f"   - {constants_path}")
        if readme_updated:
            print(f"   - {readme_path}")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
