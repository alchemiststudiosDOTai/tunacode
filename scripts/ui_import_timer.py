#!/usr/bin/env python3
"""Measure import-time cost for TunaCode UI modules.

This script launches isolated Python interpreters to time how long it takes to
import specific modules. The approach ensures each timing run starts from a
clean interpreter so module caching does not skew results.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_ITERATIONS = 5
DEFAULT_WARMUP = 1
SEPARATOR_WIDTH = 60
DISPLAY_PRECISION = 4
DEFAULT_MODULES: Sequence[str] = (
    "tunacode.ui.console",
    "tunacode.ui.output",
    "tunacode.ui.panels",
)


@dataclass(slots=True)
class ModuleTiming:
    """Timing measurements for a single module."""

    module: str
    times: list[float]


@dataclass(slots=True)
class ModuleSummary:
    """Summary statistics for a module's import timings."""

    module: str
    mean: float
    median: float
    minimum: float
    maximum: float
    stdev: float
    runs: int
    times: list[float]


def _run_single_import(module: str) -> float:
    """Execute a fresh interpreter that imports *module* and reports duration."""

    timing_snippet = textwrap.dedent(
        f"""
        import importlib
        import time

        start = time.perf_counter()
        importlib.import_module({module!r})
        end = time.perf_counter()
        print(end - start)
        """
    ).strip()

    command = [sys.executable, "-c", timing_snippet]
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        raise RuntimeError(f"Importing {module!r} failed: {stderr}")

    output = result.stdout.strip()
    try:
        return float(output)
    except ValueError as exc:
        raise RuntimeError(f"Unexpected output while importing {module!r}: {output!r}") from exc


def measure_module(module: str, iterations: int, warmup: int) -> ModuleTiming:
    """Measure repeated import times for *module*."""

    if warmup > 0:
        for _ in range(warmup):
            _run_single_import(module)

    measurements: list[float] = []
    for _ in range(iterations):
        measurements.append(_run_single_import(module))

    return ModuleTiming(module=module, times=measurements)


def summarize(timing: ModuleTiming) -> ModuleSummary:
    """Compute summary statistics for the collected timings."""

    times = timing.times
    if not times:
        raise ValueError(f"No timing data collected for module {timing.module!r}")

    mean_time = statistics.fmean(times)
    median_time = statistics.median(times)
    min_time = min(times)
    max_time = max(times)
    stdev_time = statistics.pstdev(times) if len(times) > 1 else 0.0
    run_count = len(times)

    return ModuleSummary(
        module=timing.module,
        mean=mean_time,
        median=median_time,
        minimum=min_time,
        maximum=max_time,
        stdev=stdev_time,
        runs=run_count,
        times=list(times),
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of timing runs per module (default: %(default)s)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP,
        help="Warm-up runs to discard before measuring (default: %(default)s)",
    )
    parser.add_argument(
        "--module",
        action="append",
        dest="modules",
        metavar="MODULE",
        help="Fully qualified module to time; may be provided multiple times.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> Sequence[str]:
    """Validate CLI arguments and return the target modules."""

    if args.iterations <= 0:
        raise ValueError("--iterations must be a positive integer")

    if args.warmup < 0:
        raise ValueError("--warmup cannot be negative")

    modules: Sequence[str] = tuple(args.modules) if args.modules else DEFAULT_MODULES
    return modules


def format_seconds(value: float) -> str:
    """Format seconds with millisecond precision."""

    return f"{value:.{DISPLAY_PRECISION}f}s"


def main() -> None:
    """Entry point for CLI usage."""

    args = parse_args()
    modules = validate_args(args)

    print("Measuring import times (fresh interpreter per run)...")
    print(f"Iterations per module: {args.iterations}")
    print(f"Warm-up runs: {args.warmup}")
    print("Modules: " + ", ".join(modules))
    print("-" * SEPARATOR_WIDTH)

    for module in modules:
        timing = measure_module(module, iterations=args.iterations, warmup=args.warmup)
        stats = summarize(timing)

        print(f"Module: {stats.module}")
        print(f"  Mean:   {format_seconds(stats.mean)}")
        print(f"  Median: {format_seconds(stats.median)}")
        print(f"  Min:    {format_seconds(stats.minimum)}")
        print(f"  Max:    {format_seconds(stats.maximum)}")
        print(f"  Stdev:  {format_seconds(stats.stdev)}")
        formatted_runs = ", ".join(format_seconds(time_taken) for time_taken in stats.times)
        print(f"  Runs:   {formatted_runs}")
        print("-" * SEPARATOR_WIDTH)


if __name__ == "__main__":
    main()
