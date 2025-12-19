"""Deliberately non-conformant tool used for negative testing."""

from __future__ import annotations


async def bad_tool(filepath: str) -> int:
    return 1
