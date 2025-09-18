"""Reusable ReAct planning/evaluation coordination utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from pydantic_ai import Agent

from tunacode.core.agents.agent_components import create_user_message
from tunacode.core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ReactLoopSnapshot:
    step_index: int = 0
    consecutive_empty: int = 0
    last_feedback: Optional[str] = None
    last_plan: Optional[str] = None
    enabled: bool = True


@dataclass(slots=True)
class ReactEvaluation:
    status: str
    feedback: str


class ReactCoordinator:
    """Lightweight planner/evaluator loop that nudges the primary agent."""

    def __init__(
        self,
        planner: Agent,
        evaluator: Agent,
        state: Any,
        *,
        max_steps: int,
        ui_helper: Optional[Any] = None,
    ) -> None:
        self._planner = planner
        self._evaluator = evaluator
        self._state = state
        self._max_steps = max_steps
        self._snapshot = ReactLoopSnapshot()
        self._ui = ui_helper

    async def bootstrap(self, query: str) -> None:
        """Prime the loop with an initial plan message."""
        await self._generate_plan(query)

    async def observe_step(self, query: str, observation: str, *, can_continue: bool) -> None:
        """Record an observation, provide feedback, and queue the next plan if needed."""

        if not self._snapshot.enabled:
            return

        stripped_observation = observation.strip()
        forced_evaluation = False

        if not stripped_observation:
            self._snapshot.consecutive_empty += 1
            if self._snapshot.consecutive_empty <= 2:
                return
            forced_evaluation = True
        else:
            self._snapshot.consecutive_empty = 0

        evaluation = await self._evaluate_step(query, observation, forced=forced_evaluation)
        if evaluation is None:
            return

        step_label = max(self._snapshot.step_index, 1)
        feedback_text = (evaluation.feedback or "").strip()
        if feedback_text:
            feedback_lines = [f"REACT FEEDBACK STEP {step_label}: {feedback_text}"]
        else:
            feedback_lines = [f"REACT FEEDBACK STEP {step_label}: (no feedback)"]
        if evaluation.status == "done":
            feedback_lines.append(
                "Evaluator believes the task is satisfied. Provide a final answer if appropriate."
            )

        create_user_message("\n".join(feedback_lines), self._state.sm)
        self._snapshot.last_feedback = feedback_text or evaluation.feedback
        await self._log_thought(" | ".join(feedback_lines))

        if evaluation.status == "done":
            self._snapshot.enabled = False
            return

        if can_continue:
            await self._generate_plan(query)

    async def _generate_plan(self, query: str) -> None:
        if not self._snapshot.enabled:
            return

        next_step = self._snapshot.step_index + 1
        if next_step > self._max_steps:
            self._snapshot.enabled = False
            return

        prompt = self._build_plan_prompt(query)
        response_text = await self._call_agent(self._planner, prompt)
        if not response_text:
            return

        plan_text, rationale = self._parse_plan_response(response_text)
        if not plan_text:
            return

        message_lines = [f"REACT PLAN STEP {next_step}: {plan_text.strip()}"]
        if rationale:
            message_lines.append(f"Reasoning: {rationale.strip()}")

        create_user_message("\n".join(message_lines), self._state.sm)
        self._snapshot.step_index = next_step
        self._snapshot.last_plan = plan_text
        await self._log_thought(" | ".join(message_lines))

    async def _evaluate_step(
        self,
        query: str,
        observation: str,
        *,
        forced: bool = False,
    ) -> Optional[ReactEvaluation]:
        prompt = self._build_evaluator_prompt(query, observation, forced=forced)
        response_text = await self._call_agent(self._evaluator, prompt)
        if not response_text:
            return None

        status, feedback = self._parse_evaluation_response(response_text)
        return ReactEvaluation(status=status, feedback=feedback)

    async def _call_agent(self, agent: Agent, prompt: str) -> Optional[str]:
        try:
            if hasattr(agent, "run") and callable(getattr(agent, "run")):
                result = await agent.run(prompt)
            elif hasattr(agent, "arun") and callable(getattr(agent, "arun")):
                result = await agent.arun(prompt)
            elif hasattr(agent, "apredict") and callable(getattr(agent, "apredict")):
                result = await agent.apredict(prompt)
            else:
                return None
        except Exception:  # pragma: no cover - defensive against provider failures
            logger.debug("ReAct helper agent invocation failed", exc_info=True)
            self._snapshot.enabled = False
            return None

        return self._extract_output_text(result)

    @staticmethod
    def _extract_output_text(result: Any) -> Optional[str]:
        if result is None:
            return None
        if isinstance(result, str):
            return result
        if hasattr(result, "output"):
            output = getattr(result, "output")
            return output if isinstance(output, str) else str(output)
        if isinstance(result, dict):
            if "output" in result:
                output = result["output"]
                return output if isinstance(output, str) else str(output)
            return json.dumps(result)
        return str(result)

    def _build_plan_prompt(self, query: str) -> str:
        feedback = self._snapshot.last_feedback or "None yet"
        return (
            "User query: "
            f"{query}\n"
            "Latest evaluator feedback: "
            f"{feedback}\n"
            "Propose the next tiny actionable step only.\n"
            "Reply as JSON with keys 'plan' and 'rationale'."
        )

    def _build_evaluator_prompt(self, query: str, observation: str, *, forced: bool) -> str:
        plan = self._snapshot.last_plan or "No explicit plan recorded"
        observation_text = observation.strip()
        if not observation_text:
            observation_text = "Agent has not produced observable output for several iterations"
            if forced and self._snapshot.consecutive_empty > 0:
                observation_text += (
                    f" (streak: {self._snapshot.consecutive_empty}). "
                    "Provide guidance to help the agent progress."
                )

        return (
            "User query: "
            f"{query}\n"
            "Planned action: "
            f"{plan}\n"
            "Primary agent observation/output: "
            f"{observation_text}\n"
            "Decide if the goal is satisfied.\n"
            "Reply as JSON with keys 'status' ('continue' or 'done') and 'feedback'."
        )

    @staticmethod
    def _parse_plan_response(text: str) -> tuple[str, str]:
        clean_text = text.strip()
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            return clean_text, ""

        if isinstance(data, dict):
            plan = str(data.get("plan", "")).strip()
            rationale = str(data.get("rationale", "")).strip()
            return plan or clean_text, rationale
        return clean_text, ""

    @staticmethod
    def _parse_evaluation_response(text: str) -> tuple[str, str]:
        clean_text = text.strip()
        status = "continue"
        feedback = clean_text

        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            return status, feedback

        if isinstance(data, dict):
            parsed_status = str(data.get("status", status)).lower()
            if parsed_status in {"continue", "done", "complete"}:
                status = "done" if parsed_status in {"done", "complete"} else "continue"
            feedback = str(data.get("feedback", feedback)).strip() or feedback

        return status, feedback

    async def _log_thought(self, message: str) -> None:
        if not getattr(self._state, "show_thoughts", False) or self._ui is None:
            return
        try:
            await self._ui.muted(f"[react] {message}")
        except Exception:  # pragma: no cover - UI logging is best-effort
            logger.debug("ReAct thought logging failed", exc_info=True)
