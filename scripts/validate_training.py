#!/usr/bin/env python3
"""Validate training dataset for Unsloth fine-tuning.

Checks:
- Dataset file exists and is valid JSONL
- All records have required fields (conversations, system, tools)
- Conversation structure valid (from/value pairs)
- Reports stats (total examples, avg conversation length)

Usage:
    python scripts/validate_training.py [path/to/dataset.jsonl]
"""

import json
import sys
from pathlib import Path

DEFAULT_DATASET = Path("data/training.jsonl")
REQUIRED_FIELDS = {"conversations", "system", "tools"}
VALID_ROLES = {"system", "human", "gpt", "function_call", "function_response", "observation"}


def validate_conversation(conv: list[dict], idx: int) -> list[str]:
    """Validate a single conversation structure."""
    errors = []
    if not isinstance(conv, list):
        errors.append(f"[{idx}] conversations must be a list, got {type(conv).__name__}")
        return errors

    for i, turn in enumerate(conv):
        if not isinstance(turn, dict):
            errors.append(f"[{idx}] turn {i}: must be dict, got {type(turn).__name__}")
            continue
        if "from" not in turn:
            errors.append(f"[{idx}] turn {i}: missing 'from' field")
        elif turn["from"] not in VALID_ROLES:
            errors.append(f"[{idx}] turn {i}: invalid role '{turn['from']}'")
        if "value" not in turn:
            errors.append(f"[{idx}] turn {i}: missing 'value' field")

    return errors


def validate_record(record: dict, idx: int) -> list[str]:
    """Validate a single training record."""
    errors = []

    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        errors.append(f"[{idx}] missing required fields: {missing}")

    if "conversations" in record:
        errors.extend(validate_conversation(record["conversations"], idx))

    if "tools" in record:
        tools = record["tools"]
        if isinstance(tools, str):
            try:
                parsed = json.loads(tools)
                if not isinstance(parsed, list):
                    errors.append(f"[{idx}] tools JSON must be a list")
            except json.JSONDecodeError:
                errors.append(f"[{idx}] tools is invalid JSON string")
        elif not isinstance(tools, list):
            errors.append(f"[{idx}] tools must be list or JSON string")

    return errors


def validate_dataset(path: Path) -> tuple[bool, dict]:
    """Validate entire dataset file.

    Returns:
        Tuple of (success, stats_dict)
    """
    if not path.exists():
        return False, {"error": f"File not found: {path}"}

    stats = {
        "total_records": 0,
        "total_turns": 0,
        "errors": [],
        "role_counts": {},
        "avg_turns_per_record": 0.0,
    }

    with path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                stats["errors"].append(f"Line {line_num}: Invalid JSON - {e}")
                continue

            stats["total_records"] += 1
            errors = validate_record(record, line_num)
            stats["errors"].extend(errors)

            if "conversations" in record and isinstance(record["conversations"], list):
                stats["total_turns"] += len(record["conversations"])
                for turn in record["conversations"]:
                    if isinstance(turn, dict) and "from" in turn:
                        role = turn["from"]
                        stats["role_counts"][role] = stats["role_counts"].get(role, 0) + 1

    if stats["total_records"] > 0:
        stats["avg_turns_per_record"] = stats["total_turns"] / stats["total_records"]

    success = len(stats["errors"]) == 0
    return success, stats


def main() -> int:
    """Main entry point."""
    if len(sys.argv) > 1:
        dataset_path = Path(sys.argv[1])
    else:
        dataset_path = DEFAULT_DATASET

    print(f"Validating: {dataset_path}")
    print("-" * 50)

    success, stats = validate_dataset(dataset_path)

    if "error" in stats:
        print(f"ERROR: {stats['error']}")
        return 1

    print(f"Total records: {stats['total_records']}")
    print(f"Total turns: {stats['total_turns']}")
    print(f"Avg turns/record: {stats['avg_turns_per_record']:.1f}")
    print(f"Role distribution: {stats['role_counts']}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats["errors"][:20]:
            print(f"  {err}")
        if len(stats["errors"]) > 20:
            print(f"  ... and {len(stats['errors']) - 20} more")
        return 1

    print("\nDataset is valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
