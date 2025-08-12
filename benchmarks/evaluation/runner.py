import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from evaluation.grader import TestGrader
from evaluation.utils import (
    apply_patch_to_file,
    cleanup_temp_workspace,
    create_temp_workspace,
    format_test_results,
    get_benchmark_root,
    list_problem_instances,
    load_problem_instance,
    save_results,
)


class BenchmarkRunner:
    """
    Main runner for the benchmark evaluation system.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize benchmark runner.

        Args:
            verbose: Whether to output verbose information
        """
        self.verbose = verbose
        self.grader = TestGrader(verbose=verbose)
        self.benchmark_root = get_benchmark_root()

    def run_single_problem(self, problem_id: str, patch_content: str) -> Dict[str, Any]:
        """
        Run evaluation on a single problem with provided patch.

        Args:
            problem_id: ID of the problem to evaluate
            patch_content: Content of the patched file

        Returns:
            Evaluation results dictionary
        """
        # Find and load problem instance
        instance_file = self.benchmark_root / "instances" / f"{problem_id}.json"

        if not instance_file.exists():
            return {
                "problem_id": problem_id,
                "status": "error",
                "error": f"Problem instance {problem_id} not found",
                "score": 0.0
            }

        try:
            problem_instance = load_problem_instance(str(instance_file))
            return self._evaluate_problem(problem_instance, patch_content)

        except Exception as e:
            return {
                "problem_id": problem_id,
                "status": "error",
                "error": f"Failed to evaluate problem: {str(e)}",
                "score": 0.0
            }

    def run_baseline_test(self, problem_id: str) -> Dict[str, Any]:
        """
        Run baseline test (original buggy code) to verify tests fail as expected.

        Args:
            problem_id: ID of the problem to test

        Returns:
            Baseline test results
        """
        instance_file = self.benchmark_root / "instances" / f"{problem_id}.json"

        if not instance_file.exists():
            return {
                "problem_id": problem_id,
                "status": "error",
                "error": f"Problem instance {problem_id} not found",
                "score": 0.0
            }

        try:
            problem_instance = load_problem_instance(str(instance_file))

            # Read original buggy code
            base_code_path = self.benchmark_root / problem_instance["base_code_path"]
            with open(base_code_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            return self._evaluate_problem(problem_instance, original_content, is_baseline=True)

        except Exception as e:
            return {
                "problem_id": problem_id,
                "status": "error",
                "error": f"Failed to run baseline test: {str(e)}",
                "score": 0.0
            }

    def _evaluate_problem(self, problem_instance: Dict[str, Any], patch_content: str, is_baseline: bool = False) -> Dict[str, Any]:
        """
        Evaluate a single problem with given patch content.

        Args:
            problem_instance: Problem instance data
            patch_content: Content of the patched file
            is_baseline: Whether this is a baseline test

        Returns:
            Evaluation results
        """
        workspace_path = create_temp_workspace()

        try:
            # Setup workspace
            self._setup_workspace(workspace_path, problem_instance, patch_content)

            # Run tests
            test_file = problem_instance["test_file"]
            test_results = self.grader.run_pytest(test_file, workspace_path)

            # Grade results
            results = self.grader.grade_problem(test_results, problem_instance)

            # Add evaluation metadata
            results.update({
                "evaluated_at": datetime.now().isoformat(),
                "is_baseline": is_baseline,
                "workspace_path": workspace_path if self.verbose else None
            })

            if self.verbose:
                print(format_test_results(results))

            return results

        except Exception as e:
            return {
                "problem_id": problem_instance["id"],
                "status": "error",
                "error": str(e),
                "score": 0.0,
                "evaluated_at": datetime.now().isoformat(),
                "is_baseline": is_baseline
            }
        finally:
            if not self.verbose:  # Keep workspace for debugging if verbose
                cleanup_temp_workspace(workspace_path)

    def _setup_workspace(self, workspace_path: str, problem_instance: Dict[str, Any], patch_content: str) -> None:
        """
        Setup temporary workspace for test execution.

        Args:
            workspace_path: Path to workspace directory
            problem_instance: Problem instance data
            patch_content: Content of patched file
        """
        workspace = Path(workspace_path)

        # Copy test file to workspace
        test_src = self.benchmark_root / problem_instance["test_file"]
        test_dst = workspace / problem_instance["test_file"]

        # Create test directory structure
        test_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(test_src, test_dst)

        # Create base_code directory and write patched file
        base_code_path = problem_instance["base_code_path"]
        patched_file = workspace / base_code_path
        patched_file.parent.mkdir(parents=True, exist_ok=True)

        # Write patched content
        apply_patch_to_file(
            str(self.benchmark_root / base_code_path),
            patch_content,
            str(patched_file)
        )

        # Create __init__.py files for Python package structure
        for dir_path in [workspace / "base_code", workspace / "tests"]:
            if dir_path.exists():
                init_file = dir_path / "__init__.py"
                init_file.touch()

    def run_full_benchmark(self, patches: Dict[str, str], output_file: str = None) -> Dict[str, Any]:
        """
        Run the full benchmark with multiple problem patches.

        Args:
            patches: Dictionary mapping problem_id to patch content
            output_file: Optional file path to save results

        Returns:
            Complete benchmark results
        """
        results = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "evaluated_at": datetime.now().isoformat(),
            "problems": {},
            "summary": {}
        }

        # Get all available problems
        instance_files = list_problem_instances()

        total_problems = 0
        total_score = 0.0
        status_counts = {"passed": 0, "failed": 0, "partial": 0, "error": 0}

        for instance_file in instance_files:
            problem_instance = load_problem_instance(instance_file)
            problem_id = problem_instance["id"]

            if problem_id in patches:
                # Run with provided patch
                result = self.run_single_problem(problem_id, patches[problem_id])
            else:
                # Run baseline test
                result = self.run_baseline_test(problem_id)
                result["note"] = "No patch provided - baseline test"

            results["problems"][problem_id] = result

            total_problems += 1
            total_score += result["score"]
            status_counts[result["status"]] += 1

        # Calculate summary statistics
        avg_score = total_score / total_problems if total_problems > 0 else 0.0

        results["summary"] = {
            "total_problems": total_problems,
            "average_score": avg_score,
            "status_distribution": status_counts
        }

        # Save results if output file specified
        if output_file:
            save_results(results, output_file)

        return results

    def list_available_problems(self) -> List[Dict[str, Any]]:
        """
        List all available problems in the benchmark.

        Returns:
            List of problem information dictionaries
        """
        instance_files = list_problem_instances()
        problems = []

        for instance_file in instance_files:
            try:
                problem_instance = load_problem_instance(instance_file)
                problems.append({
                    "id": problem_instance["id"],
                    "description": problem_instance["problem_statement"][:100] + "...",
                    "category": problem_instance.get("metadata", {}).get("category", "unknown"),
                    "difficulty": problem_instance.get("metadata", {}).get("difficulty", "unknown")
                })
            except Exception as e:
                problems.append({
                    "id": f"error_loading_{Path(instance_file).stem}",
                    "description": f"Error loading: {str(e)}",
                    "category": "error",
                    "difficulty": "unknown"
                })

        return problems
