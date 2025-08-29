"""Model management commands for TunaCode CLI."""

from typing import Dict, List, Optional

from ....exceptions import ConfigurationError
from ....types import CommandArgs, CommandContext
from ....ui import console as ui
from ....ui.model_selector import select_model_interactive
from ....utils import user_configuration
from ....utils.models_registry import ModelInfo, ModelsRegistry
from ..base import CommandCategory, CommandSpec, SimpleCommand


class ModelCommand(SimpleCommand):
    """Manage model selection with models.dev integration."""

    spec = CommandSpec(
        name="model",
        aliases=["/model"],
        description="Switch model with interactive selection or search",
        category=CommandCategory.MODEL,
    )

    def __init__(self):
        """Initialize the model command."""
        super().__init__()
        self.registry = ModelsRegistry()
        self._registry_loaded = False

    async def _ensure_registry(self) -> bool:
        """Ensure the models registry is loaded."""
        if not self._registry_loaded:
            self._registry_loaded = await self.registry.load()
        return self._registry_loaded

    async def execute(self, args: CommandArgs, context: CommandContext) -> Optional[str]:
        # Handle special flags
        if args and args[0] in ["--list", "-l"]:
            return await self._list_models()

        if args and args[0] in ["--info", "-i"]:
            if len(args) < 2:
                await ui.error("Usage: /model --info <model-id>")
                return None
            return await self._show_model_info(args[1])

        # No arguments - show interactive selector
        if not args:
            return await self._interactive_select(context)

        # Single argument - could be search query or model ID
        model_query = args[0]

        # Check for flags
        if model_query in ["--search", "-s"]:
            search_query = " ".join(args[1:]) if len(args) > 1 else ""
            return await self._interactive_select(context, search_query)

        # Direct model specification
        return await self._set_model(model_query, args[1:], context)

    async def _interactive_select(
        self,
        context: CommandContext,
        initial_query: str = ""
    ) -> Optional[str]:
        """Show interactive model selector."""
        await self._ensure_registry()

        # Show current model
        current_model = context.state_manager.session.current_model
        await ui.info(f"Current model: {current_model}")

        # Check if we have models loaded
        if not self.registry.models:
            await ui.error("No models available. Try /model --list to see if models can be loaded.")
            return None

        # For now, use a simple text-based approach instead of complex UI
        # This avoids prompt_toolkit compatibility issues
        if initial_query:
            models = self.registry.search_models(initial_query)
            if not models:
                await ui.error(f"No models found matching '{initial_query}'")
                return None
        else:
            # Show popular models for quick selection
            popular_searches = ["gpt", "claude", "gemini"]
            await ui.info("Popular model searches:")
            for search in popular_searches:
                models = self.registry.search_models(search)[:3]  # Top 3
                if models:
                    await ui.info(f"\n{search.upper()} models:")
                    for model in models:
                        await ui.muted(f"  • {model.full_id} - {model.name}")

            await ui.info("\nUsage:")
            await ui.muted("  /model <search-term>  - Search for models")
            await ui.muted("  /model --list         - Show all models")
            await ui.muted("  /model --info <id>    - Show model details")
            await ui.muted("  /model <provider:id>  - Set model directly")
            return None

        # Show search results
        if len(models) == 1:
            # Auto-select single result
            model = models[0]
            context.state_manager.session.current_model = model.full_id
            await ui.success(f"Switched to model: {model.full_id} - {model.name}")
            return None

        # Show multiple results
        await ui.info(f"Found {len(models)} models:")
        for i, model in enumerate(models[:10], 1):  # Show top 10
            details = []
            if model.cost.input is not None:
                details.append(f"${model.cost.input}/{model.cost.output}")
            if model.limits.context:
                details.append(f"{model.limits.context//1000}k")
            detail_str = f" ({', '.join(details)})" if details else ""

            await ui.info(f"{i:2d}. {model.full_id} - {model.name}{detail_str}")

        if len(models) > 10:
            await ui.muted(f"... and {len(models) - 10} more")

        await ui.muted("Use '/model <provider:model-id>' to select a specific model")
        return None

    async def _set_model(
        self,
        model_name: str,
        extra_args: CommandArgs,
        context: CommandContext
    ) -> Optional[str]:
        """Set model directly or by search."""
        # Load registry for validation
        await self._ensure_registry()

        # Check if it's a direct model ID
        if ":" in model_name:
            # Validate against registry if loaded
            if self._registry_loaded:
                model_info = self.registry.get_model(model_name)
                if not model_info:
                    # Search for similar models
                    similar = self.registry.search_models(model_name.split(":")[-1])
                    if similar:
                        await ui.warning(f"Model '{model_name}' not found in registry")
                        await ui.muted("Did you mean one of these?")
                        for model in similar[:5]:
                            await ui.muted(f"  • {model.full_id} - {model.name}")
                        return None
                    else:
                        await ui.warning("Model not found in registry - setting anyway")
                else:
                    # Show model info
                    await ui.info(f"Selected: {model_info.name}")
                    if model_info.cost.input is not None:
                        await ui.muted(f"  Pricing: {model_info.cost.format_cost()}")
                    if model_info.limits.context:
                        await ui.muted(f"  Limits: {model_info.limits.format_limits()}")

            # Set the model
            context.state_manager.session.current_model = model_name

            # Check if setting as default
            if extra_args and extra_args[0] == "default":
                try:
                    user_configuration.set_default_model(model_name, context.state_manager)
                    await ui.muted("Updating default model")
                    return "restart"
                except ConfigurationError as e:
                    await ui.error(str(e))
                    return None

            await ui.success(f"Switched to model: {model_name}")
            return None

        # No colon - treat as search query
        models = self.registry.search_models(model_name)

        if not models:
            await ui.error(f"No models found matching '{model_name}'")
            await ui.muted("Try /model --list to see all available models")
            return None

        if len(models) == 1:
            # Single match - use it
            model = models[0]
            context.state_manager.session.current_model = model.full_id
            await ui.success(f"Switched to model: {model.full_id} - {model.name}")
            return None

        # Multiple matches - show interactive selector with results
        await ui.info(f"Found {len(models)} models matching '{model_name}'")
        selected_model = await select_model_interactive(self.registry, model_name)

        if selected_model:
            context.state_manager.session.current_model = selected_model
            await ui.success(f"Switched to model: {selected_model}")
        else:
            await ui.info("Model selection cancelled")

        return None

    async def _list_models(self) -> Optional[str]:
        """List all available models."""
        await self._ensure_registry()

        if not self.registry.models:
            await ui.error("No models available")
            return None

        # Group by provider
        providers: Dict[str, List[ModelInfo]] = {}
        for model in self.registry.models.values():
            if model.provider not in providers:
                providers[model.provider] = []
            providers[model.provider].append(model)

        # Display models
        await ui.info(f"Available models ({len(self.registry.models)} total):")

        for provider_id in sorted(providers.keys()):
            provider_info = self.registry.providers.get(provider_id)
            provider_name = provider_info.name if provider_info else provider_id

            await ui.print(f"\n{provider_name}:")

            for model in sorted(providers[provider_id], key=lambda m: m.name):
                line = f"  • {model.id}"
                if model.cost.input is not None:
                    line += f" (${model.cost.input}/{model.cost.output})"
                if model.limits.context:
                    line += f" [{model.limits.context//1000}k]"
                await ui.muted(line)

        return None

    async def _show_model_info(self, model_id: str) -> Optional[str]:
        """Show detailed information about a model."""
        await self._ensure_registry()

        model = self.registry.get_model(model_id)
        if not model:
            # Try to find similar models or routing options
            base_name = self.registry._extract_base_model_name(model_id)
            variants = self.registry.get_model_variants(base_name)
            if variants:
                await ui.warning(f"Model '{model_id}' not found directly")
                await ui.info(f"Found routing options for '{base_name}':")

                # Sort variants by cost (FREE first)
                sorted_variants = sorted(variants, key=lambda m: (
                    0 if m.cost.input == 0 else 1,  # FREE first
                    m.cost.input or float('inf'),   # Then by cost
                    m.provider                      # Then by provider name
                ))

                for variant in sorted_variants:
                    cost_display = "FREE" if variant.cost.input == 0 else f"${variant.cost.input}/{variant.cost.output}"
                    provider_name = self._get_provider_display_name(variant.provider)

                    await ui.muted(f"  • {variant.full_id} - {provider_name} ({cost_display})")

                await ui.muted("\nUse '/model <provider:model-id>' to select a specific routing option")
                return None
            else:
                await ui.error(f"Model '{model_id}' not found")
                return None

        # Display model information
        await ui.info(f"{model.name}")
        await ui.muted(f"ID: {model.full_id}")

        # Show routing alternatives for this base model
        base_name = self.registry._extract_base_model_name(model)
        variants = self.registry.get_model_variants(base_name)
        if len(variants) > 1:
            await ui.print("\nRouting Options:")

            # Sort variants by cost (FREE first)
            sorted_variants = sorted(variants, key=lambda m: (
                0 if m.cost.input == 0 else 1,  # FREE first
                m.cost.input or float('inf'),   # Then by cost
                m.provider                      # Then by provider name
            ))

            for variant in sorted_variants:
                cost_display = "FREE" if variant.cost.input == 0 else f"${variant.cost.input}/{variant.cost.output}"
                provider_name = self._get_provider_display_name(variant.provider)

                # Highlight current selection
                prefix = "→ " if variant.full_id == model.full_id else "  "
                free_indicator = " ⭐" if variant.cost.input == 0 else ""

                await ui.muted(f"{prefix}{variant.full_id} - {provider_name} ({cost_display}){free_indicator}")

        if model.cost.input is not None:
            await ui.print("\nPricing:")
            await ui.muted(f"  Input: ${model.cost.input} per 1M tokens")
            await ui.muted(f"  Output: ${model.cost.output} per 1M tokens")

        if model.limits.context or model.limits.output:
            await ui.print("\nLimits:")
            if model.limits.context:
                await ui.muted(f"  Context: {model.limits.context:,} tokens")
            if model.limits.output:
                await ui.muted(f"  Output: {model.limits.output:,} tokens")

        caps = []
        if model.capabilities.attachment:
            caps.append("Attachments")
        if model.capabilities.reasoning:
            caps.append("Reasoning")
        if model.capabilities.tool_call:
            caps.append("Tool calling")

        if caps:
            await ui.print("\nCapabilities:")
            for cap in caps:
                await ui.muted(f"  ✓ {cap}")

        if model.capabilities.knowledge:
            await ui.print(f"\nKnowledge cutoff: {model.capabilities.knowledge}")

        return None

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
