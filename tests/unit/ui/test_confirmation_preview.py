"""Confirmation preview safety tests.

These tests guard against UI hangs caused by extremely large tool confirmation previews,
especially for `write_file` where the preview is rendered using Rich `Syntax`.
"""

from __future__ import annotations

from tunacode.constants import MAX_CALLBACK_CONTENT

from tunacode.tools.authorization.requests import (
    MAX_PREVIEW_LINES,
    TRUNCATION_NOTICE,
    ConfirmationRequestFactory,
)


def test_write_file_preview_bounded_for_large_single_line_payload() -> None:
    factory = ConfirmationRequestFactory()
    content = "a" * (MAX_CALLBACK_CONTENT * 5)

    request = factory.create("write_file", {"filepath": "big.txt", "content": content})

    assert request.diff_content is not None
    assert len(request.diff_content) <= MAX_CALLBACK_CONTENT
    assert TRUNCATION_NOTICE in request.diff_content


def test_write_file_preview_truncates_after_max_preview_lines() -> None:
    factory = ConfirmationRequestFactory()
    content = ("x\n" * (MAX_PREVIEW_LINES + 50)).rstrip("\n")

    request = factory.create("write_file", {"filepath": "many_lines.txt", "content": content})

    assert request.diff_content is not None
    assert f"@@ -0,0 +1,{MAX_PREVIEW_LINES} @@" in request.diff_content
    assert TRUNCATION_NOTICE in request.diff_content


def test_write_file_preview_not_truncated_for_small_content() -> None:
    factory = ConfirmationRequestFactory()
    content = "hello\nworld\n"

    request = factory.create("write_file", {"filepath": "small.txt", "content": content})

    assert request.diff_content is not None
    assert TRUNCATION_NOTICE not in request.diff_content
