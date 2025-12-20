"""Generate synthetic training data from scenarios.

This module converts scenarios into ShareGPT-format training conversations,
with support for:
- Single-turn and multi-turn conversations
- Tool call sequences
- Error recovery patterns
- Randomized query variations
"""

import json
import random

from tunacode.training.scenarios import ALL_SCENARIOS, Scenario
from tunacode.training.schema import (
    FunctionCall,
    ShareGPTConversation,
    TrainingDataset,
)
from tunacode.training.tool_extractor import get_tools_for_training

# System prompt for training data
DEFAULT_SYSTEM_PROMPT = """You are a helpful coding assistant with access to tools.
When the user asks you to perform tasks, use the available tools to help them.
Always explain what you're doing and provide clear, helpful responses."""


def scenario_to_conversation(
    scenario: Scenario,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    include_tools: bool = True,
) -> ShareGPTConversation:
    """Convert a scenario to a ShareGPT conversation.

    Args:
        scenario: The scenario to convert
        system_prompt: System prompt to include
        include_tools: Whether to include tool definitions

    Returns:
        A ShareGPTConversation object
    """
    conv = ShareGPTConversation(
        conversations=[],
        system=system_prompt,
        tools=get_tools_for_training() if include_tools else None,
    )

    # Add user query (random variation)
    conv.add_human_message(scenario.get_random_query())

    # Add tool calls and observations
    for i, tool_call in enumerate(scenario.tool_calls):
        # Create function call
        fc = FunctionCall(name=tool_call.name, arguments=tool_call.arguments)
        conv.add_function_call(fc)

        # Add tool response as observation
        if i < len(scenario.tool_responses):
            conv.add_observation(scenario.tool_responses[i])

    # Add model response
    conv.add_gpt_message(scenario.model_response_template)

    return conv


def generate_dataset(
    count: int = 100,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    include_tools: bool = True,
    shuffle: bool = True,
    variations_per_scenario: int = 3,
) -> TrainingDataset:
    """Generate a dataset of training conversations.

    Args:
        count: Target number of conversations to generate
        system_prompt: System prompt for all conversations
        include_tools: Whether to include tool definitions
        shuffle: Whether to shuffle the final dataset
        variations_per_scenario: Number of query variations per scenario

    Returns:
        A TrainingDataset object
    """
    conversations: list[ShareGPTConversation] = []

    # Calculate how many times to use each scenario
    scenarios_needed = count // len(ALL_SCENARIOS) + 1

    for _ in range(scenarios_needed):
        for scenario in ALL_SCENARIOS:
            # Generate multiple variations for each scenario
            for _ in range(variations_per_scenario):
                if len(conversations) >= count:
                    break
                conv = scenario_to_conversation(
                    scenario,
                    system_prompt=system_prompt,
                    include_tools=include_tools,
                )
                conversations.append(conv)
            if len(conversations) >= count:
                break
        if len(conversations) >= count:
            break

    # Trim to exact count
    conversations = conversations[:count]

    if shuffle:
        random.shuffle(conversations)

    return TrainingDataset(
        conversations=conversations,
        metadata={
            "count": len(conversations),
            "scenarios_used": len(ALL_SCENARIOS),
            "variations_per_scenario": variations_per_scenario,
        },
    )


def generate_with_augmentation(
    base_scenarios: list[Scenario] | None = None,
    count: int = 100,
    augment_queries: bool = True,
    augment_paths: bool = True,
) -> TrainingDataset:
    """Generate dataset with augmented variations.

    Augmentation includes:
    - Query rephrasing (if augment_queries=True)
    - Path variations (e.g., README.md -> CONTRIBUTING.md)

    Args:
        base_scenarios: Scenarios to use (defaults to ALL_SCENARIOS)
        count: Number of conversations to generate
        augment_queries: Whether to add query variations
        augment_paths: Whether to vary file paths

    Returns:
        A TrainingDataset object
    """
    scenarios = base_scenarios or ALL_SCENARIOS
    conversations: list[ShareGPTConversation] = []

    # Path variations for augmentation
    path_variations = {
        "README.md": ["CONTRIBUTING.md", "CHANGELOG.md", "docs/README.md"],
        "main.py": ["app.py", "server.py", "cli.py"],
        "config.py": ["settings.py", "constants.py"],
        "src/": ["lib/", "app/", "core/"],
    }

    for _ in range(count):
        scenario = random.choice(scenarios)

        # Create base conversation
        conv = scenario_to_conversation(scenario)

        # Optionally augment paths in tool calls
        if augment_paths:
            for msg in conv.conversations:
                if msg.from_.value == "function_call":
                    try:
                        call_data = json.loads(msg.value)
                        args = call_data.get("arguments", {})

                        # Augment filepath if present
                        if "filepath" in args:
                            original = args["filepath"]
                            if original in path_variations:
                                args["filepath"] = random.choice(path_variations[original])
                                msg.value = json.dumps(call_data)
                    except json.JSONDecodeError:
                        pass

        conversations.append(conv)

    random.shuffle(conversations)

    return TrainingDataset(
        conversations=conversations,
        metadata={
            "count": len(conversations),
            "augmented": True,
            "augment_queries": augment_queries,
            "augment_paths": augment_paths,
        },
    )


def generate_multi_turn_conversation(
    tool_sequence: list[str],
    max_turns: int = 4,
) -> ShareGPTConversation:
    """Generate a multi-turn conversation with specified tools.

    Args:
        tool_sequence: List of tool names to use in sequence
        max_turns: Maximum number of tool calls

    Returns:
        A multi-turn ShareGPTConversation
    """
    from tunacode.training.scenarios import get_scenarios_by_tool

    conv = ShareGPTConversation(
        conversations=[],
        system=DEFAULT_SYSTEM_PROMPT,
        tools=get_tools_for_training(),
    )

    # Initial user query (generic exploration)
    queries = [
        "Help me understand and fix a bug in this project",
        "I need to add a new feature, let's explore the codebase first",
        "Can you help me refactor some code?",
        "Let's investigate an issue in the codebase",
    ]
    conv.add_human_message(random.choice(queries))

    # Build conversation using tool sequence
    for i, tool_name in enumerate(tool_sequence[:max_turns]):
        scenarios = get_scenarios_by_tool(tool_name)
        if not scenarios:
            continue

        scenario = random.choice(scenarios)

        # Use first tool call from scenario
        if scenario.tool_calls:
            tc = scenario.tool_calls[0]
            fc = FunctionCall(name=tc.name, arguments=tc.arguments)
            conv.add_function_call(fc)

            # Add observation
            if scenario.tool_responses:
                conv.add_observation(scenario.tool_responses[0])

    # Final model response
    conv.add_gpt_message(
        "Based on my exploration, I've gathered the information needed to help you. "
        "Would you like me to proceed with the next steps?"
    )

    return conv


def save_dataset(dataset: TrainingDataset, output_path: str) -> None:
    """Save dataset to a JSONL file.

    Args:
        dataset: The dataset to save
        output_path: Path to the output file
    """
    dataset.save_jsonl(output_path)
