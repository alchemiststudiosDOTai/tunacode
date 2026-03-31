#!/usr/bin/env python3
"""
Local PyPI publishing script for tunacode-cli.

This script handles local PyPI publishing using the .pypirc token.
It's useful for testing and local releases when GitHub Actions isn't available.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if check and result.returncode != 0:
        print(f"❌ Command failed: {' '.join(cmd)}")
        print(f"   stdout: {result.stdout}")
        print(f"   stderr: {result.stderr}")
        sys.exit(1)

    return result.returncode, result.stdout, result.stderr


def check_pypirc_token() -> bool:
    """Check if .pypirc token exists and is accessible."""
    pypirc_path = Path.home() / ".pypirc"

    if not pypirc_path.exists():
        print("❌ ~/.pypirc file not found")
        return False

    # Check if file contains token
    with open(pypirc_path) as f:
        content = f.read()
        if "pypi-AgEIcHlwaS5vcmc" in content:
            print("✅ PyPI token found in ~/.pypirc")
            return True
        else:
            print("❌ PyPI token not found in ~/.pypirc")
            return False


def build_package() -> None:
    """Build the package using hatch."""
    print("🔨 Building package...")
    run_command(["hatch", "build"])
    print("  ✓ Package built successfully")


def check_dist_files() -> bool:
    """Check if distribution files exist."""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("❌ dist/ directory not found")
        return False

    # Look for .tar.gz and .whl files
    wheel_files = list(dist_dir.glob("*.whl"))
    tar_files = list(dist_dir.glob("*.tar.gz"))

    if not wheel_files and not tar_files:
        print("❌ No distribution files found in dist/")
        return False

    print(f"✅ Found {len(wheel_files)} wheel files and {len(tar_files)} source files")
    return True


def publish_to_pypi() -> None:
    """Publish to PyPI using .pypirc token."""
    print("🚀 Publishing to PyPI...")

    # Set environment variables to use .pypirc
    env = os.environ.copy()
    env["TWINE_USERNAME"] = "__token__"

    # Extract token from .pypirc
    pypirc_path = Path.home() / ".pypirc"
    with open(pypirc_path) as f:
        content = f.read()
        for line in content.split("\n"):
            if line.startswith("password = pypi-"):
                token = line.split(" = ")[1].strip()
                env["TWINE_PASSWORD"] = token
                break
        else:
            print("❌ Could not extract token from .pypirc")
            sys.exit(1)

    # Upload using twine with environment variables
    result = subprocess.run(
        [sys.executable, "-m", "twine", "upload", "dist/*"],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✅ Published to PyPI successfully!")
        print(result.stdout)
    else:
        print("❌ Failed to publish to PyPI")
        print(result.stderr)
        sys.exit(1)


def main() -> int:
    """Main local publishing workflow."""
    print("=" * 60)
    print("Local PyPI Publishing")
    print("=" * 60 + "\n")

    try:
        # Check .pypirc token
        if not check_pypirc_token():
            print("\nTo set up PyPI token locally:")
            print("1. Create ~/.pypirc file with:")
            print("   [distutils]")
            print("   index-servers = pypi")
            print("   ")
            print("   [pypi]")
            print("   username = __token__")
            print("   password = pypi-your-token-here")
            return 1

        # Build package
        build_package()

        # Check dist files
        if not check_dist_files():
            return 1

        # Publish to PyPI
        publish_to_pypi()

        print("\n" + "=" * 60)
        print("✅ Local PyPI publishing completed!")
        print("=" * 60)
        print("\nPackage available at: https://pypi.org/project/tunacode-cli/")
        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Publishing cancelled by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
