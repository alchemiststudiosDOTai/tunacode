#!/usr/bin/env python3
"""Example: streaming chat using Agent.stream_text() (no subscribe()).

Usage:
    uv run python examples/example_chat_stream_text.py
"""

import asyncio
import os

from dotenv import load_dotenv

from tinyagent import Agent, AgentOptions, OpenRouterModel, stream_openrouter


def should_exit(user_input: str) -> bool:
    return user_input.lower() in ("quit", "exit", "q")


async def main() -> None:
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Please set OPENROUTER_API_KEY environment variable")
        return

    agent = Agent(AgentOptions(stream_fn=stream_openrouter))
    agent.set_system_prompt("You are a helpful assistant. Be concise.")
    agent.set_model(OpenRouterModel(id="moonshotai/kimi-k2.5"))

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
        async for chunk in agent.stream_text(user_input):
            print(chunk, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
