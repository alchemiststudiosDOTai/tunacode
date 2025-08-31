"""Unit tests for feature flags."""

import os

import pytest

from tunacode.tools.feature_flags import ToolFeatureFlags


class TestToolFeatureFlags:
    """Test cases for tool feature flags."""

    def setup_method(self):
        """Clean up environment variables before each test."""
        env_vars = [
            "TUNACODE_USE_UNIFIED_REGISTRY",
            "TUNACODE_USE_DYNAMIC_PROMPTS",
            "TUNACODE_DISABLE_XML",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_use_unified_registry_default_false(self):
        """Test that unified registry defaults to False."""
        assert ToolFeatureFlags.use_unified_registry() is False

    def test_use_unified_registry_enabled(self):
        """Test enabling unified registry."""
        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "true"
        assert ToolFeatureFlags.use_unified_registry() is True

        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "TRUE"
        assert ToolFeatureFlags.use_unified_registry() is True

    def test_use_unified_registry_disabled(self):
        """Test disabling unified registry."""
        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "false"
        assert ToolFeatureFlags.use_unified_registry() is False

        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "anything_else"
        assert ToolFeatureFlags.use_unified_registry() is False

    def test_use_dynamic_prompts_default_false(self):
        """Test that dynamic prompts defaults to False."""
        assert ToolFeatureFlags.use_dynamic_prompts() is False

    def test_use_dynamic_prompts_enabled(self):
        """Test enabling dynamic prompts."""
        os.environ["TUNACODE_USE_DYNAMIC_PROMPTS"] = "true"
        assert ToolFeatureFlags.use_dynamic_prompts() is True

    def test_disable_xml_default_false(self):
        """Test that XML disable defaults to False."""
        assert ToolFeatureFlags.disable_xml_loading() is False

    def test_disable_xml_enabled(self):
        """Test disabling XML loading."""
        os.environ["TUNACODE_DISABLE_XML"] = "true"
        assert ToolFeatureFlags.disable_xml_loading() is True

    def test_get_migration_status(self):
        """Test getting migration status."""
        # Default state
        status = ToolFeatureFlags.get_migration_status()
        expected = {"unified_registry": False, "dynamic_prompts": False, "xml_disabled": False}
        assert status == expected

        # Enable some flags
        os.environ["TUNACODE_USE_UNIFIED_REGISTRY"] = "true"
        os.environ["TUNACODE_DISABLE_XML"] = "true"

        status = ToolFeatureFlags.get_migration_status()
        expected = {"unified_registry": True, "dynamic_prompts": False, "xml_disabled": True}
        assert status == expected

    def test_enable_full_migration(self):
        """Test enabling full migration."""
        ToolFeatureFlags.enable_full_migration()

        assert ToolFeatureFlags.use_unified_registry() is True
        assert ToolFeatureFlags.use_dynamic_prompts() is True
        assert ToolFeatureFlags.disable_xml_loading() is True

    def test_disable_all_migration(self):
        """Test disabling all migration features."""
        # First enable everything
        ToolFeatureFlags.enable_full_migration()
        assert ToolFeatureFlags.use_unified_registry() is True

        # Then disable all
        ToolFeatureFlags.disable_all_migration()

        assert ToolFeatureFlags.use_unified_registry() is False
        assert ToolFeatureFlags.use_dynamic_prompts() is False
        assert ToolFeatureFlags.disable_xml_loading() is False


if __name__ == "__main__":
    pytest.main([__file__])
