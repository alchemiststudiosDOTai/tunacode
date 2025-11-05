"""
Tests for configuration dashboard UI components.
"""

from unittest.mock import Mock, patch

import pytest
from rich.panel import Panel

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.ui.config_dashboard import (
    ConfigDashboard,
    DashboardConfig,
    generate_config_report,
    show_config_dashboard,
)


class TestDashboardConfig:
    """Test suite for DashboardConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DashboardConfig()

        assert config.show_defaults is True
        assert config.show_custom is True
        assert config.show_missing is True
        assert config.show_extra is True
        assert config.show_type_mismatches is True
        assert config.max_section_items == 20
        assert config.sort_by == "section"
        assert config.filter_section is None
        assert config.filter_type is None

    def test_custom_config(self):
        """Test custom configuration values."""
        config = DashboardConfig(
            show_defaults=False, max_section_items=10, sort_by="type", filter_section="settings"
        )

        assert config.show_defaults is False
        assert config.max_section_items == 10
        assert config.sort_by == "type"
        assert config.filter_section == "settings"


class TestConfigDashboard:
    """Test suite for ConfigDashboard class."""

    def test_init_with_user_config(self):
        """Test initialization with user configuration."""
        user_config = {"default_model": "test:model"}
        dashboard = ConfigDashboard(user_config)

        assert dashboard.analysis is not None
        assert dashboard.console is not None
        assert dashboard.config == DashboardConfig()

    def test_init_without_user_config(self):
        """Test initialization without user configuration (loads from file)."""
        with patch("tunacode.utils.user_configuration.load_config") as mock_load_config:
            mock_load_config.return_value = {"default_model": "loaded:model"}

            dashboard = ConfigDashboard()

            mock_load_config.assert_called_once()
            assert dashboard.analysis is not None

    def test_init_with_no_config_available(self):
        """Test initialization when no configuration is available."""
        with patch("tunacode.utils.user_configuration.load_config") as mock_load_config:
            mock_load_config.return_value = None

            with pytest.raises(ValueError, match="No user configuration found"):
                ConfigDashboard()

    def test_load_analysis(self):
        """Test configuration analysis loading."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        # Re-load with different config
        new_config = {"settings": {"max_retries": 5}}
        dashboard.load_analysis(new_config)

        assert dashboard.analysis is not None
        assert dashboard.analysis.user_config == new_config

    def test_render_overview_with_analysis(self):
        """Test overview panel rendering with analysis data."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        panel = dashboard.render_overview()

        assert isinstance(panel, Panel)
        assert "Configuration Overview" in panel.title
        assert panel.box is not None

    def test_render_overview_without_analysis(self):
        """Test overview panel rendering without analysis data."""
        dashboard = ConfigDashboard()
        dashboard.analysis = None

        panel = dashboard.render_overview()

        assert isinstance(panel, Panel)
        assert "No configuration loaded" in panel.renderable

    def test_render_section_tree(self):
        """Test section tree rendering."""
        user_config = {"default_model": "custom:model", "settings": {"max_retries": 5}}
        dashboard = ConfigDashboard(user_config)

        panel = dashboard.render_section_tree()

        assert isinstance(panel, Panel)
        assert "Configuration Sections" in panel.title

    def test_render_differences_table(self):
        """Test differences table rendering."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        panel = dashboard.render_differences_table()

        assert isinstance(panel, Panel)
        assert "Configuration Differences" in panel.title

    def test_render_recommendations_with_issues(self):
        """Test recommendations panel rendering with configuration issues."""
        user_config = {"settings": {"max_retries": "invalid"}}  # Type mismatch
        dashboard = ConfigDashboard(user_config)

        panel = dashboard.render_recommendations()

        assert isinstance(panel, Panel)
        assert "Recommendations" in panel.title
        # Should contain recommendations about type mismatches

    def test_render_recommendations_no_issues(self):
        """Test recommendations panel rendering with no issues."""
        dashboard = ConfigDashboard(DEFAULT_USER_CONFIG.copy())

        panel = dashboard.render_recommendations()

        assert isinstance(panel, Panel)
        # Should show positive message when no issues

    def test_render_help(self):
        """Test help panel rendering."""
        dashboard = ConfigDashboard(DEFAULT_USER_CONFIG.copy())

        panel = dashboard.render_help()

        assert isinstance(panel, Panel)
        assert "Help" in panel.title
        # The renderable is now a Group, so we need to check differently
        assert hasattr(panel.renderable, "renderables")

    def test_mask_sensitive_value_none(self):
        """Test masking of None values."""
        dashboard = ConfigDashboard(DEFAULT_USER_CONFIG.copy())

        result = dashboard._mask_sensitive_value(None, "any_key")
        assert result == ""

    def test_mask_sensitive_value_api_key(self):
        """Test masking of API key values."""
        dashboard = ConfigDashboard(DEFAULT_USER_CONFIG.copy())

        result = dashboard._mask_sensitive_value("sk-test123456789", "env.OPENAI_API_KEY")
        # New format shows service and partial key
        assert "OpenAI:" in result
        assert "sk-t...6789" in result
        assert "test123456" not in result  # Middle part should be masked

    def test_mask_sensitive_value_sensitive_key(self):
        """Test masking of values with sensitive key names."""
        dashboard = ConfigDashboard(DEFAULT_USER_CONFIG.copy())

        result = dashboard._mask_sensitive_value("my-secret-password", "secret_key")
        assert "•" in result
        assert "password" not in result

    def test_mask_sensitive_value_normal(self):
        """Test masking of normal values."""
        dashboard = ConfigDashboard(DEFAULT_USER_CONFIG.copy())

        result = dashboard._mask_sensitive_value("normal_value", "normal_setting")
        assert result == "normal_value"

    def test_filter_differences_no_filters(self):
        """Test difference filtering with no filters applied."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        filtered = dashboard._filter_differences()

        assert len(filtered) > 0
        # Should include both custom and missing differences
        diff_types = {diff.difference_type for diff in filtered}
        assert "custom" in diff_types  # At least one custom difference

    def test_filter_differences_by_type(self):
        """Test difference filtering by type."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)
        dashboard.config.filter_type = "custom"

        filtered = dashboard._filter_differences()

        assert all(diff.difference_type == "custom" for diff in filtered)

    def test_filter_differences_by_section(self):
        """Test difference filtering by section."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)
        dashboard.config.filter_section = "root"

        filtered = dashboard._filter_differences()

        assert all(diff.section == "root" for diff in filtered)

    def test_filter_differences_hide_types(self):
        """Test difference filtering with hidden types."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)
        dashboard.config.show_custom = False

        filtered = dashboard._filter_differences()

        # Should hide custom differences
        assert all(diff.difference_type != "custom" for diff in filtered)

    def test_filter_differences_sort_by_section(self):
        """Test difference sorting by section."""
        user_config = {"settings": {"max_retries": 5}, "env": {"CUSTOM_VAR": "value"}}
        dashboard = ConfigDashboard(user_config)
        dashboard.config.sort_by = "section"

        filtered = dashboard._filter_differences()

        # Should be sorted by section
        sections = [diff.section for diff in filtered]
        assert sections == sorted(sections)

    def test_filter_differences_sort_by_type(self):
        """Test difference sorting by type."""
        user_config = {
            "default_model": "custom:model",
            "settings": {"max_retries": "invalid"},  # Type mismatch
        }
        dashboard = ConfigDashboard(user_config)
        dashboard.config.sort_by = "type"

        filtered = dashboard._filter_differences()

        # Should be sorted by type
        types = [diff.difference_type for diff in filtered]
        assert types == sorted(types)

    def test_render_dashboard_layout(self):
        """Test complete dashboard layout rendering."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        layout = dashboard.render_dashboard()

        assert layout is not None
        assert hasattr(layout, "split_column")
        assert hasattr(layout, "split_row")

    def test_generate_report(self):
        """Test report generation."""
        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        report = dashboard.generate_report()

        assert isinstance(report, str)
        assert "Configuration Analysis Report" in report

    def test_generate_report_no_analysis(self):
        """Test report generation without analysis data."""
        dashboard = ConfigDashboard()
        dashboard.analysis = None

        report = dashboard.generate_report()

        assert report == "No configuration analysis available"

    @patch("builtins.input")
    def test_show_dashboard(self, mock_input):
        """Test dashboard display."""
        mock_input.return_value = ""  # Simulate pressing Enter

        user_config = {"default_model": "custom:model"}
        dashboard = ConfigDashboard(user_config)

        # This should not raise an exception
        dashboard.show()

        mock_input.assert_called_once()


class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_show_config_dashboard_with_config(self):
        """Test show_config_dashboard function with config."""
        with patch("tunacode.ui.config_dashboard.ConfigDashboard") as mock_dashboard:
            mock_instance = Mock()
            mock_dashboard.return_value = mock_instance

            user_config = {"test": "config"}
            show_config_dashboard(user_config)

            mock_dashboard.assert_called_once_with(user_config)
            mock_instance.show.assert_called_once()

    def test_show_config_dashboard_without_config(self):
        """Test show_config_dashboard function without config."""
        with patch("tunacode.ui.config_dashboard.ConfigDashboard") as mock_dashboard:
            mock_instance = Mock()
            mock_dashboard.return_value = mock_instance

            show_config_dashboard()

            mock_dashboard.assert_called_once_with(None)
            mock_instance.show.assert_called_once()

    def test_generate_config_report_with_config(self):
        """Test generate_config_report function with config."""
        with patch("tunacode.ui.config_dashboard.ConfigDashboard") as mock_dashboard:
            mock_instance = Mock()
            mock_instance.generate_report.return_value = "test report"
            mock_dashboard.return_value = mock_instance

            user_config = {"test": "config"}
            result = generate_config_report(user_config)

            assert result == "test report"
            mock_dashboard.assert_called_once_with(user_config)
            mock_instance.generate_report.assert_called_once()

    def test_generate_config_report_without_config(self):
        """Test generate_config_report function without config."""
        with patch("tunacode.ui.config_dashboard.ConfigDashboard") as mock_dashboard:
            mock_instance = Mock()
            mock_instance.generate_report.return_value = "test report"
            mock_dashboard.return_value = mock_instance

            result = generate_config_report()

            assert result == "test report"
            mock_dashboard.assert_called_once_with(None)
            mock_instance.generate_report.assert_called_once()


class TestIntegration:
    """Integration tests for dashboard components."""

    def test_end_to_end_dashboard_with_custom_config(self):
        """Test complete dashboard functionality with custom configuration."""
        custom_config = {
            "default_model": "custom:test-model",
            "env": {"ANTHROPIC_API_KEY": "sk-test123", "CUSTOM_ENV": "custom-value"},
            "settings": {"max_retries": 15, "max_iterations": 50, "custom_setting": "test"},
        }

        dashboard = ConfigDashboard(custom_config)

        # Test all components
        overview = dashboard.render_overview()
        assert isinstance(overview, Panel)

        sections = dashboard.render_section_tree()
        assert isinstance(sections, Panel)

        differences = dashboard.render_differences_table()
        assert isinstance(differences, Panel)

        recommendations = dashboard.render_recommendations()
        assert isinstance(recommendations, Panel)

        layout = dashboard.render_dashboard()
        assert layout is not None

        report = dashboard.generate_report()
        assert isinstance(report, str)
        assert "default_model" in report  # Check for the key name instead
        assert "Custom keys:" in report

        # Test filtering
        filtered = dashboard._filter_differences()
        assert len(filtered) > 0

        # Test sensitive value masking with key path
        masked = dashboard._mask_sensitive_value("sk-test123456789", "env.OPENAI_API_KEY")
        assert "OpenAI:" in masked
        assert "sk-t...6789" in masked
        assert "test123456" not in masked
