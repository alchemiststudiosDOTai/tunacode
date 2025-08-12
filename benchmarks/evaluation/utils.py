import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def load_problem_instance(instance_path: str) -> Dict[str, Any]:
    """
    Load a problem instance from JSON file.

    Args:
        instance_path: Path to the problem instance JSON file

    Returns:
        Dictionary containing problem instance data

    Raises:
        FileNotFoundError: If instance file doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    with open(instance_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_results(results: Dict[str, Any], output_path: str) -> None:
    """
    Save evaluation results to JSON file.

    Args:
        results: Results dictionary to save
        output_path: Path where to save the results
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def create_temp_workspace() -> str:
    """
    Create a temporary workspace directory for test execution.

    Returns:
        Path to temporary directory
    """
    return tempfile.mkdtemp(prefix='benchmark_eval_')


def cleanup_temp_workspace(workspace_path: str) -> None:
    """
    Clean up temporary workspace directory.

    Args:
        workspace_path: Path to temporary directory to remove
    """
    try:
        shutil.rmtree(workspace_path)
    except OSError:
        pass  # Ignore cleanup errors


def apply_patch_to_file(original_file: str, patched_content: str, output_file: str) -> None:
    """
    Apply a patch by replacing file content.

    Args:
        original_file: Path to original file
        patched_content: New content to write
        output_file: Path where to write patched file
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(patched_content)


def get_benchmark_root() -> Path:
    """
    Get the benchmark root directory.

    Returns:
        Path to benchmark directory
    """
    return Path(__file__).parent.parent


def list_problem_instances(instances_dir: str = None) -> List[str]:
    """
    List all available problem instances.

    Args:
        instances_dir: Directory containing instance files (optional)

    Returns:
        List of problem instance file paths
    """
    if instances_dir is None:
        instances_dir = get_benchmark_root() / "instances"

    instances_dir = Path(instances_dir)
    return [str(p) for p in instances_dir.glob("problem_*.json")]


def format_test_results(results: Dict[str, Any]) -> str:
    """
    Format test results for display.

    Args:
        results: Test results dictionary

    Returns:
        Formatted string representation
    """
    output = []
    output.append(f"Problem: {results['problem_id']}")
    output.append(f"Status: {results['status']}")
    output.append(f"Score: {results['score']:.2%}")

    if 'test_results' in results:
        passed = results['test_results']['passed']
        total = results['test_results']['total']
        output.append(f"Tests: {passed}/{total} passed")

        if results['test_results']['failures']:
            output.append("Failed tests:")
            for failure in results['test_results']['failures']:
                output.append(f"  - {failure}")

    if 'error' in results:
        output.append(f"Error: {results['error']}")

    return "\n".join(output)
