# Research – Compaction System Architecture

**Date:** 2026-02-07
**Owner:** claude
**Phase:** Research

## Goal

Understand how the pi agent handles context compaction effectively, including auto-compaction, manual compaction, and branch summarization mechanisms.

## Summary

The compaction system is a sophisticated multi-layered approach to managing context window limitations in LLM conversations. It combines intelligent token estimation, structured summarization, cumulative file tracking, and tree-aware navigation to preserve context while staying within token budgets.

## Additional Search

```bash
grep -ri "compact" .claude/
```

## Key Files

| File | Purpose |
|------|---------|
| [`packages/coding-agent/src/core/compaction/compaction.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/compaction/compaction.ts) | Core compaction logic, cut point detection, summarization |
| [`packages/coding-agent/src/core/compaction/branch-summarization.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/compaction/branch-summarization.ts) | Branch summarization for tree navigation |
| [`packages/coding-agent/src/core/compaction/utils.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/compaction/utils.ts) | File operation tracking, message serialization |
| [`packages/coding-agent/src/core/agent-session.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/agent-session.ts#L1324) | Integration with agent session, auto-compaction triggers |
| [`packages/coding-agent/docs/compaction.md`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/docs/compaction.md) | Complete documentation |

## Key Patterns / Solutions Found

### 1. Dual-Trigger Compaction

The system handles compaction through two distinct triggers:

| Trigger | When | Behavior |
|---------|------|----------|
| **Overflow** | LLM returns context overflow error | Compacts + auto-retries the request |
| **Threshold** | `contextTokens > contextWindow - reserveTokens` | Compacts + waits for user to continue |

Default thresholds (configurable):
- `reserveTokens: 16384` - Space reserved for LLM response
- `keepRecentTokens: 20000` - Recent context to keep unsummarized

**Implementation:** `agent-session.ts:1449-1505`

### 2. Intelligent Cut Point Detection

The compaction algorithm walks **backwards** from newest messages, accumulating tokens until `keepRecentTokens` is reached. Key innovations:

```typescript
// compaction.ts:376-438
function findCutPoint(entries, startIndex, endIndex, keepRecentTokens) {
  // Walk backwards, accumulating token estimates
  // Stop when accumulated >= keepRecentTokens
  // Cut at nearest valid cut point
}
```

**Valid cut points:** User messages, Assistant messages, BashExecution, Custom messages
**Never cut at:** Tool results (must stay with their tool call)

### 3. Split Turn Handling

When a single turn exceeds `keepRecentTokens`, the system cuts mid-turn at an assistant message and generates **two merged summaries**:

1. **History summary** - Previous context (if any)
2. **Turn prefix summary** - Early part of the split turn

```
Split turn example:
  entry:  usr → ass → tool → ass → tool → tool → ass → tool
                └─────────────────────────┘    └────────┘
                 turnPrefixMessages            kept
```

**Implementation:** `compaction.ts:683-809`

### 4. Cumulative File Tracking

File operations accumulate across compactions, preserving full history:

```typescript
// Extracted from tool calls in messages being summarized
// + extracted from previous compaction/branch summary details
interface CompactionDetails {
  readFiles: string[];
  modifiedFiles: string[];
}
```

This means file tracking is **cumulative** - when a new compaction happens, it includes:
- File ops from current messages
- File ops from the previous compaction entry

**Implementation:** `compaction.ts:41-69`, `utils.ts:29-67`

### 5. Structured Summary Format

Both compaction and branch summarization use the same structured format:

```markdown
## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
- [Requirements]

## Progress
### Done
- [x] [Completed]
### In Progress
- [ ] [Current]
### Blocked
- [Issues]

## Key Decisions
- **[Decision]**: [Rationale]

## Next Steps
1. [What should happen next]

## Critical Context
- [Data needed to continue]

<read-files>
path/to/file.ts
</read-files>

<modified-files>
path/to/changed.ts
</modified-files>
```

**Implementation:** `compaction.ts:444-515`

### 6. Message Serialization

To prevent the LLM from treating conversation as something to continue, messages are serialized to text:

```
[User]: What they said
[Assistant thinking]: Internal reasoning
[Assistant]: Response text
[Assistant tool calls]: read(path="foo.ts"); edit(...)
[Tool result]: Output
```

**Implementation:** `utils.ts:93-146`

### 7. Iterative Summary Updates

When a previous compaction exists, the system uses an **update prompt** instead of a fresh summary:

```
UPDATE_SUMMARIZATION_PROMPT = `
The messages above are NEW conversation messages to incorporate
into the existing summary in <previous-summary>.

RULES:
- PRESERVE all existing information
- ADD new progress, decisions, context
- UPDATE Progress section (move items from In Progress to Done)
- UPDATE Next Steps based on accomplishments
`
```

**Implementation:** `compaction.ts:477-514`

### 8. Branch Summarization for Navigation

When navigating to a different branch with `/tree`:

1. Find common ancestor between old and new positions
2. Walk from old leaf back to ancestor
3. Generate summary with token budget (newest first)
4. Append `BranchSummaryEntry` at navigation point

**Result:** Context from abandoned branch is preserved in the new branch.

**Implementation:** `branch-summarization.ts:96-134`

### 9. Extension Hooks

Extensions can intercept and customize compaction:

```typescript
pi.on("session_before_compact", async (event, ctx) => {
  // Can cancel compaction
  return { cancel: true };

  // Or provide custom summary
  return {
    compaction: {
      summary: "Custom summary...",
      firstKeptEntryId: preparation.firstKeptEntryId,
      tokensBefore: preparation.tokensBefore,
      details: { /* custom data */ },
    }
  };
});
```

**Example:** `examples/extensions/custom-compaction.ts`

### 10. Token Estimation Strategy

The system uses a conservative `chars/4` heuristic for token estimation:

```typescript
function estimateTokens(message: AgentMessage): number {
  // Count characters in all content blocks
  // Divide by 4 (overestimates, safe)
  return Math.ceil(chars / 4);
}
```

For actual token counts, it uses the `usage.totalTokens` from the last non-aborted assistant message.

**Implementation:** `compaction.ts:179-207`

## Why It Works So Well

1. **Conservative estimation** - The `chars/4` heuristic overestimates, ensuring compaction triggers before actual overflow

2. **Structured preservation** - The summary format preserves goals, constraints, progress, decisions, and file operations

3. **Cumulative tracking** - File operations accumulate across compactions, preventing loss of context

4. **Smart cut points** - Never cuts at tool results, ensures related context stays together

5. **Split turn handling** - Gracefully handles single turns that are larger than the keep budget

6. **Tree awareness** - Branch summarization preserves context when exploring alternate paths

7. **Extension hooks** - Allows custom summarization strategies without modifying core

8. **Overflow recovery** - Automatic detection and retry when LLM reports context overflow

## Knowledge Gaps

- Exact token counting behavior for different models (the system relies on `usage.totalTokens` from the LLM response)
- Performance characteristics of very large sessions (10k+ entries)
- Interaction with cached prompts (Anthropic's prompt caching)

## References

- Documentation: [`packages/coding-agent/docs/compaction.md`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/docs/compaction.md)
- Core implementation: [`packages/coding-agent/src/core/compaction/compaction.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/compaction/compaction.ts)
- Branch summarization: [`packages/coding-agent/src/core/compaction/branch-summarization.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/compaction/branch-summarization.ts)
- Session integration: [`packages/coding-agent/src/core/agent-session.ts#L1324`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/core/agent-session.ts#L1324)
- Custom compaction example: [`packages/coding-agent/examples/extensions/custom-compaction.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/examples/extensions/custom-compaction.ts)
- Interactive mode UI handling: [`packages/coding-agent/src/modes/interactive/interactive-mode.ts#L2153`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/modes/interactive/interactive-mode.ts#L2153)
- Compaction UI component: [`packages/coding-agent/src/modes/interactive/components/compaction-summary-message.ts`](https://github.com/badlogic/pi-mono/blob/2cc25448/packages/coding-agent/src/modes/interactive/components/compaction-summary-message.ts)

---

## Follow-up Research [2026-02-07]

### The Action of Compaction - Runtime Flow

The user asked about the **runtime action** of compaction - what happens during the process, what the user sees, the flow of events. Here is the complete runtime flow:

#### Event Flow Timeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. CHECKPOINT: After LLM response (agent_end event)                 │
│    - Checks last assistant message                                  │
│    - Detects overflow OR exceeds threshold                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. EVENT: auto_compaction_start                                     │
│    - reason: "overflow" or "threshold"                              │
│    - Creates AbortController for cancellation                      │
│    - UI shows: "Auto-compacting... (Esc to cancel)"                │
│    - Editor stays active (submissions queued)                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. PREPARE: prepareCompaction()                                     │
│    - Find cut point (walks backwards)                               │
│    - Extract messages to summarize                                 │
│    - Extract file operations                                       │
│    - Get previous summary (if exists)                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. EXTENSION HOOK: session_before_compact                           │
│    - Extensions can intercept and provide custom summary           │
│    - Or cancel compaction entirely                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. GENERATE: compact() - LLM call                                   │
│    - Serialize messages to text                                    │
│    - Call LLM with summarization prompt                            │
│    - Handles split turns (generates 2 summaries in parallel)       │
│    - Appends <read-files> and <modified-files> tags                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. PERSIST: SessionManager.appendCompaction()                       │
│    - Save CompactionEntry to session file                          │
│    - Includes: summary, firstKeptEntryId, tokensBefore, details    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. RELOAD: buildSessionContext() + replaceMessages()                │
│    - Session rebuilds context from compaction + kept entries       │
│    - Agent's internal state is replaced                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. EXTENSION HOOK: session_compact                                  │
│    - Notifies extensions that compaction completed                 │
│    - Passes the saved CompactionEntry                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 9. EVENT: auto_compaction_end                                       │
│    - result: { summary, firstKeptEntryId, tokensBefore, details }  │
│    - willRetry: true for overflow, false for threshold             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 10. UI UPDATE: Rebuild chat + show compaction message               │
│     - chatContainer.clear()                                         │
│     - rebuildChatFromMessages()                                    │
│     - Add CompactionSummaryMessageComponent at bottom              │
│     - Shows collapsed: "[compaction] Compacted from X tokens"      │
│     - Press expand key to show full summary                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 11. OVERFLOW RETRY (only if reason="overflow")                      │
│     - Wait 100ms                                                   │
│     - Remove error message from agent state                        │
│     - Auto-retry the last request with compacted context          │
└─────────────────────────────────────────────────────────────────────┘
```

#### User Experience

**What the user sees:**

1. **During compaction:**
   - Status bar shows: `"Auto-compacting... (Esc to cancel)"` or `"Context overflow detected, Auto-compacting... (Esc to cancel)"`
   - Spinner animation
   - Editor remains active (can keep typing)

2. **After compaction:**
   - Chat clears and rebuilds (old messages collapsed)
   - New message at bottom: `[compaction] Compacted from 123,456 tokens`
   - Can press expand key to see full summary

3. **If overflow recovery:**
   - Same as above, plus automatic retry of the failed request
   - User sees the original request completed successfully

#### Key Implementation Details

**Cancellable Compaction:**
```typescript
// interactive-mode.ts:2157-2158
this.defaultEditor.onEscape = () => {
  this.session.abortCompaction();
};
```

**Overflow vs Threshold Behavior:**
```typescript
// agent-session.ts:1485-1504
if (overflow) {
  // Remove error message, compact, auto-retry
  await this._runAutoCompaction("overflow", true);
} else if (threshold) {
  // Compact, wait for user to continue
  await this._runAutoCompaction("threshold", false);
}
```

**Split Turn Parallel Summarization:**
```typescript
// compaction.ts:726-741
const [historyResult, turnPrefixResult] = await Promise.all([
  generateSummary(messagesToSummarize, ...),
  generateTurnPrefixSummary(turnPrefixMessages, ...),
]);
// Merge into single summary
summary = `${historyResult}\n\n---\n\n**Turn Context:**\n\n${turnPrefixResult}`;
```

#### Why the Action is Seamless

1. **Editor stays active** - User can continue typing while compaction runs
2. **Submissions are queued** - Any new submissions during compaction are processed after
3. **Graceful cancellation** - Press Esc to abort, extensions can cancel via hook
4. **Visual feedback** - Clear status indicators and compaction message
5. **Auto-retry for overflow** - Context overflow errors are transparently recovered
