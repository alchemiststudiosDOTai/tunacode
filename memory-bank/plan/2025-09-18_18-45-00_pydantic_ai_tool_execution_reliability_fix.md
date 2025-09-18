---
title: "Pydantic-AI Tool Execution Reliability Fix – Plan"
phase: Plan
date: "2025-09-18_18-45-00"
owner: "Claude"
parent_research: "memory-bank/research/2025-09-18_16-46-19_pydantic_ai_tool_execution_reliability.md"
git_commit_at_plan: "bad6ec0"
tags: [plan, pydantic-ai, tool-execution, reliability]
---

## Goal
Implement a bulletproof tool execution system that guarantees every tool call has a corresponding response before any API request to OpenAI, eliminating the "tool_call_ids did not have response messages" error while maintaining acceptable performance.

## Scope & Assumptions

### In Scope
- Fix the core race condition between tool buffering and API retries
- Ensure API contract compliance (every tool call has response)
- Maintain backward compatibility with existing tool system
- Preserve performance optimizations where possible
- Add comprehensive testing for reliability

### Out of Scope
- Complete architectural redesign of tool system
- Removal of tool buffering (making it optional enhancement)
- Changes to Pydantic-AI core library
- Breaking changes to existing tool APIs

### Assumptions
- Current buffer flush logic has correct intent but wrong timing
- Tool buffering provides meaningful performance benefit worth preserving
- Pydantic-AI's conversation management requirements are non-negotiable
- Race condition occurs due to timing, not fundamental design flaw

## Deliverables (DoD)

1. **Proactive Tool Call Validation System**
   - Tool call state validation before all API requests
   - Automatic buffer flush when orphaned calls detected
   - Integration with Pydantic-AI's retry mechanism

2. **Enhanced Buffer Flush Coordinator**
   - Coordinated flush timing with API request lifecycle
   - Prevention of early exits without buffer flush
   - Thread-safe buffer state management


## Readiness (DoR)

### Preconditions
- Current codebase in working state (branch: react-shim-tunacode)
- Ability to run existing test suite



### M1: Architecture & Skeleton (Week 1)
- Design proactive validation system
- Create buffer flush coordinator interface
- Set up test infrastructure
- Define integration points with existing code

### M2: Core Reliability Fix (Week 2)
- Implement proactive tool call validation
- Enhance buffer flush coordination
- Integrate with Pydantic-AI request lifecycle
- Add safety mechanisms for edge cases

#

### M1: Architecture & Skeleton

**T1.1**: Design proactive validation system
- Owner: Lead Developer
- Estimate: 2 days
- Dependencies: None
- **Acceptance Tests**:
  - Design document approved
  - Interface definitions complete
  - Integration points identified
- **Files/Interfaces**: `src/tunacode/core/agents/agent_components/tool_validation.py`, design docs

**T1.2**: Create buffer flush coordinator
- Owner: Lead Developer
- Estimate: 2 days
- Dependencies: T1.1
- **Acceptance Tests**:
  - Coordinator interface defined
  - Integration points with existing buffer system
  - Thread safety guarantees documented
- **Files/Interfaces**: `src/tunacode/core/agents/agent_components/flush_coordinator.py`

*
### M2: Core Reliability Fix

**T2.1**: Implement proactive validation
- Owner: Lead Developer
- Estimate: 3 days
- Dependencies: T1.1, T1.2
- **Acceptance Tests**:
  - Validation catches orphaned tool calls
  - Automatic buffer flush triggered when needed
  - No false positives in validation
- **Files/Interfaces**: `tool_validation.py`, integration with `main.py`

**T2.2**: Enhance buffer flush coordination
- Owner: Lead Developer
- Estimate: 2 days
- Dependencies: T1.2, T2.1
- **Acceptance Tests**:
  - Buffer flush happens before API requests
  - Early exits cannot bypass buffer flush
  - Thread safety under concurrent load
- **Files/Interfaces**: `flush_coordinator.py`, updates to `buffer_flush.py`

**T2.3**: Integrate with request lifecycle
- Owner: Lead Developer
- Estimate: 2 days
- Dependencies: T2.1, T2.2
- **Acceptance Tests**:
  - Validation runs before all API requests
  - Retry mechanism respects buffer state
  - No race conditions during retries
