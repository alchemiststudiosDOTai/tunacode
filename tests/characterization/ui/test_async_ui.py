"""
Characterization tests for TunaCode UI async UI updates.
Covers: async output functions and async-safe UI flows.
"""

from unittest.mock import patch

import pytest

import tunacode.ui.output as output_mod


@pytest.mark.asyncio
async def test_async_print_calls_console_print():
    with patch("tunacode.ui.output.console.print") as mock_print:
        with patch("tunacode.ui.output.run_in_terminal") as mock_run:

            async def fake_run(fn):
                fn()

            mock_run.side_effect = fake_run
            await output_mod.print("Hello", style="bold")
            mock_print.assert_called_once_with("Hello", style="bold")


@pytest.mark.asyncio
async def test_async_info_formats_and_prints(caplog):
    # info() now goes through ui_logger, let's test that
    await output_mod.info("Test info")
    assert "Test info" in caplog.text
