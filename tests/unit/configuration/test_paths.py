from subprocess import CalledProcessError, TimeoutExpired
from unittest.mock import MagicMock, patch

from tunacode.configuration.paths import check_for_updates
from tunacode.constants import APP_NAME, APP_VERSION, PULLING_VERSIONS_TIMEOUT_SECONDS


class TestCheckForUpdatesTool:
    """Verify checking for updates via semantic versioning."""

    def test_no_update(self) -> None:
        """Check for updates when there is no need for updates."""
        has_update, latest_version = check_for_updates()
        assert not has_update
        assert latest_version == APP_VERSION

    def test_update_available(self) -> None:
        """Check for updates when they are needed."""
        mock_output = "Available versions: 2.0.0, 1.0.0"
        mock_result = MagicMock()
        mock_result.stdout = mock_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            has_update, latest_version = check_for_updates()
            assert has_update
            assert latest_version == "2.0.0"

    def test_check_for_updates_timeout(self) -> None:
        """Check if the timeout is correct to check for updates."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutExpired(
                cmd=["pip", "index", "versions", "tunacode-cli"],
                timeout=PULLING_VERSIONS_TIMEOUT_SECONDS,
            )

            has_update, latest_version = check_for_updates()
            assert not has_update
            assert latest_version == APP_VERSION

    def test_check_for_updates_with_malformed_versions(self) -> None:
        """Checking for distorted version strings."""
        mock_output = f"Available versions: {APP_NAME}:2.0.0, 1.0.0[stable]"
        mock_result = MagicMock()
        mock_result.stdout = mock_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            has_update, latest_version = check_for_updates()
            assert not has_update
            assert latest_version == APP_VERSION

    def test_check_for_updates_with_pip_index_not_available(self) -> None:
        """Check for updates if the pip index is unavailable"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = CalledProcessError(
                cmd=["pip", "index", "versions", "tunacode-cli"],
                returncode=1,
            )

            has_update, latest_version = check_for_updates()
            assert not has_update
            assert latest_version == APP_VERSION
