from __future__ import annotations

from tunacode.configuration.models import (
    get_provider_alchemy_api,
    get_provider_env_var,
    load_models_registry,
)

MINIMAX_ALCHEMY_API = "minimax-completions"
MINIMAX_API_KEY_ENV = "MINIMAX_API_KEY"
MINIMAX_CN_API_KEY_ENV = "MINIMAX_CN_API_KEY"


def test_minimax_provider_env_contracts_are_normalized() -> None:
    load_models_registry()

    assert get_provider_env_var("minimax") == MINIMAX_API_KEY_ENV
    assert get_provider_env_var("minimax-coding-plan") == MINIMAX_API_KEY_ENV
    assert get_provider_env_var("minimax-cn") == MINIMAX_CN_API_KEY_ENV
    assert get_provider_env_var("minimax-cn-coding-plan") == MINIMAX_CN_API_KEY_ENV


def test_minimax_provider_alchemy_api_contracts_are_normalized() -> None:
    load_models_registry()

    assert get_provider_alchemy_api("minimax") == MINIMAX_ALCHEMY_API
    assert get_provider_alchemy_api("minimax-coding-plan") == MINIMAX_ALCHEMY_API
    assert get_provider_alchemy_api("minimax-cn") == MINIMAX_ALCHEMY_API
    assert get_provider_alchemy_api("minimax-cn-coding-plan") == MINIMAX_ALCHEMY_API
