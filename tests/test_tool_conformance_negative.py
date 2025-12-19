"""Negative coverage to prove conformance validation catches bad tools."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from tests.tool_conformance_utils import DEFAULT_TOOL_RULES, ToolRule, validate_tool


class BadToolFixture(str, Enum):
    DIRECTORY = "fixtures"
    FILE_NAME = "bad_tool_example.py"
    FUNCTION_NAME = "bad_tool"
    MODULE_NAME = "bad_tool_example"


EXPECTED_VIOLATIONS = frozenset(
    [
        ToolRule.DECORATED,
        ToolRule.DOCSTRING_MISSING,
        ToolRule.RETURN_ANNOTATION_INVALID,
        ToolRule.XML_PROMPT,
    ]
)


def _fixture_path() -> Path:
    tests_dir = Path(__file__).parent
    fixtures_dir = tests_dir / BadToolFixture.DIRECTORY.value
    return fixtures_dir / BadToolFixture.FILE_NAME.value


def _load_bad_tool() -> Callable[..., object]:
    fixture_path = _fixture_path()
    spec = importlib.util.spec_from_file_location(
        BadToolFixture.MODULE_NAME.value,
        fixture_path,
    )
    assert spec is not None, f"Failed to load spec for {fixture_path}"
    loader = spec.loader
    assert loader is not None, f"No loader for {fixture_path}"
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    tool = getattr(module, BadToolFixture.FUNCTION_NAME.value)
    return tool


def test_bad_tool_fails_conformance() -> None:
    bad_tool = _load_bad_tool()
    violations = validate_tool(bad_tool, rules=DEFAULT_TOOL_RULES)
    violation_rules = {violation.rule for violation in violations}
    missing_rules = EXPECTED_VIOLATIONS - violation_rules
    assert violations, "Expected conformance violations for the bad tool"
    missing_rule_names = sorted(rule.value for rule in missing_rules)
    assert not missing_rules, f"Missing expected violations: {missing_rule_names}"