- **Files/Interfaces**: `main.py`, `streaming.py`, `react_pattern.py`

#

his page covers advanced features for function tools in Pydantic AI. For basic tool usage, see the Function Tools documentation.

Tool Output
Tools can return anything that Pydantic can serialize to JSON, as well as audio, video, image or document content depending on the types of multi-modal input the model supports:

function_tool_output.py

from datetime import datetime

from pydantic import BaseModel

from pydantic_ai import Agent, DocumentUrl, ImageUrl
from pydantic_ai.models.openai import OpenAIResponsesModel


class User(BaseModel):
    name: str
    age: int


agent = Agent(model=OpenAIResponsesModel('gpt-4o'))


@agent.tool_plain
def get_current_time() -> datetime:
    return datetime.now()


@agent.tool_plain
def get_user() -> User:
    return User(name='John', age=30)


@agent.tool_plain
def get_company_logo() -> ImageUrl:
    return ImageUrl(url='https://iili.io/3Hs4FMg.png')


@agent.tool_plain
def get_document() -> DocumentUrl:
    return DocumentUrl(url='https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf')


result = agent.run_sync('What time is it?')
print(result.output)
#> The current time is 10:45 PM on April 17, 2025.

result = agent.run_sync('What is the user name?')
print(result.output)
#> The user's name is John.

result = agent.run_sync('What is the company name in the logo?')
print(result.output)
#> The company name in the logo is "Pydantic."

result = agent.run_sync('What is the main content of the document?')
print(result.output)
#> The document contains just the text "Dummy PDF file."
(This example is complete, it can be run "as is")

Some models (e.g. Gemini) natively support semi-structured return values, while some expect text (OpenAI) but seem to be just as good at extracting meaning from the data. If a Python object is returned and the model expects a string, the value will be serialized to JSON.

Advanced Tool Returns
For scenarios where you need more control over both the tool's return value and the content sent to the model, you can use ToolReturn. This is particularly useful when you want to:

Provide rich multi-modal content (images, documents, etc.) to the model as context
Separate the programmatic return value from the model's context
Include additional metadata that shouldn't be sent to the LLM
Here's an example of a computer automation tool that captures screenshots and provides visual feedback:

advanced_tool_return.py

import time
from pydantic_ai import Agent
from pydantic_ai.messages import ToolReturn, BinaryContent

agent = Agent('openai:gpt-4o')

@agent.tool_plain
def click_and_capture(x: int, y: int) -> ToolReturn:
    """Click at coordinates and show before/after screenshots."""
    # Take screenshot before action
    before_screenshot = capture_screen()

    # Perform click operation
    perform_click(x, y)
    time.sleep(0.5)  # Wait for UI to update

    # Take screenshot after action
    after_screenshot = capture_screen()

    return ToolReturn(
        return_value=f"Successfully clicked at ({x}, {y})",
        content=[
            f"Clicked at coordinates ({x}, {y}). Here's the comparison:",
            "Before:",
            BinaryContent(data=before_screenshot, media_type="image/png"),
            "After:",
            BinaryContent(data=after_screenshot, media_type="image/png"),
            "Please analyze the changes and suggest next steps."
        ],
        metadata={
            "coordinates": {"x": x, "y": y},
            "action_type": "click_and_capture",
            "timestamp": time.time()
        }
    )

# The model receives the rich visual content for analysis
# while your application can access the structured return_value and metadata
result = agent.run_sync("Click on the submit button and tell me what happened")
print(result.output)
# The model can analyze the screenshots and provide detailed feedback
return_value: The actual return value used in the tool response. This is what gets serialized and sent back to the model as the tool's result.
content: A sequence of content (text, images, documents, etc.) that provides additional context to the model. This appears as a separate user message.
metadata: Optional metadata that your application can access but is not sent to the LLM. Useful for logging, debugging, or additional processing. Some other AI frameworks call this feature "artifacts".
This separation allows you to provide rich context to the model while maintaining clean, structured return values for your application logic.

Custom Tool Schema
If you have a function that lacks appropriate documentation (i.e. poorly named, no type information, poor docstring, use of *args or **kwargs and suchlike) then you can still turn it into a tool that can be effectively used by the agent with the Tool.from_schema function. With this you provide the name, description, JSON schema, and whether the function takes a RunContext for the function directly:


