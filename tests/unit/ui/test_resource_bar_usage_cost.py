from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from tunacode.types.canonical import UsageMetrics

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp


@dataclass
class _FakeResourceBar:
    last_kwargs: dict[str, Any] | None = None

    def update_stats(self, **kwargs: Any) -> None:
        self.last_kwargs = kwargs


@pytest.mark.asyncio
async def test_update_resource_bar_passes_session_cost_total() -> None:
    state_manager = StateManager()
    state_manager.session.usage.session_total_usage = UsageMetrics.from_dict(
        {
            "input": 10,
            "output": 5,
            "cache_read": 2,
            "cache_write": 1,
            "total_tokens": 15,
            "cost": {
                "input": 0.01,
                "output": 0.02,
                "cache_read": 0.003,
                "cache_write": 0.001,
                "total": 0.034,
            },
        }
    )

    app = TextualReplApp(state_manager=state_manager)
    fake_resource_bar = _FakeResourceBar()
    app.resource_bar = cast(Any, fake_resource_bar)

    app._update_resource_bar()

    assert fake_resource_bar.last_kwargs is not None
    assert fake_resource_bar.last_kwargs["session_cost"] == pytest.approx(0.034)
