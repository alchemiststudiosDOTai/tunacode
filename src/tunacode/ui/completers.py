"""Completers for file references and commands."""

import os
from typing import TYPE_CHECKING, Iterable, List, Optional

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    merge_completers,
)
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from ..cli.commands import CommandRegistry
    from ..utils.models_registry import ModelInfo, ModelsRegistry


class CommandCompleter(Completer):
    """Completer for slash commands."""

    def __init__(self, command_registry: Optional["CommandRegistry"] = None):
        self.command_registry = command_registry

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for slash commands."""
        # Get the text before cursor
        text = document.text_before_cursor

        # Check if we're at the start of a line or after whitespace
        if text and not text.isspace() and text[-1] != "\n":
            # Only complete commands at the start of input or after a newline
            last_newline = text.rfind("\n")
            line_start = text[last_newline + 1 :] if last_newline >= 0 else text

            # Skip if not at the beginning of a line
            if line_start and not line_start.startswith("/"):
                return

        # Get the word before cursor
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        # Only complete if word starts with /
        if not word_before_cursor.startswith("/"):
            return

        # Get command names from registry
        if self.command_registry:
            command_names = self.command_registry.get_command_names()
        else:
            # Fallback list of commands
            command_names = ["/help", "/clear", "/dump", "/yolo", "/branch", "/compact", "/model"]

        # Get the partial command (without /)
        partial = word_before_cursor[1:].lower()

        # Yield completions for matching commands
        for cmd in command_names:
            if cmd.startswith("/") and cmd[1:].lower().startswith(partial):
                yield Completion(
                    text=cmd,
                    start_position=-len(word_before_cursor),
                    display=cmd,
                    display_meta="command",
                )


class FileReferenceCompleter(Completer):
    """Completer for @file references that provides file path suggestions."""

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for @file references."""
        # Get the word before cursor
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        # Check if we're in an @file reference
        if not word_before_cursor.startswith("@"):
            return

        # Get the path part after @
        path_part = word_before_cursor[1:]  # Remove @

        # Determine directory and prefix
        if "/" in path_part:
            # Path includes directory
            dir_path = os.path.dirname(path_part)
            prefix = os.path.basename(path_part)
        else:
            # Just filename, search in current directory
            dir_path = "."
            prefix = path_part

        # Get matching files
        try:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                for item in sorted(os.listdir(dir_path)):
                    if item.startswith(prefix):
                        full_path = os.path.join(dir_path, item) if dir_path != "." else item

                        # Skip hidden files unless explicitly requested
                        if item.startswith(".") and not prefix.startswith("."):
                            continue

                        # Add / for directories
                        if os.path.isdir(full_path):
                            display = item + "/"
                            completion = full_path + "/"
                        else:
                            display = item
                            completion = full_path

                        # Calculate how much to replace
                        start_position = -len(path_part)

                        yield Completion(
                            text=completion,
                            start_position=start_position,
                            display=display,
                            display_meta="dir" if os.path.isdir(full_path) else "file",
                        )
        except (OSError, PermissionError):
            # Silently ignore inaccessible directories
            pass


