
# TDD Specification: In-Memory Token & Cost Tracking

## 1. Overview & Philosophy

This document outlines the Test-Driven Development (TDD) plan for implementing an accurate, in-memory token and cost tracking feature.

Our philosophy, inspired by Sandi Metz, is to **build the simplest thing that could possibly work**. We will avoid premature complexity (like a database) and focus on delivering the core feature—accurate usage visibility—with the lowest cost of change.

**The plan is to:**
1.  Parse real usage data from API responses.
2.  Store usage data in the existing in-memory `SessionState`.
3.  Calculate costs using the **existing `ModelRegistry`** in `src/tunacode/configuration/models.py`.
4.  Provide immediate, real-time feedback to the user after each call.
5.  Add a `/usage` command to show session totals.

---

## 2. Phased Implementation Plan (TDD Cycle)

Follow these phases in order. For each phase, **write the failing test first**, then write the code to make it pass.

### Phase 1: Pricing and Cost Calculation

This is the most isolated piece of the puzzle. We'll start by building the logic that calculates cost from token counts, leveraging the project's existing model configuration.

**Step 1.1: Write the Failing Test**
*   **Action:** Create a new test file: `tests/test_cost_calculator.py`.
*   **Test Case:** Write a test that initializes our new `CostCalculator` with the existing `ModelRegistry`. Assert that it correctly calculates the cost for a known model and gracefully handles unknown models.

```python
# tests/test_cost_calculator.py
from tunacode.configuration.models import ModelRegistry
from tunacode.pricing.cost_calculator import CostCalculator

def test_calculate_cost_using_existing_registry():
    # ARRANGE
    # Use the actual ModelRegistry from the codebase
    registry = ModelRegistry()
    calculator = CostCalculator(registry)
    
    prompt_tokens = 1000
    completion_tokens = 2000
    model_name = "openai:gpt-4o" # This model has input=2.50, output=10.00 per million

    # ACT
    # Cost = (1000/1M * $2.50) + (2000/1M * $10.00) = $0.0025 + $0.02 = $0.0225
    cost = calculator.calculate_cost(model_name, prompt_tokens, completion_tokens)

    # ASSERT
    assert cost == 0.0225

def test_calculate_cost_for_unknown_model_returns_zero():
    # ARRANGE
    registry = ModelRegistry()
    calculator = CostCalculator(registry)

    # ACT
    cost = calculator.calculate_cost("unknown:model-x", 1000, 1000)

    # ASSERT
    assert cost == 0.0
```

**Step 1.2: Write the Implementation**
*   **Action:** Create the file `src/tunacode/pricing/cost_calculator.py`.
*   **Implementation:** The `CostCalculator` class will be initialized with an instance of `ModelRegistry`. Its `calculate_cost` method will:
    1.  Call `registry.get_model(model_name)` to get the `ModelConfig`.
    2.  If a model and its pricing are found, use the `pricing.input` and `pricing.output` values for the calculation.
    3.  The formula will be: `cost = (prompt_tokens / 1_000_000 * pricing.input) + (completion_tokens / 1_000_000 * pricing.output)`.
    4.  If the model or its pricing is not found, it will return `0.0`.

---

### Phase 2: Parsing the API Response

This component is our "seam" with the external world. We need to isolate the logic for parsing different provider responses.

**Step 2.1: Write the Failing Tests**
*   **Action:** Create a new test file: `tests/test_api_response_parser.py`.
*   **Test Cases:**
    1.  Create mock API response objects (as dictionaries) for OpenAI, Anthropic, and OpenRouter.
    2.  Write a test for each provider, passing the mock response to the parser.
    3.  Assert that the parser returns a standardized dictionary: `{'prompt_tokens': X, 'completion_tokens': Y}`.
    4.  Write a test for an unknown provider, asserting it returns `{'prompt_tokens': 0, 'completion_tokens': 0}`.

**Step 2.2: Write the Implementation**
*   **Action:** Create `src/tunacode/llm/api_response_parser.py`.
*   **Implementation:** Create an `ApiResponseParser` class. Use the **Adapter Pattern**: a main `parse(provider, response)` method will look at the `provider` string and call a specific private method like `_parse_openai(response)`. This makes it easy to add new providers later.

