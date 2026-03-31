#!/usr/bin/env python3
"""
Full release workflow for tunacode-cli PyPI releases.

Workflow:
1. Pre-flight checks (git status, tests, linting)
2. Bump version across all files
3. Commit version changes
4. Push the release commit to master
5. Dispatch the GitHub Actions publish workflow
6. Monitor GitHub Actions workflow
7. Report success or debug failures
"""

import json
import subprocess
import sys
import time
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


def preflight_checks() -> None:
    """Run pre-flight checks before release."""
    print("🔍 Running pre-flight checks...")

    # Check git status
    print("  → Checking git status...")
    code, stdout, _ = run_command(["git", "status", "--porcelain"])
    if stdout.strip():
        print("❌ Working directory not clean. Commit or stash changes first.")
        print(stdout)
        sys.exit(1)
    print("  ✓ Git working directory clean")

    # Check we're on master
    code, stdout, _ = run_command(["git", "branch", "--show-current"])
    branch = stdout.strip()
    if branch != "master":
        print(f"❌ Not on master branch (currently on: {branch})")
        sys.exit(1)
    print("  ✓ On master branch")

    # Run linting
    print("  → Running ruff linter...")
    run_command(["ruff", "check", "."])
    print("  ✓ Linting passed")

    # Run tests
    print("  → Running tests...")
    run_command(["bash", "-c", "source .venv/bin/activate && pytest tests/ -q"])
    print("  ✓ Tests passed")

    print("✅ All pre-flight checks passed\n")


def bump_version() -> str:
    """Bump version and return new version string."""
    print("📦 Bumping version...")

    # Run bump_version.py script
    script_dir = Path(__file__).parent
    bump_script = script_dir / "bump_version.py"

    code, stdout, stderr = run_command(["python3", str(bump_script)])

    # Extract version from output (format: "✅ Version bump complete: X.Y.Z.W")
    for line in stdout.split("\n"):
        if "Version bump complete:" in line:
            version = line.split(":")[-1].strip()
            return version

    print("❌ Could not determine new version from bump_version.py output")
    sys.exit(1)


def git_commit_and_push(version: str) -> None:
    """Commit version changes and push them to master."""
    print(f"📝 Committing version bump to {version}...")

    # Stage changes
    run_command(["git", "add", "pyproject.toml", "src/tunacode/constants.py", "README.md"])

    # Commit
    run_command(["git", "commit", "-m", f"chore: bump version to {version}"])
    print("  ✓ Changes committed")

    # Push to origin
    print("  → Pushing to origin...")
    run_command(["git", "push", "origin", "master"])
    print("  ✓ Pushed to remote")


def dispatch_publish_workflow(version: str) -> None:
    """Dispatch the manual GitHub Actions publish workflow."""
    print(f"🚀 Dispatching publish workflow for {version}...")
    run_command(
        [
            "gh",
            "workflow",
            "run",
            "publish-release.yml",
            "--ref",
            "master",
            "-f",
            f"version={version}",
        ]
    )
    print("  ✓ Workflow dispatched")


def monitor_workflow(version: str, timeout: int = 120) -> bool:
    """Monitor GitHub Actions workflow and report status."""
    print(f"⏳ Monitoring publish workflow (timeout: {timeout}s)...")

    start_time = time.time()

    # Wait a moment for workflow to start
    time.sleep(10)

    while time.time() - start_time < timeout:
        code, stdout, _ = run_command(
            [
                "gh",
                "run",
                "list",
                "--workflow=publish-release.yml",
                "--limit",
                "1",
                "--json",
                "status,conclusion",
            ],
            check=False,
        )

        if code != 0:
            print("  ⚠ Could not query workflow status")
            return False

        runs = json.loads(stdout)
        if not runs:
            elapsed = int(time.time() - start_time)
            print(f"  ⏳ Workflow not visible yet... ({elapsed}s elapsed)")
            time.sleep(10)
            continue

        run = runs[0]
        status = run.get("status", "")
        conclusion = run.get("conclusion", "")

        if status == "completed":
            if conclusion == "success":
                print("  ✅ Workflow completed successfully!")
                return True
            else:
                print(f"  ❌ Workflow failed: {conclusion}")
                print("\n  View logs: gh run list --workflow=publish-release.yml --limit 1")
                print("  Debug with: gh run view <run-id> --log-failed")
                return False

        if status == "in_progress":
            elapsed = int(time.time() - start_time)
            print(f"  ⏳ Workflow running... ({elapsed}s elapsed)")
            time.sleep(10)
        else:
            print(f"  Status: {status}")
            time.sleep(10)

    print(f"  ⏱ Timeout reached after {timeout}s")
    print("  Check status manually: gh run list --workflow=publish-release.yml")
    return False


def main() -> int:
    """Main release workflow."""
    print("=" * 60)
    print("PyPI Release Workflow")
    print("=" * 60 + "\n")

    try:
        # Pre-flight checks
        preflight_checks()

        # Bump version
        new_version = bump_version()

        # Git operations
        git_commit_and_push(new_version)

        # GitHub Actions publish workflow
        dispatch_publish_workflow(new_version)

        # Monitor workflow
        success = monitor_workflow(new_version)

        if success:
            print("\n" + "=" * 60)
            print(f"✅ Release {new_version} published successfully!")
            print("=" * 60)
            print("\nPackage available at: https://pypi.org/project/tunacode-cli/")
            return 0
        else:
            print("\n" + "=" * 60)
            print("⚠ Release workflow completed with issues")
            print("=" * 60)
            return 1

    except KeyboardInterrupt:
        print("\n\n❌ Release cancelled by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
