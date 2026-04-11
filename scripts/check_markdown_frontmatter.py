#!/usr/bin/env python3
"""Validate required frontmatter for repo-root and docs markdown files."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRONTMATTER_DELIMITER = "---"
REQUIRED_KEYS = ("when_to_read", "summary", "last_updated")
SKIP_FILENAMES = {"AGENTS.md", "README.md"}


@dataclass(frozen=True)
class ValidationError:
    path: Path
    message: str


def iter_markdown_files() -> list[Path]:
    root_markdown = [
        path
        for path in ROOT.iterdir()
        if path.is_file() and path.suffix == ".md" and path.name not in SKIP_FILENAMES
    ]
    docs_markdown = [path for path in DOCS_DIR.rglob("*.md") if path.is_file()]
    return sorted(root_markdown + docs_markdown)


def extract_frontmatter(path: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise ValueError("missing YAML frontmatter at top of file")

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_DELIMITER:
            end_index = index
            break

    if end_index is None:
        raise ValueError("frontmatter is missing closing '---' delimiter")

    frontmatter_text = "\n".join(lines[1:end_index])

    try:
        data = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML frontmatter: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("frontmatter must parse to a YAML mapping")

    return data


def validate_when_to_read(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return None
    if isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value):
        return None
    return "frontmatter key 'when_to_read' must be a non-empty string or list of non-empty strings"


def validate_summary(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return None
    return "frontmatter key 'summary' must be a non-empty string"


def validate_last_updated(value: object) -> str | None:
    if isinstance(value, str) and DATE_PATTERN.match(value):
        return None
    return "frontmatter key 'last_updated' must be a YYYY-MM-DD string"


def validate_frontmatter(path: Path) -> list[ValidationError]:
    try:
        frontmatter = extract_frontmatter(path)
    except ValueError as exc:
        return [ValidationError(path=path, message=str(exc))]

    errors: list[ValidationError] = []
    for key in REQUIRED_KEYS:
        if key not in frontmatter:
            errors.append(
                ValidationError(
                    path=path,
                    message=f"missing required frontmatter key '{key}'",
                )
            )

    if errors:
        return errors

    validators = (
        validate_when_to_read(frontmatter["when_to_read"]),
        validate_summary(frontmatter["summary"]),
        validate_last_updated(frontmatter["last_updated"]),
    )
    for message in validators:
        if message is not None:
            errors.append(ValidationError(path=path, message=message))

    return errors


def main() -> int:
    errors: list[ValidationError] = []
    for path in iter_markdown_files():
        errors.extend(validate_frontmatter(path))

    if not errors:
        print("All repo-root/docs markdown files have required frontmatter.")
        return 0

    print("Markdown frontmatter validation failed:")
    for error in errors:
        relative_path = error.path.relative_to(ROOT)
        print(f"- {relative_path}: {error.message}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
