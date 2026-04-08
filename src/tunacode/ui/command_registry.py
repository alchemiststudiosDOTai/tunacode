"""Lazy slash-command registry for TunaCode REPL."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tunacode.ui.commands.base import Command


@dataclass(frozen=True, slots=True)
class CommandSpec:
    module_name: str
    class_name: str
    description: str


_COMMAND_SPECS: dict[str, CommandSpec] = {
    "help": CommandSpec("help", "HelpCommand", "Show available commands"),
    "cancel": CommandSpec("cancel", "CancelCommand", "Cancel current request"),
    "clear": CommandSpec("clear", "ClearCommand", "Clear chat history display"),
    "compact": CommandSpec(
        "compact",
        "CompactCommand",
        "Summarize old context and keep recent messages",
    ),
    "debug": CommandSpec("debug", "DebugCommand", "Toggle debug mode and agent-timing NDJSON"),
    "exit": CommandSpec("exit", "ExitCommand", "Exit TunaCode"),
    "model": CommandSpec("model", "ModelCommand", "Change or show current model"),
    "resume": CommandSpec("resume", "ResumeCommand", "Resume a previous session"),
    "skills": CommandSpec("skills", "SkillsCommand", "Browse, search, and load session skills"),
    "theme": CommandSpec("theme", "ThemeCommand", "Change the active theme"),
    "thoughts": CommandSpec(
        "thoughts",
        "ThoughtsCommand",
        "Toggle streaming of agent thought text",
    ),
    "update": CommandSpec("update", "UpdateCommand", "Update tunacode to latest version"),
}

COMMAND_DESCRIPTIONS: dict[str, str] = {
    name: spec.description for name, spec in _COMMAND_SPECS.items()
}


class LazyCommandRegistry(Mapping[str, "Command"]):
    """Instantiate command handlers only when they are first used."""

    def __init__(self, specs: Mapping[str, CommandSpec]) -> None:
        self._specs = dict(specs)
        self._instances: dict[str, Command] = {}

    def __getitem__(self, name: str) -> Command:
        if name not in self._specs:
            raise KeyError(name)

        command = self._instances.get(name)
        if command is not None:
            return command

        spec = self._specs[name]
        module = import_module(f"tunacode.ui.commands.{spec.module_name}")
        command_class = getattr(module, spec.class_name)
        command = command_class()
        self._instances[name] = command
        return command

    def __iter__(self) -> Iterator[str]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)


COMMANDS = LazyCommandRegistry(_COMMAND_SPECS)
