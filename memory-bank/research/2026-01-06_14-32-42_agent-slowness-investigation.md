# Research - Agent Perceived Slowness Investigation
**Date:** 2026-01-06
**Owner:** agent
**Phase:** Research

## Goal
Identify root causes of perceived slowness in the tunacode agent, particularly when using read-only tools that should execute in parallel batches.

## Findings

### Critical Issues Found

#### 1. Synchronous Token Counting Blocks Event Loop
- `src/tunacode/core/state.py:117-124` → `update_token_count()` iterates ALL messages synchronously
- Calls `estimate_tokens()` which uses tiktoken's `encoding.encode(text)` - CPU-bound synchronous work
- Called after every model response at `node_processor.py:102`
- **Impact**: As conversation history grows, this blocks the async event loop longer each iteration

#### 2. Blocking `time.sleep()` in JSON Parsing
- `src/tunacode/utils/parsing/retry.py:53-75` → Uses synchronous `time.sleep()` in async context
- Called from `repl_support.py:119` for every tool's argument parsing
- **Config**: Up to 10 retries with exponential backoff (0.1s base, 5.0s max)
- **Impact**: Malformed JSON can block event loop for 50+ seconds total

#### 3. Full Markdown Re-render on Each Streaming Update
- `src/tunacode/ui/app.py:396` → `Markdown(self.current_stream_text)` parses ENTIRE accumulated text
- Called every 100ms during streaming
- **Impact**: Grows increasingly expensive as response length increases

### Moderate Issues

#### 4. Streaming Display Throttle (100ms)
- `src/tunacode/ui/app.py:71-72` → `STREAM_THROTTLE_MS = 100.0`
- Text accumulates immediately but display updates limited to 10/sec
- **Impact**: Up to 100ms perceived latency in text appearance

#### 5. Research Agent Phase Separation
- `src/tunacode/core/agents/agent_components/node_processor.py:282-304`
- `research_codebase` runs in separate phase BEFORE other read-only tools
- **Impact**: If model calls research + grep + read_file, they run in 2 phases not 1

#### 6. File I/O for Update Confirmation Diffs
- `src/tunacode/ui/requests.py:50-51` → Synchronous file read for diff generation
- **Impact**: Large files slow down confirmation dialog generation

### Not Issues (Verified)

| Suspected | Actual Finding |
|-----------|----------------|
| `request_delay` slowing tools | Only affects HTTP requests to LLM API, not between tools |
| Tool retry backoff | Only triggers on actual failures, not normal operation |
| React snapshot capturing | Minimal overhead, only runs on even iterations 2-10 |
| Authorization checks | Synchronous but fast O(1) operations |

## Key Patterns / Solutions Found

### Already Fixed This Session
- `ParallelGrep()` singleton: Eliminated per-call ThreadPoolExecutor creation and gitignore reloading

### Recommended Fixes

1. **Token counting**: Wrap in `asyncio.to_thread()` or use incremental counting
   ```python
   # state.py:117
   async def update_token_count_async(self) -> None:
       self.total_tokens = await asyncio.to_thread(self._count_tokens_sync)
   ```

2. **JSON parsing**: Replace `time.sleep()` with `asyncio.sleep()`
   ```python
   # retry.py - use async version for async callers
   await asyncio.sleep(delay)  # instead of time.sleep(delay)
   ```

3. **Streaming render**: Incremental markdown append instead of full re-parse
   - Only parse and append the new chunk, not entire accumulated text

4. **Reduce throttle**: Consider `STREAM_THROTTLE_MS = 50.0` for snappier feel

## Knowledge Gaps
- Need profiling data to confirm relative impact of each bottleneck
- Unknown if tiktoken has async-friendly alternatives
- Unknown cumulative effect of multiple small synchronous operations

## References

### Files Analyzed
- `src/tunacode/core/agents/main.py` - Agent iteration loop
- `src/tunacode/core/agents/agent_components/node_processor.py` - Tool processing
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Parallel execution
- `src/tunacode/core/state.py` - Token counting
- `src/tunacode/ui/app.py` - Streaming and display
- `src/tunacode/ui/repl_support.py` - Tool callback construction
- `src/tunacode/utils/parsing/retry.py` - JSON parsing with retries
- `src/tunacode/tools/authorization/` - Authorization pipeline

### Configuration Constants
- `STREAM_THROTTLE_MS = 100.0` at `ui/app.py:72`
- `JSON_PARSE_MAX_RETRIES = 10` at `constants.py:199`
- `JSON_PARSE_BASE_DELAY = 0.1` at `constants.py:200`
- `TOOL_MAX_RETRIES = 3` at `constants.py:204`
- `TUNACODE_MAX_PARALLEL` env var (default: cpu_count)
