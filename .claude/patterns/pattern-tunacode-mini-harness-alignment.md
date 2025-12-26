---
title: pattern — tunacode mini harness alignment
link: pattern-tunacode-mini-harness-alignment
type: patterns
ontological_relations: []
tags:
- tunacode
- mini-evals
- qwen2
- tool-calls
- harness
- timeout
created_at: 2025-12-25T18:06:14Z
updated_at: 2025-12-25T18:06:39Z
uuid: df083604-8ea6-4395-88ca-d6f08c536428
---

Mini harness that preserves TunaCode "soul" while staying independent from runtime code.

Pattern:
1) Keep the harness self-contained under `mini_evals/` (no `src/tunacode` imports).
2) Match TunaCode tool schema and parsing order:
   - OpenAI `tool_calls` first.
   - Qwen2.5 raw JSON / `<tool_call>` / code fences via fallback parser.
3) Keep prompt rules that define the TunaCode feel:
   - Search funnel (glob -> grep -> read_file).
   - Read-only tool preference.
   - Completion marker: `TUNACODE DONE:`
   - No emojis, no raw JSON to user.
4) Keep evaluation simple:
   - Single tool call per response.
   - Default to 100 scenarios.
   - Hard per-scenario timeout (30s) and move on.

Why:
- GRPO evals need a tiny, deterministic harness that still mirrors TunaCode behavior.
- Qwen2.5 on vLLM often emits raw tool JSON; the parser must handle that.

Notes:
- Runtime TunaCode raw-text tool parsing can be added later; track separately.
