# Vulture whitelist for false positives.
#
# Vulture scans this file and considers any symbol referenced here as "used".
# Keep this file dependency-free so it can run in minimal environments.

from typing import Any


# Protocol/Abstract method parameters - these define interfaces, not unused code.
# Vulture can't understand that Protocol method params ARE the interface.
def _whitelist_protocol_params(
    context: dict[str, Any],
    session_id: str,
    renderable: Any,
    response: Any,
) -> None:
    """Dummy function to whitelist Protocol method parameters."""

    _ = context
    _ = session_id
    _ = renderable
    _ = response