from pydantic_ai import Agent, Tool
from pydantic_ai.models.test import TestModel


def foobar(**kwargs) -> str:
    return kwargs['a'] + kwargs['b']

tool = Tool.from_schema(
    function=foobar,
    name='sum',
    description='Sum two numbers.',
    json_schema={
        'additionalProperties': False,
        'properties': {
            'a': {'description': 'the first number', 'type': 'integer'},
            'b': {'description': 'the second number', 'type': 'integer'},
        },
        'required': ['a', 'b'],
        'type': 'object',
    },
    takes_ctx=False,
)

test_model = TestModel()
agent = Agent(test_model, tools=[tool])

result = agent.run_sync('testing...')
print(result.output)
#> {"sum":0}
Please note that validation of the tool arguments will not be performed, and this will pass all arguments as keyword arguments.

Dynamic Tools
Tools can optionally be defined with another function: prepare, which is called at each step of a run to customize the definition of the tool passed to the model, or omit the tool completely from that step.

A prepare method can be registered via the prepare kwarg to any of the tool registration mechanisms:

@agent.tool decorator
@agent.tool_plain decorator
Tool dataclass
The prepare method, should be of type ToolPrepareFunc, a function which takes RunContext and a pre-built ToolDefinition, and should either return that ToolDefinition with or without modifying it, return a new ToolDefinition, or return None to indicate this tools should not be registered for that step.

Here's a simple prepare method that only includes the tool if the value of the dependency is 42.

As with the previous example, we use TestModel to demonstrate the behavior without calling a real model.

tool_only_if_42.py

from pydantic_ai import Agent, RunContext, ToolDefinition

agent = Agent('test')


async def only_if_42(
    ctx: RunContext[int], tool_def: ToolDefinition
) -> ToolDefinition | None:
    if ctx.deps == 42:
        return tool_def


@agent.tool(prepare=only_if_42)
def hitchhiker(ctx: RunContext[int], answer: str) -> str:
    return f'{ctx.deps} {answer}'


result = agent.run_sync('testing...', deps=41)
print(result.output)
#> success (no tool calls)
result = agent.run_sync('testing...', deps=42)
print(result.output)
#> {"hitchhiker":"42 a"}
(This example is complete, it can be run "as is")

Here's a more complex example where we change the description of the name parameter to based on the value of deps

For the sake of variation, we create this tool using the Tool dataclass.

customize_name.py

from __future__ import annotations

from typing import Literal

from pydantic_ai import Agent, RunContext, Tool, ToolDefinition
from pydantic_ai.models.test import TestModel


def greet(name: str) -> str:
    return f'hello {name}'


async def prepare_greet(
    ctx: RunContext[Literal['human', 'machine']], tool_def: ToolDefinition
) -> ToolDefinition | None:
    d = f'Name of the {ctx.deps} to greet.'
    tool_def.parameters_json_schema['properties']['name']['description'] = d
    return tool_def


greet_tool = Tool(greet, prepare=prepare_greet)
test_model = TestModel()
agent = Agent(test_model, tools=[greet_tool], deps_type=Literal['human', 'machine'])

result = agent.run_sync('testing...', deps='human')
print(result.output)
#> {"greet":"hello a"}
print(test_model.last_model_request_parameters.function_tools)
"""
[
    ToolDefinition(
        name='greet',
        parameters_json_schema={
            'additionalProperties': False,
            'properties': {
                'name': {'type': 'string', 'description': 'Name of the human to greet.'}
            },
            'required': ['name'],
            'type': 'object',
        },
    )
]
"""
(This example is complete, it can be run "as is")

Agent-wide Dynamic Tools
In addition to per-tool prepare methods, you can also define an agent-wide prepare_tools function. This function is called at each step of a run and allows you to filter or modify the list of all tool definitions available to the agent for that step. This is especially useful if you want to enable or disable multiple tools at once, or apply global logic based on the current context.

The prepare_tools function should be of type ToolsPrepareFunc, which takes the RunContext and a list of ToolDefinition, and returns a new list of tool definitions (or None to disable all tools for that step).

Note

The list of tool definitions passed to prepare_tools includes both regular function tools and tools from any toolsets registered on the agent, but not output tools.

To modify output tools, you can set a prepare_output_tools function instead.

