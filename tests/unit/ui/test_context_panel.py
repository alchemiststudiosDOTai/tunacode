from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from textual.dom import DOMNode

from tunacode.ui.context_panel import is_widget_within_field


@dataclass
class _NodeStub:
    id: str | None
    parent: "_NodeStub | None" = None


def test_is_widget_within_field_matches_ancestor_id() -> None:
    root = _NodeStub(id="root")
    field = _NodeStub(id="field-model", parent=root)
    child = _NodeStub(id="child", parent=field)

    assert is_widget_within_field(
        cast(DOMNode, child),
        cast(DOMNode, root),
        field_id="field-model",
    )


def test_is_widget_within_field_stops_at_root_boundary() -> None:
    root = _NodeStub(id="root")
    sibling = _NodeStub(id="field-skills", parent=root)
    child = _NodeStub(id="child", parent=sibling)

    assert not is_widget_within_field(
        cast(DOMNode, child),
        cast(DOMNode, sibling),
        field_id="root",
    )
