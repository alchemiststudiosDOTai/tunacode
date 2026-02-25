"""Fast query-to-agent handoff routing."""

from __future__ import annotations

from dataclasses import dataclass

COMMAND_PREFIX: str = "/"
ROUTING_HEADER: str = "[ROUTING HANDOFF]"
USER_QUERY_LABEL: str = "User query:"

DEBUG_KEYWORDS: tuple[str, ...] = (
    "bug",
    "debug",
    "error",
    "failing",
    "failure",
    "fix",
    "traceback",
)
BUILD_KEYWORDS: tuple[str, ...] = (
    "add",
    "build",
    "create",
    "implement",
    "refactor",
    "write",
)
EXPLAIN_KEYWORDS: tuple[str, ...] = (
    "explain",
    "how",
    "summarize",
    "what",
    "why",
)

DEBUG_HANDOFF: str = "Prioritize fast diagnosis, isolate root cause, then propose a minimal fix."
BUILD_HANDOFF: str = "Prioritize a small typed implementation with minimal surface area changes."
EXPLAIN_HANDOFF: str = (
    "Prioritize clear explanation first, then provide concrete implementation guidance."
)
GENERAL_HANDOFF: str = (
    "Prioritize the smallest correct next step and surface assumptions explicitly."
)


@dataclass(frozen=True, slots=True)
class QueryHandoff:
    """Routing decision passed to the main agent."""

    original_query: str
    route: str
    handoff_instruction: str
    message_for_main_agent: str


def _contains_any_keyword(query_text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in query_text for keyword in keywords)


def _route_query(query: str) -> tuple[str, str]:
    normalized_query = query.strip()
    if not normalized_query:
        return "general", GENERAL_HANDOFF

    if normalized_query.startswith(COMMAND_PREFIX):
        return "command", "Pass through exactly without rewriting."

    lowered_query = normalized_query.lower()

    if _contains_any_keyword(lowered_query, DEBUG_KEYWORDS):
        return "debug", DEBUG_HANDOFF

    if _contains_any_keyword(lowered_query, BUILD_KEYWORDS):
        return "build", BUILD_HANDOFF

    if _contains_any_keyword(lowered_query, EXPLAIN_KEYWORDS):
        return "explain", EXPLAIN_HANDOFF

    return "general", GENERAL_HANDOFF


def build_query_handoff(query: str) -> QueryHandoff:
    """Create a compact routing handoff for the main agent."""
    route, handoff_instruction = _route_query(query)
    stripped_query = query.strip()
    if route == "command":
        return QueryHandoff(
            original_query=query,
            route=route,
            handoff_instruction=handoff_instruction,
            message_for_main_agent=stripped_query,
        )

    message_for_main_agent = (
        f"{ROUTING_HEADER}\n"
        f"Route: {route}\n"
        f"Handoff: {handoff_instruction}\n"
        f"{USER_QUERY_LABEL}\n"
        f"{stripped_query}"
    )
    return QueryHandoff(
        original_query=query,
        route=route,
        handoff_instruction=handoff_instruction,
        message_for_main_agent=message_for_main_agent,
    )
