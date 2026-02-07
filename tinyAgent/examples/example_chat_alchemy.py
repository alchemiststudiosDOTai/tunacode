#!/usr/bin/env python3
"""Example: interactive chat using the Rust `alchemy-llm` backend.

This uses the PyO3 binding in `bindings/alchemy_llm_py` and streams events in
real-time by pulling events from Rust in a thread.

Setup:
  uv pip install -p .venv/bin/python maturin
  cd bindings/alchemy_llm_py
  ../../.venv/bin/python -m maturin develop --release --uv

Auth:
  Add OPENROUTER_API_KEY to .env or export it.

Run:
  uv run python examples/example_chat_alchemy.py
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from tinyagent import Agent, AgentOptions, extract_text
from tinyagent.alchemy_provider import OpenAICompatModel, stream_alchemy_openai_completions


def should_exit(user_input: str) -> bool:
    return user_input.lower() in ("quit", "exit", "q")


async def chat_once(agent: Agent, user_input: str) -> None:
    printed_any = False

    async for event in agent.stream(user_input):
        if event.type == "message_update":
            ame = event.assistant_message_event
            if isinstance(ame, dict) and ame.get("type") == "text_delta" and ame.get("delta"):
                print(str(ame["delta"]), end="", flush=True)
                printed_any = True

        is_assistant_end = (
            event.type == "message_end"
            and event.message
            and event.message.get("role") == "assistant"
        )
        if is_assistant_end:
            if not printed_any:
                print(extract_text(event.message), end="", flush=True)
            print()


async def main() -> None:
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Please set OPENROUTER_API_KEY environment variable")
        return

    agent = Agent(AgentOptions(stream_fn=stream_alchemy_openai_completions))
    agent.set_system_prompt("You are a helpful assistant. Be concise.")
    agent.set_model(
        OpenAICompatModel(
            provider="openrouter",
            id="moonshotai/kimi-k2.5",
            base_url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "X-Title": "tinyagent-alchemy-example",
            },
        )
    )

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
        await chat_once(agent, user_input)


if __name__ == "__main__":
    asyncio.run(main())
