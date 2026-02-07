#!/usr/bin/env python3
"""Example: interactive chat with OpenRouter using async iteration.

Usage:
    uv run python examples/example_chat.py

This example demonstrates:
- streaming text via `async for event in agent.stream(...)`
- tool calling (tool_execution_* events)
"""

import asyncio
import os

from dotenv import load_dotenv

from tinyagent import (
    Agent,
    AgentOptions,
    AgentTool,
    AgentToolResult,
    OpenRouterModel,
    extract_text,
    stream_openrouter,
)


# Example tool: get current time
async def get_current_time(tool_call_id: str, args: dict, signal, on_update) -> AgentToolResult:
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return AgentToolResult(content=[{"type": "text", "text": f"Current time: {now}"}], details={})


# Example tool: simple calculator
async def calculate(tool_call_id: str, args: dict, signal, on_update) -> AgentToolResult:
    expression = args.get("expression", "")
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            raise ValueError("Invalid characters in expression")
        result = eval(expression)
        return AgentToolResult(content=[{"type": "text", "text": f"Result: {result}"}], details={})
    except Exception as e:
        return AgentToolResult(content=[{"type": "text", "text": f"Error: {e}"}], details={})


def create_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="get_current_time",
            description="Get the current date and time",
            parameters={"type": "object", "properties": {}},
            execute=get_current_time,
        ),
        AgentTool(
            name="calculate",
            description="Perform a mathematical calculation",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. '2 + 2' or '(10 * 5) / 2'",
                    }
                },
                "required": ["expression"],
            },
            execute=calculate,
        ),
    ]


def build_agent() -> Agent:
    agent = Agent(AgentOptions(stream_fn=stream_openrouter))
    agent.set_system_prompt(
        "You are a helpful assistant. You can use tools when needed. Be concise in your responses."
    )
    agent.set_model(OpenRouterModel(id="moonshotai/kimi-k2.5"))
    agent.set_tools(create_tools())
    return agent


def should_exit(user_input: str) -> bool:
    return user_input.lower() in ("quit", "exit", "q")


async def chat_once(agent: Agent, user_input: str) -> None:
    printed_any = False

    async for event in agent.stream(user_input):
        if event.type == "tool_execution_start":
            print(f"\n[Using tool: {event.tool_name}]\n")
            continue

        if event.type == "message_update":
            ame = event.assistant_message_event
            if isinstance(ame, dict) and ame.get("type") == "text_delta" and ame.get("delta"):
                print(str(ame["delta"]), end="", flush=True)
                printed_any = True
            continue

        if (
            event.type == "message_end"
            and event.message
            and event.message.get("role") == "assistant"
        ):
            if not printed_any:
                print(extract_text(event.message), end="", flush=True)
            print()  # newline after assistant message


async def main() -> None:
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Please set OPENROUTER_API_KEY environment variable")
        return

    agent = build_agent()

    print("Chat with the agent (type 'quit' to exit)")
    print("-" * 40)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            return

        if not user_input:
            continue
        if should_exit(user_input):
            return

        print("Assistant: ", end="", flush=True)
        try:
            await chat_once(agent, user_input)
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            return
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
