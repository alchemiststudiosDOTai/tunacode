# Continuous Learning Log

Bugs, smells, issues dumped here as encountered. Raw is fine. A skill will organize this into proper kb entries later.

Format: `[date] [type] description`

Types: bug, smell, pattern, lesson, antipattern

---

[2026-01-07] [lesson] When there's a type mismatch between A and B, fix where A or B is defined, not every place that uses them. Don't scatter changes across 5+ files when one line at the source fixes everything.

[2026-01-08] [pattern] Local mode config: `docs/configuration/tunacode.local.json.example` - use when running local models. Key settings: `local_mode: true`, `local_max_tokens: 1000`, `context_window_size: 10000`, `OPENAI_BASE_URL` for local server.

[2026-01-08] [pattern] Syntax highlighting in tool renderers: Use `syntax_utils.py` for `get_lexer(filepath)` and `syntax_or_text(content, filepath)`. Consistent monokai theme. 9 renderers now registered: bash, glob, grep, list_dir, read_file, research_codebase, update_file, web_fetch, write_file. Commit `9db8e92`.

[2026-01-08] [antipattern] **RichLog.write(expand=True) is NOT terminal width!** `expand=True` expands to `scrollable_content_region`, which excludes padding and scrollbar gutter (~4-8 chars narrower than terminal). For full-width panels, pass explicit `width=` to the Panel constructor. Never trust `expand=True` to mean "full width" - it means "fill container" and the container is smaller than you think. See Gate 5: Indirection Requires Verification.

[2026-01-14] [antipattern] **Semantically dead code: loaded but never read.** Static analysis (Vulture) only catches syntactically dead code (never called). It misses code that IS called but whose result is never consumed. Example: `glob.py` had `_load_gitignore_patterns()` that populated a global, but nothing ever read that global. The `use_gitignore` parameter was a lie - it triggered work but had zero effect. **Prevention:** When adding a "load X" function, grep for reads of X before shipping. If a parameter controls behavior, trace the data flow to prove it actually changes output.

[2026-01-17] [bug] **Dangling tool calls on user abort (PR #246).** User aborts mid-tool-call → `messages` has `ModelResponse` with tool calls but no `ToolReturn` → next API request fails. Root cause: exception path violated message invariant (every tool call needs a return). Fix: `_remove_dangling_tool_calls()` in `except UserAbortError`. **Prevention:** Document state invariants. Test exception scenarios. See Gate 6.

[2026-01-24] [bug] **Shallow copy corrupts DEFAULT_USER_CONFIG.** `.copy()` is shallow - nested dicts (`settings`, `env`) still reference the constant. Setup was mutating user_config in-place → polluted module-level default → first-run config missing all defaults. **Fix:** Don't mutate, replace. `state.py` assigns constant directly (reference replaced by setup). `setup.py` builds new dict from `deepcopy(DEFAULT_USER_CONFIG)`. **Key insight:** If you don't mutate, you don't need to copy. See `.claude/JOURNAL.md` 2026-01-24 entry.

[2026-01-25] [pattern] **Canonical messaging adoption complete (Task 01).** Migrated production code to use `adapter.get_content()` (P1) and routed sanitize.py through adapter helpers (P2). Key insight: adapter layer now handles ALL message polymorphism. Detection uses adapter (`find_dangling_tool_calls`, `get_tool_call_ids`), mutation stays in sanitize.py. Deleted ~117 LOC of duplicate accessors. Branch: `types-architect`. See `.claude/JOURNAL.md` 2026-01-25 entry.

[2026-01-25] [bug] **Orphaned retry-prompt parts after dangling tool call cleanup.** When pruning dangling tool calls, `_filter_dangling_tool_calls_from_parts()` only removed `tool-call` parts. This left behind `retry-prompt` parts (pydantic-ai's error response for failed tools like 403). **Fix:** Filter ANY part with `tool_call_id` matching a dangling ID, not just `part_kind == "tool-call"`. **Key insight:** pydantic-ai uses multiple part kinds (`tool-call`, `tool-return`, `retry-prompt`) that all reference the same `tool_call_id`. Cleanup must be ID-based, not kind-based.

[2026-02-11] [bug] **Detached Textual widget mount during teardown causes secondary crash.** `ChatContainer.write()` mounted unconditionally, so exception rendering during app teardown raised `MountError` and masked the original exception. **Fix:** Guard mount with `if not self.is_attached:`, emit stderr warning, and return the unmounted widget. Added unit tests for detached and attached paths in `tests/unit/ui/test_chat_container.py`. **Key insight:** Error-rendering paths must be teardown-safe and non-throwing, or they can hide the real failure.

[2026-02-11] [bug] **Provider usage contracts drift silently across backends.** Python OpenRouter stream emitted `prompt_tokens/completion_tokens`, but Rust alchemy emitted `input/output/cache_read/cost.total`. Parser assumptions caused usage to be dropped, which removed UI throughput (`t/s`). **Fix pattern:** centralize usage-key aliases and test each provider shape explicitly.