class ModelCompleter(Completer):
    """Completer for model names in /model command."""

    def __init__(self, registry: Optional["ModelsRegistry"] = None):
        """Initialize the model completer."""
        self.registry = registry
        self._models_cache: Optional[List[ModelInfo]] = None
        self._registry_loaded = False

    async def _ensure_registry_loaded(self):
        """Ensure the models registry is loaded."""
        if self.registry and not self._registry_loaded:
            try:
                # Try to load models (this will be fast if already loaded)
                await self.registry.load()
                self._registry_loaded = True
                self._models_cache = list(self.registry.models.values()) if self.registry.models else []
            except Exception:
                # If loading fails, use empty cache
                self._models_cache = []
                self._registry_loaded = True

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for model names."""
        if not self.registry:
            return

        text = document.text_before_cursor

        # Check if we're in a /model command context
        lines = text.split('\n')
        current_line = lines[-1].strip()

        # Must start with /model
        if not current_line.startswith('/model'):
            return

        # Try to load registry synchronously if not loaded
        # Note: This is a compromise - ideally we'd use async completion
        if not self._registry_loaded:
            try:
                # Quick attempt to load cached data only
                if self.registry._is_cache_valid() and self.registry._load_from_cache():
                    self._registry_loaded = True
                    self._models_cache = list(self.registry.models.values())
                elif not self._models_cache:
                    # Use fallback models for immediate completion
                    self.registry._load_fallback_models()
                    self._registry_loaded = True
                    self._models_cache = list(self.registry.models.values())
            except Exception:
                return  # Skip completion if we can't load models

        # Get the part after /model
        parts = current_line.split()
        if len(parts) < 2:
            # Just "/model" - suggest popular searches and top models
            popular_searches = ["claude", "gpt", "gemini", "openai", "anthropic"]
            for search_term in popular_searches:
                yield Completion(
                    text=search_term,
                    display=f"{search_term} (search)",
                    display_meta="search term"
                )

            # Also show top 3 most popular models if we have them
            if self._models_cache:
                popular_models = []
                # Look for common popular models
                for model in self._models_cache:
                    if any(pop in model.id.lower() for pop in ['gpt-4o', 'claude-3', 'gemini-2']):
                        popular_models.append(model)
                        if len(popular_models) >= 3:
                            break

                for model in popular_models:
                    display = f"{model.full_id} - {model.name}"
                    if model.cost.input is not None:
                        display += f" (${model.cost.input}/{model.cost.output})"

                    yield Completion(
                        text=model.full_id,
                        display=display,
                        display_meta=f"{model.provider} model"
                    )
            return

        # Get the current word being typed
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        if not word_before_cursor or not self._models_cache:
            return

        query = word_before_cursor.lower()

        # Use the new grouped approach to find base models with variants
        base_models = self.registry.find_base_models(query)

        if not base_models:
            return

        results = []
        shown_base_models = 0

        # Sort base models by popularity/relevance
        sorted_base_models = sorted(base_models.items(), key=lambda x: (
            # Popular models first
            -1 if any(pop in x[0] for pop in ['gpt-4o', 'gpt-4', 'claude-3', 'gemini-2', 'o3', 'o1']) else 0,
            # Then by name
            x[0]
        ))

        for base_model_name, variants in sorted_base_models:
            if shown_base_models >= 5:  # Limit to top 5 base models
                break

            shown_variants = 0
            for i, model in enumerate(variants):
                if shown_variants >= 3:  # Show max 3 variants per base model
                    break

                # Calculate start position for replacement
                start_pos = -len(word_before_cursor)

                # Build display text with enhanced info
                cost_str = ""
                if model.cost.input is not None:
                    if model.cost.input == 0:
                        cost_str = " (FREE)"
                    else:
                        cost_str = f" (${model.cost.input}/{model.cost.output})"

                # Format provider info
                provider_display = self._get_provider_display_name(model.provider)

                # Primary variant gets the bullet, others get indentation
                if i == 0:
                    # First variant - primary option with bullet
                    display = f"● {model.full_id} - {model.name}{cost_str}"
                    if model.cost.input == 0:
                        display += " ⭐"  # Star for free models
                else:
                    # Additional variants - indented
                    display = f"   {model.full_id} - {model.name}{cost_str}"
                    if model.cost.input == 0:
                        display += " ⭐"

                meta_info = f"{provider_display}"
                if len(variants) > 1:
                    meta_info += f" ({len(variants)} sources)"

                results.append(Completion(
                    text=model.full_id,
                    start_position=start_pos,
                    display=display,
                    display_meta=meta_info
                ))

                shown_variants += 1

            shown_base_models += 1

        # Limit total results for readability
        for completion in results[:20]:
            yield completion

    def _get_provider_display_name(self, provider: str) -> str:
        """Get a user-friendly provider display name."""
        provider_names = {
            'openai': 'OpenAI Direct',
            'anthropic': 'Anthropic Direct',
            'google': 'Google Direct',
            'google-gla': 'Google Labs',
            'openrouter': 'OpenRouter',
            'github-models': 'GitHub Models (FREE)',
            'azure': 'Azure OpenAI',
            'fastrouter': 'FastRouter',
            'requesty': 'Requesty',
            'cloudflare-workers-ai': 'Cloudflare',
            'amazon-bedrock': 'AWS Bedrock',
            'chutes': 'Chutes AI',
            'deepinfra': 'DeepInfra',
            'venice': 'Venice AI'
        }
        return provider_names.get(provider, provider.title())


def create_completer(
    command_registry: Optional["CommandRegistry"] = None,
    models_registry: Optional["ModelsRegistry"] = None
) -> Completer:
    """Create a merged completer for commands, file references, and models."""
    completers = [
        CommandCompleter(command_registry),
        FileReferenceCompleter(),
    ]

    if models_registry:
        completers.append(ModelCompleter(models_registry))

    return merge_completers(completers)
