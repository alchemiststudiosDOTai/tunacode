from __future__ import annotations

import os
import time
from pathlib import Path

from tinyagent import Agent

from tunacode.tools.cache_accessors.ignore_manager_cache import (
    clear_ignore_manager_cache,
    get_ignore_manager,
)

from tunacode.infrastructure.cache.caches.agents import clear_agents, get_agent, set_agent
from tunacode.infrastructure.cache.caches.tunacode_context import (
    clear_context_cache,
    get_context,
)


def test_agents_accessor_is_version_aware() -> None:
    clear_agents()

    model = "gpt-test"
    agent_v1 = Agent()

    set_agent(model, agent=agent_v1, version=1)
    assert get_agent(model, expected_version=1) is agent_v1

    # Mismatched version invalidates.
    assert get_agent(model, expected_version=2) is None
    assert get_agent(model, expected_version=1) is None


def test_tunacode_context_accessor_is_mtime_aware(tmp_path: Path) -> None:
    clear_context_cache()

    context_path = tmp_path / "AGENTS.md"
    context_path.write_text("hello\n")

    first = get_context(context_path)
    second = get_context(context_path)
    assert first == second

    # Force mtime change (ns) deterministically.
    original_mtime_ns = os.stat(context_path).st_mtime_ns
    context_path.write_text("hello again\n")

    new_mtime_ns = original_mtime_ns + 1_000_000_000
    os.utime(context_path, ns=(new_mtime_ns, new_mtime_ns))
    assert os.stat(context_path).st_mtime_ns == new_mtime_ns

    third = get_context(context_path)
    assert third != first
    assert "hello again" in third


def test_ignore_manager_accessor_is_mtime_aware(tmp_path: Path) -> None:
    clear_ignore_manager_cache()

    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text("ignored.txt\n")

    first = get_ignore_manager(tmp_path)
    second = get_ignore_manager(tmp_path)
    assert first is second

    time.sleep(0.01)
    gitignore_path.write_text("ignored2.txt\n")

    third = get_ignore_manager(tmp_path)
    assert third is not second