---

### Phase 3: State Management & Integration

Now we connect the pieces and store the data in memory.

**Step 3.1: Write the Failing Integration Test**
*   **Action:** Create a new test file: `tests/integration/test_usage_tracking_integration.py`.
*   **Test Case:** This test will be more involved.
    1.  Create a mock `StateManager` instance.
    2.  Mock the `ApiResponseParser` and `CostCalculator` to return predictable values.
    3.  Simulate a full agent processing cycle (you can call the relevant function in `main.py` directly).
    4.  Assert that after the cycle, the `state_manager.session` object contains the correct, updated values in `last_call_usage` and `session_total_usage`.

**Step 3.2: Write the Implementation**
1.  **Modify `SessionState`:**
    *   **File:** `src/tunacode/core/state.py`
    *   **Action:** Add the new fields to the `SessionState` class.
    ```python
    class SessionState:
        # ... existing fields
        last_call_usage: dict = {"prompt": 0, "completion": 0, "cost": 0.0}
        session_total_usage: dict = {"prompt": 0, "completion": 0, "cost": 0.0}
    ```
2.  **Integrate into the Agent Loop:**
    *   **File:** `src/tunacode/core/agents/main.py`
    *   **Action:** Find the main agent processing loop (likely in `process_request`). After an API call completes, use your new `ApiResponseParser` and `CostCalculator` to get the usage data. Then, write the logic to update the `last_call_usage` and accumulate the totals in `session_total_usage` on the `state_manager`.

---

## 3. UI Implementation

With the backend logic in place, we can build the user-facing parts.

**Step 4.1: Real-time Feedback**
*   **File:** `src/tunacode/core/agents/main.py`
*   **Action:** After you update the state in the agent loop, use the `ui.console.print()` function to display the formatted usage summary for the last call. This provides immediate feedback.
*   **Format:** `[ Tokens: 1,536 (P: 512, C: 1,024) | Cost: $0.0028 | Session Total: $0.0451 ]`

**Step 4.2: The `/usage` Command**
*   **Test First:** Add a test to `tests/test_characterization_commands_system.py` that simulates running `/usage` and captures the output to verify it's correct.
*   **Implementation:**
    *   **File:** `src/tunacode/cli/commands.py`
    *   **Action:** Create a new `UsageCommand(SimpleCommand)` class.
    *   Its `execute` method will access the `context.state_manager.session.session_total_usage` dictionary, format the data into a user-friendly string, and print it to the console.

---

## 4. Helpful Pointers for a New Contributor

*   **Running Tests:** Use the `Makefile` for convenience. From the project root, run `make test`. This will run all tests using `pytest`.
*   **Existing Commands:** Look at other commands in `src/tunacode/cli/commands.py` (like `YoloCommand` or `ModelCommand`) as a template for creating your new `UsageCommand`. They follow a simple, consistent pattern.
*   **UI Output:** To print styled output to the console, import the `ui` object (e.g., `from tunacode.ui import ui`) and use its methods like `ui.console.print()` or `ui.info()`.
*   **State Access:** In a command's `execute` method, you can get the `StateManager` from the `context` object that is passed in: `context.state_manager`.
*   **Key Files for this Feature:**
    *   `src/tunacode/core/state.py` (Modifying `SessionState`)
    *   `src/tunacode/core/agents/main.py` (Integrating the logic into the agent loop)
    *   `src/tunacode/cli/commands.py` (Adding the new `/usage` command)
    *   `src/tunacode/configuration/models.json` (New file for pricing)
    *   `src/tunacode/pricing/cost_calculator.py` (New file for cost logic)
    *   `src/tunacode/llm/api_response_parser.py` (New file for parsing logic)

---

## 5. Final Acceptance Criteria

*   [ ] All new tests are written and pass.
*   [ ] The `models.json` file is created and populated.
*   [ ] The `CostCalculator` correctly calculates costs.
*   [ ] The `ApiResponseParser` correctly parses responses from major providers.
*   [ ] `SessionState` is updated correctly after each API call.
*   [ ] A real-time summary is printed after each command.
*   [ ] The `/usage` command correctly displays the total for the current session.
*   [ ] The old token estimation logic in `token_counter.py` is deprecated or removed.
