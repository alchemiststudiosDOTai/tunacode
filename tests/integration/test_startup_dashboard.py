"""
Tests for startup integration of configuration dashboard.
"""

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from tunacode.cli.main import app
from tunacode.ui.config_dashboard import show_config_dashboard


class TestStartupIntegration:
    """Test suite for startup integration of configuration dashboard."""

    def test_show_config_flag_exists(self):
        """Test that --show-config flag is properly defined."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "--show-config" in result.stdout
        assert "Show configuration dashboard and exit" in result.stdout

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    def test_show_config_flag_execution(self, mock_show_dashboard, mock_banner):
        """Test execution of --show-config flag."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--show-config"])

        assert result.exit_code == 0
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_called_once()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.ui.version")
    def test_version_flag_priority(self, mock_version, mock_show_dashboard, mock_banner):
        """Test that --version flag takes priority over --show-config."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--version", "--show-config"])

        assert result.exit_code == 0
        mock_version.assert_called_once()
        mock_banner.assert_not_called()
        mock_show_dashboard.assert_not_called()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.setup")
    @patch("tunacode.cli.main.repl")
    def test_normal_execution_without_show_config(
        self, mock_repl, mock_setup, mock_show_dashboard, mock_banner
    ):
        """Test normal execution flow without --show-config flag."""
        runner = CliRunner(env={"COLUMNS": "200"})
        runner.invoke(app, [])

        # The command should exit normally (not necessarily 0 due to async complexity)
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_not_called()
        mock_setup.assert_called_once()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.setup")
    @patch("tunacode.cli.main.repl")
    def test_show_config_with_other_flags(
        self, mock_repl, mock_setup, mock_show_dashboard, mock_banner
    ):
        """Test --show-config with other configuration flags."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--show-config", "--model", "test-model"])

        assert result.exit_code == 0
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_called_once()
        mock_setup.assert_not_called()
        mock_repl.assert_not_called()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    def test_show_config_handles_exceptions(self, mock_show_dashboard, mock_banner):
        """Test that --show-config handles exceptions gracefully."""
        mock_show_dashboard.side_effect = Exception("Dashboard error")

        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--show-config"])

        # Should exit with error code when dashboard fails
        assert result.exit_code != 0
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_called_once()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    def test_show_config_import_error_handling(self, mock_show_dashboard, mock_banner):
        """Test handling of import errors when dashboard module is missing."""
        with patch("tunacode.cli.main.sys.modules", {}):
            # Simulate import error by making the import fail
            def import_error(*args, **kwargs):
                raise ImportError("No module named 'tunacode.ui.config_dashboard'")

            with patch("builtins.__import__", side_effect=import_error):
                runner = CliRunner(env={"COLUMNS": "200"})
                result = runner.invoke(app, ["--show-config"])

                # Should exit with error code when import fails
                assert result.exit_code != 0

    @patch("tunacode.ui.config_dashboard.ConfigDashboard")
    def test_show_config_dashboard_function(self, mock_dashboard_class):
        """Test the show_config_dashboard utility function."""
        mock_dashboard = Mock()
        mock_dashboard_class.return_value = mock_dashboard

        show_config_dashboard()

        mock_dashboard_class.assert_called_once_with(None)
        mock_dashboard.show.assert_called_once()

    @patch("tunacode.ui.config_dashboard.ConfigDashboard")
    def test_show_config_dashboard_with_custom_config(self, mock_dashboard_class):
        """Test show_config_dashboard with custom configuration."""
        mock_dashboard = Mock()
        mock_dashboard_class.return_value = mock_dashboard

        custom_config = {"test": "config"}
        show_config_dashboard(custom_config)

        mock_dashboard_class.assert_called_once_with(custom_config)
        mock_dashboard.show.assert_called_once()


class TestBackwardCompatibility:
    """Test suite for backward compatibility with existing CLI."""

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.setup")
    @patch("tunacode.cli.main.repl")
    def test_existing_flags_still_work(
        self, mock_repl, mock_setup, mock_show_dashboard, mock_banner
    ):
        """Test that existing CLI flags still work as expected."""
        runner = CliRunner(env={"COLUMNS": "200"})

        # Test --setup flag
        runner.invoke(app, ["--setup"])
        mock_setup.assert_called_once()
        mock_show_dashboard.assert_not_called()

        # Test --wizard flag
        runner.invoke(app, ["--wizard"])
        mock_setup.assert_called()
        mock_show_dashboard.assert_not_called()

        # Test --model flag without --show-config
        runner.invoke(app, ["--model", "test-model"])
        mock_setup.assert_called()
        mock_show_dashboard.assert_not_called()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.ui.version")
    def test_version_flag_unaffected(self, mock_version, mock_show_dashboard, mock_banner):
        """Test that --version flag is unaffected by new functionality."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        mock_version.assert_called_once()
        mock_banner.assert_not_called()
        mock_show_dashboard.assert_not_called()


class TestIntegrationScenarios:
    """Integration test scenarios for dashboard startup."""

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    def test_dashboard_display_workflow(self, mock_show_dashboard, mock_banner):
        """Test complete dashboard display workflow."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--show-config"])

        # Verify workflow: banner -> dashboard -> exit
        assert result.exit_code == 0
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_called_once()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.check_for_updates")
    def test_show_config_skips_update_check(
        self, mock_check_updates, mock_show_dashboard, mock_banner
    ):
        """Test that --show-config skips the update check process."""
        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(app, ["--show-config"])

        assert result.exit_code == 0
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_called_once()
        mock_check_updates.assert_not_called()

    @patch("tunacode.cli.main.ui.banner")
    @patch("tunacode.cli.main.show_config_dashboard")
    @patch("tunacode.cli.main.setup")
    @patch("tunacode.cli.main.repl")
    def test_normal_flow_unchanged(self, mock_repl, mock_setup, mock_show_dashboard, mock_banner):
        """Test that normal startup flow is unchanged."""
        runner = CliRunner(env={"COLUMNS": "200"})
        runner.invoke(app, [])

        # Normal flow should not trigger dashboard
        mock_banner.assert_called_once()
        mock_show_dashboard.assert_not_called()
        # Setup and REPL should be called for normal flow
        mock_setup.assert_called_once()
