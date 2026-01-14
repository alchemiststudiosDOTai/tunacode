"""
Module: tunacode.configuration.settings

Application settings management for the TunaCode CLI.
Handles configuration paths, model registries, and application metadata.
"""

from pathlib import Path

from tunacode.constants import APP_NAME, APP_VERSION, CONFIG_FILE_NAME, ToolName
from tunacode.types import ConfigFile, ConfigPath


class PathConfig:
    def __init__(self):
        self.config_dir: ConfigPath = Path.home() / ".config"
        self.config_file: ConfigFile = self.config_dir / CONFIG_FILE_NAME


class ApplicationSettings:
    def __init__(self):
        self.version = APP_VERSION
        self.name = APP_NAME
        self.guide_file = f"{self.name.upper()}.md"
        self.paths = PathConfig()
        self.internal_tools: list[ToolName] = [
            ToolName.BASH,
            ToolName.GLOB,
            ToolName.GREP,
            ToolName.LIST_DIR,
            ToolName.READ_FILE,
            ToolName.RESEARCH_CODEBASE,
            ToolName.SUBMIT,
            ToolName.UPDATE_FILE,
            ToolName.WRITE_FILE,
        ]
