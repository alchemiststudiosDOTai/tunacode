#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REGISTRY_PATH="${REPO_ROOT}/src/tunacode/configuration/models_registry.json"
MODELS_DEV_REGISTRY_URL="https://models.dev/api.json"

curl -fsSL "${MODELS_DEV_REGISTRY_URL}" -o "${REGISTRY_PATH}"

# Patch provider API endpoints for OpenAI-compatible routing.
#
# Providers in API_OVERRIDES have stable base URLs and should always get an
# explicit `api` value in the bundled registry.
#
# Providers in OMIT_API_PROVIDERS are deployment-specific; endpoint URLs vary
# per user account/region/resource and must not be hardcoded here.
REGISTRY_PATH="${REGISTRY_PATH}" uv run python - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

API_OVERRIDES: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "xai": "https://api.x.ai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "cohere": "https://api.cohere.ai/compatibility/v1",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "togetherai": "https://api.together.xyz/v1",
    "perplexity": "https://api.perplexity.ai",
    "venice": "https://api.venice.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "v0": "https://api.v0.dev/v1",
    "vercel": "https://ai-gateway.vercel.sh/v1",
}

OMIT_API_PROVIDERS: frozenset[str] = frozenset(
    {
        "amazon-bedrock",
        "azure",
        "azure-cognitive-services",
        "cloudflare-workers-ai",
        "gitlab",
        "google-vertex",
        "google-vertex-anthropic",
        "sap-ai-core",
    }
)

registry_path = Path(os.environ["REGISTRY_PATH"])
registry = json.loads(registry_path.read_text(encoding="utf-8"))
if not isinstance(registry, dict):
    raise TypeError(f"Expected top-level dict in models registry, got {type(registry).__name__}")

missing_override_providers = sorted(pid for pid in API_OVERRIDES if pid not in registry)
if missing_override_providers:
    missing = ", ".join(missing_override_providers)
    raise KeyError(f"API override providers missing from models registry: {missing}")

missing_omit_providers = sorted(pid for pid in OMIT_API_PROVIDERS if pid not in registry)
if missing_omit_providers:
    missing = ", ".join(missing_omit_providers)
    raise KeyError(f"OMIT_API providers missing from models registry: {missing}")

for provider_id, api_url in API_OVERRIDES.items():
    provider_data = registry[provider_id]
    if not isinstance(provider_data, dict):
        raise TypeError(f"Provider entry must be a dict for '{provider_id}'")
    provider_data["api"] = api_url

for provider_id in OMIT_API_PROVIDERS:
    provider_data = registry[provider_id]
    if not isinstance(provider_data, dict):
        raise TypeError(f"Provider entry must be a dict for '{provider_id}'")
    provider_data.pop("api", None)

registry_path.write_text(f"{json.dumps(registry, indent=2)}\n", encoding="utf-8")

print(f"Updated models registry at: {registry_path}")
print(f"Applied API overrides for {len(API_OVERRIDES)} providers")
print(f"Cleared API field for {len(OMIT_API_PROVIDERS)} deployment-specific providers")
PY

echo "Updated models_registry.json"
