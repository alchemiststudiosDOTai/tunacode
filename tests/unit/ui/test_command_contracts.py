"""Contract tests for UI slash commands."""

from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path

from tunacode.ui import commands as command_module
from tunacode.ui.commands.base import Command


def _discover_command_classes() -> dict[str, type[Command]]:
    """Discover Command subclasses defined in ui/commands modules."""
    command_dir = Path(command_module.__file__).resolve().parent

    discovered: dict[str, type[Command]] = {}

    for path in sorted(command_dir.glob("*.py")):
        if path.name in {"__init__.py", "base.py"}:
            continue

        module_name = f"{command_module.__name__}.{path.stem}"
        module = import_module(module_name)

        module_commands = [
            cls
            for _, cls in inspect.getmembers(module, inspect.isclass)
            if cls.__module__ == module.__name__ and issubclass(cls, Command) and cls is not Command
        ]
        assert len(module_commands) >= 1, f"{module_name} has no Command subclass"
        assert len(module_commands) == 1, (
            f"{module_name} should define exactly one command class, found: "
            + ", ".join(cls.__name__ for cls in module_commands)
        )

        command_class = module_commands[0]
        assert not inspect.isabstract(command_class)

        command_name = command_class.name
        assert isinstance(command_name, str)
        assert command_name
        assert command_name not in discovered
        discovered[command_name] = command_class

    return discovered


def test_all_commands_use_command_base_and_are_registered() -> None:
    discovered_commands = _discover_command_classes()

    assert set(discovered_commands.keys()) == set(command_module.COMMANDS.keys())

    for command_name, command_cls in discovered_commands.items():
        command_instance = command_module.COMMANDS[command_name]
        assert isinstance(command_instance, command_cls)
        assert isinstance(command_instance, Command)
        assert command_instance.name == command_name
        assert isinstance(command_instance.description, str)
        assert command_instance.description
        assert inspect.iscoroutinefunction(command_cls.execute)

        # Command contract includes optional usage string, defaulting to empty in base.
        assert isinstance(command_instance.usage, str)


def test_command_registry_entries_match_names() -> None:
    for command_name, command_instance in command_module.COMMANDS.items():
        assert command_instance.name == command_name
        assert command_instance.description, f"/{command_name} is missing description"
        assert inspect.iscoroutinefunction(command_instance.execute)
        assert isinstance(command_instance, Command)
