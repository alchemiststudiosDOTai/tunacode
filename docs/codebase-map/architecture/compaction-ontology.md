---
title: Compaction System Ontology
link: compaction-ontology
type: doc
path: docs/codebase-map/architecture/compaction-ontology.md
depth: 2
seams: [A, M, D]
ontological_relations:
  - relates_to: [[core-compaction]]
  - relates_to: [[core-limits]]
  - relates_to: [[core-state]]
  - relates_to: [[core-agents]]
  - affects: [[session-messages]]
  - affects: [[context-window]]
tags:
  - compaction
  - context-management
  - architecture
  - ontology
created_at: 2026-01-20T16:25:00Z
updated_at: 2026-01-20T16:25:00Z
---

# Compaction System Ontology

## Entity Relationships

```
                                    ┌─────────────────────┐
                                    │   User Request      │
                                    └──────────┬──────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         RequestOrchestrator                                   │
│                         (core/agents/main.py)                                │
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ state_manager   │───▶│ session.messages│───▶│ prune_old_tool  │         │
│  │                 │    │                 │    │ _outputs()      │         │
│  └─────────────────┘    └─────────────────┘    └────────┬────────┘         │
│                                                          │                  │
└──────────────────────────────────────────────────────────┼──────────────────┘
                                                           │
                          ┌────────────────────────────────┼────────────────────┐
                          │                                ▼                    │
                          │              ┌─────────────────────────────────┐   │
                          │              │      compaction.py              │   │
                          │              │                                 │   │
                          │              │  ┌───────────────────────────┐  │   │
                          │              │  │ get_prune_thresholds()    │──┼───┼──┐
                          │              │  └───────────────────────────┘  │   │  │
                          │              │                                 │   │  │
                          │              │  ┌───────────────────────────┐  │   │  │
                          │              │  │ is_tool_return_part()     │  │   │  │
                          │              │  └───────────────────────────┘  │   │  │
                          │              │                                 │   │  │
                          │              │  ┌───────────────────────────┐  │   │  │
                          │              │  │ estimate_part_tokens()    │──┼───┼──┼──┐
                          │              │  └───────────────────────────┘  │   │  │  │
                          │              │                                 │   │  │  │
                          │              │  ┌───────────────────────────┐  │   │  │  │
                          │              │  │ prune_part_content()      │  │   │  │  │
                          │              │  └───────────────────────────┘  │   │  │  │
                          │              └─────────────────────────────────┘   │  │  │
                          │                                                    │  │  │
                          └────────────────────────────────────────────────────┘  │  │
                                                                                  │  │
                    ┌─────────────────────────────────────────────────────────────┘  │
                    │                                                                │
                    ▼                                                                │
          ┌─────────────────────┐                                                   │
          │     limits.py       │                                                   │
          │                     │                                                   │
          │  is_local_mode()    │                                                   │
          │  _load_settings()   │                                                   │
          └─────────────────────┘                                                   │
                                                                                    │
                    ┌───────────────────────────────────────────────────────────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │  token_counter.py   │
          │                     │
          │  estimate_tokens()  │
          │  CHARS_PER_TOKEN=4  │
          └─────────────────────┘
```

## Ontological Classes

### Primary Entities

| Entity | Type | Location | Description |
|--------|------|----------|-------------|
| `Compaction` | Process | `core/compaction.py` | Context pruning system |
| `Message` | Data | `session.messages` | Conversation history item |
| `Part` | Data | `message.parts` | Sub-component of message |
| `ToolReturn` | Data | `part_kind="tool-return"` | Tool execution result |
| `Token` | Unit | Estimated | Context window unit |

### Secondary Entities

| Entity | Type | Location | Description |
|--------|------|----------|-------------|
| `Threshold` | Config | `compaction.py:14-18` | Pruning boundaries |
| `Placeholder` | Constant | `compaction.py:21` | Replacement text |
| `Mode` | State | `limits.py` | Local vs Standard |
| `Session` | State | `state.py` | Conversation container |

## Relationships

### Compositional (HAS-A)

```
Session
  └── messages: list[Message]
        └── parts: list[Part]
              └── content: str | Any
              └── part_kind: str
```

### Functional (OPERATES-ON)

