from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from tunacode.utils.models_registry import ModelsRegistry


def _data_with_cost(cost_input: Any = 1.0, cost_output: Any = 1.0) -> Dict[str, Any]:
    return {
        "prov": {
            "name": "Prov",
            "models": {
                "m": {
                    "name": "M",
                    "cost": {"input": cost_input, "output": cost_output},
                    "limit": {"context": 1000, "output": 256},
                }
            },
        }
    }


def _data_with_limits(context: Any = 1000, output: Any = 256) -> Dict[str, Any]:
    return {
        "prov": {
            "name": "Prov",
            "models": {
                "m": {
                    "name": "M",
                    "cost": {"input": 1.0, "output": 1.0},
                    "limit": {"context": context, "output": output},
                }
            },
        }
    }


def test_negative_costs_raise_validation_error() -> None:
    registry = ModelsRegistry()
    bad = _data_with_cost(cost_input=-0.1, cost_output=1.0)
    with pytest.raises(ValidationError):
        registry._parse_data(bad)


def test_negative_limits_raise_validation_error() -> None:
    registry = ModelsRegistry()
    bad = _data_with_limits(context=-1, output=-1)
    with pytest.raises(ValidationError):
        registry._parse_data(bad)


def test_type_coercion_for_numeric_fields() -> None:
    registry = ModelsRegistry()
    data = _data_with_cost(cost_input="1.5", cost_output="2.5")
    # limits as strings should coerce to ints
    data["prov"]["models"]["m"]["limit"] = {"context": "32000", "output": "2048"}

    registry._parse_data(data)

    mid = "prov:m"
    assert mid in registry.models
    model = registry.models[mid]
    assert model.cost.input == 1.5
    assert model.cost.output == 2.5
    assert model.limits.context == 32000
    assert model.limits.output == 2048


def test_zero_limits_treated_as_unbounded() -> None:
    registry = ModelsRegistry()
    data = _data_with_limits(context=0, output=0)

    registry._parse_data(data)

    mid = "prov:m"
    assert mid in registry.models
    model = registry.models[mid]
    assert model.limits.context is None
    assert model.limits.output is None
