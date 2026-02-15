"""Tests for ChatContainer write behavior."""

from __future__ import annotations

from typing import cast

import pytest
from rich.console import RenderableType

from tunacode.ui.widgets.chat import ChatContainer, PanelMeta

TEST_RENDERABLE = "hello"
DETACHED_WARNING_FRAGMENT = "skipped mount because container is detached"


def test_write_returns_unmounted_widget_when_detached(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Detached containers should not attempt mount()."""
    container = ChatContainer()

    assert container.is_attached is False

    widget = container.write(TEST_RENDERABLE)

    captured = capsys.readouterr()
    assert DETACHED_WARNING_FRAGMENT in captured.err
    assert widget.parent is None
    assert len(container.children) == 0


def test_write_mounts_widget_when_attached(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Attached containers should continue using mount()."""
    container = ChatContainer(auto_scroll=False)
    mounted_widgets: list[object] = []

    def _fake_mount(_self: ChatContainer, *widgets: object, **_kwargs: object) -> None:
        mounted_widgets.extend(widgets)

    monkeypatch.setattr(ChatContainer, "is_attached", property(lambda _self: True))
    monkeypatch.setattr(ChatContainer, "mount", _fake_mount)

    widget = container.write(TEST_RENDERABLE)

    captured = capsys.readouterr()
    assert captured.err == ""
    assert mounted_widgets == [widget]


def test_write_mounts_tuple_renderable_with_panel_meta(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Panel tuples should be unpacked and metadata applied by write()."""

    container = ChatContainer(auto_scroll=False)
    mounted_widgets: list[object] = []

    def _fake_mount(_self: ChatContainer, *widgets: object, **_kwargs: object) -> None:
        mounted_widgets.extend(widgets)

    monkeypatch.setattr(ChatContainer, "is_attached", property(lambda _self: True))
    monkeypatch.setattr(ChatContainer, "mount", _fake_mount)

    widget = container.write(
        (
            TEST_RENDERABLE,
            PanelMeta(css_class="tool-panel", border_title="title", border_subtitle="sub"),
        )
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert mounted_widgets == [widget]
    assert widget.has_class("tool-panel")
    assert widget.border_title == "title"
    assert widget.border_subtitle == "sub"


def test_write_rejects_invalid_tuple_renderable() -> None:
    """Non-panel tuples must fail fast in write()."""
    container = ChatContainer(auto_scroll=False)

    bad_renderable = cast(tuple[RenderableType, PanelMeta], ("just", "a plain tuple"))
    with pytest.raises(TypeError, match=r"unsupported tuple renderable"):
        container.write(bad_renderable)
