import os
import subprocess
import sys
from typing import Any, Dict


class TestGrader:
    """
    Grades test execution results and calculates scores.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize grader.

        Args:
            verbose: Whether to output verbose information
        """
        self.verbose = verbose

    def run_pytest(self, test_file: str, workspace_path: str) -> Dict[str, Any]:
        """
        Run pytest on a test file and collect results.

        Args:
            test_file: Path to test file relative to workspace
            workspace_path: Path to workspace directory

        Returns:
            Dictionary containing test results
        """
        # Change to workspace directory for test execution
        original_cwd = os.getcwd()
        test_results = {
            "passed": 0,
            "total": 0,
            "failures": [],
            "errors": [],
            "output": ""
        }

        try:
            os.chdir(workspace_path)

            # Run pytest with JSON reporting
            cmd = [
                sys.executable, "-m", "pytest",
                test_file,
                "-v",  # verbose
                "--tb=short",  # short traceback format
                "--no-header"  # no header
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            test_results["output"] = result.stdout + result.stderr

            # Parse pytest output
            self._parse_pytest_output(result.stdout, result.stderr, test_results)

            if self.verbose:
                print(f"Pytest exit code: {result.returncode}")
                print(f"Output: {test_results['output']}")
                print(f"Parsed results: {test_results}")

        except subprocess.TimeoutExpired:
            test_results["errors"].append("Test execution timed out")
        except Exception as e:
            test_results["errors"].append(f"Error running tests: {str(e)}")
        finally:
            os.chdir(original_cwd)

        return test_results

    def _parse_pytest_output(self, stdout: str, stderr: str, test_results: Dict[str, Any]) -> None:
        """
        Parse pytest output to extract test results.

        Args:
            stdout: Standard output from pytest
            stderr: Standard error from pytest
            test_results: Dictionary to update with parsed results
        """
        lines = (stdout + stderr).split('\n')

        for line in lines:
            line = line.strip()

            # Look for test result lines (format: "test_file.py::TestClass::test_method PASSED")
            if "::test_" in line and (" PASSED" in line or " FAILED" in line or " ERROR" in line):
                test_results["total"] += 1

                if " PASSED" in line:
                    test_results["passed"] += 1
                else:
                    # Extract test name
                    test_name = line.split()[0] if line.split() else "unknown_test"
                    test_results["failures"].append(test_name)

        # Look for pytest summary line (e.g., "2 failed, 3 passed in 0.05s")
        for line in lines:
            if " passed in " in line or " failed, " in line:
                self._parse_summary_line(line, test_results)
                break

    def _parse_summary_line(self, summary_line: str, test_results: Dict[str, Any]) -> None:
        """
        Parse pytest summary line to get accurate counts.

        Args:
            summary_line: Summary line from pytest output
            test_results: Dictionary to update with parsed results
        """
        # Examples:
        # "5 passed in 0.02s"
        # "1 failed, 12 passed in 0.05s"
        # "1 error, 2 failed, 1 passed in 0.03s"

        parts = summary_line.split()
        total_count = 0
        passed_count = 0

        for i, part in enumerate(parts):
            if part.endswith(","):
                part = part[:-1]  # Remove comma

            if part == "passed" and i > 0:
                try:
                    passed_count = int(parts[i-1])
                    total_count += passed_count
                except ValueError:
                    pass
            elif part == "failed" and i > 0:
                try:
                    total_count += int(parts[i-1])
                except ValueError:
                    pass
            elif part == "error" and i > 0:
                try:
                    total_count += int(parts[i-1])
                except ValueError:
                    pass

        # Update results if we got meaningful data from summary
        if total_count > 0:
            test_results["total"] = total_count
            test_results["passed"] = passed_count

    def calculate_score(self, test_results: Dict[str, Any]) -> float:
        """
        Calculate score based on test results.

        Args:
            test_results: Dictionary containing test execution results

        Returns:
            Score between 0.0 and 1.0
        """
        if test_results["total"] == 0:
            return 0.0

        return test_results["passed"] / test_results["total"]

    def grade_problem(self, test_results: Dict[str, Any], problem_instance: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grade a problem based on test results.

        Args:
            test_results: Results from running tests
            problem_instance: Problem instance data

        Returns:
            Grading results dictionary
        """
        score = self.calculate_score(test_results)

        # Determine status
        if test_results["errors"]:
            status = "error"
        elif score == 1.0:
            status = "passed"
        elif score > 0.0:
            status = "partial"
        else:
            status = "failed"

        return {
            "problem_id": problem_instance["id"],
            "status": status,
            "score": score,
            "test_results": test_results,
            "metadata": problem_instance.get("metadata", {})
        }
