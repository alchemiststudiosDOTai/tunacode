# tunacode MCP Interface [experimental]

This document describes tunacode’s experimental MCP interface: a JSON‑RPC API that runs over the Model Context Protocol (MCP) transport to control a local tunacode engine.

- Status: experimental and subject to change without notice
- Server binary: `tunacode mcp-server` (or `tunacode-mcp-server`)
- Transport: standard MCP over stdio (JSON‑RPC 2.0, line‑delimited)

## Overview

tunacode exposes a small set of MCP‑compatible methods to create and manage conversations, send user input, receive live events, and handle approval prompts. The types are defined in `protocol/src/mcp_protocol.rs` and re‑used by the MCP server implementation in `mcp-server/`.

At a glance:

- Conversations
  - `newConversation` → start a tunacode session
  - `sendUserMessage` / `sendUserTurn` → send user input into a conversation
  - `interruptConversation` → stop the current turn
  - `listConversations`, `resumeConversation`, `archiveConversation`
- Configuration and info
  - `getUserSavedConfig`, `setDefaultModel`, `getUserAgent`, `userInfo`
- Auth
  - `loginApiKey`, `loginChatGpt`, `cancelLoginChatGpt`, `logoutChatGpt`, `getAuthStatus`
- Utilities
  - `gitDiffToRemote`, `execOneOffCommand`
- Approvals (server → client requests)
  - `applyPatchApproval`, `execCommandApproval`
- Notifications (server → client)
  - `loginChatGptComplete`, `authStatusChange`
  - `tunacode/event` stream with agent events

See code for full type definitions and exact shapes: `protocol/src/mcp_protocol.rs`.

## Starting the server

Run tunacode as an MCP server and connect an MCP client:

```bash
tunacode mcp-server | your_mcp_client
```

For a simple inspection UI, you can also try:

```bash
npx @modelcontextprotocol/inspector tunacode mcp-server
```

Use the separate `tunacode mcp` subcommand to manage configured MCP server launchers in `config.toml`.

## Conversations

Start a new session with optional overrides:

Request `newConversation` params (subset):

- `model`: string model id (e.g. "o3", "gpt-5", "gpt-5-tunacode")
- `profile`: optional named profile
- `cwd`: optional working directory
- `approvalPolicy`: `untrusted` | `on-request` | `on-failure` | `never`
- `sandbox`: `read-only` | `workspace-write` | `danger-full-access`
- `config`: map of additional config overrides
- `baseInstructions`: optional instruction override
- `includePlanTool` / `includeApplyPatchTool`: booleans

Response: `{ conversationId, model, reasoningEffort?, rolloutPath }`

Send input to the active turn:

- `sendUserMessage` → enqueue items to the conversation
- `sendUserTurn` → structured turn with explicit `cwd`, `approvalPolicy`, `sandboxPolicy`, `model`, optional `effort`, and `summary`

Interrupt a running turn: `interruptConversation`.

List/resume/archive: `listConversations`, `resumeConversation`, `archiveConversation`.

## Event stream

While a conversation runs, the server sends notifications:

- `tunacode/event` with the serialized tunacode event payload. The shape matches `core/src/protocol.rs`’s `Event` and `EventMsg` types. Some notifications include a `_meta.requestId` to correlate with the originating request.
- Auth notifications via method names `loginChatGptComplete` and `authStatusChange`.

Clients should render events and, when present, surface approval requests (see next section).

## Approvals (server → client)

When tunacode needs approval to apply changes or run commands, the server issues JSON‑RPC requests to the client:

- `applyPatchApproval { conversationId, callId, fileChanges, reason?, grantRoot? }`
- `execCommandApproval { conversationId, callId, command, cwd, reason? }`

The client must reply with `{ decision: "allow" | "deny" }` for each request.

## Auth helpers

For ChatGPT or API‑key based auth flows, the server exposes helpers:

- `loginApiKey { apiKey }`
- `loginChatGpt` → returns `{ loginId, authUrl }`; browser completes flow; then `loginChatGptComplete` notification follows
- `cancelLoginChatGpt { loginId }`, `logoutChatGpt`, `getAuthStatus { includeToken?, refreshToken? }`

## Example: start and send a message

```json
{ "jsonrpc": "2.0", "id": 1, "method": "newConversation", "params": { "model": "gpt-5", "approvalPolicy": "on-request" } }
```

Server responds:

```json
{ "jsonrpc": "2.0", "id": 1, "result": { "conversationId": "c7b0…", "model": "gpt-5", "rolloutPath": "/path/to/rollout.jsonl" } }
```

Then send input:

```json
{ "jsonrpc": "2.0", "id": 2, "method": "sendUserMessage", "params": { "conversationId": "c7b0…", "items": [{ "type": "text", "text": "Hello tunacode" }] } }
```

While processing, the server emits `tunacode/event` notifications containing agent output, approvals, and status updates.

## Compatibility and stability

This interface is experimental. Method names, fields, and event shapes may evolve. For the authoritative schema, consult `protocol/src/mcp_protocol.rs` and the corresponding server wiring in `mcp-server/`.
