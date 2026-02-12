# Research – TunaCode tinyagent Rust-only stream mapping
**Date:** 2026-02-12
**Phase:** Research

## Constraint (session requirement)
- Runtime target is **Rust stream path only**.
- **No old/legacy compatibility support** in runtime usage parsing or stream selection.

## Structure
- `src/tunacode/core/agents/` — primary request runtime and tinyagent agent wiring.
- `src/tunacode/core/compaction/` — compaction summarization runtime path.
- `tinyAgent/tinyagent/` — Python provider entrypoints (`stream_openrouter`, alchemy wrapper).
- `tinyAgent/bindings/alchemy_llm_py/src/lib.rs` — Rust binding exporting OpenAI-compatible stream APIs.
- `tests/integration/core/` — TunaCode live alchemy contract test.

## Key Files
- `src/tunacode/core/agents/main.py:L282` → gets agent instance via `ac.get_or_create_agent(...)`.
- `src/tunacode/core/agents/main.py:L633` → runtime request loop consumes `agent.stream(...)` events.
- `src/tunacode/core/agents/main.py:L625` → `message_end` handler dispatch.
- `src/tunacode/core/agents/main.py:L81` → `_parse_canonical_usage` enforces canonical usage contract.
- `src/tunacode/core/agents/agent_components/agent_config.py:L16` → imports `OpenRouterModel, stream_openrouter` from tinyagent.
- `src/tunacode/core/agents/agent_components/agent_config.py:L268-L284` → `_build_stream_fn` returns `stream_openrouter(...)`.
- `src/tunacode/core/agents/agent_components/agent_config.py:L307-L327` → `_build_tinyagent_model` constructs `OpenRouterModel`.
- `src/tunacode/core/agents/agent_components/agent_config.py:L373-L377` → `AgentOptions(stream_fn=stream_fn, ...)`.
- `src/tunacode/core/compaction/controller.py:L10` → imports `OpenRouterModel, stream_openrouter`.
- `src/tunacode/core/compaction/controller.py:L348` → compaction summary path calls `stream_openrouter(...)`.
- `src/tunacode/core/compaction/controller.py:L357-L367` → compaction model builder returns `OpenRouterModel`.
- `tinyAgent/tinyagent/alchemy_provider.py:L114` → `OpenAICompatModel` (Rust-compatible model config).
- `tinyAgent/tinyagent/alchemy_provider.py:L201-L243` → `stream_alchemy_openai_completions(...)` calls `_alchemy.openai_completions_stream(...)`.
- `tinyAgent/tinyagent/alchemy_provider.py:L246-L251` → `stream_alchemy_openrouter(...)` alias to rust-backed function.
- `tinyAgent/tinyagent/alchemy_provider.py:L60-L76` + `L148` → usage contract validation required on final result.
- `tinyAgent/tinyagent/openrouter_provider.py:L273-L284` → request body includes `"stream_options": {"include_usage": True}`.
- `tinyAgent/tinyagent/openrouter_provider.py:L571` → Python path sets `partial["usage"] = _build_usage_dict(...)`.
- `tinyAgent/tinyagent/openrouter_provider.py:L55-L89` → token fields normalized; cost remains ZERO_USAGE-derived values.
- `tinyAgent/tinyagent/agent_types.py:L19-L30` → `ZERO_USAGE` defines `cost.* = 0.0` defaults.
- `tinyAgent/tinyagent/__init__.py:L50-L56` → exports `stream_openrouter`; does not export alchemy stream helpers.
- `tinyAgent/bindings/alchemy_llm_py/src/lib.rs:L732` → Rust binding `openai_completions_stream` exported.
- `tinyAgent/bindings/alchemy_llm_py/src/lib.rs:L329-L357` → Rust maps usage/cost into Python message payload.
- `tests/integration/core/test_tinyagent_alchemy_usage_contract_live.py:L9,L29,L47` → TunaCode live test explicitly uses alchemy rust stream path.

## Runtime Dependency Map (current)
1. TunaCode request runtime:
   - `process_request` (`main.py:L720`) → `ac.get_or_create_agent` (`main.py:L282`) → `AgentOptions(stream_fn=_build_stream_fn(...))` (`agent_config.py:L373-L377`) → `_build_stream_fn` returns `stream_openrouter` (`agent_config.py:L282`).
2. TunaCode compaction runtime:
   - `CompactionController._generate_summary` (`controller.py:L332-L351`) → `stream_openrouter` (`controller.py:L348`).
3. Rust stream path availability:
   - available in tinyagent module `tinyagent.alchemy_provider` (`alchemy_provider.py:L201,L246`) and backed by `_alchemy` Rust binding (`lib.rs:L732`), but not wired in TunaCode runtime call chains above.

## Interface Mismatch Map (Python path vs Rust path)
- TunaCode runtime model object is `OpenRouterModel` (`agent_config.py:L307-L327`, `controller.py:L357-L367`).
- Rust entrypoint examples and API shape use `OpenAICompatModel` from `tinyagent.alchemy_provider` (`alchemy_provider.py:L114`; `tinyAgent/examples/example_chat_alchemy.py:L27,L60`).
- TunaCode imports tinyagent top-level package for stream/runtime wiring (`agent_config.py:L16`, `controller.py:L10`), while alchemy stream helpers are in submodule import path (`tinyagent.alchemy_provider`).

## No-legacy evidence (current code)
- Canonical usage parser rejects non-canonical payloads at runtime:
  - `src/tunacode/core/agents/main.py:L81-L89`.
- Canonical schema requires full key set:
  - `src/tunacode/types/canonical.py:L255-L268` (`UsageMetrics.from_dict` required keys).
  - `src/tunacode/types/canonical.py:L202-L216` (`UsageCost.from_dict` required keys).
- Unit tests assert rejection behavior:
  - `tests/unit/core/test_openrouter_usage_metrics.py:L31-L45`.

## Cost field behavior evidence
- tinyagent docs state current cost semantics are placeholder/default:
  - `tinyAgent/docs/api/usage-semantics.md:L54` (`cost` present for contract stability; currently zero/default values).
- Python OpenRouter provider normalizes token fields and keeps ZERO_USAGE-based cost defaults:
  - `tinyAgent/tinyagent/openrouter_provider.py:L47-L51`, `L55-L89`.
- TunaCode debug trace currently shows increasing token totals with zero cost:
  - `/root/.local/share/tunacode/logs/tunacode.log:L6,L11,L17` (Usage lines with non-zero tokens, `cost=0.000000`).

## Symbol Index
- TunaCode stream wiring: `_build_stream_fn`, `_build_tinyagent_model`, `get_or_create_agent`, `_generate_summary`, `_build_model`.
- TinyAgent Python stream: `stream_openrouter`, `_build_request_body`, `_build_usage_dict`.
- TinyAgent Rust stream: `stream_alchemy_openai_completions`, `stream_alchemy_openrouter`, `openai_completions_stream` (PyO3 export).
- TunaCode canonical enforcement: `_parse_canonical_usage`, `UsageMetrics.from_dict`, `UsageCost.from_dict`.
