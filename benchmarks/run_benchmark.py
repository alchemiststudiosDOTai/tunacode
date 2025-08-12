#!/usr/bin/env python3
"""
Sample script demonstrating the SWE-bench style benchmark system.

This script shows how to:
1. Run baseline tests (with buggy code)
2. Apply patches and test fixes
3. Generate evaluation reports

Usage:
    python run_benchmark.py [--verbose] [--baseline-only]
"""

import argparse
import json
import sys
from pathlib import Path

# Add evaluation package to path
sys.path.insert(0, str(Path(__file__).parent))

from evaluation.runner import BenchmarkRunner
from evaluation.utils import get_benchmark_root


def load_reference_solutions() -> dict:
    """Load reference solutions for demonstration."""
    benchmark_root = get_benchmark_root()
    solutions = {}

    # Load string utils solution
    with open(benchmark_root / "solutions" / "solution_001.json", 'r') as f:
        sol1 = json.load(f)
        solutions["problem_001"] = sol1["patch"]

    # Load math utils solution
    with open(benchmark_root / "solutions" / "solution_002.json", 'r') as f:
        sol2 = json.load(f)
        solutions["problem_002"] = sol2["patch"]

    return solutions


def run_baseline_tests(runner: BenchmarkRunner):
    """Run baseline tests to show that original code fails."""
    print("=" * 60)
    print("RUNNING BASELINE TESTS (Original Buggy Code)")
    print("=" * 60)

    problems = ["problem_001", "problem_002"]
    baseline_results = {}

    for problem_id in problems:
        print(f"\n--- Testing {problem_id} (baseline) ---")
        result = runner.run_baseline_test(problem_id)
        baseline_results[problem_id] = result

        print(f"Status: {result['status']}")
        print(f"Score: {result['score']:.2%}")

        if result['status'] == 'error':
            print(f"Error: {result.get('error', 'Unknown error')}")
        elif 'test_results' in result:
            tr = result['test_results']
            print(f"Tests: {tr['passed']}/{tr['total']} passed")
            if tr['failures']:
                print(f"Failed tests: {', '.join(tr['failures'][:3])}")
                if len(tr['failures']) > 3:
                    print(f"  ... and {len(tr['failures']) - 3} more")

    return baseline_results


def run_fixed_tests(runner: BenchmarkRunner, solutions: dict):
    """Run tests with reference solutions."""
    print("\n" + "=" * 60)
    print("RUNNING TESTS WITH REFERENCE SOLUTIONS")
    print("=" * 60)

    fixed_results = {}

    for problem_id, patch_content in solutions.items():
        print(f"\n--- Testing {problem_id} (with fix) ---")
        result = runner.run_single_problem(problem_id, patch_content)
        fixed_results[problem_id] = result

        print(f"Status: {result['status']}")
        print(f"Score: {result['score']:.2%}")

        if result['status'] == 'error':
            print(f"Error: {result.get('error', 'Unknown error')}")
        elif 'test_results' in result:
            tr = result['test_results']
            print(f"Tests: {tr['passed']}/{tr['total']} passed")
            if tr['failures']:
                print(f"Still failing: {', '.join(tr['failures'])}")

    return fixed_results


def print_summary(baseline_results: dict, fixed_results: dict):
    """Print comparison summary."""
    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)

    print(f"{'Problem':<15} {'Baseline Score':<15} {'Fixed Score':<15} {'Improvement':<15}")
    print("-" * 60)

    for problem_id in baseline_results.keys():
        baseline_score = baseline_results[problem_id]['score']
        fixed_score = fixed_results.get(problem_id, {}).get('score', 0.0)
        improvement = fixed_score - baseline_score

        print(f"{problem_id:<15} {baseline_score:>13.2%} {fixed_score:>13.2%} {improvement:>+13.2%}")

    avg_baseline = sum(r['score'] for r in baseline_results.values()) / len(baseline_results)
    avg_fixed = sum(r['score'] for r in fixed_results.values()) / len(fixed_results)
    avg_improvement = avg_fixed - avg_baseline

    print("-" * 60)
    print(f"{'Average':<15} {avg_baseline:>13.2%} {avg_fixed:>13.2%} {avg_improvement:>+13.2%}")


def demonstrate_api_usage(runner: BenchmarkRunner):
    """Demonstrate various API functions."""
    print("\n" + "=" * 60)
    print("API USAGE DEMONSTRATION")
    print("=" * 60)

    # List available problems
    print("\nAvailable problems:")
    problems = runner.list_available_problems()
    for problem in problems:
        print(f"  {problem['id']}: {problem['description']}")
        print(f"    Category: {problem['category']}, Difficulty: {problem['difficulty']}")

    # Demonstrate full benchmark run
    print("\nRunning full benchmark with reference solutions...")
    solutions = load_reference_solutions()

    results = runner.run_full_benchmark(
        patches=solutions,
        output_file=str(get_benchmark_root() / "results" / "demo_results.json")
    )

    print("Full benchmark completed:")
    print(f"  Total problems: {results['summary']['total_problems']}")
    print(f"  Average score: {results['summary']['average_score']:.2%}")
    print(f"  Status distribution: {results['summary']['status_distribution']}")
    print("  Results saved to: benchmarks/results/demo_results.json")


def main():
    """Main demonstration script."""
    parser = argparse.ArgumentParser(description="SWE-bench style benchmark demonstration")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--baseline-only", action="store_true", help="Only run baseline tests")
    parser.add_argument("--api-demo", action="store_true", help="Demonstrate API usage")

    args = parser.parse_args()

    print("SWE-bench Style Benchmark System Demo")
    print("====================================")

    # Initialize runner
    runner = BenchmarkRunner(verbose=args.verbose)

    # Run baseline tests
    baseline_results = run_baseline_tests(runner)

    if not args.baseline_only:
        # Load and run with reference solutions
        solutions = load_reference_solutions()
        fixed_results = run_fixed_tests(runner, solutions)

        # Print comparison
        print_summary(baseline_results, fixed_results)

    if args.api_demo:
        demonstrate_api_usage(runner)

    print(f"\n{'='*60}")
    print("Demo completed successfully!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
