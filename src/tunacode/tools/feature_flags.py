"""Feature flags for tool system migration.

This module provides feature flags to control the rollout of the unified tool system
while maintaining backward compatibility during the transition.
"""

import os
from typing import Any, Dict


class ToolFeatureFlags:
    """Feature flags for controlling tool system behavior."""

    @staticmethod
    def use_unified_registry() -> bool:
        """Whether to use the unified tool registry for schema generation.

        Returns:
            True if unified registry should be used, False for XML fallback
        """
        return os.getenv("TUNACODE_USE_UNIFIED_REGISTRY", "false").lower() == "true"

    @staticmethod
    def use_dynamic_prompts() -> bool:
        """Whether to use dynamically generated prompts from registry.

        Returns:
            True if dynamic prompts should be used, False for static prompts
        """
        return os.getenv("TUNACODE_USE_DYNAMIC_PROMPTS", "false").lower() == "true"

    @staticmethod
    def disable_xml_loading() -> bool:
        """Whether to disable XML prompt/schema loading entirely.

        Returns:
            True if XML loading should be disabled, False to keep XML fallback
        """
        return os.getenv("TUNACODE_DISABLE_XML", "false").lower() == "true"

    @staticmethod
    def get_migration_status() -> Dict[str, Any]:
        """Get current migration status for debugging.

        Returns:
            Dictionary with current feature flag states
        """
        return {
            "unified_registry": ToolFeatureFlags.use_unified_registry(),
            "dynamic_prompts": ToolFeatureFlags.use_dynamic_prompts(),
            "xml_disabled": ToolFeatureFlags.disable_xml_loading(),
        }

    @staticmethod
    def enable_full_migration():
        """Enable all unified tool system features.

        This is a convenience method for testing the full migration.
        """
        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "true"
        os.environ["TUNACODE_USE_DYNAMIC_PROMPTS"] = "true"
        os.environ["TUNACODE_DISABLE_XML"] = "true"

    @staticmethod
    def disable_all_migration():
        """Disable all unified tool system features (full fallback).

        This reverts to the original XML-based system.
        """
        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "false"
        os.environ["TUNACODE_USE_DYNAMIC_PROMPTS"] = "false"
        os.environ["TUNACODE_DISABLE_XML"] = "false"
