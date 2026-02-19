from __future__ import annotations

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG

MINIMAX_API_KEY_ENV = "MINIMAX_API_KEY"
MINIMAX_CN_API_KEY_ENV = "MINIMAX_CN_API_KEY"


def test_default_user_config_exposes_minimax_api_key_slots() -> None:
    env = DEFAULT_USER_CONFIG["env"]

    assert MINIMAX_API_KEY_ENV in env
    assert MINIMAX_CN_API_KEY_ENV in env
    assert env[MINIMAX_API_KEY_ENV] == ""
    assert env[MINIMAX_CN_API_KEY_ENV] == ""
