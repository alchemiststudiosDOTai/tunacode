"""OpenAI function call formatter for tool integration.

This module handles formatting tool calls in OpenAI function calling format
with stringified arguments as required by new_prompt.xml.
"""

import json
from typing import Any, Dict, List


class OpenAIFormatter:
    """Formats tool calls for OpenAI function calling API."""

    @staticmethod
    def format_tool_call(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Format tool call in OpenAI function format.

        Args:
            tool_name: Name of the tool to call
            args: Arguments dictionary for the tool

        Returns:
            OpenAI function call format with stringified arguments
        """
        return {
            "tool_calls": [
                {
                    "id": f"call_{abs(hash(str(args))) % 100000000}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args),  # CRITICAL: Stringify args
                    },
                }
            ]
        }

    @staticmethod
    def format_multiple_tool_calls(calls: List[tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Format multiple tool calls for parallel execution.

        Args:
            calls: List of (tool_name, args) tuples

        Returns:
            OpenAI function call format with multiple tool calls
        """
        tool_calls = []
        for i, (tool_name, args) in enumerate(calls):
            tool_calls.append(
                {
                    "id": f"call_{i}_{abs(hash(str(args))) % 1000000}",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": json.dumps(args)},
                }
            )

        return {"tool_calls": tool_calls}

    @staticmethod
    def parse_tool_response(response: str) -> Dict[str, Any]:
        """Parse OpenAI format response back to dict.

        Args:
            response: JSON string in OpenAI tool call format

        Returns:
            Parsed response with arguments as dictionaries
        """
        data = json.loads(response)

        # Parse stringified arguments back to dicts
        for call in data.get("tool_calls", []):
            if "function" in call and "arguments" in call["function"]:
                # Parse stringified arguments
                call["function"]["arguments"] = json.loads(call["function"]["arguments"])

        return data

    @staticmethod
    def validate_format(data: Dict[str, Any]) -> bool:
        """Validate that data follows OpenAI function call format.

        Args:
            data: Data to validate

        Returns:
            True if valid OpenAI format
        """
        if not isinstance(data, dict) or "tool_calls" not in data:
            return False

        tool_calls = data["tool_calls"]
        if not isinstance(tool_calls, list):
            return False

        for call in tool_calls:
            if not isinstance(call, dict):
                return False
            if not all(key in call for key in ["id", "type", "function"]):
                return False
            if call["type"] != "function":
                return False
            if not isinstance(call["function"], dict):
                return False
            if not all(key in call["function"] for key in ["name", "arguments"]):
                return False
            # Arguments must be a string (JSON)
            if not isinstance(call["function"]["arguments"], str):
                return False

        return True
