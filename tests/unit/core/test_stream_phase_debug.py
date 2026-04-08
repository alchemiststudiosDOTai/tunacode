from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from tinyagent.agent_types import AssistantMessageEvent, MessageUpdateEvent

from tunacode.core.agents.agent_components import stream_events
from tunacode.core.agents.main import RequestOrchestrator
from tunacode.core.session import StateManager


@dataclass
class _FakeLogger:
    messages: list[str] = field(default_factory=list)

    def lifecycle(self, message: str) -> None:
        self.messages.append(message)

    def info(self, message: str, **_kwargs: object) -> None:
        self.messages.append(message)

    def warning(self, message: str, **_kwargs: object) -> None:
        self.messages.append(message)

    def debug(self, message: str, **_kwargs: object) -> None:
        self.messages.append(message)


class _FakeAgent:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self.state = SimpleNamespace(error=None, messages=[])

    async def stream(self, _message: str):
        for event in self._events:
            yield event


async def test_run_stream_logs_first_event_and_large_event_gap(
    monkeypatch,
) -> None:
    logger = _FakeLogger()
    state_manager = StateManager()
    orchestrator = RequestOrchestrator(
        message="hello",
        model="openai/gpt-4o",
        state_manager=state_manager,
        streaming_callback=None,
        thinking_callback=None,
    )
    fake_agent = _FakeAgent(
        [
            MessageUpdateEvent(
                assistant_message_event=AssistantMessageEvent(
                    type="thinking_delta",
                    delta="a",
                )
            ),
            MessageUpdateEvent(
                assistant_message_event=AssistantMessageEvent(
                    type="thinking_delta",
                    delta="b",
                )
            ),
        ]
    )

    perf_counter_values = iter(
        [
            100.0,
            100.350,
            100.351,
            100.352,
            100.900,
            100.901,
            100.902,
            101.000,
        ]
    )
    monkeypatch.setattr(stream_events, "get_logger", lambda: logger)
    monkeypatch.setattr(stream_events.time, "perf_counter", lambda: next(perf_counter_values))
    monkeypatch.setattr(stream_events.threading, "get_ident", lambda: 777)

    await orchestrator._run_stream(
        agent=fake_agent,
        max_iterations=4,
        baseline_message_count=0,
    )

    assert logger.messages[0] == "Stream: start thread=777"
    assert (
        logger.messages[1]
        == "Stream: first_event type=message_update/thinking_delta since_start=350.0ms thread=777"
    )
    assert (
        logger.messages[2]
        == "Stream: event_gap type=message_update/thinking_delta gap=550.0ms count=2"
    )
    assert logger.messages[3] == "Stream: end events=2 first_event=350.0ms"
    assert logger.messages[4] == "Request complete (1000ms)"