| Subject | Verb | Object |
|---------|------|--------|
| `prune_old_tool_outputs` | scans | `messages` |
| `prune_old_tool_outputs` | identifies | `tool-return` parts |
| `prune_old_tool_outputs` | mutates | `part.content` |
| `get_prune_thresholds` | reads | `is_local_mode()` |
| `estimate_part_tokens` | delegates-to | `estimate_tokens()` |

### Dependency (DEPENDS-ON)

```
compaction.py
    │
    ├──▶ limits.py::is_local_mode()
    │
    └──▶ token_counter.py::estimate_tokens()

main.py
    │
    ├──▶ compaction.py::prune_old_tool_outputs()
    │
    └──▶ state.py::session.messages
```

### Trigger (INVOKED-BY)

```
User Request
    │
    └──▶ RequestOrchestrator._run_impl()
            │
            └──▶ prune_old_tool_outputs()  [line 342]
```

## Data Flow

### Input/Output

```
INPUT:
  messages: list[ModelMessage]    # Full conversation history
  model: str                      # Model name (for token estimation)

OUTPUT:
  messages: list[ModelMessage]    # Same list, mutated in-place
  tokens_reclaimed: int           # Net tokens freed
```

### State Transitions

```
           ┌─────────────────────────────────────────────┐
           │                                             │
           ▼                                             │
    ┌──────────────┐                              ┌──────┴───────┐
    │   PRISTINE   │──────[accumulate > protect]──▶│   CANDIDATE  │
    │  (protected) │                              │  (to prune)  │
    └──────────────┘                              └──────┬───────┘
                                                         │
                                          [total > minimum_threshold]
                                                         │
                                                         ▼
                                                  ┌──────────────┐
                                                  │    PRUNED    │
                                                  │ (placeholder)│
                                                  └──────────────┘
```

## Threshold Ontology

### Standard Mode (Cloud APIs)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     200,000 token context window                     │
│                                                                      │
│  ┌──────────────────────────────────────────┬───────────────────┐   │
│  │         PRUNABLE ZONE                    │  PROTECTED ZONE   │   │
│  │         (oldest)                         │  (40,000 tokens)  │   │
│  │                                          │                   │   │
│  │  Only pruned if total > 20,000 tokens    │  Never pruned     │   │
│  └──────────────────────────────────────────┴───────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Local Mode (Small Context)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      10,000 token context window                     │
│                                                                      │
│  ┌────────────────────────────────────────────────┬─────────────┐   │
│  │              PRUNABLE ZONE                     │ PROTECTED   │   │
│  │              (aggressive)                      │ (2,000)     │   │
│  │                                                │             │   │
│  │  Pruned if total > 500 tokens                  │ Never       │   │
│  └────────────────────────────────────────────────┴─────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Invariants

### Pre-conditions

| Invariant | Check Location | Failure Behavior |
|-----------|----------------|------------------|
| `messages` is mutable list | Caller responsibility | Silent no-op |
| `len(messages) > 0` | line 179 | Early return |
| `user_turns >= 2` | line 183-185 | Early return |

### Post-conditions

| Invariant | Guarantee |
|-----------|-----------|
| Message list identity preserved | Same list object returned |
| Protected content unchanged | Recent tokens untouched |
| Pruned parts contain placeholder | Exactly `PRUNE_PLACEHOLDER` |
| Idempotent | Re-running produces no change |

### Class Invariants

| Class | Invariant |
|-------|-----------|
| `Part` | `part_kind` is immutable |
| `Message` | `parts` list is mutable |
| `Session` | `messages` persists across requests |

## Seams

### Architecture Seams (A)

- **Trigger Location**: Can move compaction to different lifecycle points
- **Proactive vs Reactive**: Currently proactive; could add reactive overflow handling

### Module Seams (M)

- **Threshold Configuration**: Currently hardcoded; could externalize to config
- **Token Estimation**: Uses heuristic; could swap in actual tokenizer
- **Placeholder Format**: Static string; could make dynamic/contextual

### Data Seams (D)

- **Pruning Granularity**: Currently part-level; could do message-level
- **Preservation Rules**: Currently all tool-returns; could add selective rules
- **Content Summarization**: Currently placeholder; could add LLM summarization

## Cross-References

| Document | Relationship |
|----------|--------------|
| [[core-compaction]] | Implementation details |
| [[core-limits]] | Mode detection |
| [[core-state]] | Session/message storage |
| [[core-agents]] | Integration point |
| [[conversation-turns]] | Message structure |
| [[architecture]] | System overview |
