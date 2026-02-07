"""Tests for tunacode.configuration.feature_flags."""

import os
from unittest.mock import patch

from tunacode.configuration.feature_flags import (
    _DEFAULTS,
    _ENV_PREFIX,
    get_all_flags,
    is_enabled,
)


class TestIsEnabled:
    def test_returns_false_for_unknown_flag(self):
        assert is_enabled("nonexistent_flag") is False

    def test_env_var_true_values(self):
        flag = "test_flag"
        env_key = f"{_ENV_PREFIX}{flag.upper()}"
        for val in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
            with patch.dict(os.environ, {env_key: val}):
                assert is_enabled(flag) is True, f"Expected True for env={val}"

    def test_env_var_false_values(self):
        flag = "test_flag"
        env_key = f"{_ENV_PREFIX}{flag.upper()}"
        for val in ("0", "false", "False", "no", "off", "anything_else"):
            with patch.dict(os.environ, {env_key: val}):
                assert is_enabled(flag) is False, f"Expected False for env={val}"

    def test_env_var_takes_precedence_over_defaults(self):
        flag = "override_test"
        env_key = f"{_ENV_PREFIX}{flag.upper()}"

        with patch.dict(_DEFAULTS, {flag: False}), patch.dict(os.environ, {env_key: "1"}):
            assert is_enabled(flag) is True

        with patch.dict(_DEFAULTS, {flag: True}), patch.dict(os.environ, {env_key: "0"}):
            assert is_enabled(flag) is False

    def test_uses_default_when_env_not_set(self):
        flag = "default_test"
        env_key = f"{_ENV_PREFIX}{flag.upper()}"

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(env_key, None)
            with patch.dict(_DEFAULTS, {flag: True}):
                assert is_enabled(flag) is True

            with patch.dict(_DEFAULTS, {flag: False}):
                assert is_enabled(flag) is False


class TestGetAllFlags:
    def test_returns_dict_of_bools(self):
        result = get_all_flags()
        assert isinstance(result, dict)
        for v in result.values():
            assert isinstance(v, bool)

    def test_reflects_defaults(self):
        with patch.dict(_DEFAULTS, {"flag_a": True, "flag_b": False}, clear=True):
            result = get_all_flags()
            assert result == {"flag_a": True, "flag_b": False}

    def test_reflects_env_overrides(self):
        with patch.dict(_DEFAULTS, {"flag_c": False}, clear=True):
            env_key = f"{_ENV_PREFIX}FLAG_C"
            with patch.dict(os.environ, {env_key: "1"}):
                result = get_all_flags()
                assert result["flag_c"] is True
