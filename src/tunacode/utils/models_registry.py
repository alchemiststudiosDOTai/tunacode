"""Models.dev integration for model discovery and validation."""

import json
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelCapabilities(BaseModel):
    """Model capabilities and features."""

    model_config = ConfigDict(extra="ignore")

    attachment: bool = False
    reasoning: bool = False
    tool_call: bool = False
    temperature: bool = True
    knowledge: Optional[str] = None


class ModelCost(BaseModel):
    """Model pricing information."""

    model_config = ConfigDict(extra="ignore")

    input: Optional[float] = None
    output: Optional[float] = None
    cache: Optional[float] = None

    @field_validator("input", "output", "cache")
    @classmethod
    def _non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("cost values must be non-negative")
        return float(v)

    def format_cost(self) -> str:
        """Format cost as a readable string."""
        if self.input is None or self.output is None:
            return "Pricing not available"
        return f"${self.input}/{self.output} per 1M tokens"


class ModelLimits(BaseModel):
    """Model context and output limits."""

    model_config = ConfigDict(extra="ignore")

    context: Optional[int] = None
    output: Optional[int] = None

    @field_validator("context", "output")
    @classmethod
    def _positive_int(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        iv = int(v)
        if iv < 0:
            raise ValueError("limits must be non-negative integers")
        return iv if iv > 0 else None

    def format_limits(self) -> str:
        """Format limits as a readable string."""
        parts: List[str] = []
        if self.context:
            parts.append(f"{self.context:,} context")
        if self.output:
            parts.append(f"{self.output:,} output")
        return ", ".join(parts) if parts else "Limits not specified"


class ModelInfo(BaseModel):
    """Complete model information."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    provider: str
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    cost: ModelCost = Field(default_factory=ModelCost)
    limits: ModelLimits = Field(default_factory=ModelLimits)
    release_date: Optional[str] = None
    last_updated: Optional[str] = None
    open_weights: bool = False
    modalities: Dict[str, List[str]] = Field(default_factory=dict)

    @property
    def full_id(self) -> str:
        """Get the full model identifier with provider prefix."""
        return f"{self.provider}:{self.id}"

    def format_display(self, include_details: bool = True) -> str:
        """Format model for display."""
        display = f"{self.full_id} - {self.name}"
        if include_details:
            details: List[str] = []
            if self.cost.input is not None:
                details.append(self.cost.format_cost())
            if self.limits.context:
                details.append(f"{self.limits.context // 1000}k context")
            if details:
                display += f" ({', '.join(details)})"
        return display

    # we need to make this lighter for future dev, low priority
    def matches_search(self, query: str) -> float:
        """Calculate match score for search query (0-1)."""
        query_lower = query.lower()

        # Exact match in ID or name
        if query_lower in self.id.lower():
            return 1.0
        if query_lower in self.name.lower():
            return 0.9
        if query_lower in self.provider.lower():
            return 0.8

        # Fuzzy match
        best_ratio = 0.0
        for field_value in [self.id, self.name, self.provider]:
            ratio = SequenceMatcher(None, query_lower, field_value.lower()).ratio()
            best_ratio = max(best_ratio, ratio)

        return best_ratio


class ProviderInfo(BaseModel):
    """Provider information."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    env: List[str] = Field(default_factory=list)
    npm: Optional[str] = None
    doc: Optional[str] = None


class ModelsRegistry:
    """Registry for managing models from models.dev."""

    API_URL = "https://models.dev/api.json"
    CACHE_FILE = "models_cache.json"
    CACHE_TTL = timedelta(hours=24)

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the models registry."""
        if cache_dir is None:
            cache_dir = Path.home() / ".tunacode" / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / self.CACHE_FILE

        self.models: Dict[str, ModelInfo] = {}
        self.providers: Dict[str, ProviderInfo] = {}
        self._loaded = False

    def _is_cache_valid(self) -> bool:
        """Check if cache file exists and is still valid."""
        if not self.cache_file.exists():
            return False

        # Check cache age
        cache_age = datetime.now() - datetime.fromtimestamp(self.cache_file.stat().st_mtime)
        return cache_age < self.CACHE_TTL

    def _load_from_cache(self) -> bool:
        """Load models from cache file."""
        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
                self._parse_data(data)
                return True
        except (json.JSONDecodeError, OSError, KeyError):
            return False

    def _fetch_from_api(self) -> bool:
        """Fetch models from models.dev API."""
        try:
            # Add User-Agent header to avoid blocking
            import urllib.request

            req = urllib.request.Request(self.API_URL, headers={"User-Agent": "TunaCode-CLI/1.0"})
            with urlopen(req, timeout=10) as response:  # nosec B310 - Using trusted models.dev API
                data = json.loads(response.read())

                # Save to cache
                with open(self.cache_file, "w") as f:
                    json.dump(data, f, indent=2)

                self._parse_data(data)
                return True
        except (URLError, json.JSONDecodeError, OSError):
            # Log error but don't fail
            return False

    def _load_fallback_models(self) -> None:
        """Load hardcoded popular models as fallback."""
        fallback_data = {
            "openai": {
                "name": "OpenAI",
                "env": ["OPENAI_API_KEY"],
                "npm": "@ai-sdk/openai",
                "doc": "https://platform.openai.com/docs",
                "models": {
                    "gpt-4": {
                        "name": "GPT-4",
                        "attachment": True,
                        "reasoning": True,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 30.0, "output": 60.0},
                        "limit": {"context": 128000, "output": 4096},
                    },
                    "gpt-4-turbo": {
                        "name": "GPT-4 Turbo",
                        "attachment": True,
                        "reasoning": True,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 10.0, "output": 30.0},
                        "limit": {"context": 128000, "output": 4096},
                    },
                    "gpt-3.5-turbo": {
                        "name": "GPT-3.5 Turbo",
                        "attachment": False,
                        "reasoning": False,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-01",
                        "cost": {"input": 0.5, "output": 1.5},
                        "limit": {"context": 16000, "output": 4096},
                    },
                },
            },
            "anthropic": {
                "name": "Anthropic",
                "env": ["ANTHROPIC_API_KEY"],
                "npm": "@ai-sdk/anthropic",
                "doc": "https://docs.anthropic.com",
                "models": {
                    "claude-3-opus-20240229": {
                        "name": "Claude 3 Opus",
                        "attachment": True,
                        "reasoning": True,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 15.0, "output": 75.0},
                        "limit": {"context": 200000, "output": 4096},
                    },
                    "claude-3-sonnet-20240229": {
                        "name": "Claude 3 Sonnet",
                        "attachment": True,
                        "reasoning": True,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 3.0, "output": 15.0},
                        "limit": {"context": 200000, "output": 4096},
                    },
                    "claude-3-haiku-20240307": {
                        "name": "Claude 3 Haiku",
                        "attachment": True,
                        "reasoning": False,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 0.25, "output": 1.25},
                        "limit": {"context": 200000, "output": 4096},
                    },
                },
            },
            "google": {
                "name": "Google",
                "env": ["GOOGLE_API_KEY"],
                "npm": "@ai-sdk/google",
                "doc": "https://ai.google.dev",
                "models": {
                    "gemini-1.5-pro": {
                        "name": "Gemini 1.5 Pro",
                        "attachment": True,
                        "reasoning": True,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 3.5, "output": 10.5},
                        "limit": {"context": 2000000, "output": 8192},
                    },
                    "gemini-1.5-flash": {
                        "name": "Gemini 1.5 Flash",
                        "attachment": True,
                        "reasoning": True,
                        "tool_call": True,
                        "temperature": True,
                        "knowledge": "2024-04",
                        "cost": {"input": 0.075, "output": 0.3},
                        "limit": {"context": 1000000, "output": 8192},
                    },
                },
            },
        }

        self._parse_data(fallback_data)

    def _parse_data(self, data: Dict[str, Any]) -> None:
        """Parse models data from API response."""
        self.models.clear()
        self.providers.clear()

        for provider_id, provider_data in data.items():
            # Skip non-provider keys
            if not isinstance(provider_data, dict) or "models" not in provider_data:
                continue

            # Parse provider info
            provider = ProviderInfo(
                id=provider_id,
                name=provider_data.get("name", provider_id),
                env=provider_data.get("env", []),
                npm=provider_data.get("npm"),
                doc=provider_data.get("doc"),
            )
            self.providers[provider_id] = provider

            # Parse models
            models_data = provider_data.get("models", {})
            for model_id, model_data in models_data.items():
                if not isinstance(model_data, dict):
                    continue

                # Parse capabilities
                capabilities = ModelCapabilities(
                    attachment=bool(model_data.get("attachment", False)),
                    reasoning=bool(model_data.get("reasoning", False)),
                    tool_call=bool(model_data.get("tool_call", False)),
                    temperature=bool(model_data.get("temperature", True)),
                    knowledge=model_data.get("knowledge"),
                )

                # Parse cost
                cost_data = model_data.get("cost", {})
                cost = ModelCost(
                    input=(cost_data.get("input") if isinstance(cost_data, dict) else None),
                    output=(cost_data.get("output") if isinstance(cost_data, dict) else None),
                    cache=(cost_data.get("cache") if isinstance(cost_data, dict) else None),
                )

                # Parse limits
                limit_data = model_data.get("limit", {})
                limits = ModelLimits(
                    context=(limit_data.get("context") if isinstance(limit_data, dict) else None),
                    output=(limit_data.get("output") if isinstance(limit_data, dict) else None),
                )

                # Create model info
                model = ModelInfo(
                    id=model_id,
                    name=model_data.get("name", model_id),
                    provider=provider_id,
                    capabilities=capabilities,
                    cost=cost,
                    limits=limits,
                    release_date=model_data.get("release_date"),
                    last_updated=model_data.get("last_updated"),
                    open_weights=bool(model_data.get("open_weights", False)),
                    modalities=(
                        model_data.get("modalities", {})
                        if isinstance(model_data.get("modalities", {}), dict)
                        else {}
                    ),
                )

                # Store with full ID as key
                self.models[model.full_id] = model

    async def load(self, force_refresh: bool = False) -> bool:
        """Load models data, using cache if available."""
        if self._loaded and not force_refresh:
            return True

        # Try cache first
        if not force_refresh and self._is_cache_valid():
            if self._load_from_cache():
                self._loaded = True
                return True

        # Fetch from API
        if self._fetch_from_api():
            self._loaded = True
            return True

        # Try cache as fallback even if expired
        if self._load_from_cache():
            self._loaded = True
            # Import ui locally to avoid circular imports
            from ..ui import console as ui

            await ui.warning("Using cached models data (API unavailable)")
            return True

        # Use fallback models as last resort
        from ..ui import console as ui

        await ui.warning("models.dev API unavailable, using fallback model list")
        self._load_fallback_models()
        self._loaded = True
        return True

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get a specific model by ID."""
        # Try exact match first
        if model_id in self.models:
            return self.models[model_id]

        # Try without provider prefix
        for full_id, model in self.models.items():
            if model.id == model_id:
                return model

        return None

    def validate_model(self, model_id: str) -> bool:
        """Check if a model ID is valid."""
        return self.get_model(model_id) is not None

    def search_models(
        self, query: str = "", provider: Optional[str] = None, min_score: float = 0.3
    ) -> List[ModelInfo]:
        """Search for models matching query."""
        results = []

        for model in self.models.values():
            # Filter by provider if specified
            if provider and model.provider != provider:
                continue

            # Calculate match score
            if query:
                score = model.matches_search(query)
                if score < min_score:
                    continue
                results.append((score, model))
            else:
                # No query, include all
                results.append((1.0, model))

        # Sort by score (descending) and name
        results.sort(key=lambda x: (-x[0], x[1].name))

        return [model for _, model in results]

    def get_providers(self) -> List[ProviderInfo]:
        """Get list of all providers."""
        return sorted(self.providers.values(), key=lambda p: p.name)

    def get_models_by_provider(self, provider: str) -> List[ModelInfo]:
        """Get all models for a specific provider."""
        return [m for m in self.models.values() if m.provider == provider]

    def _extract_base_model_name(self, model: ModelInfo) -> str:
        """Extract the base model name from a model (e.g., 'gpt-4o' from 'openai:gpt-4o')."""
        model_id = model.id.lower()

        # Handle common patterns
        base_name = model_id

        # Remove common suffixes
        suffixes_to_remove = [
            "-latest",
            "-preview",
            "-turbo",
            "-instruct",
            "-chat",
            "-base",
            "-20240229",
            "-20240307",
            "-20240620",
            "-20241022",
            "-20250514",
            "-0613",
            "-0125",
            "-0301",
            "-1106",
            "-2024",
            "-2025",
        ]

        for suffix in suffixes_to_remove:
            if base_name.endswith(suffix):
                base_name = base_name[: -len(suffix)]

        # Handle versioned models (e.g., 'claude-3-5-sonnet' -> 'claude-3-sonnet')
        if "claude-3-5" in base_name:
            base_name = base_name.replace("claude-3-5", "claude-3")
        elif "claude-3-7" in base_name:
            base_name = base_name.replace("claude-3-7", "claude-3")

        # Handle OpenRouter nested paths (e.g., 'openai/gpt-4o' -> 'gpt-4o')
        if "/" in base_name:
            base_name = base_name.split("/")[-1]

        return base_name

    def get_model_variants(self, base_model_name: str) -> List[ModelInfo]:
        """Get all variants of a base model across different providers."""
        base_name = base_model_name.lower()
        variants = []

        for model in self.models.values():
            model_base = self._extract_base_model_name(model)
            if model_base == base_name or base_name in model_base:
                variants.append(model)

        # Sort by cost (free first, then ascending cost)
        def sort_key(model: ModelInfo) -> tuple:
            cost = model.cost.input or 999
            is_free = cost == 0
            return (not is_free, cost, model.provider, model.id)

        variants.sort(key=sort_key)
        return variants

    def find_base_models(self, query: str) -> Dict[str, List[ModelInfo]]:
        """Find base models and group their variants by routing source."""
        query_lower = query.lower()
        base_models: Dict[str, List[ModelInfo]] = {}

        # Find all models matching the query
        matching_models = []
        for model in self.models.values():
            base_name = self._extract_base_model_name(model)
            if (
                query_lower in model.id.lower()
                or query_lower in model.name.lower()
                or query_lower in base_name
                or query_lower in model.provider.lower()
            ):
                matching_models.append((base_name, model))

        # Group by base model name
        for base_name, model in matching_models:
            if base_name not in base_models:
                base_models[base_name] = []
            base_models[base_name].append(model)

        # Sort variants within each base model
        for base_name in base_models:

            def sort_key(model: ModelInfo) -> tuple:
                cost = model.cost.input or 999
                is_free = cost == 0
                return (not is_free, cost, model.provider, model.id)

            base_models[base_name].sort(key=sort_key)

        return base_models

    def get_popular_base_models(self) -> List[str]:
        """Get list of popular base model names for suggestions."""
        popular_patterns = [
            "gpt-4o",
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "gemini-2",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "o1-preview",
            "o1-mini",
            "o3",
            "o3-mini",
        ]

        available_base_models = []
        for pattern in popular_patterns:
            variants = self.get_model_variants(pattern)
            if variants:
                available_base_models.append(pattern)

        return available_base_models
