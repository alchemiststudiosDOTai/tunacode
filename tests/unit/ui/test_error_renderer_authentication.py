from rich.console import Console

from tunacode.ui.renderers.errors import render_exception


class AuthenticationError(Exception):
    pass


def _renderable_text(renderable: object) -> str:
    console = Console(record=True, width=120)
    console.print(renderable)
    return console.export_text()


def test_render_exception_authentication_sets_error_severity() -> None:
    content, meta = render_exception(AuthenticationError("bad key"))

    assert meta.css_class == "error-panel"
    assert "AuthenticationError" in meta.border_title
    assert "bad key" in _renderable_text(content)


def test_render_exception_authentication_includes_recovery_commands() -> None:
    content, _ = render_exception(AuthenticationError("bad key"))

    rendered_text = _renderable_text(content)
    assert "/model" in rendered_text or "tunacode --setup" in rendered_text