Here's an example that makes all tools strict if the model is an OpenAI model:

agent_prepare_tools_customize.py

from dataclasses import replace

from pydantic_ai import Agent, RunContext, ToolDefinition
from pydantic_ai.models.test import TestModel


async def turn_on_strict_if_openai(
    ctx: RunContext[None], tool_defs: list[ToolDefinition]
) -> list[ToolDefinition] | None:
    if ctx.model.system == 'openai':
        return [replace(tool_def, strict=True) for tool_def in tool_defs]
    return tool_defs


test_model = TestModel()
agent = Agent(test_model, prepare_tools=turn_on_strict_if_openai)


@agent.tool_plain
def echo(message: str) -> str:
    return message


agent.run_sync('testing...')
assert test_model.last_model_request_parameters.function_tools[0].strict is None

# Set the system attribute of the test_model to 'openai'
test_model._system = 'openai'

agent.run_sync('testing with openai...')
assert test_model.last_model_request_parameters.function_tools[0].strict
(This example is complete, it can be run "as is")

Here's another example that conditionally filters out the tools by name if the dependency (ctx.deps) is True:

agent_prepare_tools_filter_out.py

from pydantic_ai import Agent, RunContext, Tool, ToolDefinition


def launch_potato(target: str) -> str:
    return f'Potato launched at {target}!'


async def filter_out_tools_by_name(
    ctx: RunContext[bool], tool_defs: list[ToolDefinition]
) -> list[ToolDefinition] | None:
    if ctx.deps:
        return [tool_def for tool_def in tool_defs if tool_def.name != 'launch_potato']
    return tool_defs


agent = Agent(
    'test',
    tools=[Tool(launch_potato)],
    prepare_tools=filter_out_tools_by_name,
    deps_type=bool,
)

result = agent.run_sync('testing...', deps=False)
print(result.output)
#> {"launch_potato":"Potato launched at a!"}
result = agent.run_sync('testing...', deps=True)
print(result.output)
#> success (no tool calls)
(This example is complete, it can be run "as is")

You can use prepare_tools to:

Dynamically enable or disable tools based on the current model, dependencies, or other context
Modify tool definitions globally (e.g., set all tools to strict mode, change descriptions, etc.)
If both per-tool prepare and agent-wide prepare_tools are used, the per-tool prepare is applied first to each tool, and then prepare_tools is called with the resulting list of tool definitions.

Tool Execution and Retries
When a tool is executed, its arguments (provided by the LLM) are first validated against the function's signature using Pydantic. If validation fails (e.g., due to incorrect types or missing required arguments), a ValidationError is raised, and the framework automatically generates a RetryPromptPart containing the validation details. This prompt is sent back to the LLM, informing it of the error and allowing it to correct the parameters and retry the tool call.

Beyond automatic validation errors, the tool's own internal logic can also explicitly request a retry by raising the ModelRetry exception. This is useful for situations where the parameters were technically valid, but an issue occurred during execution (like a transient network error, or the tool determining the initial attempt needs modification).


from pydantic_ai import ModelRetry


def my_flaky_tool(query: str) -> str:
    if query == 'bad':
        # Tell the LLM the query was bad and it should try again
        raise ModelRetry("The query 'bad' is not allowed. Please provide a different query.")
    # ... process query ...
    return 'Success!'
Raising ModelRetry also generates a RetryPromptPart containing the exception message, which is sent back to the LLM to guide its next attempt. Both ValidationError and ModelRetry respect the retries setting configured on the Tool or Agent.

Parallel tool calls & concurrency
When a model returns multiple tool calls in one response, Pydantic AI schedules them concurrently using asyncio.create_task. If a tool requires sequential/serial execution, you can pass the sequential flag when registering the tool, or wrap the agent run in the with agent.sequential_tool_calls() context manager.

Async functions are run on the event loop, while sync functions are offloaded to threads. To get the best performance, always use an async function unless you're doing blocking I/O (and there's no way to use a non-blocking library instead) or CPU-bound work (like numpy or scikit-learn operations), so that simple functions are not offloaded to threads unnecessarily.

Limiting tool executions

You can cap tool executions within a run using UsageLimits(tool_calls_limit=...). The counter increments only after a successful tool invocation. Output tools (used for structured output) are
