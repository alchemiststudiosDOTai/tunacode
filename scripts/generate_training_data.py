#!/usr/bin/env python3
"""CLI for generating synthetic training data for tunacode tool calling.

Usage:
    uv run python scripts/generate_training_data.py --count 100 --output data/training.jsonl
    uv run python scripts/generate_training_data.py --count 500 --augment
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Generate synthetic training data."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic training data for tunacode tool calling",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of training conversations to generate",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="training_data.jsonl",
        help="Output file path (JSONL format)",
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        help="Apply data augmentation (path variations)",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Exclude tool definitions from training data",
    )
    parser.add_argument(
        "--variations",
        type=int,
        default=3,
        help="Number of query variations per scenario",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview first 3 conversations without saving",
    )

    args = parser.parse_args()

    # Set random seed if provided
    if args.seed is not None:
        import random

        random.seed(args.seed)

    # Import here to avoid slow startup for --help
    from tunacode.training.dataset_generator import (
        generate_dataset,
        generate_with_augmentation,
    )
    from tunacode.training.scenarios import ALL_SCENARIOS

    print(f"Generating {args.count} training conversations...")
    print(f"Using {len(ALL_SCENARIOS)} base scenarios")

    # Generate dataset
    if args.augment:
        print("Augmentation enabled: applying path variations")
        dataset = generate_with_augmentation(
            count=args.count,
            augment_queries=True,
            augment_paths=True,
        )
    else:
        dataset = generate_dataset(
            count=args.count,
            include_tools=not args.no_tools,
            variations_per_scenario=args.variations,
        )

    print(f"Generated {len(dataset.conversations)} conversations")

    # Preview mode
    if args.preview:
        import json

        print("\n--- Preview (first 3 conversations) ---\n")
        for i, conv in enumerate(dataset.conversations[:3]):
            print(f"=== Conversation {i + 1} ===")
            conv_dict = conv.to_dict()
            # Truncate tools for readability
            if "tools" in conv_dict and conv_dict["tools"]:
                conv_dict["tools"] = "[TOOL DEFINITIONS TRUNCATED]"
            print(json.dumps(conv_dict, indent=2))
            print()
        return 0

    # Save dataset
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataset.save_jsonl(str(output_path))
    print(f"Saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
