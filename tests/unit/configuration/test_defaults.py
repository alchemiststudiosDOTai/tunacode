"""Tests for tunacode.configuration.defaults."""

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.constants import ENV_OPENAI_BASE_URL, GUIDE_FILE_NAME


class TestDefaultUserConfig:
    def test_has_default_model(self):
        assert "default_model" in DEFAULT_USER_CONFIG
        assert isinstance(DEFAULT_USER_CONFIG["default_model"], str)
        assert ":" in DEFAULT_USER_CONFIG["default_model"]

    def test_has_env_section(self):
        env = DEFAULT_USER_CONFIG["env"]
        assert isinstance(env, dict)
        assert "ANTHROPIC_API_KEY" in env
        assert "OPENAI_API_KEY" in env
        assert "OPENROUTER_API_KEY" in env
        assert "GEMINI_API_KEY" in env
        assert ENV_OPENAI_BASE_URL in env

    def test_all_env_values_are_empty_strings(self):
        for key, value in DEFAULT_USER_CONFIG["env"].items():
            assert value == "", f"Expected empty string for env[{key}], got {value!r}"

    def test_has_settings(self):
        settings = DEFAULT_USER_CONFIG["settings"]
        assert isinstance(settings, dict)

    def test_settings_has_expected_keys(self):
        settings = DEFAULT_USER_CONFIG["settings"]
        assert "max_retries" in settings
        assert "max_iterations" in settings
        assert "request_delay" in settings
        assert "global_request_timeout" in settings
        assert "guide_file" in settings
        assert "theme" in settings
        assert "ripgrep" in settings
        assert "lsp" in settings

    def test_settings_types(self):
        settings = DEFAULT_USER_CONFIG["settings"]
        assert isinstance(settings["max_retries"], int)
        assert isinstance(settings["max_iterations"], int)
        assert isinstance(settings["request_delay"], float)
        assert isinstance(settings["global_request_timeout"], float)
        assert isinstance(settings["guide_file"], str)
        assert isinstance(settings["theme"], str)

    def test_guide_file_matches_constant(self):
        assert DEFAULT_USER_CONFIG["settings"]["guide_file"] == GUIDE_FILE_NAME

    def test_ripgrep_settings(self):
        rg = DEFAULT_USER_CONFIG["settings"]["ripgrep"]
        assert isinstance(rg, dict)
        assert "timeout" in rg
        assert "max_results" in rg
        assert "enable_metrics" in rg
        assert rg["enable_metrics"] is False

    def test_lsp_settings(self):
        lsp = DEFAULT_USER_CONFIG["settings"]["lsp"]
        assert isinstance(lsp, dict)
        assert lsp["enabled"] is True
        assert isinstance(lsp["timeout"], float)

    def test_positive_numeric_defaults(self):
        settings = DEFAULT_USER_CONFIG["settings"]
        assert settings["max_retries"] > 0
        assert settings["max_iterations"] > 0
        assert settings["global_request_timeout"] > 0
