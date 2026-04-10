from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_check_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_stale_symbol_surfaces.py"
    spec = importlib.util.spec_from_file_location("check_stale_symbol_surfaces", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_stale_protocol_and_reexported_helper_are_reported(tmp_path: Path) -> None:
    module = _load_check_module()

    src_root = tmp_path / "src"
    package_root = src_root / "tunacode" / "pkg"
    tests_root = tmp_path / "tests"
    package_root.mkdir(parents=True)
    tests_root.mkdir()

    (package_root / "__init__.py").write_text(
        "from .agent_helpers import handle_empty_response\n",
        encoding="utf-8",
    )
    (package_root / "agent_helpers.py").write_text(
        """
from typing import Protocol


class EmptyResponseStateView(Protocol):
    sm: object
    show_thoughts: bool


async def handle_empty_response(message: str, state: EmptyResponseStateView) -> str:
    return message
""".lstrip(),
        encoding="utf-8",
    )

    violations = module.find_stale_symbol_surface_violations(
        target_root=src_root,
        scan_roots=(src_root, tests_root),
    )

    formatted = [violation.format() for violation in violations]
    assert any("SSS001" in line and "handle_empty_response" in line for line in formatted)
    assert any("SSS002" in line and "EmptyResponseStateView" in line for line in formatted)


def test_live_function_signature_keeps_protocol_surface_alive(tmp_path: Path) -> None:
    module = _load_check_module()

    src_root = tmp_path / "src"
    package_root = src_root / "tunacode" / "pkg"
    tests_root = tmp_path / "tests"
    package_root.mkdir(parents=True)
    tests_root.mkdir()

    (package_root / "__init__.py").write_text(
        "from .agent_helpers import handle_empty_response\n",
        encoding="utf-8",
    )
    (package_root / "agent_helpers.py").write_text(
        """
from typing import Protocol


class EmptyResponseStateView(Protocol):
    sm: object
    show_thoughts: bool


async def handle_empty_response(message: str, state: EmptyResponseStateView) -> str:
    return message
""".lstrip(),
        encoding="utf-8",
    )
    (tests_root / "test_usage.py").write_text(
        """
from tunacode.pkg import handle_empty_response


async def test_usage() -> None:
    assert handle_empty_response is not None
""".lstrip(),
        encoding="utf-8",
    )

    violations = module.find_stale_symbol_surface_violations(
        target_root=src_root,
        scan_roots=(src_root, tests_root),
    )

    assert violations == []
