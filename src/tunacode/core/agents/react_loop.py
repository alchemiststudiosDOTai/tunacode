from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Iterable, Optional

from pydantic_ai.usage import UsageLimits

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.types import ModelName

from .agent_components import (
    get_or_create_agent,
    get_or_create_manager_agent,
    get_or_create_react_agent,
)

_MAX_WORKERS = 3
_TURN_LIMIT = 10
_FINAL_TURN_LIMIT = 6

logger = get_logger(__name__)


async def run_react_loop(
    task: str,
    model: ModelName,
    state_manager: StateManager,
    thought_log: Optional[Callable[[str], Awaitable[None]]] = None,
) -> dict[str, Any]:
    await _emit_thought(thought_log, f"Manager planning for task: {task}")
    manager = get_or_create_manager_agent(model, state_manager)
    plan_run = await manager.run(task)
    plan_text = _as_text(plan_run)
    await _emit_thought(thought_log, f"Manager plan received: {plan_text}")
    goals = (_parse_json_goals(plan_text) or _parse_bullet_goals(plan_text) or [task])[
        :_MAX_WORKERS
    ]
    if not goals:
        goals = [task]
    await _emit_thought(
        thought_log,
        "Workers assigned goals: " + ", ".join(goals),
    )
    workers = await asyncio.gather(
        *(
            _run_worker(i + 1, goal, model, state_manager, thought_log)
            for i, goal in enumerate(goals)
        )
    )
    final_message = await _synthesize_final_answer(
        task, plan_text, workers, model, state_manager, thought_log
    )
    return {"plan": plan_text, "workers": workers, "final": final_message}


async def _run_worker(
    index: int,
    goal: str,
    model: ModelName,
    state_manager: StateManager,
    thought_log: Optional[Callable[[str], Awaitable[None]]],
) -> dict[str, str]:
    await _emit_thought(thought_log, f"worker-{index} starting goal: {goal}")
    agent = get_or_create_react_agent(model, state_manager)
    run = await agent.run(goal, usage_limits=UsageLimits(request_limit=_TURN_LIMIT))
    output = _as_text(run).strip()
    await _emit_thought(thought_log, f"worker-{index} completed with summary: {output}")
    return {"name": f"worker-{index}", "goal": goal, "output": output}


async def _synthesize_final_answer(
    task: str,
    plan_text: str,
    workers: list[dict[str, str]],
    model: ModelName,
    state_manager: StateManager,
    thought_log: Optional[Callable[[str], Awaitable[None]]],
) -> str:
    await _emit_thought(thought_log, "Synthesizing final answer from worker results")

    agent = get_or_create_agent(model, state_manager)
    worker_summaries = []
    for worker in workers:
        name = worker.get("name") or "worker"
        goal = worker.get("goal") or ""
        output = (worker.get("output") or "").strip()
        worker_summaries.append(f"Name: {name}\nGoal: {goal}\nOutput: {output}")

    synthesis_prompt = (
        "You are the final TunaCode assistant. Combine the manager plan and the worker"
        " findings into a single actionable response that directly addresses the user's"
        " original question. If critical details are missing, request targeted follow-up."
        "\n\nTask: "
        + task
        + "\nOriginal Question: "
        + task
        + "\nManager Plan:\n"
        + (plan_text or "(no plan)")
        + "\n\nWorker Reports:\n"
        + ("\n\n".join(worker_summaries) if worker_summaries else "(no worker output)")
        + "\n\nRespond with a concise summary that begins with 'TUNACODE DONE:' and includes"
        " key findings or next steps. Explicitly confirm how the answer satisfies the"
        " user request, referencing evidence from the worker reports."
    )

    try:
        run = await agent.run(
            synthesis_prompt,
            usage_limits=UsageLimits(request_limit=_FINAL_TURN_LIMIT),
        )
    except Exception as exc:  # pragma: no cover - defensive
        await _emit_thought(thought_log, f"Final synthesis failed: {exc}")
        logger.warning("ReAct loop final synthesis failed: %s", exc)
        return "TUNACODE DONE: ReAct loop finished, but final synthesis failed."

    final_text = _as_text(run).strip()
    if not final_text.upper().startswith("TUNACODE DONE:"):
        final_text = f"TUNACODE DONE: {final_text}" if final_text else "TUNACODE DONE:"

    await _emit_thought(thought_log, "Final answer ready")
    return final_text


def _parse_json_goals(plan_text: str) -> list[str]:
    if not plan_text:
        return []
    cleaned = plan_text.strip()
    if cleaned.startswith("```"):
        match = re.search(r"```[a-zA-Z0-9_-]*\s*(\{.*\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        tasks: Iterable[Any] = data.get("tasks", [])
    elif isinstance(data, list):
        tasks = data
    else:
        return []
    goals: list[str] = []
    for item in tasks:
        if isinstance(item, dict):
            text = item.get("goal") or item.get("description")
        else:
            text = item
        if isinstance(text, str):
            text = text.strip()
            if text:
                goals.append(text)
    return goals


def _parse_bullet_goals(plan_text: str) -> list[str]:
    goals = []
    for line in plan_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```") or stripped in {"[", "]", "{", "}"}:
            continue
        cleaned = stripped.lstrip("-•1234567890. ").strip()
        if cleaned:
            goals.append(cleaned)
    return goals


def _as_text(run: Any) -> str:
    for attr in ("output", "output_text", "result"):
        value = getattr(run, attr, None)
        if isinstance(value, str):
            return value
    return ""


async def _emit_thought(
    thought_log: Optional[Callable[[str], Awaitable[None]]],
    message: str,
) -> None:
    logger.debug("ReAct loop: %s", message)
    if thought_log is not None:
        try:
            await thought_log(message)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to emit thought log: %s", exc)


__all__ = ["run_react_loop"]
