"""Per-tool argument schemas for model tool calls.

Each TypedDict declares the JSON argument shape a tool renderer reads from
the model's tool call (`ToolCallContent.arguments`). All schemas use
total=False: model output is untrusted, so every key may be missing and
readers keep defensive .get() defaults.
"""

from typing import TypedDict


class BashArgs(TypedDict, total=False):
    command: str
    timeout: int


class ReadFileArgs(TypedDict, total=False):
    filepath: str
    offset: int


class WriteFileArgs(TypedDict, total=False):
    filepath: str
    content: str


class WebFetchArgs(TypedDict, total=False):
    url: str
    timeout: int


class HashlineEditArgs(TypedDict, total=False):
    filepath: str
