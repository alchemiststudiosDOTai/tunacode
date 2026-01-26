---
title: Core Prompting Engine
path: src/tunacode/core/prompting
type: directory
depth: 1
description: System prompt composition from modular sections
exports: [PromptingEngine, get_prompting_engine, resolve_prompt, compose_prompt, SystemPromptSection, LOCAL_TEMPLATE, MAIN_TEMPLATE, RESEARCH_TEMPLATE, TEMPLATE_OVERRIDES, SectionLoader]
seams: [M, D]
---

# Core Prompting Engine

## Purpose
Composes modular system prompts from sections, templates, and dynamic placeholders for AI agents.

## Key Components

### Prompting Engine (prompting_engine.py)

**PromptingEngine Class**
- Loads and caches prompt sections from files
- Resolves dynamic placeholders ({{CWD}}, {{OS}}, {{DATE}})
- Applies model-specific template overrides
- Composes final system prompt from sections

**Dynamic Placeholders:**
- `{{CWD}}` - Current working directory
- `{{OS}}` - Operating system name
- `{{DATE}}` - Current date
- `{{AGENTS_MD_CONTENT}}` - Project-specific AGENTS.md content

**Templates:**
- **MAIN_TEMPLATE** - Standard agent prompt structure (11 sections)
- **RESEARCH_TEMPLATE** - Research agent prompt structure (4 sections)
- **LOCAL_TEMPLATE** - Minimal template for small context models (3 sections: AGENT_ROLE, TOOL_USE, USER_INSTRUCTIONS)
- **TEMPLATE_OVERRIDES** - Model-specific template variations

### Section Loader (loader.py)

**SectionLoader Class**
- Reads markdown section files from prompts/ directory
- Caches loaded sections for performance
- Provides get_section() method for section retrieval

### Sections (sections.py)

**SystemPromptSection Enum**
Defines all prompt section types:
- **AGENT_ROLE** - Core agent identity and purpose
- **CRITICAL_RULES** - Mandatory behavior constraints
- **TOOL_USE** - Tool usage guidelines
- **CODE_STYLE** - Code quality standards
- **WORKFLOW** - Step-by-step process rules
- **OUTPUT_FORMAT** - Response format requirements

### Templates (templates.py)

Defines three prompt templates with different section compositions:

- **MAIN_TEMPLATE** - Full-featured agent for standard context windows
- **RESEARCH_TEMPLATE** - Simplified template for research agents
- **LOCAL_TEMPLATE** - Minimal template for small context models (8k-16k tokens), triggered by `is_local_mode()`

## Section Files Location

```
src/tunacode/prompts/sections/
├── agent_role.md
├── critical_rules.md
├── tool_use.md
├── code_style.md
├── workflow.md
└── output_format.md
```

## Guide Files

```
src/tunacode/core/prompting/
└── local_prompt.md      # Condensed guide for local_mode (replaces AGENTS.md)
```

Context injection via `{{USER_INSTRUCTIONS}}` placeholder:
- **Standard mode:** loads from `settings.guide_file` (defaults to AGENTS.md)
- **Local mode:** loads `local_prompt.md` for minimal token usage

## Prompt Composition Flow

```
1. Load sections from files (SectionLoader)
2. Resolve dynamic placeholders ({{CWD}}, {{OS}}, etc.)
3. Select template:
   - LOCAL_TEMPLATE if is_local_mode() is True
   - Model-specific override from TEMPLATE_OVERRIDES if model matches
   - MAIN_TEMPLATE as default
4. Compose final system prompt from template and sections
```

## Integration Points

- **core/agents/agent_config.py** - Loads prompts, selects template based on `is_local_mode()`
- **utils/limits.py** - `is_local_mode()` determines LOCAL_TEMPLATE usage
- **configuration/** - Model-specific settings, `local_mode` flag
- **AGENTS.md** - Project-specific context injection (standard mode)
- **local_prompt.md** - Condensed context injection (local mode)

## Seams (M, D)

**Modification Points:**
- Add new prompt section types
- Customize placeholder resolution logic
- Extend template variations
- Add model-specific prompt overrides

**Extension Points:**
- Create custom section loaders
- Implement dynamic prompt generators
- Add prompt validation/analysis
- Support prompt versioning
