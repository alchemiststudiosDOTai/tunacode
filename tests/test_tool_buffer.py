from dataclasses import dataclass

from tunacode.core.agents.agent_components.tool_buffer import ToolBuffer


@dataclass
class DummyPart:
    tool_name: str


def test_tool_buffer_counts_and_peek():
    buffer = ToolBuffer()

    parts = [DummyPart("read_file"), DummyPart("grep"), DummyPart("read_file")]
    nodes = [object() for _ in parts]
    for part, node in zip(parts, nodes):
        buffer.add(part, node)

    counts = buffer.count_by_type()
    assert counts == {"read_file": 2, "grep": 1}

    peeked = buffer.peek()
    assert peeked == list(zip(parts, nodes))
    assert buffer.size() == 3
    assert buffer.has_tasks()

    flushed = buffer.flush()
    assert flushed == list(zip(parts, nodes))
    assert buffer.size() == 0
    assert buffer.count_by_type() == {}
