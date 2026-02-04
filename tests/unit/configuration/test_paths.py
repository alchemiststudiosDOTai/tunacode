from unittest.mock import MagicMock, patch

from tunacode.configuration.paths import check_for_updates
from tunacode.constants import APP_VERSION


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
