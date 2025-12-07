#!/usr/bin/env python3
"""
TunaCode Startup Performance Timer

This script measures TunaCode's startup time to track performance improvements
during the Phase 1 optimization implementation.

Usage:
    python scripts/startup_timer.py [--iterations N] [--command CMD] [--output FILE]

Examples:
    # Basic timing
    python scripts/startup_timer.py

    # Test specific command
    python scripts/startup_timer.py --command "--version"

    # More iterations for better accuracy
    python scripts/startup_timer.py --iterations 10

    # Save results to file
    python scripts/startup_timer.py --output results.json
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class StartupTimer:
    """Measures and tracks TunaCode startup performance."""

    def __init__(self, iterations: int = 5, command: str | None = None):
        self.iterations = iterations
        self.command = command or "--version"
        self.results: list[dict[str, Any]] = []

    def measure_startup_time(self) -> dict:
        """Measure startup time over multiple iterations."""
        print("Measuring TunaCode startup time...")
        print(f"Command: tunacode {self.command}")
        print(f"Iterations: {self.iterations}")
        print("-" * 50)

        times = []
        failed_runs = 0

        for i in range(self.iterations):
            print(f"Run {i + 1}/{self.iterations}...", end=" ", flush=True)

            try:
                start_time = time.perf_counter()

                # Run tunacode command
                result = subprocess.run(
                    ["tunacode"] + self.command.split(),
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30 second timeout
                )

                end_time = time.perf_counter()
                elapsed = end_time - start_time

                if result.returncode == 0:
                    times.append(elapsed)
                    print(f"{elapsed:.3f}s ✓")
                else:
                    failed_runs += 1
                    print(f"FAILED (code: {result.returncode})")
                    if result.stderr:
                        print(f"  Error: {result.stderr.strip()}")

            except subprocess.TimeoutExpired:
                failed_runs += 1
                print("TIMEOUT")
            except Exception as e:
                failed_runs += 1
                print(f"ERROR: {e}")

        if not times:
            raise RuntimeError("All startup attempts failed!")

        # Calculate statistics
        stats = {
            "timestamp": datetime.now().isoformat(),
            "command": f"tunacode {self.command}",
            "iterations": self.iterations,
            "successful_runs": len(times),
            "failed_runs": failed_runs,
            "times": times,
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0.0,
        }

        self.results.append(stats)
        return stats

    def print_results(self, stats: dict):
        """Print formatted results to console."""
        print("\n" + "=" * 60)
        print("STARTUP PERFORMANCE RESULTS")
        print("=" * 60)
        print(f"Command: {stats['command']}")
        print(f"Timestamp: {stats['timestamp']}")
        print(f"Successful runs: {stats['successful_runs']}/{stats['iterations']}")

        if stats["failed_runs"] > 0:
            print(f"Failed runs: {stats['failed_runs']}")

        print("\nTiming Results:")
        print(f"  Mean:     {stats['mean']:.3f}s")
        print(f"  Median:   {stats['median']:.3f}s")
        print(f"  Min:      {stats['min']:.3f}s")
        print(f"  Max:      {stats['max']:.3f}s")
        print(f"  Std Dev:  {stats['std_dev']:.3f}s")

        print(f"\nIndividual times: {[f'{t:.3f}s' for t in stats['times']]}")

        # Performance assessment
        mean_time = stats["mean"]
        if mean_time < 2.5:
            status = "🎯 EXCELLENT - Phase 1 target achieved!"
        elif mean_time < 3.0:
            status = "✅ GOOD - Significant improvement"
        elif mean_time < 4.0:
            status = "⚠️  MODERATE - Some improvement"
        else:
            status = "❌ SLOW - Needs optimization"

        print(f"\nPerformance Status: {status}")
        print("=" * 60)

    def save_results(self, filename: str):
        """Save results to JSON file."""
        filepath = Path(filename)

        # Load existing results if file exists
        existing_results = []
        if filepath.exists():
            try:
                with open(filepath) as f:
                    existing_results = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not read existing results from {filename}")

        # Append new results
        all_results = existing_results + self.results

        # Save updated results
        with open(filepath, "w") as f:
            json.dump(all_results, f, indent=2)

        print(f"\nResults saved to: {filename}")

    def compare_with_baseline(self, baseline_file: str):
        """Compare current results with baseline measurements."""
        try:
            with open(baseline_file) as f:
                baseline_data = json.load(f)

            if not baseline_data:
                print("No baseline data found")
                return

            # Get most recent baseline
            latest_baseline = baseline_data[-1]
            current_stats = self.results[-1]

            baseline_mean = latest_baseline["mean"]
            current_mean = current_stats["mean"]

            improvement = baseline_mean - current_mean
            improvement_pct = (improvement / baseline_mean) * 100

            print("\n" + "=" * 60)
            print("PERFORMANCE COMPARISON")
            print("=" * 60)
            print(f"Baseline:  {baseline_mean:.3f}s ({latest_baseline['timestamp']})")
            print(f"Current:   {current_mean:.3f}s")
            print(f"Change:    {improvement:+.3f}s ({improvement_pct:+.1f}%)")

            if improvement > 0:
                print(f"🚀 IMPROVEMENT: {improvement:.3f}s faster!")
            elif improvement < 0:
                print(f"⚠️  REGRESSION: {abs(improvement):.3f}s slower")
            else:
                print("➡️  NO CHANGE")

        except FileNotFoundError:
            print(f"Baseline file {baseline_file} not found")
        except Exception as e:
            print(f"Error comparing with baseline: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Measure TunaCode startup performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=5,
        help="Number of startup measurements to perform (default: 5)",
    )

    parser.add_argument(
        "--command",
        "-c",
        type=str,
        default="--version",
        help="Command to run for timing (default: --version)",
    )

    parser.add_argument("--output", "-o", type=str, help="Save results to JSON file")

    parser.add_argument("--baseline", "-b", type=str, help="Compare results with baseline file")

    parser.add_argument(
        "--save-as-baseline", action="store_true", help="Save results as baseline.json"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.iterations < 1:
        print("Error: iterations must be >= 1")
        sys.exit(1)

    try:
        # Create timer and run measurements
        timer = StartupTimer(iterations=args.iterations, command=args.command)
        stats = timer.measure_startup_time()

        # Print results
        timer.print_results(stats)

        # Save results if requested
        if args.output:
            timer.save_results(args.output)

        if args.save_as_baseline:
            timer.save_results("baseline.json")
            print("Results saved as baseline for future comparisons")

        # Compare with baseline if requested
        if args.baseline:
            timer.compare_with_baseline(args.baseline)

    except KeyboardInterrupt:
        print("\nMeasurement interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
