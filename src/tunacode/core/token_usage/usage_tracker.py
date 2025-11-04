from typing import Any

from tunacode.core.state import StateManager
from tunacode.core.token_usage.api_response_parser import ApiResponseParser
from tunacode.core.token_usage.cost_calculator import CostCalculator
from tunacode.types import UsageTrackerProtocol
from tunacode.ui import console as ui  # Import the ui console directly


class UsageTracker(UsageTrackerProtocol):
    """
    Handles parsing, calculating, storing, and displaying token usage and cost.
    """

    def __init__(
        self,
        parser: ApiResponseParser,
        calculator: CostCalculator,
        state_manager: StateManager,
    ):
        self.parser = parser
        self.calculator = calculator
        self.state_manager = state_manager

    async def track_and_display(self, response_obj: Any):
        """
        Main method to process a model response for usage tracking.
        """
        try:
            # 1. Parse the response to get token data
            requested_model = self.state_manager.session.current_model
            parsed_data = self.parser.parse(model=requested_model, response_obj=response_obj)

            if not parsed_data:
                return

            # 2. Calculate the cost
            cost = self._calculate_cost(parsed_data)

            # 3. Update the session state (always done to track totals for session cost display)
            self._update_state(parsed_data, cost)

            # 4. Display detailed per-call summary only if debugging enabled
            if self.state_manager.session.show_thoughts:
                await self._display_summary()

        except Exception as e:
            if self.state_manager.session.show_thoughts:
                import traceback

                await ui.error(f"Error during cost calculation: {e}")
                # Log the full traceback for debugging
                await ui.debug(f"Traceback: {traceback.format_exc()}")

    def _calculate_cost(self, parsed_data: dict) -> float:
        """Calculates the cost for the given parsed data."""
        requested_model = self.state_manager.session.current_model
        api_model_name = parsed_data.get("model_name", requested_model)
        final_model_name = api_model_name

        # Logic to preserve the provider prefix
        if ":" in requested_model:
            provider_prefix = requested_model.split(":", 1)[0]
            if not api_model_name.startswith(provider_prefix + ":"):
                final_model_name = f"{provider_prefix}:{api_model_name}"

        cost = self.calculator.calculate_cost(
            prompt_tokens=parsed_data.get("prompt_tokens", 0),
            completion_tokens=parsed_data.get("completion_tokens", 0),
            model_name=final_model_name,
        )

        # Ensure cost is never None
        return cost if cost is not None else 0.0

    def _update_state(self, parsed_data: dict, cost: float):
        """Updates the last_call and session_total usage in the state."""
        session = self.state_manager.session
        prompt_tokens = parsed_data.get("prompt_tokens", 0)
        completion_tokens = parsed_data.get("completion_tokens", 0)

        # Initialize usage dicts if they're None
        if session.last_call_usage is None:
            session.last_call_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        if session.session_total_usage is None:
            session.session_total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}

        # Normalize values defensively to avoid None propagation
        try:
            prompt_tokens = int(prompt_tokens or 0)
        except (TypeError, ValueError):
            prompt_tokens = 0
        try:
            completion_tokens = int(completion_tokens or 0)
        except (TypeError, ValueError):
            completion_tokens = 0
        try:
            cost = float(cost or 0.0)
        except (TypeError, ValueError):
            cost = 0.0

        # Update last call usage
        session.last_call_usage["prompt_tokens"] = prompt_tokens
        session.last_call_usage["completion_tokens"] = completion_tokens
        session.last_call_usage["cost"] = cost

        # Accumulate session totals with normalization
        session.session_total_usage["prompt_tokens"] = (
            int(session.session_total_usage.get("prompt_tokens", 0) or 0) + prompt_tokens
        )
        session.session_total_usage["completion_tokens"] = (
            int(session.session_total_usage.get("completion_tokens", 0) or 0) + completion_tokens
        )
        session.session_total_usage["cost"] = (
            float(session.session_total_usage.get("cost", 0.0) or 0.0) + cost
        )

    async def _display_summary(self):
        """Formats and prints the usage summary to the console."""
        session = self.state_manager.session

        # Initialize usage dicts if they're None
        if session.last_call_usage is None:
            session.last_call_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        if session.session_total_usage is None:
            session.session_total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}

        prompt = session.last_call_usage["prompt_tokens"]
        completion = session.last_call_usage["completion_tokens"]
        last_cost = session.last_call_usage["cost"]
        session_cost = session.session_total_usage["cost"]

        # Ensure tokens are not None before arithmetic operations
        prompt_safe = prompt if prompt is not None else 0
        completion_safe = completion if completion is not None else 0
        last_cost_safe = last_cost if last_cost is not None else 0.0
        session_cost_safe = session_cost if session_cost is not None else 0.0

        total_tokens = prompt_safe + completion_safe
        usage_summary = (
            f"[ Tokens: {total_tokens:,} "
            f"(P: {prompt_safe:,}, C: {completion_safe:,}) | "
            f"Cost: ${last_cost_safe:.4f} | "
            f"Session Total: ${session_cost_safe:.4f} ]"
        )
        await ui.muted(usage_summary)
