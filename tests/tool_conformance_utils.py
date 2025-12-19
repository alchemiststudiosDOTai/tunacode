"""Shared utilities for tool conformance tests."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from tunacode.tools.xml_helper import load_prompt_from_xml

DEFAULT_FILEPATH_PARAM_NAME = "filepath"
DEFAULT_MIN_DOCSTRING_LENGTH = 10
DEFAULT_MIN_PARAM_COUNT = 1
DEFAULT_RETURN_TYPE_NAME = "str"
FIRST_PARAM_INDEX = 0


class ToolRule(str, Enum):
    ASYNC = "async"
    DECORATED = "decorated"
    DOCSTRING_LENGTH = "docstring_length"
    DOCSTRING_MISMATCH = "docstring_mismatch"
    DOCSTRING_MISSING = "docstring_missing"
    FILEPATH_ANNOTATION_INVALID = "filepath_annotation_invalid"
    FILEPATH_ANNOTATION_MISSING = "filepath_annotation_missing"
    PARAM_COUNT = "param_count"
    RETURN_ANNOTATION_INVALID = "return_annotation_invalid"
    RETURN_ANNOTATION_MISSING = "return_annotation_missing"
    XML_PROMPT = "xml_prompt"


@dataclass(frozen=True)
class ToolValidationRules:
    filepath_param_name: str
    min_docstring_length: int
    min_param_count: int
    return_type_name: str
    require_decorator: bool
    require_return_annotation: bool
    require_xml_prompt: bool


@dataclass(frozen=True)
class ToolViolation:
    rule: ToolRule
    message: str


DEFAULT_TOOL_RULES = ToolValidationRules(
    filepath_param_name=DEFAULT_FILEPATH_PARAM_NAME,
    min_docstring_length=DEFAULT_MIN_DOCSTRING_LENGTH,
    min_param_count=DEFAULT_MIN_PARAM_COUNT,
    return_type_name=DEFAULT_RETURN_TYPE_NAME,
    require_decorator=True,
    require_return_annotation=True,
    require_xml_prompt=True,
)


def _add_violation(
    violations: list[ToolViolation],
    rule: ToolRule,
    message: str,
) -> None:
    violation = ToolViolation(rule=rule, message=message)
    violations.append(violation)


def validate_tool(
    tool: Callable[..., object],
    *,
    rules: ToolValidationRules,
) -> tuple[ToolViolation, ...]:
    violations: list[ToolViolation] = []
    tool_name = tool.__name__

    is_async = inspect.iscoroutinefunction(tool)
    if not is_async:
        _add_violation(
            violations,
            ToolRule.ASYNC,
            f"{tool_name} is not an async function",
        )

    unwrapped = inspect.unwrap(tool)
    is_wrapped = unwrapped is not tool
    if rules.require_decorator and not is_wrapped:
        _add_violation(
            violations,
            ToolRule.DECORATED,
            f"{tool_name} is not wrapped by a tool decorator",
        )

    xml_prompt = load_prompt_from_xml(tool_name)
    if rules.require_xml_prompt and xml_prompt is None:
        _add_violation(
            violations,
            ToolRule.XML_PROMPT,
            f"{tool_name} is missing an XML prompt",
        )

    docstring = tool.__doc__
    if not docstring:
        _add_violation(
            violations,
            ToolRule.DOCSTRING_MISSING,
            f"{tool_name} has no docstring",
        )

    if docstring:
        docstring_length = len(docstring)
        min_docstring_length = rules.min_docstring_length
        if docstring_length <= min_docstring_length:
            _add_violation(
                violations,
                ToolRule.DOCSTRING_LENGTH,
                f"{tool_name} docstring too short: {docstring!r}",
            )

    if xml_prompt and docstring and docstring != xml_prompt:
        _add_violation(
            violations,
            ToolRule.DOCSTRING_MISMATCH,
            f"{tool_name} docstring does not match XML prompt",
        )

    signature = inspect.signature(tool)
    params = list(signature.parameters.values())
    param_count = len(params)
    min_param_count = rules.min_param_count
    has_required_param_count = param_count >= min_param_count
    if not has_required_param_count:
        _add_violation(
            violations,
            ToolRule.PARAM_COUNT,
            f"{tool_name} has {param_count} parameters, expected {min_param_count}",
        )

    first_param_name = params[FIRST_PARAM_INDEX].name if params else None
    filepath_param_name = rules.filepath_param_name
    is_file_tool = has_required_param_count and first_param_name == filepath_param_name
    if is_file_tool:
        filepath_param = params[FIRST_PARAM_INDEX]
        annotation = filepath_param.annotation
        if annotation is inspect.Parameter.empty:
            _add_violation(
                violations,
                ToolRule.FILEPATH_ANNOTATION_MISSING,
                f"{tool_name} filepath annotation is missing",
            )
        if annotation is not inspect.Parameter.empty and annotation is not str:
            _add_violation(
                violations,
                ToolRule.FILEPATH_ANNOTATION_INVALID,
                f"{tool_name} filepath annotation is {annotation}, expected str",
            )

    return_annotation = signature.return_annotation
    return_annotation_missing = return_annotation is inspect.Parameter.empty
    requires_return_annotation = rules.require_return_annotation
    if return_annotation_missing and requires_return_annotation:
        _add_violation(
            violations,
            ToolRule.RETURN_ANNOTATION_MISSING,
            f"{tool_name} is missing a return annotation",
        )
    if not return_annotation_missing:
        return_annotation_name = str(return_annotation)
        return_type_name = rules.return_type_name
        has_valid_return = return_annotation is str or return_type_name in return_annotation_name
        if not has_valid_return:
            _add_violation(
                violations,
                ToolRule.RETURN_ANNOTATION_INVALID,
                f"{tool_name} return annotation is {return_annotation}",
            )

    return tuple(violations)
